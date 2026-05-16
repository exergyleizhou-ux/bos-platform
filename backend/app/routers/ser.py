"""
BOS Pipeline v9.0 — SER Engine Router

API endpoints for the System Efficiency Ratio computation engine.
Provides single-batch and multi-batch SER calculation with
result persistence and audit logging.
"""

import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import PaginationParams, get_pagination, require_minimum_role, set_tenant_context
from app.models import User, Batch, Calculation
from app.schemas import SERRequest, SERResponse
from app.engine.ser_engine import SERInput, compute_ser, compute_ser_batch, compute_ser_statistics

router = APIRouter()


@router.post("/compute", response_model=SERResponse)
async def compute_ser_endpoint(
    body: SERRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Compute SER for a single batch.

    Creates a Calculation record and returns the result.
    """
    start_time = time.perf_counter()

    batch: Batch | None = None
    if body.batch_id is not None:
        # Verify batch ownership if a batch_id is provided.
        result = await db.execute(
            select(Batch).where(
                Batch.id == body.batch_id,
                Batch.tenant_id == current_user.tenant_id,
            )
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Build engine input
    ser_input = SERInput(
        dm_in=body.dm_in,
        dm_out=body.dm_out,
        n_in=body.n_in,
        n_larvae=body.n_larvae,
        n_frass=body.n_frass,
        ash_in=body.ash_in or 0.0,
        ash_out=body.ash_out or 0.0,
        fat_in=body.fat_in or 0.0,
        fat_out=body.fat_out or 0.0,
    )

    # Compute
    ser_result = compute_ser(ser_input)
    duration_ms = (time.perf_counter() - start_time) * 1000

    computed_at = datetime.now(timezone.utc)
    if batch is not None:
        # Persist only when the compute is bound to a concrete batch.
        calc = Calculation(
            batch_id=batch.id,
            calc_type="ser",
            status="completed",
            inputs=body.model_dump(),
            result={
                "ser_value": ser_result.ser_value,
                "eer": ser_result.eer,
                "mcr": ser_result.mcr,
                "bcr": ser_result.bcr,
                "nitrogen_balance": ser_result.nitrogen_balance,
                "ash_balance": ser_result.ash_balance,
                "fat_balance": ser_result.fat_balance,
                "grade": ser_result.grade,
                "recommendations": ser_result.recommendations,
            },
            ser_value=ser_result.ser_value,
            passed=ser_result.passed,
            fail_codes=ser_result.fail_codes,
            duration_ms=round(duration_ms, 2),
            engine_version=ser_result.engine_version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        db.add(calc)

        # Keep batch score synced for list/dashboard surfaces.
        batch.score = ser_result.ser_value
        await db.commit()

    return SERResponse(
        ser_value=ser_result.ser_value,
        ser_system=ser_result.ser_value,
        eer=ser_result.eer,
        mcr=ser_result.mcr,
        bcr=ser_result.bcr,
        nitrogen_balance=ser_result.nitrogen_balance,
        ash_balance=ser_result.ash_balance,
        fat_balance=ser_result.fat_balance,
        passed=ser_result.passed,
        fail_codes=ser_result.fail_codes,
        grade=ser_result.grade,
        recommendations=ser_result.recommendations,
        engine_version=ser_result.engine_version,
        batch_id=body.batch_id,
        computed_at=computed_at,
        computation_time_ms=round(duration_ms, 2),
    )


@router.post("/compute-batch")
async def compute_ser_batch_endpoint(
    bodies: List[SERRequest],
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute SER for multiple batches in one request."""
    if len(bodies) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 batches per request",
        )

    results = []
    for body in bodies:
        ser_input = SERInput(
            dm_in=body.dm_in,
            dm_out=body.dm_out,
            n_in=body.n_in,
            n_larvae=body.n_larvae,
            n_frass=body.n_frass,
            ash_in=body.ash_in or 0.0,
            ash_out=body.ash_out or 0.0,
            fat_in=body.fat_in or 0.0,
            fat_out=body.fat_out or 0.0,
        )
        r = compute_ser(ser_input)
        results.append({
            "batch_id": body.batch_id,
            "ser_value": r.ser_value,
            "grade": r.grade,
            "passed": r.passed,
            "fail_codes": r.fail_codes,
        })

    return {"results": results, "count": len(results)}


