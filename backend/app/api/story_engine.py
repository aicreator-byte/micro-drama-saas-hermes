from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, SeriesBible, Character, Location, Episode, EpisodeStatus, EpisodeRevision, Scene, SceneCharacter, Dialogue, SceneStatus
from app.schemas import (
    StoryGenerationRequest, StoryGenerationResponse,
    SceneBreakdownRequest, SceneBreakdownResponse,
    EpisodeCreate, SceneCreate
)
from app.services.ai_client import (
    AIClient, get_ai_client, generate_series_outline, generate_scene_breakdown,
    AIProviderError
)

router = APIRouter(prefix="/story-engine", tags=["story-engine"])


def _get_ai_client(db: AsyncSession) -> AIClient:
    """Get AI client with database session."""
    return AIClient(db)


def _parse_uuid(value) -> Optional[UUID]:
    """Parse a UUID string leniently; return None instead of raising 500."""
    if not value:
        return None
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


async def _snapshot_episode(db: AsyncSession, episode: Episode, user_id: UUID, note: str) -> None:
    """Write the episode's current outline + scenes into EpisodeRevision
    BEFORE any regeneration deletes them (data-loss guard)."""
    result = await db.execute(
        select(Scene).where(Scene.episode_id == episode.id)
    )
    scenes = result.scalars().all()
    scenes_snapshot = []
    for scene in scenes:
        result = await db.execute(
            select(SceneCharacter).where(SceneCharacter.scene_id == scene.id)
        )
        scene_chars = result.scalars().all()
        result = await db.execute(
            select(Dialogue).where(Dialogue.scene_id == scene.id)
        )
        dialogues = result.scalars().all()
        scenes_snapshot.append({
            "scene_number": scene.scene_number,
            "title": scene.title,
            "description": scene.description,
            "shot_list": scene.shot_list,
            "camera_directions": scene.camera_directions,
            "location_id": str(scene.location_id) if scene.location_id else None,
            "characters": [
                {"character_id": str(sc.character_id), "actions": sc.actions,
                 "emotional_state": sc.emotional_state, "position": sc.position}
                for sc in scene_chars
            ],
            "dialogues": [
                {"character_id": str(d.character_id), "text": d.text, "direction": d.direction}
                for d in dialogues
            ],
        })
    rev_result = await db.execute(
        select(func.max(EpisodeRevision.revision_number)).where(
            EpisodeRevision.episode_id == episode.id
        )
    )
    max_rev = rev_result.scalar() or 0
    db.add(EpisodeRevision(
        episode_id=episode.id,
        revision_number=max_rev + 1,
        outline=episode.outline,
        scenes_snapshot=scenes_snapshot,
        notes=note,
        created_by=user_id,
    ))


