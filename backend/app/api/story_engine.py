from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, SeriesBible, Character, Location, Episode, EpisodeStatus, Scene, SceneStatus
from app.schemas import (
    StoryGenerationRequest, StoryGenerationResponse,
    SceneBreakdownRequest, SceneBreakdownResponse,
    EpisodeCreate, SceneCreate
)

router = APIRouter(prefix="/story-engine", tags=["story-engine"])


@router.post("/{project_id}/generate-series", response_model=StoryGenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_series(
    project_id: UUID,
    request: StoryGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a complete 20-episode series outline from a premise.
    In production, this would call an LLM API.
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

    # Generate episode outlines (mock implementation - replace with LLM call)
    episodes_data = []
    for i in range(1, request.num_episodes + 1):
        episode_outline = _generate_episode_outline(
            premise=request.premise,
            genre=request.genre or "drama",
            themes=request.themes or [],
            episode_number=i,
            total_episodes=request.num_episodes,
            tone=request.tone
        )
        episodes_data.append(episode_outline)

        # Create episode record
        episode = Episode(
            project_id=project_id,
            episode_number=i,
            title=episode_outline["title"],
            outline=episode_outline["outline"],
            status=EpisodeStatus.PLANNED
        )
        db.add(episode)

    # Update series bible with generated data
    bible.main_plot = _generate_main_plot(request.premise, request.num_episodes)
    bible.subplots = _generate_subplots(request.premise, request.themes or [])
    bible.episode_structure = {
        "total_episodes": request.num_episodes,
        "structure": "three_act",
        "acts": {
            "act1": {"episodes": f"1-{request.num_episodes//3}", "focus": "setup"},
            "act2": {"episodes": f"{request.num_episodes//3 + 1}-{2*request.num_episodes//3}", "focus": "confrontation"},
            "act3": {"episodes": f"{2*request.num_episodes//3 + 1}-{request.num_episodes}", "focus": "resolution"}
        }
    }
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
    Break down an episode outline into scenes with shot lists.
    In production, this would call an LLM API.
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

    # Generate scene breakdown (mock implementation)
    scenes_data = _generate_scene_breakdown(
        episode_outline=episode.outline or request.episode_outline,
        characters=[{"id": str(c.id), "name": c.name, "role": c.role} for c in characters],
        locations=[{"id": str(l.id), "name": l.name} for l in locations]
    )

    # Create scene records
    for i, scene_data in enumerate(scenes_data, 1):
        scene = Scene(
            episode_id=episode_id,
            scene_number=i,
            title=scene_data["title"],
            description=scene_data["description"],
            shot_list=scene_data.get("shot_list"),
            camera_directions=scene_data.get("camera_directions"),
            location_id=UUID(scene_data["location_id"]) if scene_data.get("location_id") else None,
            status=SceneStatus.PLANNED
        )
        db.add(scene)
        await db.flush()

        # Add characters to scene
        for char_data in scene_data.get("characters", []):
            from app.models import SceneCharacter
            scene_char = SceneCharacter(
                scene_id=scene.id,
                character_id=UUID(char_data["character_id"]),
                actions=char_data.get("actions"),
                emotional_state=char_data.get("emotional_state"),
                position=char_data.get("position")
            )
            db.add(scene_char)

    episode.status = EpisodeStatus.SCENES_READY
    episode.updated_at = datetime.utcnow()
    await db.commit()

    return SceneBreakdownResponse(scenes=scenes_data)


def _generate_episode_outline(premise: str, genre: str, themes: List[str], episode_number: int, total_episodes: int, tone: Optional[str]) -> Dict[str, Any]:
    """Generate a single episode outline. Replace with LLM call in production."""
    act = "setup" if episode_number <= total_episodes // 3 else ("confrontation" if episode_number <= 2 * total_episodes // 3 else "resolution")

    templates = {
        "setup": [
            "Introduction of main character and their world",
            "Inciting incident disrupts status quo",
            "Character makes a choice that commits them to the journey",
            "First major obstacle appears",
            "Character forms initial alliances",
            "Stakes are established"
        ],
        "confrontation": [
            "Character faces escalating challenges",
            "A major setback forces reevaluation",
            "Secret or revelation changes everything",
            "Character's flaw is exploited",
            "Midpoint climax - apparent victory or defeat",
            "Darkest moment - all seems lost",
            "Character finds new resolve",
            "Preparation for final confrontation"
        ],
        "resolution": [
            "Final confrontation begins",
            "Character uses everything they've learned",
            "Climactic moment of truth",
            "Aftermath and consequences",
            "New equilibrium established",
            "Epilogue - hint of future"
        ]
    }

    theme_str = ", ".join(themes) if themes else "human drama"
    focus = templates[act][(episode_number - 1) % len(templates[act])]

    return {
        "episode_number": episode_number,
        "title": f"Episode {episode_number}: {focus}",
        "outline": f"In this {act} phase episode, {focus.lower()}. The story explores {theme_str} through the lens of {premise}. Tone: {tone or 'dramatic'}. This episode advances the {act} arc.",
        "act": act,
        "key_beats": [
            f"Beat 1: {focus}",
            f"Beat 2: Character development moment",
            f"Beat 3: Plot advancement",
            f"Beat 4: Cliffhanger/setup for next episode"
        ],
        "cliffhanger": f"A shocking revelation or dangerous situation that compels the viewer to continue." if episode_number < total_episodes else None
    }


def _generate_main_plot(premise: str, num_episodes: int) -> str:
    return f"A {num_episodes}-episode journey following the core premise: {premise}. Structured in three acts: Setup (episodes 1-{num_episodes//3}), Confrontation (episodes {num_episodes//3 + 1}-{2*num_episodes//3}), Resolution (episodes {2*num_episodes//3 + 1}-{num_episodes})."


def _generate_subplots(premise: str, themes: List[str]) -> List[Dict[str, Any]]:
    return [
        {"name": "Character Growth Arc", "description": "Protagonist's internal transformation", "theme": themes[0] if themes else "identity"},
        {"name": "Relationship Dynamics", "description": "Evolving relationships between key characters", "theme": themes[1] if len(themes) > 1 else "loyalty"},
        {"name": "External Conflict", "description": "Antagonist's opposing force", "theme": themes[2] if len(themes) > 2 else "power"}
    ]


def _generate_scene_breakdown(episode_outline: str, characters: List[Dict], locations: List[Dict]) -> List[Dict[str, Any]]:
    """Generate scene breakdown for an episode. Replace with LLM call in production."""
    num_scenes = 5  # Typical episode has 5-8 scenes
    scenes = []

    for i in range(1, num_scenes + 1):
        location = locations[i % len(locations)] if locations else None
        scene_chars = characters[:min(3, len(characters))]  # Max 3 chars per scene

        scenes.append({
            "scene_number": i,
            "title": f"Scene {i}",
            "description": f"Scene {i} of episode: {episode_outline[:200]}...",
            "location_id": location["id"] if location else None,
            "location_name": location["name"] if location else "Unknown Location",
            "characters": [
                {
                    "character_id": c["id"],
                    "character_name": c["name"],
                    "actions": f"{c['name']} performs key action in scene",
                    "emotional_state": "determined" if i <= 2 else ("conflicted" if i <= 4 else "resolved"),
                    "position": "center" if i == 1 else "various"
                }
                for c in scene_chars
            ],
            "shot_list": [
                {"shot": 1, "type": "establishing", "description": f"Wide shot of {location['name'] if location else 'Unknown Location'}"},
                {"shot": 2, "type": "medium", "description": "Characters enter frame"},
                {"shot": 3, "type": "close_up", "description": "Key emotional moment"},
                {"shot": 4, "type": "reverse", "description": "Reaction shot"},
                {"shot": 5, "type": "wide", "description": "Scene conclusion"}
            ],
            "camera_directions": "Start wide, push in to medium, close-ups for emotional beats, pull back for resolution"
        })

    return scenes


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