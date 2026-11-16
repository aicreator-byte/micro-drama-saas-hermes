from datetime import datetime
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.db.session import get_db
from app.core.security import get_current_active_user
from app.models import User, Project, Location
from app.schemas import LocationCreate, LocationUpdate, LocationResponse, PaginationParams, PaginatedResponse

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/{project_id}", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    project_id: UUID,
    location_data: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    location = Location(project_id=project_id, **location_data.model_dump())
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return location


@router.get("/{project_id}", response_model=PaginatedResponse)
async def list_locations(
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
        select(func.count(Location.id)).where(Location.project_id == project_id)
    )
    total = count_result.scalar() or 0

    # Get paginated results
    result = await db.execute(
        select(Location)
        .where(Location.project_id == project_id)
        .order_by(Location.order_index, Location.created_at)
        .offset((pagination.page - 1) * pagination.page_size)
        .limit(pagination.page_size)
    )
    locations = result.scalars().all()

    # Convert to response schemas
    location_responses = [LocationResponse.model_validate(l) for l in locations]

    return PaginatedResponse(
        items=location_responses,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.get("/{project_id}/{location_id}", response_model=LocationResponse)
async def get_location(
    project_id: UUID,
    location_id: UUID,
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
        select(Location).where(and_(Location.id == location_id, Location.project_id == project_id))
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


@router.patch("/{project_id}/{location_id}", response_model=LocationResponse)
async def update_location(
    project_id: UUID,
    location_id: UUID,
    location_data: LocationUpdate,
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
        select(Location).where(and_(Location.id == location_id, Location.project_id == project_id))
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    update_data = location_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    location.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(location)
    return location


@router.delete("/{project_id}/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    project_id: UUID,
    location_id: UUID,
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
        select(Location).where(and_(Location.id == location_id, Location.project_id == project_id))
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    await db.delete(location)
    await db.commit()


@router.post("/{project_id}/reorder", response_model=List[LocationResponse])
async def reorder_locations(
    project_id: UUID,
    location_ids: List[UUID],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify project ownership
    result = await db.execute(
        select(Project).where(and_(Project.id == project_id, Project.owner_id == current_user.id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify all locations belong to project
    result = await db.execute(
        select(Location).where(and_(Location.project_id == project_id, Location.id.in_(location_ids)))
    )
    locations = result.scalars().all()
    if len(locations) != len(location_ids):
        raise HTTPException(status_code=400, detail="Some locations not found or don't belong to project")

    # Update order
    for index, loc_id in enumerate(location_ids):
        loc = next(l for l in locations if l.id == loc_id)
        loc.order_index = index

    await db.commit()

    # Return updated list
    result = await db.execute(
        select(Location)
        .where(Location.project_id == project_id)
        .order_by(Location.order_index)
    )
    return result.scalars().all()