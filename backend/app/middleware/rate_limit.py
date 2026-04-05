"""
BOS Pipeline v9.0 �� Rate Limiting Middleware

Per-tenant rate limiting using Redis sliding window.

Limits:
  - free       : 100 req/min
  - starter    : 500 req/min
  - pro        : 2000 req/min
  - enterprise : 10000 req/min

Returns 429 Too Many Requests when limit is exceeded.
"""

import time
from typing import Callable, Optional

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

# Paths excluded from rate limiting
EXCLUDED_PATHS = {
    "/api/v1/health/live",
    "/api/v1/health/ready",
    "/api/v1/health/info",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant rate limiting using Redis sliding window counter."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        # Skip if no Redis available
        redis = getattr(request.app.state, "redis", None)
        if not redis:
            return await call_next(request)

        # Extract tenant from JWT (lightweight check)
        tenant_id, plan = await self._extract_tenant_info(request)
        if tenant_id is None:
            # Unauthenticated �� use IP-based limiting
            client_ip = request.client.host if request.client else "unknown"
            rate_key = f"rl:ip:{client_ip}"
            limit = 60  # 60 req/min for unauthenticated
        else:
            rate_key = f"rl:tenant:{tenant_id}"
            limit = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS["free"])

        # Sliding window counter
        try:
            now = int(time.time())
            window_key = f"{rate_key}:{now // 60}"  # Per-minute window

            pipe = redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, 120)  # Expire 2 minutes after window
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

            # Add rate limit headers
            remaining = max(limit - current_count, 0)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(now + (60 - now % 60))

            return response

        except Exception:
            # If Redis fails, don't block the request
            return await call_next(request)

    async def _extract_tenant_info(self, request: Request) -> tuple:
        """Extract tenant_id and plan from the JWT without full validation."""
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
                options={"verify_exp": False},  # We just need tenant info
            )
            tenant_id = payload.get("tenant_id")

            # Cache plan lookup in Redis
            redis = getattr(request.app.state, "redis", None)
            if redis and tenant_id:
                plan = await redis.get(f"tenant_plan:{tenant_id}")
                if plan:
                    return tenant_id, plan.decode()

            return tenant_id, "free"

        except Exception:
            return None, None

