"""
BOS Pipeline v9.0 �� Dashboard Router

Aggregated endpoints for frontend dashboard widgets:
  - Summary statistics
  - Recent batches
  - SER trend
  - Grade distribution
  - Species distribution
  - Alerts and warnings
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import set_tenant_context
from app.models import User, Batch, Calculation

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get dashboard summary statistics."""
    tid = current_user.tenant_id

    total_batches = (await db.execute(
        select(func.count()).where(Batch.tenant_id == tid)
    )).scalar() or 0

    active_batches = (await db.execute(
        select(func.count()).where(Batch.tenant_id == tid, Batch.status == "active")
    )).scalar() or 0

    completed_batches = (await db.execute(
        select(func.count()).where(Batch.tenant_id == tid, Batch.status == "completed")
    )).scalar() or 0

    avg_ser = (await db.execute(
        select(func.avg(Batch.score)).where(
            Batch.tenant_id == tid,
            Batch.score.isnot(None),
        )
    )).scalar()

    total_calcs = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid)
    )).scalar() or 0

    passed_calcs = (await db.execute(
        select(func.count()).where(Calculation.tenant_id == tid, Calculation.passed == True)
    )).scalar() or 0

    batches_this_week = (await db.execute(
        select(func.count()).where(
            Batch.tenant_id == tid,
            Batch.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
    )).scalar() or 0

    return {
        "total_batches": total_batches,
        "active_batches": active_batches,
        "completed_batches": completed_batches,
        "avg_ser": round(float(avg_ser), 4) if avg_ser else None,
        "avg_pass_rate": round(passed_calcs / max(total_calcs, 1), 4),
        "total_calculations": total_calcs,
        "total_twins": 0,
        "batches_this_week": batches_this_week,
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
            "pass_rate": round(passed_calcs / max(total_calcs, 1), 4),
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
        select(Batch)
        .where(Batch.tenant_id == current_user.tenant_id)
        .order_by(Batch.created_at.desc())
        .limit(limit)
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
    period: Optional[int] = Query(None, ge=7, le=365),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get SER trend over time for charting."""
    days = period or days
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
    from app.engine.ser_engine import grade_ser

    result = await db.execute(
        select(Batch.score)
        .where(
            Batch.tenant_id == current_user.tenant_id,
            Batch.score.isnot(None),
        )
    )
    scores = [float(row[0]) for row in result.all()]

    distribution = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for score in scores:
        grade = grade_ser(score)
        distribution[grade] = distribution.get(grade, 0) + 1

    return {
        "distribution": distribution,
        "total": len(scores),
    }


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

    return {
        "distribution": [
            {
                "species": row[0],
                "count": row[1],
                "percentage": round((row[1] / max(sum(item[1] for item in rows), 1)) * 100, 2),
            }
            for row in rows
            if row[0]
        ],
        "total": sum(row[1] for row in rows),
    }


@router.get("/recent-activity")
async def recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Return a lightweight recent activity feed for the dashboard."""
    batch_result = await db.execute(
        select(Batch)
        .where(Batch.tenant_id == current_user.tenant_id)
        .order_by(Batch.created_at.desc())
        .limit(limit)
    )
    calc_result = await db.execute(
        select(Calculation)
        .where(Calculation.tenant_id == current_user.tenant_id)
        .order_by(Calculation.created_at.desc())
        .limit(limit)
    )

    activities = []
    for batch in batch_result.scalars().all():
        activities.append({
            "id": batch.id,
            "action": "batch_created",
            "user_name": batch.operator or current_user.username,
            "description": f"created batch {batch.batch_id}",
            "entity_type": "batch",
            "entity_id": batch.id,
            "timestamp": batch.created_at.isoformat() if batch.created_at else None,
        })
    for calc in calc_result.scalars().all():
        activities.append({
            "id": 1_000_000 + calc.id,
            "action": "ser_computed" if calc.calc_type == "ser" else "simulation_run",
            "user_name": current_user.username,
            "description": f"completed {calc.calc_type} calculation",
            "entity_type": "calculation",
            "entity_id": calc.id,
            "timestamp": calc.created_at.isoformat() if calc.created_at else None,
        })

    activities.sort(key=lambda item: item["timestamp"] or "", reverse=True)
    return {"activities": activities[:limit]}


@router.get("/alerts")
async def dashboard_alerts(
    current_user: User = Depends(set_tenant_context),
    db: AsyncSession = Depends(get_async_session),
):
    """Get recent alerts for the dashboard."""
    # Failed calculations
    failed_calcs = (await db.execute(
        select(func.count()).where(
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.status == "failed",
            Calculation.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
    )).scalar() or 0

    # Low SER batches (below 0.15)
    low_ser = (await db.execute(
        select(func.count()).where(
            Batch.tenant_id == current_user.tenant_id,
            Batch.score.isnot(None),
            Batch.score < 0.15,
            Batch.status == "completed",
        )
    )).scalar() or 0

    # Critical risk assessments
    critical_risk = (await db.execute(
        select(func.count()).where(
            Calculation.tenant_id == current_user.tenant_id,
            Calculation.calc_type == "risk",
            Calculation.passed == False,
        )
    )).scalar() or 0

    alerts = []
    if failed_calcs > 0:
        alerts.append({
            "level": "warning",
            "message": f"{failed_calcs} failed calculations in the last 7 days",
            "type": "calculation_failure",
        })
    if low_ser > 0:
        alerts.append({
            "level": "warning",
            "message": f"{low_ser} batches with SER below pass threshold (0.15)",
            "type": "low_ser",
        })
    if critical_risk > 0:
        alerts.append({
            "level": "critical",
            "message": f"{critical_risk} batches with critical contaminant risk",
            "type": "risk_critical",
        })

    if not alerts:
        alerts.append({
            "level": "info",
            "message": "No active alerts",
            "type": "all_clear",
        })

    return {"alerts": alerts, "count": len(alerts)}