def _validate_series_output(llm_result: dict) -> list[dict]:
    """Validate LLM series output per item BEFORE old data is touched.
    Raises ValueError on the first invalid episode."""
    episodes = llm_result.get("episodes")
    bible = llm_result.get("series_bible")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("LLM response has no episodes list")
    if not isinstance(bible, dict) or not bible.get("main_plot"):
        raise ValueError("LLM response has no series_bible.main_plot")
    seen = set()
    for ep in episodes:
        if not isinstance(ep, dict):
            raise ValueError("Episode entry is not an object")
        try:
            num = int(ep["episode_number"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Episode is missing a numeric episode_number")
        if num in seen:
            raise ValueError(f"Duplicate episode_number {num} in LLM response")
        seen.add(num)
        if not str(ep.get("title") or "").strip():
            raise ValueError(f"Episode {num} is missing a title")
        if not str(ep.get("outline") or "").strip():
            raise ValueError(f"Episode {num} is missing an outline")
    return episodes


def _validate_breakdown_output(scenes_data, character_ids: set, location_ids: set) -> list[dict]:
    """Validate LLM scene breakdown per item; drop bad references instead of
    crashing (unknown character/location UUIDs become None/skipped)."""
    if not isinstance(scenes_data, list) or not scenes_data:
        raise ValueError("LLM response is not a non-empty scenes list")
    cleaned = []
    for i, scene_data in enumerate(scenes_data, 1):
        if not isinstance(scene_data, dict):
            raise ValueError(f"Scene entry {i} is not an object")
        if not str(scene_data.get("title") or "").strip():
            raise ValueError(f"Scene {i} is missing a title")
        if not str(scene_data.get("description") or "").strip():
            raise ValueError(f"Scene {i} is missing a description")
        loc_id = _parse_uuid(scene_data.get("location_id"))
        if loc_id is not None and str(loc_id) not in location_ids:
            loc_id = None
        chars = []
        for char_data in scene_data.get("characters") or []:
            if not isinstance(char_data, dict):
                continue
            char_id = _parse_uuid(char_data.get("character_id"))
            if char_id is None or str(char_id) not in character_ids:
                continue
            chars.append({
                "character_id": char_id,
                "actions": char_data.get("actions"),
                "emotional_state": char_data.get("emotional_state"),
                "position": char_data.get("position"),
            })
        cleaned.append({
            "title": scene_data["title"],
            "description": scene_data["description"],
            "shot_list": scene_data.get("shot_list"),
            "camera_directions": scene_data.get("camera_directions"),
            "location_id": loc_id,
            "characters": chars,
        })
    return cleaned


@router.post("/{project_id}/generate-series", response_model=StoryGenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_series(
    project_id: UUID,
    request: StoryGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a complete series outline from a premise using real LLM.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get or create series bible
    result = await db.execute(
        select(SeriesBible).where(SeriesBible.project_id == project_id)
    )
    bible = result.scalar_one_or_none()

    if not bible:
        bible = SeriesBible(
            project_id=project_id,
            premise=request.premise,
            tone=request.tone
        )
        db.add(bible)
        await db.flush()

    # Get AI client
    ai_client = _get_ai_client(db)

    # Project characters/locations go into the LLM prompt so the outline is
    # written for THIS project's cast and settings (previously ignored).
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    project_characters = result.scalars().all()
    result = await db.execute(
        select(Location).where(Location.project_id == project_id)
    )
    project_locations = result.scalars().all()

    try:
        # Call real LLM
        llm_result = await generate_series_outline(
            ai_client=ai_client,
            premise=request.premise,
            genre=request.genre or "drama",
            themes=request.themes or [],
            num_episodes=request.num_episodes,
            tone=request.tone,
            characters=[{"id": str(c.id), "name": c.name, "role": c.role or ""}
                        for c in project_characters],
            locations=[{"id": str(loc.id), "name": loc.name} for loc in project_locations],
        )
    except AIProviderError as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI generation failed: {str(e)}"
        )

    # Validate LLM output BEFORE touching existing data — a bad response
    # must not delete anything.
    try:
        episodes_data = _validate_series_output(llm_result)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"AI generation returned invalid data: {e}")
    series_bible_data = llm_result["series_bible"]

    # Snapshot existing episodes, then delete them (to avoid unique
    # constraint violation on episode_number)
    result = await db.execute(
        select(Episode).where(Episode.project_id == project_id)
    )
    existing_episodes = result.scalars().all()
    for ep in existing_episodes:
        await _snapshot_episode(db, ep, current_user.id, "Snapshot before series regeneration")
    await db.flush()
    for ep in existing_episodes:
        # Delete scenes and related data first
        result = await db.execute(
            select(Scene).where(Scene.episode_id == ep.id)
        )
        scenes = result.scalars().all()
        for scene in scenes:
            await db.execute(
                delete(SceneCharacter).where(SceneCharacter.scene_id == scene.id)
            )
            await db.execute(
                delete(Dialogue).where(Dialogue.scene_id == scene.id)
            )
            await db.delete(scene)
        await db.delete(ep)
    await db.flush()

    # Create episode records
    for ep_data in episodes_data:
        episode = Episode(
            project_id=project_id,
            episode_number=ep_data["episode_number"],
            title=ep_data["title"],
            outline=ep_data["outline"],
            status=EpisodeStatus.PLANNED
        )
        db.add(episode)

    # Update series bible with generated data
    bible.main_plot = series_bible_data["main_plot"]
    bible.subplots = series_bible_data["subplots"]
    bible.episode_structure = series_bible_data["episode_structure"]
    bible.updated_at = datetime.utcnow()

    await db.commit()

    return StoryGenerationResponse(
        episodes=episodes_data,
        series_bible={
            "premise": bible.premise,
            "main_plot": bible.main_plot,
            "subplots": bible.subplots,
            "episode_structure": bible.episode_structure
        }
    )


@router.post("/{project_id}/episodes/{episode_id}/breakdown", response_model=SceneBreakdownResponse)
async def breakdown_episode(
    project_id: UUID,
    episode_id: UUID,
    request: SceneBreakdownRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Break down an episode outline into scenes with shot lists using real LLM.
    """
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

    # Get project characters and locations for context
    result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = result.scalars().all()

    result = await db.execute(
        select(Location).where(Location.project_id == project_id)
    )
    locations = result.scalars().all()

    # Prepare character/location data for LLM
    characters_data = [
        {"id": str(c.id), "name": c.name, "role": c.role or ""}
        for c in characters
    ]
    locations_data = [
        {"id": str(l.id), "name": l.name}
        for l in locations
    ]

    # Get AI client
    ai_client = _get_ai_client(db)

    try:
        # Call real LLM
        scenes_data_raw = await generate_scene_breakdown(
            ai_client=ai_client,
            episode_outline=episode.outline or request.episode_outline,
            characters=characters_data,
            locations=locations_data,
        )
    except AIProviderError as e:
        raise HTTPException(
            status_code=502,
            detail=f"AI generation failed: {str(e)}"
        )

    # Validate LLM output BEFORE touching existing scenes.
    try:
        scenes_data = _validate_breakdown_output(
            scenes_data_raw,
            character_ids={str(c.id) for c in characters},
            location_ids={str(loc.id) for loc in locations},
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=f"AI generation returned invalid data: {e}")

    # Snapshot current scenes, then delete them (to avoid unique constraint
    # violation on scene_number)
    await _snapshot_episode(db, episode, current_user.id, "Snapshot before episode breakdown regeneration")
    await db.flush()
    result = await db.execute(
        select(Scene).where(Scene.episode_id == episode_id)
    )
    existing_scenes = result.scalars().all()
    for scene in existing_scenes:
        # Delete scene characters first (cascade should handle this, but be explicit)
        await db.execute(
            delete(SceneCharacter).where(SceneCharacter.scene_id == scene.id)
        )
        await db.delete(scene)
    await db.flush()

    # Create scene records
    for i, scene_data in enumerate(scenes_data, 1):
        scene = Scene(
            episode_id=episode_id,
            scene_number=i,
            title=scene_data["title"],
            description=scene_data["description"],
            shot_list=scene_data.get("shot_list"),
            camera_directions=scene_data.get("camera_directions"),
            location_id=scene_data.get("location_id"),
            status=SceneStatus.PLANNED
        )
        db.add(scene)
        await db.flush()

        # Add characters to scene
        for char_data in scene_data.get("characters", []):
            scene_char = SceneCharacter(
                scene_id=scene.id,
                character_id=char_data["character_id"],
                actions=char_data.get("actions"),
                emotional_state=char_data.get("emotional_state"),
                position=char_data.get("position")
            )
            db.add(scene_char)

    episode.status = EpisodeStatus.SCENES_READY
    episode.updated_at = datetime.utcnow()
    await db.commit()

    return SceneBreakdownResponse(scenes=scenes_data)


# Episode auto-creation from story generation
@router.post("/{project_id}/create-episodes")
async def create_episodes_from_outline(
    project_id: UUID,
    episodes_data: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create episode records from generated outlines."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    created = []
    for ep_data in episodes_data:
        # Check if episode number exists
        result = await db.execute(
            select(Episode).where(and_(
                Episode.project_id == project_id,
                Episode.episode_number == ep_data["episode_number"]
            ))
        )
        if result.scalar_one_or_none():
            continue  # Skip existing

        episode = Episode(
            project_id=project_id,
            episode_number=ep_data["episode_number"],
            title=ep_data.get("title"),
            outline=ep_data.get("outline"),
            status=EpisodeStatus.PLANNED
        )
        db.add(episode)
        created.append(ep_data["episode_number"])

    await db.commit()
    return {"created_episodes": created, "count": len(created)}