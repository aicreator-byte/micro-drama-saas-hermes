"""Subtitle otomatis: upload audio/video -> Whisper lokal (faster-whisper)
-> SRT + VTT. Atau bangun SRT/VTT langsung dari segmen transkrip yang
diberikan (tanpa engine).

Transkrip jalan di background thread (model Whisper sinkron/blocking) via
asyncio.to_thread supaya event loop tidak macet. File sumber disimpan di
UPLOAD_DIR/subtitles/; hasil SRT/VTT di sampingnya.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db, AsyncSessionLocal
from app.core.security import get_current_active_user
from app.models import User, Project, Episode, SubtitleJob, SubtitleJobStatus
from app.schemas import (
    SubtitleJobResponse, SubtitleFromSegmentsCreate, SubtitleSegment,
)
from app.services.subtitles import (
    ALLOWED_MODEL_SIZES,
    transcribe_file, write_subtitle_files, segments_to_srt,
    segments_to_vtt, engine_available, SubtitleEngineUnavailable,
)

router = APIRouter(prefix="/projects", tags=["subtitles"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm"}
MAX_AUDIO_MB = 200
# Upload dibaca per chunk (audit ronde 2, P1-3): file GB-an harus ditolak
# SEBELUM memenuhi RAM — jangan pernah file.read() tanpa batas.
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _utcnow_naive() -> datetime:
    """UTC naive — sama seperti default kolom DateTime model lainnya."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_project(db: AsyncSession, user: User, project_id: UUID) -> Project:
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == user.id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_response(j: SubtitleJob) -> SubtitleJobResponse:
    return SubtitleJobResponse(
        id=j.id, project_id=j.project_id, episode_id=j.episode_id,
        source_filename=j.source_filename, status=j.status.value,
        language=j.language, engine=j.engine, model_size=j.model_size,
        segments=j.segments, error_message=j.error_message,
        created_at=j.created_at, completed_at=j.completed_at,
    )


def _subtitle_dir() -> Path:
    d = Path(settings.UPLOAD_DIR) / "subtitles"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _run_transcription(job_id: uuid.UUID, source_path: str, language: str, model_size: str) -> None:
    """Background: transkrip lalu tulis SRT/VTT. Session sendiri."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SubtitleJob).where(SubtitleJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return
        job.status = SubtitleJobStatus.RUNNING
        await db.commit()
        try:
            segments = await asyncio.to_thread(
                transcribe_file, source_path, language=language, model_size=model_size
            )
            files = write_subtitle_files(segments, _subtitle_dir(), str(job.id))
            job.segments = segments
            job.srt_path = files["srt_path"]
            job.vtt_path = files["vtt_path"]
            job.engine = "faster-whisper"
            job.status = SubtitleJobStatus.COMPLETED
        except Exception as e:  # noqa: BLE001
            job.status = SubtitleJobStatus.FAILED
            job.error_message = str(e)[:500]
        job.completed_at = _utcnow_naive()
        await db.commit()


@router.get("/subtitles/engine")
async def subtitle_engine_status(
    current_user: User = Depends(get_current_active_user),
):
    return {
        "engine": "faster-whisper" if engine_available() else None,
        "available": engine_available(),
        "note": None if engine_available() else (
            "faster-whisper belum terpasang — pasang: pip install faster-whisper"
        ),
    }


@router.post("/{project_id}/subtitles", response_model=SubtitleJobResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_job(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    episode_id: UUID | None = None,
    language: str = "id",
    model_size: str = "tiny",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    if not engine_available():
        raise HTTPException(
            status_code=503,
            detail="Whisper engine (faster-whisper) belum tersedia di server ini — "
                   "pasang: pip install faster-whisper",
        )
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format tidak didukung: {ext or '(tanpa ekstensi)'}. "
                   f"Didukung: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if model_size not in ALLOWED_MODEL_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"model_size tidak diizinkan: {model_size!r}. "
                   f"Diizinkan: {', '.join(sorted(ALLOWED_MODEL_SIZES))}",
        )
    if episode_id is not None:
        result = await db.execute(
            select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Episode not found")
    # Streaming berbatas (P1-3): baca per chunk langsung ke disk, batalkan
    # + hapus file parsial begitu melewati batas — RAM tidak pernah
    # memegang file utuh.
    job_id = uuid.uuid4()
    source_path = _subtitle_dir() / f"{job_id}{ext}"
    max_bytes = MAX_AUDIO_MB * 1024 * 1024
    total = 0
    try:
        with open(source_path, "wb") as out:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File terlalu besar (maks {MAX_AUDIO_MB} MB)",
                    )
                out.write(chunk)
    except HTTPException:
        source_path.unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001 — upload gagal di tengah jalan
        source_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Upload gagal: {e}")
    job = SubtitleJob(
        id=job_id, project_id=project_id, episode_id=episode_id,
        user_id=current_user.id, source_filename=file.filename,
        source_path=str(source_path), status=SubtitleJobStatus.PENDING,
        language=language, model_size=model_size,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    background_tasks.add_task(
        _run_transcription, job_id, str(source_path), language, model_size
    )
    return _to_response(job)


@router.post("/{project_id}/subtitles/from-segments", response_model=SubtitleJobResponse, status_code=status.HTTP_201_CREATED)
async def create_subtitle_from_segments(
    project_id: UUID, data: SubtitleFromSegmentsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bangun SRT/VTT dari segmen transkrip yang sudah ada — tanpa engine.
    Berguna bila transkrip dibuat di tempat lain / engine belum tersedia."""
    await _get_project(db, current_user, project_id)
    segments = [s.model_dump() for s in data.segments]
    job_id = uuid.uuid4()
    files = write_subtitle_files(segments, _subtitle_dir(), str(job_id))
    job = SubtitleJob(
        id=job_id, project_id=project_id, episode_id=data.episode_id,
        user_id=current_user.id, source_filename=None,
        status=SubtitleJobStatus.COMPLETED, language=data.language,
        engine="manual-segments", model_size="-",
        segments=segments, srt_path=files["srt_path"], vtt_path=files["vtt_path"],
        completed_at=_utcnow_naive(),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _to_response(job)


@router.get("/{project_id}/subtitles", response_model=list[SubtitleJobResponse])
async def list_subtitle_jobs(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(SubtitleJob).where(SubtitleJob.project_id == project_id)
        .order_by(SubtitleJob.created_at.desc())
    )
    return [_to_response(j) for j in result.scalars().all()]


@router.get("/{project_id}/subtitles/{job_id}", response_model=SubtitleJobResponse)
async def get_subtitle_job(
    project_id: UUID, job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(SubtitleJob).where(
            and_(SubtitleJob.id == job_id, SubtitleJob.project_id == project_id)
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    return _to_response(job)


@router.get("/{project_id}/subtitles/{job_id}/download")
async def download_subtitle(
    project_id: UUID, job_id: UUID, fmt: str = "srt",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(SubtitleJob).where(
            and_(SubtitleJob.id == job_id, SubtitleJob.project_id == project_id)
        )
    )
    job = result.scalar_one_or_none()
    if not job or job.status != SubtitleJobStatus.COMPLETED:
        raise HTTPException(status_code=404, detail="Subtitle belum siap")
    if fmt == "vtt":
        path, media = job.vtt_path, "text/vtt"
    else:
        path, media = job.srt_path, "application/x-subrip"
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="File subtitle tidak ditemukan")
    return FileResponse(path, media_type=media, filename=f"{job.id}.{fmt}")
