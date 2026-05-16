"""
BOS Pipeline v9.0 — Export Tasks

Async data export generation for large datasets.
"""

import csv
import io
import json
import time
from typing import Any, Dict, List, Optional

from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(
    name="app.tasks.export.generate_batch_export",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
    time_limit=720,
)
def generate_batch_export(
    self,
    tenant_id: int,
    user_id: int,
    format: str = "csv",
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a large batch export file asynchronously."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.config import get_settings
    from app.models import Batch

    logger.info(f"Generating batch export: tenant={tenant_id}, format={format}")
    start = time.perf_counter()

    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)

    try:
        with Session(engine) as session:
            query = select(Batch).where(Batch.tenant_id == tenant_id)

            if filters:
                if filters.get("species"):
                    query = query.where(Batch.species == filters["species"])
                if filters.get("status"):
                    query = query.where(Batch.status == filters["status"])

            query = query.order_by(Batch.created_at.desc()).limit(100_000)
            result = session.execute(query)
            batches = result.scalars().all()

        if format == "csv":
            output = _batches_to_csv(batches)
        elif format == "json":
            output = _batches_to_json(batches)
        else:
            output = _batches_to_csv(batches)

        duration = (time.perf_counter() - start) * 1000

        # In production, upload to S3/MinIO and return URL
        logger.info(f"Export complete: {len(batches)} batches, {duration:.0f}ms")

        return {
            "status": "completed",
            "format": format,
            "row_count": len(batches),
            "size_bytes": len(output.encode("utf-8") if isinstance(output, str) else output),
            "computation_time_ms": round(duration, 2),
            # "download_url": "https://storage.example.com/exports/..."
        }

    except Exception as exc:
        logger.error(f"Export failed: {exc}")
        self.retry(exc=exc, countdown=60)


def _batches_to_csv(batches) -> str:
    """Convert batches to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "batch_id",
            "species",
            "status",
            "dm_in",
            "dm_out",
            "score",
            "temperature",
            "moisture",
            "operator",
            "batch_date",
        ]
    )
    for b in batches:
        writer.writerow(
            [
                b.id,
                b.batch_id,
                b.species,
                b.status,
                b.dm_in,
                b.dm_out,
                b.score,
                b.temperature,
                b.moisture,
                b.operator,
                b.batch_date.isoformat() if b.batch_date else None,
            ]
        )
    return output.getvalue()


def _batches_to_json(batches) -> str:
    """Convert batches to JSON string."""
    data = [
        {
            "id": b.id,
            "batch_id": b.batch_id,
            "species": b.species,
            "status": b.status,
            "dm_in": b.dm_in,
            "dm_out": b.dm_out,
            "score": b.score,
        }
        for b in batches
    ]
    return json.dumps({"batches": data, "count": len(data)}, default=str)


@shared_task(
    name="app.tasks.export.generate_report",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
)
def generate_report(
    self,
    tenant_id: int,
    user_id: int,
    report_type: str = "monthly",
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate a periodic report (monthly/quarterly)."""
    logger.info(f"Generating {report_type} report: tenant={tenant_id}")

    # Report generation logic would aggregate data, compute statistics,
    # generate charts, and compile into a PDF/HTML document.

    return {
        "status": "completed",
        "report_type": report_type,
        "tenant_id": tenant_id,
        "message": "Report generated (storage integration pending)",
    }
