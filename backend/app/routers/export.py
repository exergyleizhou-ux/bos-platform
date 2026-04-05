"""
BOS Pipeline v9.0 �� Export Router

Exports batch and calculation data in multiple formats:
  - CSV
  - JSON
  - Excel (XLSX)
  - Parquet (feature-flagged)

Supports:
  - Filtered exports (by date, species, status)
  - Column selection
  - Streaming for large datasets
"""

import csv
import io
import json
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.deps import require_minimum_role, set_tenant_context
from app.models import User, Batch, Calculation

router = APIRouter()
settings = get_settings()


@router.get("/batches/csv")
async def export_batches_csv(
    species: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    columns: Optional[str] = Query(
        None,
        description="Comma-separated column names to include",
    ),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export batches as CSV."""
    batches = await _fetch_batches(db, current_user.tenant_id, species, status_filter, date_from, date_to)

    if not batches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No batches found matching criteria")

    # Determine columns
    default_columns = [
        "id", "batch_id", "species", "status", "dm_in", "dm_out", "score",
        "temperature", "moisture", "n_in", "n_larvae", "n_frass",
        "operator", "notes", "batch_date", "created_at",
    ]
    if columns:
        selected_cols = [c.strip() for c in columns.split(",")]
    else:
        selected_cols = default_columns

    # Generate CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=selected_cols, extrasaction="ignore")
    writer.writeheader()

    for b in batches:
        row = {}
        for col in selected_cols:
            val = getattr(b, col, None)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            row[col] = val
        writer.writerow(row)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=batches_export_{date.today().isoformat()}.csv",
        },
    )


@router.get("/batches/json")
async def export_batches_json(
    species: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export batches as JSON."""
    batches = await _fetch_batches(db, current_user.tenant_id, species, status_filter, date_from, date_to)

    data = []
    for b in batches:
        row = {
            "id": b.id,
            "batch_id": b.batch_id,
            "species": b.species,
            "status": b.status,
            "dm_in": b.dm_in,
            "dm_out": b.dm_out,
            "score": b.score,
            "temperature": b.temperature,
            "moisture": b.moisture,
            "n_in": b.n_in,
            "n_larvae": b.n_larvae,
            "n_frass": b.n_frass,
            "operator": b.operator,
            "notes": b.notes,
            "batch_date": b.batch_date.isoformat() if b.batch_date else None,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        data.append(row)

    json_str = json.dumps({"batches": data, "count": len(data)}, indent=2, default=str)

    return StreamingResponse(
        iter([json_str]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=batches_export_{date.today().isoformat()}.json",
        },
    )


@router.get("/batches/xlsx")
async def export_batches_xlsx(
    species: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export batches as Excel (XLSX)."""
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="openpyxl is not installed. Use CSV or JSON export.",
        )

    batches = await _fetch_batches(db, current_user.tenant_id, species, status_filter, date_from, date_to)

    if not batches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No batches found")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Batches"

    headers = [
        "ID", "Batch ID", "Species", "Status", "DM In (kg)", "DM Out (kg)",
        "SER Score", "Temperature (��C)", "Moisture (%)", "Operator", "Batch Date",
    ]
    ws.append(headers)

    for b in batches:
        ws.append([
            b.id, b.batch_id, b.species, b.status, b.dm_in, b.dm_out,
            b.score, b.temperature, b.moisture, b.operator,
            b.batch_date.isoformat() if b.batch_date else None,
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=batches_export_{date.today().isoformat()}.xlsx",
        },
    )


@router.get("/batches/parquet")
async def export_batches_parquet(
    species: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export batches as Parquet (feature-flagged)."""
    if not settings.FF_ENABLE_EXPORT_PARQUET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Parquet export is not enabled. Enable FF_ENABLE_EXPORT_PARQUET.",
        )

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="pyarrow is not installed.",
        )

    batches = await _fetch_batches(db, current_user.tenant_id, species, status_filter, date_from, date_to)

    if not batches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No batches found")

    table = pa.table({
        "id": [b.id for b in batches],
        "batch_id": [b.batch_id for b in batches],
        "species": [b.species for b in batches],
        "status": [b.status for b in batches],
        "dm_in": [float(b.dm_in) if b.dm_in else 0.0 for b in batches],
        "dm_out": [float(b.dm_out) if b.dm_out else 0.0 for b in batches],
        "score": [float(b.score) if b.score else 0.0 for b in batches],
        "temperature": [float(b.temperature) if b.temperature else 0.0 for b in batches],
        "moisture": [float(b.moisture) if b.moisture else 0.0 for b in batches],
    })

    output = io.BytesIO()
    pq.write_table(table, output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=batches_export_{date.today().isoformat()}.parquet",
        },
    )


@router.get("/calculations/csv")
async def export_calculations_csv(
    calc_type: Optional[str] = None,
    batch_id: Optional[int] = None,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Export calculations as CSV."""
    query = select(Calculation).where(Calculation.tenant_id == current_user.tenant_id)
    if calc_type:
        query = query.where(Calculation.calc_type == calc_type)
    if batch_id:
        query = query.where(Calculation.batch_id == batch_id)
    query = query.order_by(Calculation.created_at.desc()).limit(10000)

    result = await db.execute(query)
    calcs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "batch_id", "calc_type", "status", "ser_value", "passed", "duration_ms", "created_at"])

    for c in calcs:
        writer.writerow([
            c.id, c.batch_id, c.calc_type, c.status, c.ser_value,
            c.passed, c.duration_ms,
            c.created_at.isoformat() if c.created_at else None,
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=calculations_export.csv"},
    )


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Helper
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


async def _fetch_batches(
    db: AsyncSession,
    tenant_id: int,
    species: Optional[str],
    status_filter: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    limit: int = 50000,
):
    """Fetch filtered batches for export."""
    query = select(Batch).where(Batch.tenant_id == tenant_id)

    if species:
        query = query.where(Batch.species == species)
    if status_filter:
        query = query.where(Batch.status == status_filter)
    if date_from:
        query = query.where(Batch.batch_date >= date_from)
    if date_to:
        query = query.where(Batch.batch_date <= date_to)

    query = query.order_by(Batch.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