@router.post("/compute-batch/{batch_id}", response_model=SERResponse)
async def compute_ser_from_batch_endpoint(
    batch_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    """Compute SER directly from a stored batch record."""
    start_time = time.perf_counter()
    result = await db.execute(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.tenant_id == current_user.tenant_id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    ser_input = SERInput(
        dm_in=batch.dm_in or 0.0,
        dm_out=batch.dm_out or 0.0,
        n_in=batch.n_in or 0.0,
        n_larvae=batch.n_larvae or 0.0,
        n_frass=batch.n_frass or 0.0,
        ash_in=batch.ash_in or 0.0,
        ash_out=batch.ash_out or 0.0,
        fat_in=batch.fat_in or 0.0,
        fat_out=batch.fat_out or 0.0,
    )

    ser_result = compute_ser(ser_input)
    duration_ms = (time.perf_counter() - start_time) * 1000
    computed_at = datetime.now(timezone.utc)

    calc = Calculation(
        batch_id=batch.id,
        calc_type="ser",
        status="completed",
        inputs={
            "batch_id": batch.id,
            "dm_in": batch.dm_in,
            "dm_out": batch.dm_out,
            "n_in": batch.n_in,
            "n_larvae": batch.n_larvae,
            "n_frass": batch.n_frass,
            "ash_in": batch.ash_in,
            "ash_out": batch.ash_out,
            "fat_in": batch.fat_in,
            "fat_out": batch.fat_out,
        },
        result={
            "ser_value": ser_result.ser_value,
            "eer": ser_result.eer,
            "mcr": ser_result.mcr,
            "bcr": ser_result.bcr,
            "nitrogen_balance": ser_result.nitrogen_balance,
            "ash_balance": ser_result.ash_balance,
            "fat_balance": ser_result.fat_balance,
            "grade": ser_result.grade,
            "recommendations": ser_result.recommendations,
        },
        ser_value=ser_result.ser_value,
        passed=ser_result.passed,
        fail_codes=ser_result.fail_codes,
        duration_ms=round(duration_ms, 2),
        engine_version=ser_result.engine_version,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(calc)
    batch.score = ser_result.ser_value
    await db.commit()

    return SERResponse(
        ser_value=ser_result.ser_value,
        ser_system=ser_result.ser_value,
        eer=ser_result.eer,
        mcr=ser_result.mcr,
        bcr=ser_result.bcr,
        nitrogen_balance=ser_result.nitrogen_balance,
        ash_balance=ser_result.ash_balance,
        fat_balance=ser_result.fat_balance,
        passed=ser_result.passed,
        fail_codes=ser_result.fail_codes,
        grade=ser_result.grade,
        recommendations=ser_result.recommendations,
        engine_version=ser_result.engine_version,
        batch_id=batch_id,
        computed_at=computed_at,
        computation_time_ms=round(duration_ms, 2),
    )


@router.get("/result/batch/{batch_id}", response_model=SERResponse)
async def get_ser_result_for_batch(
    batch_id: int,
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get the latest SER result for a specific batch."""
    batch_result = await db.execute(
        select(Batch).where(
            Batch.id == batch_id,
            Batch.tenant_id == current_user.tenant_id,
        )
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    calc_result = await db.execute(
        select(Calculation)
        .where(
            Calculation.batch_id == batch_id,
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "ser",
            Calculation.status == "completed",
        )
        .order_by(Calculation.created_at.desc(), Calculation.id.desc())
        .limit(1)
    )
    calc = calc_result.scalar_one_or_none()

    if calc is not None:
        payload = calc.result if isinstance(calc.result, dict) else {}
        return SERResponse(
            ser_value=float(payload.get("ser_value", calc.ser_value or 0.0)),
            ser_system=float(payload.get("ser_system", payload.get("ser_value", calc.ser_value or 0.0))),
            eer=float(payload.get("eer", calc.ser_value or 0.0)),
            mcr=float(payload.get("mcr", calc.ser_value or 0.0)),
            bcr=float(payload.get("bcr", calc.ser_value or 0.0)),
            nitrogen_balance=payload.get("nitrogen_balance"),
            ash_balance=payload.get("ash_balance"),
            fat_balance=payload.get("fat_balance"),
            passed=bool(calc.passed),
            fail_codes=calc.fail_codes or [],
            grade=str(payload.get("grade", "F")),
            recommendations=payload.get("recommendations", []) or [],
            engine_version=calc.engine_version or "unknown",
            batch_id=batch_id,
            computed_at=calc.created_at,
            computation_time_ms=calc.duration_ms,
        )

    # Fallback: compute from current batch values even if no persisted SER record exists yet.
    ser_input = SERInput(
        dm_in=batch.dm_in or 0.0,
        dm_out=batch.dm_out or 0.0,
        n_in=batch.n_in or 0.0,
        n_larvae=batch.n_larvae or 0.0,
        n_frass=batch.n_frass or 0.0,
        ash_in=batch.ash_in or 0.0,
        ash_out=batch.ash_out or 0.0,
        fat_in=batch.fat_in or 0.0,
        fat_out=batch.fat_out or 0.0,
    )
    ser_result = compute_ser(ser_input)
    return SERResponse(
        ser_value=ser_result.ser_value,
        ser_system=ser_result.ser_value,
        eer=ser_result.eer,
        mcr=ser_result.mcr,
        bcr=ser_result.bcr,
        nitrogen_balance=ser_result.nitrogen_balance,
        ash_balance=ser_result.ash_balance,
        fat_balance=ser_result.fat_balance,
        passed=ser_result.passed,
        fail_codes=ser_result.fail_codes,
        grade=ser_result.grade,
        recommendations=ser_result.recommendations,
        engine_version=ser_result.engine_version,
        batch_id=batch_id,
        computed_at=datetime.now(timezone.utc),
    )


@router.get("/history")
async def ser_history(
    pagination: PaginationParams = Depends(get_pagination),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get paginated SER history for the current tenant."""
    base_query = select(Calculation).where(
        Calculation.tenant_id == current_user.tenant_id,
        Calculation.calc_type == "ser",
        Calculation.status == "completed",
    )
    total = (
        await db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
    ).scalar() or 0

    result = await db.execute(
        base_query
        .order_by(Calculation.created_at.desc(), Calculation.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    calcs = result.scalars().all()

    items = []
    for calc in calcs:
        payload = calc.result if isinstance(calc.result, dict) else {}
        items.append(
            {
                "id": calc.id,
                "batch_id": calc.batch_id,
                "ser_value": float(payload.get("ser_value", calc.ser_value or 0.0)),
                "eer": float(payload.get("eer", calc.ser_value or 0.0)),
                "mcr": float(payload.get("mcr", calc.ser_value or 0.0)),
                "bcr": float(payload.get("bcr", calc.ser_value or 0.0)),
                "grade": str(payload.get("grade", "F")),
                "passed": bool(calc.passed),
                "computed_at": calc.created_at,
            }
        )

    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "total_pages": total_pages,
    }


@router.get("/statistics")
async def ser_statistics(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get aggregate SER statistics for the current tenant."""
    result = await db.execute(
        select(Calculation).where(
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "ser",
            Calculation.status == "completed",
        )
    )
    calcs = result.scalars().all()

    if not calcs:
        return {"message": "No SER calculations found", "stats": None}

    # Reconstruct SERResult-like objects for statistics
    from app.engine.ser_engine import SERResult, grade_ser_result

    ser_results = []
    for c in calcs:
        ser_val = c.ser_value or 0.0
        ser_results.append(SERResult(
            ser_value=ser_val,
            passed=c.passed or False,
            grade=grade_ser_result(ser_val),
        ))

    stats = compute_ser_statistics(ser_results)
    return {"stats": stats}
