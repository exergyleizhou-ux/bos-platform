import platform
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_async_session
from app.schemas import HealthResponse, ReadinessResponse

router = APIRouter()
settings = get_settings()


@router.get("/live", response_model=HealthResponse)
async def liveness():
    """
    Liveness probe - always returns 200 if the process is running.
    Used by Kubernetes and Docker to detect crashed containers.
    """
    return HealthResponse(
        status="alive",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Readiness probe - checks all dependencies.
    Returns 200 only when the app can serve traffic.
    """
    db_status = "unknown"
    redis_status = "unknown"
    celery_status = "unknown"

    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        db_status = "connected"
    except Exception as exc:
        db_status = f"error: {str(exc)[:100]}"

    try:
        redis = getattr(request.app.state, "redis", None)
        if redis:
            await redis.ping()
            redis_status = "connected"
        else:
            redis_status = "not_configured"
    except Exception as exc:
        redis_status = f"error: {str(exc)[:100]}"

    try:
        from app.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=5.0)
        ping_result = inspect.ping()
        if ping_result:
            celery_status = f"connected ({len(ping_result)} workers)"
        else:
            stats_result = inspect.stats()
            celery_status = f"connected ({len(stats_result)} workers)" if stats_result else "no_workers"
    except Exception as exc:
        celery_status = f"not_available: {str(exc)[:100]}"

    overall = "ready"
    if "error" in db_status:
        overall = "not_ready"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        celery=celery_status,
        timestamp=datetime.now(UTC),
    )


@router.get("/info")
async def info():
    """
    Detailed application info - version, environment, and feature flags.
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
        "timestamp": datetime.now(UTC).isoformat(),
    }
