"""Auto-Generate API — spec §5 (Fase 1 backend).

One POST creates a job with 5 ordered steps (series_bible → characters →
locations → episodes → prompts) and runs them ASYNCHRONOUSLY in a
background task: POST returns 202 immediately with the job, and the
frontend polls GET for per-step progress (step status + result_summary
are committed after each step). A failed step stops the run; only
that step can be retried, and re-running a job skips rows that already
exist (no duplicates). Video is NOT generated here (spec §8): step 5
only writes Flow/Veo video *prompts*.

Safety rules (future-dev 19 Nov 2026):
- POST never changes the project title (request.title is the job title).
- Step 1 never overwrites a manually created bible (source='manual').
- A failed step rolls back its partial writes (no half-done rows).
- Genre is never silently defaulted to 'drama': user value, else LLM
  inference from the title, else honest label 'unknown'.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import (
    User, Project, SeriesBible, Character, Location, Episode, EpisodeStatus,
    Prompt, PromptType, AutoGenerateJob, AutoGenerateStep,
    AutoGenerateJobStatus, AutoGenerateStepStatus, AUTO_GENERATE_STEPS,
)
from app.schemas import (
    AutoGenerateCreate, AutoGenerateJobResponse,
)
from app.services.ai_client import (
    AIClient, AIProviderError,
    generate_series_outline, generate_characters, generate_locations,
    generate_episode_video_prompts, infer_genre_from_title,
)
from app.api.story_engine import _validate_series_output

router = APIRouter(prefix="/projects", tags=["auto-generate"])

STEP_KEYS = {key for key, _ in AUTO_GENERATE_STEPS}
# Idempotency thresholds (spec §4/§9): a step is skipped when the project
# already has at least this much content.
MIN_CHARACTERS = 4
MIN_LOCATIONS = 3
DEFAULT_NUM_CHARACTERS = 5
DEFAULT_NUM_LOCATIONS = 4


def _session_factory():
    """Session factory for background runs. Patchable in tests
    (tests point it at their in-memory SQLite session factory)."""
    from app.db.session import AsyncSessionLocal
    return AsyncSessionLocal()


async def _run_job_background(
    job_id: UUID, project_id: UUID, user_id: UUID, start_order: int = 1,
) -> None:
    """Background runner: own session, own AIClient. Never raises out
    (job FAILED status is the failure channel, not an exception)."""
    async with _session_factory() as session:
        job = await session.get(AutoGenerateJob, job_id)
        project = await session.get(Project, project_id)
        user = await session.get(User, user_id)
        if not job or not project or not user:
            return
        await _run_steps_from(session, job, project, user, start_order)


# ---------------------------------------------------------------- helpers
async def _get_project_or_404(db: AsyncSession, project_id: UUID, user_id: UUID) -> Project:
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == user_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_job_or_404(db: AsyncSession, project_id: UUID, job_id: UUID) -> AutoGenerateJob:
    result = await db.execute(
        select(AutoGenerateJob).where(and_(
            AutoGenerateJob.id == job_id, AutoGenerateJob.project_id == project_id
        ))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Auto-generate job not found")
    return job


def _job_to_response(job: AutoGenerateJob) -> AutoGenerateJobResponse:
    return AutoGenerateJobResponse.model_validate(job)


async def _existing_names(db: AsyncSession, model, project_id: UUID) -> set:
    result = await db.execute(select(model.name).where(model.project_id == project_id))
    return {str(n).strip().lower() for n in result.scalars().all() if n}


async def _outline_episodes(db: AsyncSession, job: AutoGenerateJob) -> list:
    """Episode outline list for step 4: this job's step-1 summary first,
    then the latest prior job for the same project."""
    for step in job.steps:
        if step.step_key == "series_bible" and step.result_summary:
            eps = step.result_summary.get("episodes")
            if isinstance(eps, list) and eps:
                return eps
    result = await db.execute(
        select(AutoGenerateJob)
        .where(and_(
            AutoGenerateJob.project_id == job.project_id,
            AutoGenerateJob.id != job.id,
        ))
        .order_by(AutoGenerateJob.created_at.desc())
        .limit(1)
    )
    prev = result.scalar_one_or_none()
    if prev:
        for step in prev.steps:
            if step.step_key == "series_bible" and step.result_summary:
                eps = step.result_summary.get("episodes")
                if isinstance(eps, list) and eps:
                    return eps
    return []


# ---------------------------------------------------------------- steps
async def _resolve_genre(db, job, ai_client):
    """Genre untuk job ini: nilai user > tebakan LLM dari judul > label
    jujur 'unknown'. Hasil disimpan ke job.genre agar langkah 2–5
    konsisten. TIDAK PERNAH default diam-diam ke 'drama'."""
    if job.genre:
        return job.genre, "user"
    inferred = await infer_genre_from_title(ai_client, job.title, job.premise)
    if inferred:
        job.genre = inferred
        return inferred, "llm"
    job.genre = "unknown"
    return "unknown", "unknown"


async def _run_step_series_bible(db, job, project, user, ai_client):
    """Step 1: LLM series outline → SeriesBible + Episode rows.
    Returns (summary, skipped).

    Bible manual (source='manual' + main_plot terisi) TIDAK PERNAH
    ditimpa: outline LLM tetap dipakai untuk membuat Episode, tapi
    field bible dibiarkan apa adanya dan summary menandai
    bible_protected=True.
    """
    result = await db.execute(select(SeriesBible).where(SeriesBible.project_id == project.id))
    bible = result.scalar_one_or_none()
    result = await db.execute(select(Episode).where(Episode.project_id == project.id))
    existing_episodes = result.scalars().all()

    if bible and bible.main_plot and existing_episodes:
        return ({"reason": "already exists", "episode_count": len(existing_episodes)}, True)

    genre, genre_source = await _resolve_genre(db, job, ai_client)

    llm_result = await generate_series_outline(
        ai_client=ai_client,
        premise=job.premise,
        genre=genre,
        themes=[],
        num_episodes=job.num_episodes,
        tone=None,
        characters=[],
        locations=[],
    )
    try:
        episodes_data = _validate_series_output(llm_result)
    except ValueError as e:
        raise AIProviderError("auto-generate", f"Invalid series output: {e}")
    series_bible_data = llm_result["series_bible"]

    # Lindungi bible manual: hanya tulis bila bible belum ada, kosong,
    # atau sebelumnya ditulis auto-generate.
    bible_protected = bool(bible and bible.main_plot and (bible.source or "manual") == "manual")
    if not bible:
        bible = SeriesBible(project_id=project.id, premise=job.premise, source="auto")
        db.add(bible)
        await db.flush()
    if not bible_protected:
        bible.main_plot = series_bible_data.get("main_plot")
        bible.subplots = series_bible_data.get("subplots")
        bible.episode_structure = series_bible_data.get("episode_structure")
        bible.source = "auto"
        bible.updated_at = datetime.utcnow()

    existing_numbers = {ep.episode_number for ep in existing_episodes}
    created, skipped = [], []
    for ep_data in episodes_data:
        num = int(ep_data["episode_number"])
        if num in existing_numbers:
            skipped.append(num)
            continue
        db.add(Episode(
            project_id=project.id,
            episode_number=num,
            title=(ep_data.get("title") or f"Episode {num}")[:255],
            outline=ep_data.get("outline"),
            status=EpisodeStatus.PLANNED,
        ))
        existing_numbers.add(num)
        created.append(num)

    return ({
        "created_episodes": created,
        "skipped_episodes": skipped,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "episode_count": len(episodes_data),
        "genre": genre,
        "genre_source": genre_source,
        "bible_protected": bible_protected,
        "episodes": episodes_data,
    }, False)


async def _run_step_characters(db, job, project, user, ai_client):
    """Step 2: LLM cast → Character rows (new write path: the old story
    engine apply cannot materialize characters). Returns (summary, skipped)."""
    result = await db.execute(select(Character).where(Character.project_id == project.id))
    existing = result.scalars().all()
    if len(existing) >= MIN_CHARACTERS:
        return ({"reason": "already exists", "character_count": len(existing)}, True)

    result = await db.execute(select(SeriesBible).where(SeriesBible.project_id == project.id))
    bible = result.scalar_one_or_none()
    chars_data = await generate_characters(
        ai_client=ai_client,
        premise=job.premise,
        genre=job.genre or "unknown",
        main_plot=bible.main_plot if bible else None,
        num_characters=DEFAULT_NUM_CHARACTERS,
    )

    existing_names = {c.name.strip().lower() for c in existing}
    max_order = max([c.order_index for c in existing], default=-1)
    created, skipped = [], []
    for i, c in enumerate(chars_data):
        name = str(c.get("name") or "").strip()
        if name.lower() in existing_names:
            skipped.append(name)
            continue
        max_order += 1
        db.add(Character(
            project_id=project.id,
            name=name[:255],
            role=(c.get("role") or None),
            physical_appearance=c.get("physical_appearance"),
            personality=c.get("personality"),
            background=c.get("background"),
            costume=c.get("costume"),
            consistency_instructions=c.get("consistency_instructions"),
            order_index=max_order,
        ))
        existing_names.add(name.lower())
        created.append(name)

    return ({"created": created, "skipped": skipped,
             "created_count": len(created), "skipped_count": len(skipped)}, False)


async def _run_step_locations(db, job, project, user, ai_client):
    """Step 3: LLM locations → Location rows. Returns (summary, skipped)."""
    result = await db.execute(select(Location).where(Location.project_id == project.id))
    existing = result.scalars().all()
    if len(existing) >= MIN_LOCATIONS:
        return ({"reason": "already exists", "location_count": len(existing)}, True)

    result = await db.execute(select(SeriesBible).where(SeriesBible.project_id == project.id))
    bible = result.scalar_one_or_none()
    locs_data = await generate_locations(
        ai_client=ai_client,
        premise=job.premise,
        genre=job.genre or "unknown",
        main_plot=bible.main_plot if bible else None,
        num_locations=DEFAULT_NUM_LOCATIONS,
    )

    existing_names = {loc.name.strip().lower() for loc in existing}
    max_order = max([loc.order_index for loc in existing], default=-1)
    created, skipped = [], []
    for loc in locs_data:
        name = str(loc.get("name") or "").strip()
        if name.lower() in existing_names:
            skipped.append(name)
            continue
        max_order += 1
        db.add(Location(
            project_id=project.id,
            name=name[:255],
            description=loc.get("description"),
            environment=loc.get("environment"),
            lighting=loc.get("lighting"),
            atmosphere=loc.get("atmosphere"),
            consistency_instructions=loc.get("consistency_instructions"),
            order_index=max_order,
        ))
        existing_names.add(name.lower())
        created.append(name)

    return ({"created": created, "skipped": skipped,
             "created_count": len(created), "skipped_count": len(skipped)}, False)


async def _run_step_episodes(db, job, project, user, ai_client):
    """Step 4: materialize any missing Episode rows from the step-1 outline.
    Returns (summary, skipped)."""
    result = await db.execute(
        select(Episode).where(Episode.project_id == project.id)
    )
    existing = result.scalars().all()
    existing_numbers = {ep.episode_number for ep in existing}

    outline = await _outline_episodes(db, job)
    if not outline and not existing:
        raise ValueError("No episode outline available to materialize (step 1 produced nothing)")

    created = []
    for ep_data in outline:
        try:
            num = int(ep_data["episode_number"])
        except (KeyError, TypeError, ValueError):
            continue
        if num in existing_numbers:
            continue
        db.add(Episode(
            project_id=project.id,
            episode_number=num,
            title=(ep_data.get("title") or f"Episode {num}")[:255],
            outline=ep_data.get("outline"),
            status=EpisodeStatus.PLANNED,
        ))
        existing_numbers.add(num)
        created.append(num)

    return ({
        "created_episodes": created,
        "total_episodes": len(existing_numbers),
        "created_count": len(created),
    }, False)


async def _run_step_prompts(db, job, project, user, ai_client):
    """Step 5: one LLM video prompt per episode missing one.
    Returns (summary, skipped)."""
    result = await db.execute(
        select(Episode).where(Episode.project_id == project.id)
        .order_by(Episode.episode_number)
    )
    episodes = result.scalars().all()
    if not episodes:
        raise ValueError("No episodes exist to generate prompts for")

    result = await db.execute(
        select(Prompt.episode_id).where(and_(
            Prompt.project_id == project.id,
            Prompt.prompt_type == PromptType.VIDEO_GENERATION,
            Prompt.episode_id.isnot(None),
        ))
    )
    covered = {row for row in result.scalars().all()}
    missing = [ep for ep in episodes if ep.id not in covered]
    if not missing:
        return ({"reason": "already exists", "prompt_count": len(episodes)}, True)

    result = await db.execute(select(SeriesBible).where(SeriesBible.project_id == project.id))
    bible = result.scalar_one_or_none()
    result = await db.execute(select(Character).where(Character.project_id == project.id))
    characters = result.scalars().all()
    result = await db.execute(select(Location).where(Location.project_id == project.id))
    locations = result.scalars().all()

    prompts_data = await generate_episode_video_prompts(
        ai_client=ai_client,
        episodes=[{
            "episode_number": ep.episode_number,
            "title": ep.title,
            "outline": ep.outline,
        } for ep in missing],
        series_title=project.title,
        genre=job.genre or "unknown",
        tone=bible.tone if bible else None,
        characters=[{"name": c.name} for c in characters],
        locations=[{"name": loc.name} for loc in locations],
    )

    by_number = {int(p["episode_number"]): p for p in prompts_data}
    uncovered = [ep.episode_number for ep in missing if ep.episode_number not in by_number]
    if uncovered:
        raise ValueError(f"LLM returned no prompt for episode(s): {uncovered}")

    created = []
    for ep in missing:
        p = by_number[ep.episode_number]
        db.add(Prompt(
            project_id=project.id,
            episode_id=ep.id,
            prompt_type=PromptType.VIDEO_GENERATION,
            title=f"Episode {ep.episode_number} - Video Generation",
            prompt_text=p["prompt_text"],
            negative_prompt=p.get("negative_prompt"),
            parameters={"duration": 8, "fps": 24, "resolution": "1920x1080"},
        ))
        created.append(ep.episode_number)

    return ({"created_prompts": created, "created_count": len(created)}, False)


STEP_RUNNERS = {
    "series_bible": _run_step_series_bible,
    "characters": _run_step_characters,
    "locations": _run_step_locations,
    "episodes": _run_step_episodes,
    "prompts": _run_step_prompts,
}


async def _run_steps_from(db, job, project, user, start_order: int = 1) -> None:
    """Run steps from start_order onward; COMPLETED/SKIPPED steps are kept.
    First failure stops the run and marks the job FAILED."""
    ai_client = AIClient(db)
    job.status = AutoGenerateJobStatus.RUNNING
    job.error_message = None
    job.completed_at = None
    await db.commit()

    steps = sorted(job.steps, key=lambda s: s.step_order)
    for step in steps:
        if step.step_order < start_order:
            continue
        if step.status in (AutoGenerateStepStatus.COMPLETED, AutoGenerateStepStatus.SKIPPED):
            continue
        step.status = AutoGenerateStepStatus.RUNNING
        step.error_message = None
        await db.commit()
        # ID disimpan dulu: rollback di bawah meng-expire objek job/step.
        step_id, job_id = step.id, job.id
        try:
            summary, skipped = await STEP_RUNNERS[step.step_key](db, job, project, user, ai_client)
        except Exception as e:  # AIProviderError, ValueError, or unexpected: stop the run
            # Buang tulisan setengah jadi dari langkah yang gagal: commit
            # di bawah ini HANYA boleh menyimpan status FAILED, bukan
            # baris parsial langkah itu (status RUNNING sudah ter-commit
            # di atas, jadi rollback hanya membatalkan tulisan langkah).
            await db.rollback()
            # Objek job/step sudah expired oleh rollback — muat ulang
            # segar sebelum menandai FAILED. Mengubah atribut expired
            # lalu commit memicu lazy-load yang gagal di AsyncSession.
            step = await db.get(AutoGenerateStep, step_id)
            job = await db.get(AutoGenerateJob, job_id)
            step.status = AutoGenerateStepStatus.FAILED
            step.error_message = str(e)
            step.completed_at = datetime.utcnow()
            job.status = AutoGenerateJobStatus.FAILED
            job.error_message = f"{step.step_key}: {e}"
            await db.commit()
            return
        step.status = AutoGenerateStepStatus.SKIPPED if skipped else AutoGenerateStepStatus.COMPLETED
        step.result_summary = summary
        step.completed_at = datetime.utcnow()
        await db.commit()

    job.status = AutoGenerateJobStatus.COMPLETED
    job.completed_at = datetime.utcnow()
    await db.commit()


# ---------------------------------------------------------------- endpoints
@router.post("/{project_id}/auto-generate", response_model=AutoGenerateJobResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def create_auto_generate_job(
    project_id: UUID,
    request: AutoGenerateCreate,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create an auto-generate job and run it in the background.
    Returns 202 immediately; poll GET for per-step progress.
    Input is just a title (+ genre / episode count / premise); the job
    fills the series bible, characters, locations, episodes and video
    prompts. The project title is NEVER changed here (request.title is
    the job title only)."""
    project = await _get_project_or_404(db, project_id, current_user.id)

    if request.genre:
        project.genre = request.genre
        project.updated_at = datetime.utcnow()

    job = AutoGenerateJob(
        project_id=project.id,
        user_id=current_user.id,
        title=request.title,
        # Genre job HANYA dari request: None = ditebak LLM dari judul di
        # langkah 1 (bukan warisan project.genre — itu bisa jadi default
        # 'Drama' form proyek, dan menebak diam-diam dari situ sama
        # saja dengan default diam-diam).
        genre=request.genre,
        num_episodes=request.num_episodes,
        premise=request.premise or request.title,
    )
    db.add(job)
    await db.flush()
    for step_key, step_order in AUTO_GENERATE_STEPS:
        db.add(AutoGenerateStep(
            job_id=job.id, step_key=step_key, step_order=step_order,
            status=AutoGenerateStepStatus.PENDING,
        ))
    await db.commit()
    await db.refresh(job)

    background.add_task(_run_job_background, job.id, project.id, current_user.id, 1)
    return _job_to_response(job)


