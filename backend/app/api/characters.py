from datetime import datetime
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Character
from app.schemas import CharacterCreate, CharacterUpdate, CharacterResponse, PaginationParams, PaginatedResponse

router = APIRouter(prefix="/characters", tags=["characters"])


@router.post("/{project_id}", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: UUID,
    character_data: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # No per-project character limit (keputusan Di 17 Nov 2026:
    # maks 6 karakter TIDAK ditegakkan — karakter ke-7+ diterima).
    character = Character(project_id=project_id, **character_data.model_dump())
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_characters(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get total count
    count_result = await db.execute(
        select(func.count(Character.id)).where(Character.project_id == project_id)
    )
    total = count_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.order_index, Character.created_at)
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    characters = result.scalars().all()

    # Convert to response schemas
    character_responses = [CharacterResponse.model_validate(c) for c in characters]

    return PaginatedResponse(
        items=character_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/{character_id}", response_model=CharacterResponse)
async def get_character(
    project_id: UUID,
    character_id: UUID,
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
        select(Character).where(and_(Character.id == character_id, Character.project_id == project_id))
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    return character


@router.patch("/{project_id}/{character_id}", response_model=CharacterResponse)
async def update_character(
    project_id: UUID,
    character_id: UUID,
    character_data: CharacterUpdate,
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
        select(Character).where(and_(Character.id == character_id, Character.project_id == project_id))
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = character_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(character, field, value)

    character.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{project_id}/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    project_id: UUID,
    character_id: UUID,
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
        select(Character).where(and_(Character.id == character_id, Character.project_id == project_id))
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    await db.delete(character)
    await db.commit()


@router.post("/{project_id}/reorder", response_model=List[CharacterResponse])
async def reorder_characters(
    project_id: UUID,
    character_ids: List[UUID],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify all characters belong to project
    result = await db.execute(
        select(Character).where(and_(Character.project_id == project_id, Character.id.in_(character_ids)))
    )
    characters = result.scalars().all()
    if len(characters) != len(character_ids):
        raise HTTPException(status_code=400, detail="Some characters not found or don't belong to project")

    # Update order
    for index, char_id in enumerate(character_ids):
        char = next(c for c in characters if c.id == char_id)
        char.order_index = index

    await db.commit()

    # Return updated list
    result = await db.execute(
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.order_index)
    )
    return result.scalars().all()