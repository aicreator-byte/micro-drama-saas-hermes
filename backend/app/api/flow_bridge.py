from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Episode, Scene, GoogleAccount, FlowTask
from app.schemas import FlowTaskCreate, FlowTaskUpdate, FlowTaskResponse, PaginationParams, PaginatedResponse

router = APIRouter(prefix="/flow", tags=["flow-bridge"])


@router.post("/{project_id}/tasks", response_model=FlowTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_flow_task(
    project_id: UUID,
    task_data: FlowTaskCreate,
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
    if task_data.episode_id:
        result = await db.execute(
            select(Episode).where(and_(Episode.id == task_data.episode_id, Episode.project_id == project_id))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Episode not found")

    # Verify scene if provided
    if task_data.scene_id:
        result = await db.execute(
            select(Scene).where(and_(Scene.id == task_data.scene_id, Scene.episode.has(Episode.project_id == project_id)))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Scene not found")

    # Verify Google account if provided
    if task_data.google_account_id:
        result = await db.execute(
            select(GoogleAccount).where(and_(
                GoogleAccount.id == task_data.google_account_id,
                GoogleAccount.user_id == current_user.id
            ))
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Google account not found")

    task = FlowTask(
        project_id=project_id,
        **task_data.model_dump()
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/{project_id}/tasks", response_model=PaginatedResponse)
async def list_flow_tasks(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    task_type: Optional[str] = Query(None),
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
    query = select(FlowTask).where(FlowTask.project_id == project_id)
    count_query = select(func.count(FlowTask.id)).where(FlowTask.project_id == project_id)

    if status_filter:
        query = query.where(FlowTask.status == status_filter)
        count_query = count_query.where(FlowTask.status == status_filter)
    if task_type:
        query = query.where(FlowTask.task_type == task_type)
        count_query = count_query.where(FlowTask.task_type == task_type)
    if episode_id:
        query = query.where(FlowTask.episode_id == episode_id)
        count_query = count_query.where(FlowTask.episode_id == episode_id)
    if scene_id:
        query = query.where(FlowTask.scene_id == scene_id)
        count_query = count_query.where(FlowTask.scene_id == scene_id)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        query.order_by(FlowTask.created_at.desc())
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    tasks = result.scalars().all()

    # Convert to response schemas
    task_responses = [FlowTaskResponse.model_validate(t) for t in tasks]

    return PaginatedResponse(
        items=task_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/tasks/{task_id}", response_model=FlowTaskResponse)
async def get_flow_task(
    project_id: UUID,
    task_id: UUID,
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
        select(FlowTask)
        .options(selectinload(FlowTask.google_account))
        .where(and_(FlowTask.id == task_id, FlowTask.project_id == project_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Flow task not found")
    return task


@router.patch("/{project_id}/tasks/{task_id}", response_model=FlowTaskResponse)
async def update_flow_task(
    project_id: UUID,
    task_id: UUID,
    task_data: FlowTaskUpdate,
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
        select(FlowTask).where(and_(FlowTask.id == task_id, FlowTask.project_id == project_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Flow task not found")

    update_data = task_data.model_dump(exclude_unset=True)

    # If status changed to completed, set completed_at
    if "status" in update_data and update_data["status"] == "completed" and task.completed_at is None:
        task.completed_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_task(
    project_id: UUID,
    task_id: UUID,
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
        select(FlowTask).where(and_(FlowTask.id == task_id, FlowTask.project_id == project_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Flow task not found")

    await db.delete(task)
    await db.commit()


@router.post("/{project_id}/export-prompts")
async def export_prompts_for_flow(
    project_id: UUID,
    episode_id: Optional[UUID] = None,
    scene_ids: Optional[List[UUID]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Export all prompts and references for Google Flow.
    Returns a structured package ready for manual use in Google Flow.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query for prompts
    from app.models import Prompt, PromptType
    query = select(Prompt).where(Prompt.project_id == project_id)

    if episode_id:
        query = query.where(Prompt.episode_id == episode_id)
    if scene_ids:
        query = query.where(Prompt.scene_id.in_(scene_ids))

    result = await db.execute(query)
    prompts = result.scalars().all()

    # Get referenced assets
    from app.models import Asset
    asset_query = select(Asset).where(Asset.project_id == project_id)
    if episode_id:
        asset_query = asset_query.where(Asset.episode_id == episode_id)
    if scene_ids:
        asset_query = asset_query.where(Asset.scene_id.in_(scene_ids))
    result = await db.execute(asset_query)
    assets = result.scalars().all()

    # Organize by type
    export_data = {
        "project_id": str(project_id),
        "episode_id": str(episode_id) if episode_id else None,
        "prompts_by_type": {},
        "assets": [
            {
                "id": str(a.id),
                "type": a.asset_type.value,
                "file_path": a.file_path,
                "file_name": a.file_name,
                "metadata": a.metadata
            }
            for a in assets
        ],
        "reference_assets": []
    }

    for prompt in prompts:
        ptype = prompt.prompt_type.value
        if ptype not in export_data["prompts_by_type"]:
            export_data["prompts_by_type"][ptype] = []
        export_data["prompts_by_type"][ptype].append({
            "id": str(prompt.id),
            "title": prompt.title,
            "prompt_text": prompt.prompt_text,
            "negative_prompt": prompt.negative_prompt,
            "parameters": prompt.parameters,
            "scene_id": str(prompt.scene_id) if prompt.scene_id else None,
            "character_id": str(prompt.character_id) if prompt.character_id else None,
            "location_id": str(prompt.location_id) if prompt.location_id else None,
        })

    return export_data


@router.post("/{project_id}/import-results")
async def import_flow_results(
    project_id: UUID,
    task_id: UUID,
    output_files: List[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Import generated video files from Google Flow into the project.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify task
    result = await db.execute(
        select(FlowTask).where(and_(FlowTask.id == task_id, FlowTask.project_id == project_id))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Flow task not found")

    # Update task with output files
    task.output_files = output_files
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()

    # Create asset records for each output file
    from app.models import Asset, AssetType
    import os

    for file_path in output_files:
        file_name = os.path.basename(file_path)
        # Determine asset type from extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext in ['.mp4', '.mov', '.avi', '.webm']:
            asset_type = AssetType.VIDEO
        elif ext in ['.png', '.jpg', '.jpeg', '.webp']:
            asset_type = AssetType.IMAGE
        elif ext in ['.wav', '.mp3', '.ogg']:
            asset_type = AssetType.AUDIO
        elif ext in ['.srt', '.vtt']:
            asset_type = AssetType.SUBTITLE
        else:
            asset_type = AssetType.DOCUMENT

        asset = Asset(
            project_id=project_id,
            episode_id=task.episode_id,
            scene_id=task.scene_id,
            asset_type=asset_type,
            file_path=file_path,
            file_name=file_name,
            metadata={"flow_task_id": str(task_id)}
        )
        db.add(asset)

    await db.commit()
    return {"message": f"Imported {len(output_files)} files", "task_id": str(task_id)}