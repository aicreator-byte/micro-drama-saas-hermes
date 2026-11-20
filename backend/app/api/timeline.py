"""Timeline video per episode: rakit shot/prompt jadi urutan klip.

Satu timeline per episode. Clip mereferensikan scene/prompt/asset yang
sudah ada; durasi total = max(start + duration) semua clip.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Episode, VideoTimeline
from app.schemas import (
    TimelineCreate, TimelineUpdate, TimelineResponse,
)

router = APIRouter(prefix="/projects", tags=["timeline"])


async def _get_episode(db: AsyncSession, user: User, project_id: UUID, episode_id: UUID) -> Episode:
    result = await db.execute(
        select(Episode).join(Project, Episode.project_id == Project.id).where(
            and_(
                Episode.id == episode_id,
                Episode.project_id == project_id,
                Project.owner_id == user.id,
            )
        )
    )
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(status_code=404, detail="Episode not found")
    return ep


def _duration(clips: list[dict]) -> float:
    total = 0.0
    for c in clips:
        total = max(total, float(c.get("start", 0)) + float(c.get("duration", 0)))
    return round(total, 3)


def _to_response(t: VideoTimeline) -> TimelineResponse:
    return TimelineResponse(
        id=t.id, episode_id=t.episode_id, project_id=t.project_id,
        name=t.name, clips=t.clips or [], duration_seconds=t.duration_seconds,
        fps=t.fps, resolution=t.resolution,
        created_at=t.created_at, updated_at=t.updated_at,
    )


@router.get("/{project_id}/episodes/{episode_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_id: UUID, episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_episode(db, current_user, project_id, episode_id)
    result = await db.execute(select(VideoTimeline).where(VideoTimeline.episode_id == episode_id))
    tl = result.scalar_one_or_none()
    if not tl:
        raise HTTPException(status_code=404, detail="Timeline not found — buat dulu via POST")
    return _to_response(tl)


@router.post("/{project_id}/episodes/{episode_id}/timeline", response_model=TimelineResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline(
    project_id: UUID, episode_id: UUID, data: TimelineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_episode(db, current_user, project_id, episode_id)
    result = await db.execute(select(VideoTimeline).where(VideoTimeline.episode_id == episode_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Timeline episode ini sudah ada — pakai PATCH")
    clips = [c.model_dump(mode="json") for c in data.clips]
    tl = VideoTimeline(
        episode_id=episode_id, project_id=project_id, name=data.name,
        clips=clips, duration_seconds=_duration(clips),
        fps=data.fps, resolution=data.resolution,
    )
    db.add(tl)
    await db.commit()
    await db.refresh(tl)
    return _to_response(tl)


@router.patch("/{project_id}/episodes/{episode_id}/timeline", response_model=TimelineResponse)
async def update_timeline(
    project_id: UUID, episode_id: UUID, data: TimelineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_episode(db, current_user, project_id, episode_id)
    result = await db.execute(select(VideoTimeline).where(VideoTimeline.episode_id == episode_id))
    tl = result.scalar_one_or_none()
    if not tl:
        raise HTTPException(status_code=404, detail="Timeline not found")
    if data.name is not None:
        tl.name = data.name
    if data.clips is not None:
        clips = [c.model_dump(mode="json") for c in data.clips]
        tl.clips = clips
        tl.duration_seconds = _duration(clips)
    if data.fps is not None:
        tl.fps = data.fps
    if data.resolution is not None:
        tl.resolution = data.resolution
    await db.commit()
    await db.refresh(tl)
    return _to_response(tl)


@router.delete("/{project_id}/episodes/{episode_id}/timeline", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline(
    project_id: UUID, episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_episode(db, current_user, project_id, episode_id)
    result = await db.execute(select(VideoTimeline).where(VideoTimeline.episode_id == episode_id))
    tl = result.scalar_one_or_none()
    if not tl:
        raise HTTPException(status_code=404, detail="Timeline not found")
    await db.delete(tl)
    await db.commit()
    return None


@router.post("/{project_id}/episodes/{episode_id}/timeline/from-prompts", response_model=TimelineResponse, status_code=status.HTTP_201_CREATED)
async def timeline_from_prompts(
    project_id: UUID, episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bangun timeline otomatis dari prompt video-generation episode:
    satu clip per prompt, masing-masing 8 detik, berurutan di track 0."""
    from app.models import Prompt, PromptType
    ep = await _get_episode(db, current_user, project_id, episode_id)
    result = await db.execute(select(VideoTimeline).where(VideoTimeline.episode_id == episode_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Timeline episode ini sudah ada — hapus dulu")
    result = await db.execute(
        select(Prompt).where(
            and_(
                Prompt.episode_id == episode_id,
                Prompt.prompt_type == PromptType.VIDEO_GENERATION,
            )
        ).order_by(Prompt.created_at)
    )
    prompts = result.scalars().all()
    if not prompts:
        raise HTTPException(status_code=400, detail="Episode ini belum punya prompt video-generation")
    clips: list[dict] = []
    t = 0.0
    for i, p in enumerate(prompts):
        clips.append({
            "id": f"clip-{i + 1}", "track": 0, "start": t, "duration": 8.0,
            "prompt_id": str(p.id), "scene_id": str(p.scene_id) if p.scene_id else None,
            "asset_id": None, "label": p.title, "transition": "cut",
        })
        t += 8.0
    tl = VideoTimeline(
        episode_id=episode_id, project_id=project_id,
        name=f"Timeline EP{ep.episode_number}",
        clips=clips, duration_seconds=_duration(clips),
        fps=30, resolution="1080x1920",
    )
    db.add(tl)
    await db.commit()
    await db.refresh(tl)
    return _to_response(tl)
