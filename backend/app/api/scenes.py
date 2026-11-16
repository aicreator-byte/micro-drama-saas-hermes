from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Episode, Scene, Location, Character, SceneCharacter, Dialogue, SceneStatus
from app.schemas import (
    SceneCreate, SceneUpdate, SceneResponse,
    SceneCharacterCreate, SceneCharacterResponse,
    DialogueCreate, DialogueUpdate, DialogueResponse,
    PaginationParams, PaginatedResponse
)

router = APIRouter(prefix="/scenes", tags=["scenes"])


# Scene endpoints
@router.post("/{project_id}/episodes/{episode_id}", response_model=SceneResponse, status_code=status.HTTP_201_CREATED)
async def create_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_data: SceneCreate,
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

    # Verify location if provided
    if scene_data.location_id:
        result = await db.execute(
            select(Location).where(and_(Location.id == scene_data.location_id, Location.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Location not found")

    # Check if scene number already exists
    result = await db.execute(
        select(Scene).where(and_(Scene.episode_id == episode_id, Scene.scene_number == scene_data.scene_number))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Scene number already exists")

    scene = Scene(episode_id=episode_id, **scene_data.model_dump())
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene


@router.get("/{project_id}/episodes/{episode_id}", response_model=PaginatedResponse)
async def list_scenes(
    project_id: UUID,
    episode_id: UUID,
    pagination: PaginationParams = Depends(),
    status_filter: Optional[SceneStatus] = Query(None, alias="status"),
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

    # Build query
    query = select(Scene).where(Scene.episode_id == episode_id)
    count_query = select(func.count(Scene.id)).where(Scene.episode_id == episode_id)

    if status_filter:
        query = query.where(Scene.status == status_filter)
        count_query = count_query.where(Scene.status == status_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        query.order_by(Scene.scene_number)
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    scenes = result.scalars().all()

    # Convert to response schemas
    scene_responses = [SceneResponse.model_validate(s) for s in scenes]

    return PaginatedResponse(
        items=scene_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/episodes/{episode_id}/{scene_id}", response_model=SceneResponse)
async def get_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
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
        select(Scene)
        .options(
            selectinload(Scene.location),
            selectinload(Scene.characters).selectinload(SceneCharacter.character),
            selectinload(Scene.dialogues).selectinload(Dialogue.character),
            selectinload(Scene.prompts)
        )
        .where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.patch("/{project_id}/episodes/{episode_id}/{scene_id}", response_model=SceneResponse)
async def update_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    scene_data: SceneUpdate,
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
        select(Scene).where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Verify location if provided
    if scene_data.location_id:
        result = await db.execute(
            select(Location).where(and_(Location.id == scene_data.location_id, Location.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Location not found")

    update_data = scene_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scene, field, value)

    scene.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(scene)
    return scene


@router.delete("/{project_id}/episodes/{episode_id}/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
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
        select(Scene).where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    await db.delete(scene)
    await db.commit()


# SceneCharacter endpoints
@router.post("/{project_id}/episodes/{episode_id}/{scene_id}/characters", response_model=SceneCharacterResponse, status_code=status.HTTP_201_CREATED)
async def add_character_to_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    character_data: SceneCharacterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify scene
    result = await db.execute(
        select(Scene).where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scene not found")

    # Verify character belongs to project
    result = await db.execute(
        select(Character).where(and_(Character.id == character_data.character_id, Character.project_id == project_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Character not found")

    # Check if already added
    result = await db.execute(
        select(SceneCharacter).where(and_(
            SceneCharacter.scene_id == scene_id,
            SceneCharacter.character_id == character_data.character_id
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Character already in scene")

    scene_char = SceneCharacter(scene_id=scene_id, **character_data.model_dump())
    db.add(scene_char)
    await db.commit()
    await db.refresh(scene_char)
    return scene_char


@router.get("/{project_id}/episodes/{episode_id}/{scene_id}/characters", response_model=List[SceneCharacterResponse])
async def list_scene_characters(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
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
        select(SceneCharacter)
        .options(selectinload(SceneCharacter.character))
        .where(SceneCharacter.scene_id == scene_id)
    )
    return result.scalars().all()


@router.delete("/{project_id}/episodes/{episode_id}/{scene_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_character_from_scene(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
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
        select(SceneCharacter).where(and_(
            SceneCharacter.scene_id == scene_id,
            SceneCharacter.character_id == character_id
        ))
    )
    scene_char = result.scalar_one_or_none()
    if not scene_char:
        raise HTTPException(status_code=404, detail="Character not in scene")

    await db.delete(scene_char)
    await db.commit()


# Dialogue endpoints
@router.post("/{project_id}/episodes/{episode_id}/{scene_id}/dialogues", response_model=DialogueResponse, status_code=status.HTTP_201_CREATED)
async def create_dialogue(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    dialogue_data: DialogueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify scene
    result = await db.execute(
        select(Scene).where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Scene not found")

    # Verify character belongs to project
    result = await db.execute(
        select(Character).where(and_(Character.id == dialogue_data.character_id, Character.project_id == project_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Character not found")

    dialogue = Dialogue(scene_id=scene_id, **dialogue_data.model_dump())
    db.add(dialogue)
    await db.commit()
    await db.refresh(dialogue)
    return dialogue


@router.get("/{project_id}/episodes/{episode_id}/{scene_id}/dialogues", response_model=List[DialogueResponse])
async def list_dialogues(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
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
        select(Dialogue)
        .options(selectinload(Dialogue.character))
        .where(Dialogue.scene_id == scene_id)
        .order_by(Dialogue.order_index)
    )
    return result.scalars().all()


@router.patch("/{project_id}/episodes/{episode_id}/{scene_id}/dialogues/{dialogue_id}", response_model=DialogueResponse)
async def update_dialogue(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    dialogue_id: UUID,
    dialogue_data: DialogueUpdate,
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
        select(Dialogue).where(and_(Dialogue.id == dialogue_id, Dialogue.scene_id == scene_id))
    )
    dialogue = result.scalar_one_or_none()
    if not dialogue:
        raise HTTPException(status_code=404, detail="Dialogue not found")

    update_data = dialogue_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dialogue, field, value)

    dialogue.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(dialogue)
    return dialogue


@router.delete("/{project_id}/episodes/{episode_id}/{scene_id}/dialogues/{dialogue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dialogue(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    dialogue_id: UUID,
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
        select(Dialogue).where(and_(Dialogue.id == dialogue_id, Dialogue.scene_id == scene_id))
    )
    dialogue = result.scalar_one_or_none()
    if not dialogue:
        raise HTTPException(status_code=404, detail="Dialogue not found")

    await db.delete(dialogue)
    await db.commit()