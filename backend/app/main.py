"""
BOS Pipeline v9.0 �� FastAPI Application Entry Point

Assembles the complete application:
  - Middleware stack
  - Router registration
  - Lifespan events (startup / shutdown)
  - Exception handlers
  - OpenAPI customization
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import engine
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timing import TimingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import api_router

settings = get_settings()
logger = logging.getLogger("bos.main")


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Lifespan (startup / shutdown)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown logic."""
    # ���� Startup ����
    logger.info(f"?? Starting BOS Pipeline v{settings.APP_VERSION} ({settings.ENVIRONMENT})")

    # Initialize Redis connection
    try:
        import redis.asyncio as aioredis

        app.state.redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            max_connections=20,
        )
        await app.state.redis.ping()
        logger.info("? Redis connected")
    except Exception as e:
        logger.warning(f"?? Redis not available: {e}")
        app.state.redis = None

    logger.info("? Application started successfully")

    yield

    # ���� Shutdown ����
    logger.info("?? Shutting down BOS Pipeline...")

    # Close Redis
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.close()
        logger.info("? Redis connection closed")

    # Dispose database engine
    await engine.dispose()
    logger.info("? Database connections closed")

    logger.info("?? Shutdown complete")


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Application Factory
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "BOS Pipeline v9.0 �� Bioconversion Optimization System\n\n"
            "Full-stack platform for insect bioconversion data management, "
            "SER computation, sustainability analytics (GHG, water, energy, LCA, TEA), "
            "digital twin simulation, anomaly detection, and process optimization.\n\n"
            "**Features:** Multi-tenant, RBAC, real-time WebSocket, Bayesian A/B testing, "
            "Monte Carlo simulation, GP calibration, PID control, sensitivity analysis."
        ),
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ���� Middleware (order matters: last added = first executed) ����

    # Rate limiting (outermost �� evaluated first)
    app.add_middleware(RateLimitMiddleware)

    # Timing
    app.add_middleware(TimingMiddleware)

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # ���� Exception Handlers ����

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Custom validation error response."""
        errors = []
        for err in exc.errors():
            errors.append({
                "field": " �� ".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", "Validation error"),
                "type": err.get("type", "unknown"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": errors,
                "error_count": len(errors),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all exception handler for unexpected errors."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"[{request_id}] Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )

    # ���� Root redirect ����

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs" if settings.DEBUG else "disabled",
            "health": "/api/v1/health/live",
        }

    # ���� Register all routers ����
    app.include_router(api_router, prefix="/api/v1")

    return app


# Create the application instance
app = create_app()
