"""
BOS Pipeline v9.0 dashboard router.

Aggregated endpoints for frontend dashboard widgets.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import set_tenant_context
from app.models import Batch, Calculation, User

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get dashboard summary statistics."""
    tenant_id = current_user.tenant_id

    total_batches = (await db.execute(select(func.count()).where(Batch.tenant_id == tenant_id))).scalar() or 0
    active_batches = (
        await db.execute(select(func.count()).where(Batch.tenant_id == tenant_id, Batch.status == "active"))
    ).scalar() or 0
    completed_batches = (
        await db.execute(select(func.count()).where(Batch.tenant_id == tenant_id, Batch.status == "completed"))
    ).scalar() or 0
    avg_ser = (
        await db.execute(select(func.avg(Batch.score)).where(Batch.tenant_id == tenant_id, Batch.score.isnot(None)))
    ).scalar()
    total_calcs = (await db.execute(select(func.count()).where(Calculation.tenant_id == tenant_id))).scalar() or 0
    passed_calcs = (
        await db.execute(select(func.count()).where(Calculation.tenant_id == tenant_id, Calculation.passed.is_(True)))
    ).scalar() or 0

    return {
        "total_batches": total_batches,
        "active_batches": active_batches,
        "completed_batches": completed_batches,
        "total_calculations": total_calcs,
        "avg_ser": round(float(avg_ser), 4) if avg_ser else None,
        "avg_pass_rate": round(passed_calcs / max(total_calcs, 1) * 100, 1),
        "total_twins": 0,
        "batches_this_week": 0,
        "ser_improvement_pct": None,
        "batches": {
            "total": total_batches,
            "active": active_batches,
            "completed": completed_batches,
        },
        "ser": {
            "average": round(float(avg_ser), 4) if avg_ser else None,
        },
        "calculations": {
            "total": total_calcs,
            "passed": passed_calcs,
            "pass_rate": round(passed_calcs / max(total_calcs, 1) * 100, 1),
        },
    }


@router.get("/recent-batches")
async def recent_batches(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent batches for the dashboard feed."""
    result = await db.execute(
        select(Batch).where(Batch.tenant_id == current_user.tenant_id).order_by(Batch.created_at.desc()).limit(limit)
    )
    batches = result.scalars().all()

    return {
        "batches": [
            {
                "id": b.id,
                "batch_id": b.batch_id,
                "species": b.species,
                "status": b.status,
                "score": b.score,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in batches
        ],
    }


@router.get("/ser-trend")
async def ser_trend(
    days: int = Query(30, ge=7, le=365),
    period: int | None = Query(None, ge=7, le=365),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get SER trend over time for charting."""
    if period is not None:
        days = period
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Batch.batch_date, Batch.score)
        .where(
            Batch.tenant_id == current_user.tenant_id,
            Batch.score.isnot(None),
            Batch.batch_date.isnot(None),
            Batch.batch_date >= since.date(),
        )
        .order_by(Batch.batch_date.asc())
    )
    rows = result.all()

    return {
        "data_points": [
            {
                "date": row[0].isoformat() if row[0] else None,
                "ser_value": float(row[1]) if row[1] else None,
                "batch_count": 1,
            }
            for row in rows
        ],
        "trend": [
            {
                "date": row[0].isoformat() if row[0] else None,
                "ser": float(row[1]) if row[1] else None,
            }
            for row in rows
        ],
        "count": len(rows),
        "period_days": days,
    }


