from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Scene, SceneCharacter, Dialogue, Character, Location, Episode, Prompt, PromptType
from app.schemas import PromptCreate, PromptUpdate, PromptResponse, PromptGenerationRequest, PromptGenerationResponse, PaginationParams, PaginatedResponse

router = APIRouter(prefix="/prompts", tags=["prompts"])


class _SafeFormatDict(dict):
    """dict for str.format that leaves unknown placeholders intact instead of KeyError."""

    def __missing__(self, key):
        return "{" + key + "}"


def _safe_format(template: str, **values) -> str:
    return template.format_map(_SafeFormatDict(values))


# AI Prompt Generation endpoints
@router.post("/generate", response_model=PromptGenerationResponse)
async def generate_prompt(
    request: PromptGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate AI prompts for various types.
    This is a placeholder that returns structured prompts based on type and context.
    In production, this would call an LLM API.
    """
    prompt_templates = {
        PromptType.CHARACTER_IMAGE: {
            "prompt": "A detailed character portrait of {name}, {physical_appearance}. {personality}. {costume}. Cinematic lighting, high quality, 8k resolution, consistent character design.",
            "negative": "blurry, low quality, distorted, deformed, ugly, bad anatomy, extra limbs, watermark, text, signature",
            "parameters": {"width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.0}
        },
        PromptType.LOCATION_IMAGE: {
            "prompt": "A cinematic establishing shot of {name}, {environment}. {lighting} lighting, {atmosphere} atmosphere. High quality, detailed environment, 8k resolution.",
            "negative": "blurry, low quality, distorted, watermark, text, people, characters",
            "parameters": {"width": 1920, "height": 1080, "steps": 30, "cfg_scale": 7.0}
        },
        PromptType.SCENE_IMAGE: {
            "prompt": "A cinematic scene: {description}. Characters: {characters}. Camera: {camera_directions}. {lighting} lighting. High quality, cinematic composition, 8k.",
            "negative": "blurry, low quality, distorted, bad composition, watermark, text",
            "parameters": {"width": 1920, "height": 1080, "steps": 30, "cfg_scale": 7.0}
        },
        PromptType.VIDEO_GENERATION: {
            "prompt": "Cinematic video: {description}. Camera movement: {camera_movement}. Characters performing: {actions}. Duration: 5-10 seconds. High quality, smooth motion.",
            "negative": "blurry, low quality, distorted, flickering, bad motion, watermark, text",
            "parameters": {"duration": 8, "fps": 24, "resolution": "1920x1080"}
        },
        PromptType.CAMERA_MOVEMENT: {
            "prompt": "Camera movement: {movement_type}. Speed: {speed}. Angle: {angle}. Smooth professional cinematography.",
            "negative": "shaky, jittery, abrupt, amateur",
            "parameters": {}
        },
        PromptType.CHARACTER_ACTION: {
            "prompt": "Character {name} performing: {action}. Emotional state: {emotion}. {direction}. Cinematic, expressive acting.",
            "negative": "stiff, unnatural, bad acting, distorted",
            "parameters": {}
        },
        PromptType.DIALOGUE_AUDIO: {
            "prompt": "Voice acting for {name}: \"{text}\". Tone: {direction}. Emotional state: {emotion}. High quality voice recording.",
            "negative": "robotic, monotone, background noise, low quality",
            "parameters": {"format": "wav", "sample_rate": 44100}
        }
    }

    template = prompt_templates.get(request.prompt_type, {
        "prompt": "Generate content for {prompt_type} with context: {context}",
        "negative": "",
        "parameters": {}
    })

    # Fill template with context
    context = request.context
    style = request.style_preferences or {}

    prompt_text = _safe_format(template["prompt"], **context, **style)
    negative_prompt = _safe_format(template["negative"], **context, **style) if template["negative"] else None
    parameters = {**template["parameters"], **(style.get("parameters", {}))}

    return PromptGenerationResponse(
        prompt_text=prompt_text,
        negative_prompt=negative_prompt,
        parameters=parameters
    )


@router.post("/{project_id}", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    project_id: UUID,
    prompt_data: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify references if provided
    if prompt_data.scene_id:
        result = await db.execute(
            select(Scene).where(and_(Scene.id == prompt_data.scene_id, Scene.episode.has(Episode.project_id == project_id)))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Scene not found")

    if prompt_data.character_id:
        result = await db.execute(
            select(Character).where(and_(Character.id == prompt_data.character_id, Character.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Character not found")

    if prompt_data.location_id:
        result = await db.execute(
            select(Location).where(and_(Location.id == prompt_data.location_id, Location.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Location not found")

    if prompt_data.episode_id:
        result = await db.execute(
            select(Episode).where(and_(Episode.id == prompt_data.episode_id, Episode.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Episode not found")

    prompt = Prompt(project_id=project_id, **prompt_data.model_dump())
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_prompts(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    prompt_type: Optional[PromptType] = Query(None),
    scene_id: Optional[UUID] = Query(None),
    character_id: Optional[UUID] = Query(None),
    location_id: Optional[UUID] = Query(None),
    episode_id: Optional[UUID] = Query(None),
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
    query = select(Prompt).where(Prompt.project_id == project_id)
    count_query = select(func.count(Prompt.id)).where(Prompt.project_id == project_id)

    if prompt_type:
        query = query.where(Prompt.prompt_type == prompt_type)
        count_query = count_query.where(Prompt.prompt_type == prompt_type)
    if scene_id:
        query = query.where(Prompt.scene_id == scene_id)
        count_query = count_query.where(Prompt.scene_id == scene_id)
    if character_id:
        query = query.where(Prompt.character_id == character_id)
        count_query = count_query.where(Prompt.character_id == character_id)
    if location_id:
        query = query.where(Prompt.location_id == location_id)
        count_query = count_query.where(Prompt.location_id == location_id)
    if episode_id:
        query = query.where(Prompt.episode_id == episode_id)
        count_query = count_query.where(Prompt.episode_id == episode_id)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        query.order_by(Prompt.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    prompts = result.scalars().all()

    # Convert to response schemas
    prompt_responses = [PromptResponse.model_validate(p) for p in prompts]

    return PaginatedResponse(
        items=prompt_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/{prompt_id}", response_model=PromptResponse)
async def get_prompt(
    project_id: UUID,
    prompt_id: UUID,
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
        select(Prompt).where(and_(Prompt.id == prompt_id, Prompt.project_id == project_id))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@router.patch("/{project_id}/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    project_id: UUID,
    prompt_id: UUID,
    prompt_data: PromptUpdate,
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
        select(Prompt).where(and_(Prompt.id == prompt_id, Prompt.project_id == project_id))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    update_data = prompt_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prompt, field, value)

    prompt.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete("/{project_id}/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    project_id: UUID,
    prompt_id: UUID,
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
        select(Prompt).where(and_(Prompt.id == prompt_id, Prompt.project_id == project_id))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    await db.delete(prompt)
    await db.commit()


# Batch prompt generation for a scene
@router.post("/{project_id}/episodes/{episode_id}/scenes/{scene_id}/generate-all", response_model=List[PromptResponse])
async def generate_all_scene_prompts(
    project_id: UUID,
    episode_id: UUID,
    scene_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Generate all standard prompts for a scene."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get scene with relations
    result = await db.execute(
        select(Scene)
        .options(
            selectinload(Scene.location),
            selectinload(Scene.characters).selectinload(SceneCharacter.character),
            selectinload(Scene.dialogues).selectinload(Dialogue.character)
        )
        .where(and_(Scene.id == scene_id, Scene.episode_id == episode_id))
    )
    scene = result.scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Get project characters and locations for context
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    all_characters = result.scalars().all()

    result = await db.execute(
        select(Location).where(Location.project_id == project_id)
    )
    all_locations = result.scalars().all()

    prompts_created = []

    # Generate scene image prompt
    scene_chars = [sc.character.name for sc in scene.characters]
    context = {
        "description": scene.description or "",
        "characters": ", ".join(scene_chars),
        "camera_directions": scene.camera_directions or "medium shot",
        "lighting": scene.location.lighting if scene.location else "natural"
    }
    scene_prompt = Prompt(
        project_id=project_id,
        scene_id=scene_id,
        episode_id=episode_id,
        prompt_type=PromptType.SCENE_IMAGE,
        title=f"Scene {scene.scene_number} - Main Image",
        prompt_text=f"A cinematic scene: {context['description']}. Characters: {context['characters']}. Camera: {context['camera_directions']}. {context['lighting']} lighting. High quality, cinematic composition, 8k.",
        negative_prompt="blurry, low quality, distorted, bad composition, watermark, text",
        parameters={"width": 1920, "height": 1080, "steps": 30, "cfg_scale": 7.0}
    )
    db.add(scene_prompt)
    prompts_created.append(scene_prompt)

    # Generate character image prompts for characters in scene
    for sc in scene.characters:
        char = sc.character
        char_context = {
            "name": char.name,
            "physical_appearance": char.physical_appearance or "",
            "personality": char.personality or "",
            "costume": char.costume or ""
        }
        char_prompt = Prompt(
            project_id=project_id,
            scene_id=scene_id,
            character_id=char.id,
            episode_id=episode_id,
            prompt_type=PromptType.CHARACTER_IMAGE,
            title=f"Character: {char.name} - Scene {scene.scene_number}",
            prompt_text=f"A detailed character portrait of {char_context['name']}, {char_context['physical_appearance']}. {char_context['personality']}. {char_context['costume']}. Cinematic lighting, high quality, 8k resolution, consistent character design.",
            negative_prompt="blurry, low quality, distorted, deformed, ugly, bad anatomy, extra limbs, watermark, text, signature",
            parameters={"width": 1024, "height": 1024, "steps": 30, "cfg_scale": 7.0}
        )
        db.add(char_prompt)
        prompts_created.append(char_prompt)

    # Generate location image prompt if scene has location
    if scene.location:
        loc = scene.location
        loc_context = {
            "name": loc.name,
            "environment": loc.environment or "",
            "lighting": loc.lighting or "natural",
            "atmosphere": loc.atmosphere or "neutral"
        }
        loc_prompt = Prompt(
            project_id=project_id,
            scene_id=scene_id,
            location_id=loc.id,
            episode_id=episode_id,
            prompt_type=PromptType.LOCATION_IMAGE,
            title=f"Location: {loc.name} - Scene {scene.scene_number}",
            prompt_text=f"A cinematic establishing shot of {loc_context['name']}, {loc_context['environment']}. {loc_context['lighting']} lighting, {loc_context['atmosphere']} atmosphere. High quality, detailed environment, 8k resolution.",
            negative_prompt="blurry, low quality, distorted, watermark, text, people, characters",
            parameters={"width": 1920, "height": 1080, "steps": 30, "cfg_scale": 7.0}
        )
        db.add(loc_prompt)
        prompts_created.append(loc_prompt)

    # Generate video generation prompt
    video_prompt = Prompt(
        project_id=project_id,
        scene_id=scene_id,
        episode_id=episode_id,
        prompt_type=PromptType.VIDEO_GENERATION,
        title=f"Scene {scene.scene_number} - Video Generation",
        prompt_text=f"Cinematic video: {scene.description or 'Scene'}. Camera movement: {scene.camera_directions or 'static'}. Characters performing actions. Duration: 5-10 seconds. High quality, smooth motion.",
        negative_prompt="blurry, low quality, distorted, flickering, bad motion, watermark, text",
        parameters={"duration": 8, "fps": 24, "resolution": "1920x1080"}
    )
    db.add(video_prompt)
    prompts_created.append(video_prompt)

    # Generate dialogue audio prompts
    for dialogue in scene.dialogues:
        audio_prompt = Prompt(
            project_id=project_id,
            scene_id=scene_id,
            character_id=dialogue.character_id,
            episode_id=episode_id,
            prompt_type=PromptType.DIALOGUE_AUDIO,
            title=f"Dialogue: {dialogue.character.name} - Scene {scene.scene_number}",
            prompt_text=f"Voice acting for {dialogue.character.name}: \"{dialogue.text}\". Tone: {dialogue.direction or 'natural'}. High quality voice recording.",
            negative_prompt="robotic, monotone, background noise, low quality",
            parameters={"format": "wav", "sample_rate": 44100}
        )
        db.add(audio_prompt)
        prompts_created.append(audio_prompt)

    await db.commit()
    for p in prompts_created:
        await db.refresh(p)

    return prompts_created
