"""
BOS Pipeline v9.0 — Batches Router

Full CRUD for bioconversion batches with:
  - Multi-tenant isolation (via RLS)
  - Pagination, filtering, sorting
  - Batch status workflow
  - Data validation before creation
"""

from datetime import date
import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
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
    MessageResponse,
    PaginatedResponse,
)
from app.engine.data_validator import validate_batch_data, ValidationInput
from app.services.bos import build_batch_bos_overview

router = APIRouter()


@router.get("", response_model=PaginatedResponse[BatchResponse])
async def list_batches(
    pagination: PaginationParams = Depends(get_pagination),
    species: Optional[str] = Query(None, max_length=100),
    substrate: Optional[str] = Query(None, max_length=255),
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
    if substrate:
        query = query.where(Batch.substrate == substrate)
    if status_filter:
        query = query.where(Batch.status == status_filter)
    if date_from:
        query = query.where(Batch.batch_date >= date_from)
    if date_to:
        query = query.where(Batch.batch_date <= date_to)
    if search:
        sf = f"%{search}%"
        query = query.where((Batch.batch_id.ilike(sf)) | (Batch.operator.ilike(sf)) | (Batch.notes.ilike(sf)))

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


@router.get("/stats")
async def batch_stats(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get aggregate batch stats for list/dashboard surfaces."""
    tenant_filter = Batch.tenant_id == current_user.tenant_id

    total = (await db.execute(select(func.count()).where(tenant_filter))).scalar() or 0
    avg_ser = (await db.execute(select(func.avg(Batch.score)).where(tenant_filter, Batch.score.isnot(None)))).scalar()

    status_rows = (
        await db.execute(
            select(Batch.status, func.count())
            .where(tenant_filter)
            .group_by(Batch.status)
        )
    ).all()
    by_status = {"logged": 0, "active": 0, "completed": 0, "archived": 0, "failed": 0}
    for status_label, count in status_rows:
        if status_label:
            by_status[str(status_label)] = int(count)

    species_rows = (
        await db.execute(
            select(Batch.species, func.count())
            .where(tenant_filter)
            .group_by(Batch.species)
        )
    ).all()
    by_species = {str(species): int(count) for species, count in species_rows if species}

    return {
        "total": int(total),
        "by_status": by_status,
        "by_species": by_species,
        "avg_ser": round(float(avg_ser), 4) if avg_ser is not None else None,
    }


@router.get("/export")
async def export_batches(
    format: str = Query("csv", pattern=r"^(csv|json|parquet)$"),
    species: Optional[str] = Query(None, max_length=100),
    substrate: Optional[str] = Query(None, max_length=255),
    status_filter: Optional[str] = Query(None, alias="status", pattern=r"^(logged|active|completed|archived)$"),
    search: Optional[str] = Query(None, max_length=100),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export filtered batches in CSV/JSON (Parquet feature-gated)."""
    query = select(Batch).where(Batch.tenant_id == current_user.tenant_id)
    if species:
        query = query.where(Batch.species == species)
    if substrate:
        query = query.where(Batch.substrate == substrate)
    if substrate:
        query = query.where(Batch.substrate == substrate)
    if status_filter:
        query = query.where(Batch.status == status_filter)
    if search:
        sf = f"%{search}%"
        query = query.where((Batch.batch_id.ilike(sf)) | (Batch.operator.ilike(sf)) | (Batch.notes.ilike(sf)))
    query = query.order_by(Batch.created_at.desc()).limit(50000)

    result = await db.execute(query)
    batches = result.scalars().all()

    rows = [
        {
            "id": b.id,
            "batch_id": b.batch_id,
            "species": b.species,
            "substrate": b.substrate,
            "status": b.status,
            "dm_in": b.dm_in,
            "dm_out": b.dm_out,
            "n_in": b.n_in,
            "n_larvae": b.n_larvae,
            "n_frass": b.n_frass,
            "ash_in": b.ash_in,
            "ash_out": b.ash_out,
            "fat_in": b.fat_in,
            "fat_out": b.fat_out,
            "temperature": b.temperature,
            "moisture": b.moisture,
            "feed_rate": b.feed_rate,
            "density": b.density,
            "score": b.score,
            "operator": b.operator,
            "notes": b.notes,
            "batch_date": b.batch_date.isoformat() if b.batch_date else None,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }
        for b in batches
    ]

    export_date = date.today().isoformat()
    if format == "json":
        payload = json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=batches_export_{export_date}.json"},
        )

    if format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Parquet export requires pyarrow",
            ) from exc

        table = pa.table({
            "id": [row["id"] for row in rows],
            "batch_id": [row["batch_id"] for row in rows],
            "species": [row["species"] for row in rows],
            "status": [row["status"] for row in rows],
            "dm_in": [row["dm_in"] for row in rows],
            "dm_out": [row["dm_out"] for row in rows],
            "score": [row["score"] for row in rows],
            "created_at": [row["created_at"] for row in rows],
        })
        out = io.BytesIO()
        pq.write_table(table, out)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=batches_export_{export_date}.parquet"},
        )

    fieldnames = list(rows[0].keys()) if rows else [
        "id",
        "batch_id",
        "species",
        "status",
        "dm_in",
        "dm_out",
        "score",
        "created_at",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batches_export_{export_date}.csv"},
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

    response = BatchDetailResponse.model_validate(batch)
    response.bos = await build_batch_bos_overview(
        db,
        batch=batch,
        tenant_id=current_user.tenant_id,
    )
    return response


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
        batch_count = (
            await db.execute(select(func.count()).where(Batch.tenant_id == current_user.tenant_id))
        ).scalar() or 0
        if batch_count >= tenant.max_batches:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Batch limit reached ({tenant.max_batches}). Upgrade your plan.",
            )

    # Validate data
    validation = validate_batch_data(
        ValidationInput(
            data=body.model_dump(),
            species=body.species,
        )
    )
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
    result = await db.execute(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id))
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


@router.delete("/{batch_id}", response_model=MessageResponse)
async def archive_batch(
    batch_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    """Archive a batch (soft delete, scientist+ role required)."""
    result = await db.execute(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id))
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    batch.status = "archived"
    await db.commit()

    return MessageResponse(message=f"Batch '{batch.batch_id}' has been archived")


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
