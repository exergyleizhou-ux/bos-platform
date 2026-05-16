"""
BOS Pipeline v9.0 rate limiting middleware.

Per-tenant rate limiting using a Redis sliding window.
"""

import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

settings = get_settings()

PLAN_RATE_LIMITS = {
    "free": 100,
    "starter": 500,
    "pro": 2000,
    "enterprise": 10000,
}

EXCLUDED_PATHS = {
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/health/info",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant rate limiting using a Redis sliding window counter."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if not redis:
            return await call_next(request)

        tenant_id, plan = await self._extract_tenant_info(request)
        if tenant_id is None:
            client_ip = request.client.host if request.client else "unknown"
            rate_key = f"rl:ip:{client_ip}"
            limit = 60
        else:
            rate_key = f"rl:tenant:{tenant_id}"
            limit = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS["free"])

        try:
            now = int(time.time())
            window_key = f"{rate_key}:{now // 60}"

            pipe = redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, 120)
            results = await pipe.execute()

            current_count = results[0]
            if current_count > limit:
                retry_after = 60 - (now % 60)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "limit": limit,
                        "window": "1 minute",
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(now + retry_after),
                    },
                )

            response = await call_next(request)
            remaining = max(limit - current_count, 0)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(now + (60 - now % 60))
            return response
        except Exception:
            return await call_next(request)

    async def _extract_tenant_info(self, request: Request) -> tuple:
        """Extract tenant information from the JWT without full validation."""
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return None, None

        token = auth_header[7:]
        try:
            from jose import jwt

            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False},
            )
            tenant_id = payload.get("tenant_id")

            redis = getattr(request.app.state, "redis", None)
            if redis and tenant_id:
                plan = await redis.get(f"tenant_plan:{tenant_id}")
                if plan:
                    return tenant_id, plan.decode()

            return tenant_id, "free"
        except Exception:
            return None, None