@router.get("/{project_id}/auto-generate/{job_id}", response_model=AutoGenerateJobResponse)
async def get_auto_generate_job(
    project_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    project = await _get_project_or_404(db, project_id, current_user.id)
    job = await _get_job_or_404(db, project.id, job_id)
    return _job_to_response(job)


@router.post("/{project_id}/auto-generate/{job_id}/retry/{step_key}",
             response_model=AutoGenerateJobResponse)
async def retry_auto_generate_step(
    project_id: UUID,
    job_id: UUID,
    step_key: str,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retry one failed step, then continue with the steps after it.
    Completed/skipped steps are kept untouched. Runs in the background;
    the response already shows status 'running' so the frontend keeps
    polling instead of treating the job as terminally failed."""
    project = await _get_project_or_404(db, project_id, current_user.id)
    job = await _get_job_or_404(db, project.id, job_id)

    if step_key not in STEP_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_key}")
    step = next((s for s in job.steps if s.step_key == step_key), None)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    if step.status != AutoGenerateStepStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Only a failed step can be retried (step is {step.status.value})",
        )
    if job.status == AutoGenerateJobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Job is still running")

    step.status = AutoGenerateStepStatus.PENDING
    step.error_message = None
    job.status = AutoGenerateJobStatus.RUNNING
    job.error_message = None
    job.completed_at = None
    await db.commit()
    await db.refresh(job)

    background.add_task(
        _run_job_background, job.id, project.id, current_user.id, step.step_order)
    return _job_to_response(job)
