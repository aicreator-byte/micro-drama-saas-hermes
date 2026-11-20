"""Cek konsistensi karakter: rule-based + LLM (via AIClient yang sama
dengan auto-generate).

Dijalankan sebagai background task (audit ronde 2, P1-1): POST membuat
check berstatus RUNNING dan kembali langsung (201); hasilnya bisa
di-poll lewat GET .../consistency-checks/{id}. Sebelumnya cek jalan
sinkron di request termasuk panggilan LLM — request bisa menggantung
30-120+ dtk sampai timeout HTTP/proxy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import (
    User, Project, Character, Episode, CharacterConsistencyCheck,
    ConsistencyCheckStatus,
)
from app.schemas import ConsistencyCheckResponse
from app.services.consistency import rule_based_issues, run_llm_check, merge_issues
from app.services.ai_client import AIClient

router = APIRouter(prefix="/projects", tags=["consistency"])


def _session_factory():
    """Session factory for background runs. Patchable in tests
    (tests point it at their in-memory SQLite session factory)."""
    from app.db.session import AsyncSessionLocal
    return AsyncSessionLocal()


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


def _to_response(c: CharacterConsistencyCheck) -> ConsistencyCheckResponse:
    return ConsistencyCheckResponse(
        id=c.id, project_id=c.project_id, status=c.status.value,
        checked_episodes=c.checked_episodes, issues=c.issues,
        issue_count=c.issue_count, error_message=c.error_message,
        created_at=c.created_at, completed_at=c.completed_at,
    )


async def _run_consistency_check(check_id: UUID) -> None:
    """Background runner: own session, own AIClient. Never raises out
    (check FAILED status is the failure channel, not an exception)."""
    async with _session_factory() as db:
        check = await db.get(CharacterConsistencyCheck, check_id)
        if not check:
            return
        result = await db.execute(
            select(Character).where(Character.project_id == check.project_id).order_by(Character.order_index)
        )
        characters = result.scalars().all()
        result = await db.execute(
            select(Episode).where(Episode.project_id == check.project_id).order_by(Episode.episode_number)
        )
        episodes = result.scalars().all()
        char_dicts = [{
            "name": c.name, "role": c.role,
            "physical_appearance": c.physical_appearance,
            "personality": c.personality, "background": c.background,
        } for c in characters]
        ep_dicts = [{
            "episode_number": e.episode_number, "title": e.title, "outline": e.outline,
        } for e in episodes]
        try:
            rule_issues = rule_based_issues(char_dicts, ep_dicts)
            llm_issues = await run_llm_check(AIClient(db), char_dicts, ep_dicts)
            issues = merge_issues(rule_issues, llm_issues)
            check.issues = issues
            check.issue_count = len(issues)
            check.status = ConsistencyCheckStatus.COMPLETED
        except Exception as e:  # noqa: BLE001 — simpan gagal, jangan 500
            check.status = ConsistencyCheckStatus.FAILED
            check.error_message = str(e)[:500]
            check.issues = []
            check.issue_count = 0
        check.completed_at = _utcnow_naive()
        await db.commit()


@router.post("/{project_id}/consistency-check", response_model=ConsistencyCheckResponse, status_code=status.HTTP_201_CREATED)
async def run_consistency_check(
    project_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Buat check konsistensi dan jalankan di background. Kembali 201
    langsung dengan status 'running'; poll GET .../consistency-checks/{id}
    untuk hasil. LLM gagal -> hasil rule-based tetap disimpan completed."""
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(Character).where(Character.project_id == project_id).order_by(Character.order_index)
    )
    characters = result.scalars().all()
    result = await db.execute(
        select(Episode).where(Episode.project_id == project_id).order_by(Episode.episode_number)
    )
    episodes = result.scalars().all()
    if not characters:
        raise HTTPException(status_code=400, detail="Proyek belum punya karakter untuk dicek")

    check = CharacterConsistencyCheck(
        project_id=project_id, user_id=current_user.id,
        status=ConsistencyCheckStatus.RUNNING,
        checked_episodes=[e.episode_number for e in episodes],
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    background_tasks.add_task(_run_consistency_check, check.id)
    return _to_response(check)


@router.get("/{project_id}/consistency-checks", response_model=list[ConsistencyCheckResponse])
async def list_consistency_checks(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(CharacterConsistencyCheck)
        .where(CharacterConsistencyCheck.project_id == project_id)
        .order_by(CharacterConsistencyCheck.created_at.desc())
    )
    return [_to_response(c) for c in result.scalars().all()]


@router.get("/{project_id}/consistency-checks/{check_id}", response_model=ConsistencyCheckResponse)
async def get_consistency_check(
    project_id: UUID, check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _get_project(db, current_user, project_id)
    result = await db.execute(
        select(CharacterConsistencyCheck).where(
            and_(
                CharacterConsistencyCheck.id == check_id,
                CharacterConsistencyCheck.project_id == project_id,
            )
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Consistency check not found")
    return _to_response(check)
