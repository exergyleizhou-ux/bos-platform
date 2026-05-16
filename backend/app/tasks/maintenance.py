"""
BOS Pipeline v9.0 — Maintenance Tasks

Periodic database cleanup, digest, and housekeeping tasks.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(name="app.tasks.maintenance.cleanup_expired_calculations")
def cleanup_expired_calculations() -> Dict[str, Any]:
    """
    Daily task: archive or remove old calculation results.

    Keeps last 90 days of detailed results; summarizes older ones.
    """
    from sqlalchemy import create_engine, text, update
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.models import Calculation

    logger.info("Starting calculation cleanup...")
    start = time.perf_counter()

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    try:
        with Session(engine) as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)

            # Remove detailed result JSON for old calculations (keep summary)
            result = session.execute(
                update(Calculation)
                .where(
                    Calculation.created_at < cutoff,
                    Calculation.result.isnot(None),
                )
                .values(result=None)
            )
            cleaned = result.rowcount
            session.commit()

        duration = (time.perf_counter() - start) * 1000
        logger.info(f"Cleanup complete: {cleaned} calculations trimmed in {duration:.0f}ms")

        return {
            "status": "completed",
            "calculations_trimmed": cleaned,
            "cutoff_date": cutoff.isoformat(),
            "duration_ms": round(duration, 2),
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"status": "error", "message": str(e)[:500]}


@shared_task(name="app.tasks.maintenance.refresh_materialized_views")
def refresh_materialized_views() -> Dict[str, Any]:
    """
    Periodic task: refresh materialized views for dashboard performance.
    """
    from sqlalchemy import create_engine, text
    from app.config import get_settings

    logger.info("Refreshing materialized views...")
    start = time.perf_counter()

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    views = [
        "mv_tenant_batch_stats",
        "mv_ser_daily_trend",
        "mv_species_distribution",
    ]

    results = {}
    with engine.connect() as conn:
        for view in views:
            try:
                conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY IF EXISTS {view}"))
                conn.commit()
                results[view] = "refreshed"
            except Exception as e:
                results[view] = f"skipped: {str(e)[:100]}"

    duration = (time.perf_counter() - start) * 1000
    logger.info(f"Materialized views refreshed in {duration:.0f}ms")

    return {"status": "completed", "views": results, "duration_ms": round(duration, 2)}


@shared_task(name="app.tasks.maintenance.generate_daily_digest")
def generate_daily_digest() -> Dict[str, Any]:
    """
    Daily task: generate a summary digest for each active tenant.

    Includes:
      - Batches created yesterday
      - SER statistics
      - Alerts triggered
      - Resource usage
    """
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.models import Tenant, Batch, Calculation

    logger.info("Generating daily digest...")
    start = time.perf_counter()

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    digests = []
    try:
        with Session(engine) as session:
            tenants = session.execute(select(Tenant).where(Tenant.is_active.is_(True))).scalars().all()

            for tenant in tenants:
                new_batches = (
                    session.execute(
                        select(func.count()).where(
                            Batch.tenant_id == tenant.id,
                            Batch.created_at >= yesterday,
                            Batch.created_at < today,
                        )
                    ).scalar()
                    or 0
                )

                new_calcs = (
                    session.execute(
                        select(func.count()).where(
                            Calculation.tenant_id == tenant.id,
                            Calculation.created_at >= yesterday,
                            Calculation.created_at < today,
                        )
                    ).scalar()
                    or 0
                )

                avg_ser = session.execute(
                    select(func.avg(Batch.score)).where(
                        Batch.tenant_id == tenant.id,
                        Batch.score.isnot(None),
                        Batch.created_at >= yesterday,
                        Batch.created_at < today,
                    )
                ).scalar()

                digests.append(
                    {
                        "tenant_id": tenant.id,
                        "tenant_name": tenant.name,
                        "new_batches": new_batches,
                        "new_calculations": new_calcs,
                        "avg_ser": round(float(avg_ser), 4) if avg_ser else None,
                    }
                )

        duration = (time.perf_counter() - start) * 1000
        logger.info(f"Daily digest generated for {len(digests)} tenants in {duration:.0f}ms")

        # In production, send email/notification with digest data
        return {
            "status": "completed",
            "tenants_processed": len(digests),
            "digests": digests,
            "duration_ms": round(duration, 2),
        }

    except Exception as e:
        logger.error(f"Daily digest failed: {e}")
        return {"status": "error", "message": str(e)[:500]}


@shared_task(name="app.tasks.maintenance.vacuum_tables")
def vacuum_tables() -> Dict[str, Any]:
    """Manual task: run VACUUM ANALYZE on specified tables."""
    from sqlalchemy import create_engine
    from app.config import get_settings

    logger.info("Running VACUUM ANALYZE...")

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    tables = ["batches", "calculations", "audit_logs", "digital_twins"]
    results = {}

    raw_conn = engine.raw_connection()
    try:
        raw_conn.set_session(autocommit=True)
        cursor = raw_conn.cursor()
        for table in tables:
            try:
                cursor.execute(f"VACUUM ANALYZE {table}")
                results[table] = "success"
            except Exception as e:
                results[table] = f"error: {str(e)[:100]}"
        cursor.close()
    finally:
        raw_conn.close()

    logger.info(f"VACUUM complete: {results}")
    return {"status": "completed", "results": results}
