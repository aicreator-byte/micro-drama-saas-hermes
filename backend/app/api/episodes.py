from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Episode, EpisodeStatus, EpisodeRevision
from app.schemas import EpisodeCreate, EpisodeUpdate, EpisodeResponse, EpisodeRevisionCreate, EpisodeRevisionResponse, PaginationParams, PaginatedResponse

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.post("/{project_id}", response_model=EpisodeResponse, status_code=status.HTTP_201_CREATED)
async def create_episode(
    project_id: UUID,
    episode_data: EpisodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if episode number already exists
    result = await db.execute(
        select(Episode).where(and_(Episode.project_id == project_id, Episode.episode_number == episode_data.episode_number))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Episode number already exists")

    episode = Episode(project_id=project_id, **episode_data.model_dump())
    db.add(episode)
    await db.commit()
    await db.refresh(episode)
    return episode


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_episodes(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    status_filter: Optional[EpisodeStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = select(Episode).where(Episode.project_id == project_id)
    count_query = select(func.count(Episode.id)).where(Episode.project_id == project_id)

    if status_filter:
        query = query.where(Episode.status == status_filter)
        count_query = count_query.where(Episode.status == status_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        query.order_by(Episode.episode_number)
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    episodes = result.scalars().all()

    # Convert to response schemas
    episode_responses = [EpisodeResponse.model_validate(ep) for ep in episodes]

    return PaginatedResponse(
        items=episode_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/{episode_id}", response_model=EpisodeResponse)
async def get_episode(
    project_id: UUID,
    episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Episode)
        .options(selectinload(Episode.scenes))
        .where(and_(Episode.id == episode_id, Episode.project_id == project_id))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.patch("/{project_id}/{episode_id}", response_model=EpisodeResponse)
async def update_episode(
    project_id: UUID,
    episode_id: UUID,
    episode_data: EpisodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    update_data = episode_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(episode, field, value)

    # If status changed to completed, set completed_at
    if episode_data.status == EpisodeStatus.COMPLETED and episode.completed_at is None:
        episode.completed_at = datetime.utcnow()

    episode.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(episode)
    return episode


@router.delete("/{project_id}/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode(
    project_id: UUID,
    episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    await db.delete(episode)
    await db.commit()


@router.post("/{project_id}/{episode_id}/revisions", response_model=EpisodeRevisionResponse, status_code=status.HTTP_201_CREATED)
async def create_revision(
    project_id: UUID,
    episode_id: UUID,
    revision_data: EpisodeRevisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify episode
    result = await db.execute(
        select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Get next revision number
    count_result = await db.execute(
        select(func.count(EpisodeRevision.id)).where(EpisodeRevision.episode_id == episode_id)
    )
    revision_number = (count_result.scalar() or 0) + 1

    revision = EpisodeRevision(
        episode_id=episode_id,
        revision_number=revision_number,
        created_by=current_user.id,
        **revision_data.model_dump()
    )
    db.add(revision)
    await db.commit()
    await db.refresh(revision)
    return revision


@router.get("/{project_id}/{episode_id}/revisions", response_model=List[EpisodeRevisionResponse])
async def list_revisions(
    project_id: UUID,
    episode_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify episode
    result = await db.execute(
        select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Episode not found")

    result = await db.execute(
        select(EpisodeRevision)
        .where(EpisodeRevision.episode_id == episode_id)
        .order_by(EpisodeRevision.revision_number.desc())
    )
    return result.scalars().all()