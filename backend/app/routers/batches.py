"""
BOS Pipeline v9.0 �� Batches Router

Full CRUD for bioconversion batches with:
  - Multi-tenant isolation (via RLS)
  - Pagination, filtering, sorting
  - Batch status workflow
  - Data validation before creation
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_async_session
from app.deps import (
    get_current_user,
    require_minimum_role,
    set_tenant_context,
    get_pagination,
    PaginationParams,
)
from app.models import User, Batch, Calculation, Tenant
from app.schemas import (
    BatchCreate,
    BatchDetailResponse,
    BatchResponse,
    BatchUpdate,
    PaginatedResponse,
)
from app.engine.data_validator import validate_batch_data, ValidationInput

router = APIRouter()


@router.get("", response_model=PaginatedResponse[BatchResponse])
async def list_batches(
    pagination: PaginationParams = Depends(get_pagination),
    species: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[str] = Query(None, alias="status", pattern=r"^(logged|active|completed|archived)$"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = Query(None, max_length=100),
    sort_by: str = Query("created_at", pattern=r"^(created_at|batch_id|species|status|score)$"),
    sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """List batches with filtering, sorting, and pagination."""
    query = select(Batch).where(Batch.tenant_id == current_user.tenant_id)

    if species:
        query = query.where(Batch.species == species)
    if status_filter:
        query = query.where(Batch.status == status_filter)
    if date_from:
        query = query.where(Batch.batch_date >= date_from)
    if date_to:
        query = query.where(Batch.batch_date <= date_to)
    if search:
        sf = f"%{search}%"
        query = query.where(
            (Batch.batch_id.ilike(sf))
            | (Batch.operator.ilike(sf))
            | (Batch.notes.ilike(sf))
        )

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sort
    sort_col = getattr(Batch, sort_by, Batch.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    batches = result.scalars().all()

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=[BatchResponse.model_validate(b) for b in batches],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a batch by ID with its calculations."""
    result = await db.execute(
        select(Batch)
        .options(selectinload(Batch.calculations))
        .where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    return BatchDetailResponse.model_validate(batch)


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: BatchCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new batch (operator+ role required)."""
    # Check tenant limits
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant:
        batch_count = (await db.execute(
            select(func.count()).where(Batch.tenant_id == current_user.tenant_id)
        )).scalar() or 0
        if batch_count >= tenant.max_batches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Batch limit reached ({tenant.max_batches}). Upgrade your plan.",
            )

    # Validate data
    validation = validate_batch_data(ValidationInput(
        data=body.model_dump(),
        species=body.species,
    ))
    if not validation.valid:
        error_messages = [i.message for i in validation.issues if i.severity == "error"]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": error_messages},
        )

    # Compute score (SER)
    score = None
    if body.dm_in and body.dm_out and body.dm_in > 0:
        score = round(body.dm_out / body.dm_in, 4)

    batch = Batch(
        **body.model_dump(),
        score=score,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    return BatchResponse.model_validate(batch)


@router.patch("/{batch_id}", response_model=BatchResponse)
async def update_batch(
    batch_id: int,
    body: BatchUpdate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a batch (operator+ role required)."""
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    if batch.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update an archived batch",
        )

    update_data = body.model_dump(exclude_unset=True)

    # Recalculate score if DM values change
    dm_in = update_data.get("dm_in", batch.dm_in)
    dm_out = update_data.get("dm_out", batch.dm_out)
    if dm_in and dm_out and dm_in > 0:
        update_data["score"] = round(dm_out / dm_in, 4)

    for key, value in update_data.items():
        setattr(batch, key, value)

    await db.commit()
    await db.refresh(batch)

    return BatchResponse.model_validate(batch)


@router.delete("/{batch_id}")
async def archive_batch(
    batch_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a batch (scientist+ role required)."""
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    await db.delete(batch)
    await db.commit()
    if current_user.role == "admin":
        return {"message": "Batch deleted"}
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{batch_id}/history")
async def get_batch_history(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get temporal history for a batch (point-in-time queries)."""
    result = await db.execute(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.tenant_id == current_user.tenant_id,
        )
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    return {
        "batch_id": batch.batch_id,
        "current_version": {
            "valid_from": batch.valid_from.isoformat() if batch.valid_from else None,
            "valid_to": batch.valid_to.isoformat() if batch.valid_to else None,
            "status": batch.status,
            "score": batch.score,
        },
    }
