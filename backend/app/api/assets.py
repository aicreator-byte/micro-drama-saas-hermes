from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.core.config import settings
from app.models import User, Project, Episode, Scene, Asset, AssetType
from app.schemas import AssetCreate, AssetResponse, PaginationParams, PaginatedResponse
import os
import shutil
import uuid as uuid_lib

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("/{project_id}/upload", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    project_id: UUID,
    file: UploadFile = File(...),
    asset_type: AssetType = Form(...),
    episode_id: Optional[UUID] = Form(None),
    scene_id: Optional[UUID] = Form(None),
    metadata: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify episode if provided
    if episode_id:
        result = await db.execute(
            select(Episode).where(and_(Episode.id == episode_id, Episode.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Episode not found")

    # Verify scene if provided
    if scene_id:
        result = await db.execute(
            select(Scene).where(and_(Scene.id == scene_id, Scene.episode.has(Episode.project_id == project_id)))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Scene not found")

    # Check file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes")

    # Validate file extension against asset type (allowlist)
    allowed_extensions = {
        AssetType.IMAGE: {".png", ".jpg", ".jpeg", ".webp", ".gif"},
        AssetType.VIDEO: {".mp4", ".mov", ".avi", ".webm", ".mkv"},
        AssetType.AUDIO: {".wav", ".mp3", ".ogg", ".m4a"},
        AssetType.SUBTITLE: {".srt", ".vtt"},
        AssetType.DOCUMENT: {".pdf", ".txt", ".md", ".json", ".docx"},
    }
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_extensions.get(asset_type, set()):
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{file_ext}' not allowed for asset type '{asset_type.value}'",
        )

    # Save file
    unique_filename = f"{uuid_lib.uuid4()}{file_ext}"
    project_upload_dir = settings.UPLOAD_DIR / str(project_id)
    project_upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_upload_dir / unique_filename

    with open(file_path, "wb") as f:
        f.write(content)

    # Parse metadata (invalid JSON -> 400, not 500)
    import json
    metadata_dict = None
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="metadata must be valid JSON")
        if not isinstance(metadata_dict, dict):
            raise HTTPException(status_code=400, detail="metadata must be a JSON object")

    # Create asset record
    asset = Asset(
        project_id=project_id,
        episode_id=episode_id,
        scene_id=scene_id,
        asset_type=asset_type,
        file_path=str(file_path),
        file_name=file.filename,
        file_size=len(content),
        mime_type=file.content_type,
        asset_metadata=metadata_dict
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_assets(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    asset_type: Optional[AssetType] = Query(None),
    episode_id: Optional[UUID] = Query(None),
    scene_id: Optional[UUID] = Query(None),
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
    query = select(Asset).where(Asset.project_id == project_id)
    count_query = select(func.count(Asset.id)).where(Asset.project_id == project_id)

    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
        count_query = count_query.where(Asset.asset_type == asset_type)
    if episode_id:
        query = query.where(Asset.episode_id == episode_id)
        count_query = count_query.where(Asset.episode_id == episode_id)
    if scene_id:
        query = query.where(Asset.scene_id == scene_id)
        count_query = count_query.where(Asset.scene_id == scene_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(
        query.order_by(Asset.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    assets = result.scalars().all()

    # Convert to response schemas
    asset_responses = [AssetResponse.model_validate(a) for a in assets]

    return PaginatedResponse(
        items=asset_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/{asset_id}", response_model=AssetResponse)
async def get_asset(
    project_id: UUID,
    asset_id: UUID,
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
        select(Asset).where(and_(Asset.id == asset_id, Asset.project_id == project_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{project_id}/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    project_id: UUID,
    asset_id: UUID,
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
        select(Asset).where(and_(Asset.id == asset_id, Asset.project_id == project_id))
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Delete file
    try:
        os.remove(asset.file_path)
    except OSError:
        pass  # File might not exist

    await db.delete(asset)
    await db.commit()


# Post-production: Video assembly with FFmpeg
@router.post("/{project_id}/episodes/{episode_id}/assemble")
async def assemble_episode_video(
    project_id: UUID,
    episode_id: UUID,
    scene_order: List[UUID],  # List of scene_ids in order
    output_filename: str = "episode_final.mp4",
    include_audio: bool = True,
    include_subtitles: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Assemble episode video from scene videos using FFmpeg.
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

    # Get video assets for each scene in order
    video_files = []
    for scene_id in scene_order:
        result = await db.execute(
            select(Asset).where(and_(
                Asset.scene_id == scene_id,
                Asset.asset_type == AssetType.VIDEO,
                Asset.project_id == project_id
            )).order_by(Asset.created_at.desc())
        )
        asset = result.scalar_one_or_none()
        if asset and os.path.exists(asset.file_path):
            video_files.append(asset.file_path)

    if not video_files:
        raise HTTPException(status_code=400, detail="No video files found for the specified scenes")

    # Create concat file for FFmpeg
    concat_file = settings.UPLOAD_DIR / str(project_id) / f"concat_{episode_id}.txt"
    with open(concat_file, "w") as f:
        for vf in video_files:
            f.write(f"file '{vf}'\n")

    output_path = settings.UPLOAD_DIR / str(project_id) / output_filename

    # Build FFmpeg command
    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
    ]

    if include_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.extend(["-an"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-movflags", "+faststart",
        str(output_path)
    ])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="FFmpeg timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assembly failed: {str(e)}")
    finally:
        # Clean up concat file
        try:
            os.remove(concat_file)
        except OSError:
            pass

    # Create asset record for final video
    file_size = os.path.getsize(output_path)
    final_asset = Asset(
        project_id=project_id,
        episode_id=episode_id,
        asset_type=AssetType.VIDEO,
        file_path=str(output_path),
        file_name=output_filename,
        file_size=file_size,
        mime_type="video/mp4",
        asset_metadata={"assembled_from": [str(s) for s in scene_order]}
    )
    db.add(final_asset)
    await db.commit()
    await db.refresh(final_asset)

    return {
        "message": "Episode assembled successfully",
        "asset_id": str(final_asset.id),
        "file_path": str(output_path),
        "file_size": file_size
    }


@router.post("/{project_id}/episodes/{episode_id}/add-subtitles")
async def add_subtitles_to_video(
    project_id: UUID,
    episode_id: UUID,
    video_asset_id: UUID,
    subtitle_asset_id: UUID,
    output_filename: str = "episode_with_subs.mp4",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Burn subtitles into video using FFmpeg."""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get video asset
    result = await db.execute(
        select(Asset).where(and_(Asset.id == video_asset_id, Asset.project_id == project_id, Asset.asset_type == AssetType.VIDEO))
    )
    video_asset = result.scalar_one_or_none()
    if not video_asset or not os.path.exists(video_asset.file_path):
        raise HTTPException(status_code=404, detail="Video asset not found")

    # Get subtitle asset
    result = await db.execute(
        select(Asset).where(and_(Asset.id == subtitle_asset_id, Asset.project_id == project_id, Asset.asset_type == AssetType.SUBTITLE))
    )
    subtitle_asset = result.scalar_one_or_none()
    if not subtitle_asset or not os.path.exists(subtitle_asset.file_path):
        raise HTTPException(status_code=404, detail="Subtitle asset not found")

    output_path = settings.UPLOAD_DIR / str(project_id) / output_filename

    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-i", video_asset.file_path,
        "-vf", f"subtitles={subtitle_asset.file_path}",
        "-c:a", "copy",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="FFmpeg timeout")

    # Create asset record
    file_size = os.path.getsize(output_path)
    final_asset = Asset(
        project_id=project_id,
        episode_id=episode_id,
        asset_type=AssetType.VIDEO,
        file_path=str(output_path),
        file_name=output_filename,
        file_size=file_size,
        mime_type="video/mp4",
        asset_metadata={"source_video": str(video_asset_id), "subtitles": str(subtitle_asset_id)}
    )
    db.add(final_asset)
    await db.commit()
    await db.refresh(final_asset)

    return {
        "message": "Subtitles added successfully",
        "asset_id": str(final_asset.id),
        "file_path": str(output_path)
    }