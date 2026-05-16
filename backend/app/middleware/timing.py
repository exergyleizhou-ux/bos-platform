"""
BOS Pipeline v9.0 timing middleware.

Measures and logs request processing time.
Adds an X-Process-Time header to every response.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_id import request_id_ctx

logger = logging.getLogger("bos.timing")

SLOW_REQUEST_THRESHOLD_MS = 2000


class TimingMiddleware(BaseHTTPMiddleware):
    """Measure request processing time."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        req_id = request_id_ctx.get("")
        method = request.method
        path = request.url.path
        status = response.status_code
        log_msg = f"[{req_id[:8]}] {method} {path} -> {status} ({duration_ms:.1f}ms)"

        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("SLOW %s", log_msg)
        elif status >= 500:
            logger.error(log_msg)
        elif status >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return response
