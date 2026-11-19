from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, SeriesBible
from app.schemas import SeriesBibleCreate, SeriesBibleUpdate, SeriesBibleResponse

router = APIRouter(prefix="/series-bible", tags=["series-bible"])


@router.post("/{project_id}", response_model=SeriesBibleResponse, status_code=status.HTTP_201_CREATED)
async def create_series_bible(
    project_id: UUID,
    bible_data: SeriesBibleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if series bible already exists
    result = await db.execute(
        select(SeriesBible).where(SeriesBible.project_id == project_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Series Bible already exists for this project")

    bible = SeriesBible(project_id=project_id, source="manual", **bible_data.model_dump())
    db.add(bible)
    await db.commit()
    await db.refresh(bible)
    return bible


@router.get("/{project_id}", response_model=SeriesBibleResponse)
async def get_series_bible(
    project_id: UUID,
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
        select(SeriesBible).where(SeriesBible.project_id == project_id)
    )
    bible = result.scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Series Bible not found")
    return bible


@router.patch("/{project_id}", response_model=SeriesBibleResponse)
async def update_series_bible(
    project_id: UUID,
    bible_data: SeriesBibleUpdate,
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
        select(SeriesBible).where(SeriesBible.project_id == project_id)
    )
    bible = result.scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Series Bible not found")

    update_data = bible_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bible, field, value)

    # Perubahan manual apa pun menandai bible sebagai manual (dilindungi
    # dari timpa auto-generate).
    bible.source = "manual"
    bible.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(bible)
    return bible


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series_bible(
    project_id: UUID,
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
        select(SeriesBible).where(SeriesBible.project_id == project_id)
    )
    bible = result.scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Series Bible not found")

    await db.delete(bible)
    await db.commit()