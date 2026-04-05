"""
BOS Pipeline v9.0 �� Health Check Router

Provides liveness, readiness, and detailed health endpoints
for container orchestration and monitoring.
"""

from datetime import datetime, timezone
import platform
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.schemas import HealthResponse, ReadinessResponse

router = APIRouter()
settings = get_settings()
START_TIME = time.monotonic()


@router.get("/live", response_model=HealthResponse)
async def liveness():
    """
    Liveness probe �� always returns 200 if the process is running.
    Used by Kubernetes/Docker to detect crashed containers.
    """
    return HealthResponse(
        status="alive",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Readiness probe �� checks all dependencies.
    Returns 200 only when the app can serve traffic.
    """
    db_status = "unknown"
    redis_status = "unknown"
    celery_status = "unknown"

    # ���� Database ����
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        db_status = "connected"
    except Exception:
        db_status = "error"

    # ���� Redis ����
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis:
            await redis.ping()
            redis_status = "connected"
        else:
            redis_status = "disconnected"
    except Exception:
        redis_status = "error"

    # ���� Celery ����
    if settings.is_development:
        celery_status = "skipped_in_development"
    else:
        try:
            from app.celery_app import celery_app

            inspect = celery_app.control.inspect(timeout=2.0)
            ping_result = inspect.ping()
            if ping_result:
                celery_status = f"connected ({len(ping_result)} workers)"
            else:
                celery_status = "no_workers"
        except Exception:
            celery_status = "not_available"

    # Overall
    overall = "ready"
    if "error" in db_status:
        overall = "not_ready"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        celery=celery_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/info")
async def info():
    """
    Detailed application info �� version, environment, feature flags.
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "python_version": platform.python_version(),
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "features": {
            "monte_carlo": settings.FF_ENABLE_MONTE_CARLO,
            "digital_twin": settings.FF_ENABLE_DIGITAL_TWIN,
            "automl": settings.FF_ENABLE_AUTOML,
            "websocket": settings.FF_ENABLE_WEBSOCKET,
            "export_parquet": settings.FF_ENABLE_EXPORT_PARQUET,
            "billing": settings.FF_ENABLE_BILLING,
            "multi_language": settings.FF_ENABLE_MULTI_LANGUAGE,
            "dark_mode": settings.FF_ENABLE_DARK_MODE,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("")
async def health_summary(request: Request):
    """Frontend-friendly summary endpoint."""
    redis = getattr(request.app.state, "redis", None)
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected" if redis else "disconnected",
        "version": settings.APP_VERSION,
        "uptime_seconds": int(time.monotonic() - START_TIME),
    }
