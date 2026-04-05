"""
BOS Pipeline v9.0 �� Request ID Middleware

Adds a unique X-Request-ID header to every request and response
for distributed tracing and log correlation.
"""

import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context var for access in logging
import contextvars

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-ID into request/response headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Use existing header or generate new
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Set context variable for use in logging
        token = request_id_ctx.set(request_id)

        # Store on request state for downstream access
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)