@router.get("/grade-distribution")
async def grade_distribution(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get SER grade distribution for pie/bar chart."""
    from app.engine.ser_engine import grade_ser_result

    result = await db.execute(
        select(Batch.score).where(Batch.tenant_id == current_user.tenant_id, Batch.score.isnot(None))
    )
    scores = [float(row[0]) for row in result.all()]

    distribution = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for score in scores:
        grade = grade_ser_result(score)
        distribution[grade] = distribution.get(grade, 0) + 1

    return {"distribution": distribution, "total": len(scores)}


@router.get("/species-distribution")
async def species_distribution(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get species distribution for the dashboard."""
    result = await db.execute(
        select(Batch.species, func.count())
        .where(Batch.tenant_id == current_user.tenant_id)
        .group_by(Batch.species)
        .order_by(func.count().desc())
    )
    rows = result.all()
    distribution_items = [
        {
            "species": row[0],
            "count": row[1],
            "percentage": 0.0,
        }
        for row in rows
        if row[0]
    ]
    total = sum(item["count"] for item in distribution_items)
    if total > 0:
        for item in distribution_items:
            item["percentage"] = (item["count"] / total) * 100

    return {
        "distribution": distribution_items,
        "total": total,
    }


@router.get("/recent-activity")
async def recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent activity for the dashboard."""
    result = await db.execute(
        select(Batch)
        .where(Batch.tenant_id == current_user.tenant_id)
        .order_by(Batch.created_at.desc())
        .limit(limit)
    )
    batches = result.scalars().all()

    return {
        "activities": [
            {
                "id": batch.id,
                "action": "batch_created",
                "user_name": batch.operator or "System",
                "description": f"updated batch {batch.batch_id}",
                "entity_type": "batch",
                "entity_id": batch.id,
                "timestamp": batch.created_at.isoformat() if batch.created_at else None,
            }
            for batch in batches
        ]
    }


@router.get("/bos-ledger-summary")
async def bos_ledger_summary(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Return a BOS-ledger-compatible summary payload.

    This endpoint intentionally degrades gracefully when BOS protocol tables are
    unavailable and computes a stable rollup from batch + SER calculation data.
    """
    tenant_filter = Batch.tenant_id == current_user.tenant_id

    batch_rows = (
        await db.execute(
            select(Batch.dm_in, Batch.dm_out, Batch.score).where(tenant_filter)
        )
    ).all()
    dm_in_values = [float(row[0]) for row in batch_rows if row[0] is not None]
    dm_out_values = [float(row[1]) for row in batch_rows if row[1] is not None]
    batch_scores = [float(row[2]) for row in batch_rows if row[2] is not None]

    calc_rows = (
        await db.execute(
            select(Calculation)
            .where(
                Calculation.tenant_id == current_user.tenant_id,
                Calculation.calc_type == "ser",
                Calculation.status == "completed",
            )
            .order_by(Calculation.created_at.desc())
            .limit(5000)
        )
    ).scalars().all()

    d_prime_values: list[float] = []
    g_prime_values: list[float] = []
    metering_values: list[float] = []
    closure_values: list[float] = []
    decision_counts: dict[str, int] = {}
    evidence_distribution: dict[str, int] = {}
    passed_count = 0

    for calc in calc_rows:
        if calc.passed:
            passed_count += 1

        payload = calc.result if isinstance(calc.result, dict) else {}
        d_prime = payload.get("d_prime")
        g_prime = payload.get("g_prime")
        metering = payload.get("metering_completeness")
        closure = payload.get("closure_residual")
        decision = payload.get("decision")
        evidence = payload.get("evidence_level")

        if isinstance(d_prime, (float, int)):
            d_prime_values.append(float(d_prime))
        if isinstance(g_prime, (float, int)):
            g_prime_values.append(float(g_prime))
        if isinstance(metering, (float, int)):
            metering_values.append(float(metering))
        if isinstance(closure, (float, int)):
            closure_values.append(float(closure))
        if isinstance(decision, str) and decision:
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if isinstance(evidence, str) and evidence:
            evidence_distribution[evidence] = evidence_distribution.get(evidence, 0) + 1

    total_decisions = sum(decision_counts.values())
    if total_decisions == 0:
        decision_counts = {
            "PASS": passed_count,
            "FAIL": max(len(calc_rows) - passed_count, 0),
        }

    avg_d_prime = _average(d_prime_values)
    avg_g_prime = _average(g_prime_values)
    avg_metering = _average(metering_values)
    avg_closure = _average(closure_values)
    avg_ser = _average([float(calc.ser_value) for calc in calc_rows if calc.ser_value is not None])
    if avg_ser is None:
        avg_ser = _average(batch_scores)

    return {
        "total_dm_in": round(sum(dm_in_values), 4),
        "total_dm_out": round(sum(dm_out_values), 4),
        "avg_d_prime": avg_d_prime,
        "avg_g_prime": avg_g_prime,
        "avg_ser": avg_ser,
        "avg_metering_completeness": avg_metering,
        "avg_closure_residual": avg_closure,
        "boundary_records": len(calc_rows),
        "release_pass_rate": (passed_count / len(calc_rows)) if calc_rows else 0.0,
        "decision_counts": decision_counts,
        "evidence_distribution": evidence_distribution,
        "total_audit_packets": 0,
    }


@router.get("/alerts")
async def dashboard_alerts(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent alerts for the dashboard."""
    failed_calcs = (
        await db.execute(
            select(func.count()).where(
                Calculation.tenant_id == current_user.tenant_id,
                Calculation.status == "failed",
                Calculation.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
            )
        )
    ).scalar() or 0

    low_ser = (
        await db.execute(
            select(func.count()).where(
                Batch.tenant_id == current_user.tenant_id,
                Batch.score.isnot(None),
                Batch.score < 0.15,
                Batch.status == "completed",
            )
        )
    ).scalar() or 0

    critical_risk = (
        await db.execute(
            select(func.count()).where(
                Calculation.tenant_id == current_user.tenant_id,
                Calculation.calc_type == "risk",
                Calculation.passed.is_(False),
            )
        )
    ).scalar() or 0

    alerts = []
    if failed_calcs > 0:
        alerts.append(
            {
                "level": "warning",
                "message": f"{failed_calcs} failed calculations in the last 7 days",
                "type": "calculation_failure",
            }
        )
    if low_ser > 0:
        alerts.append(
            {
                "level": "warning",
                "message": f"{low_ser} batches with SER below pass threshold (0.15)",
                "type": "low_ser",
            }
        )
    if critical_risk > 0:
        alerts.append(
            {
                "level": "critical",
                "message": f"{critical_risk} batches with critical contaminant risk",
                "type": "risk_critical",
            }
        )

    if not alerts:
        alerts.append({"level": "info", "message": "No active alerts", "type": "all_clear"})

    return {"alerts": alerts, "count": len(alerts)}


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)
