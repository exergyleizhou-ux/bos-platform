"""Shared httpx.AsyncClient for all agent tools.

Plan v2 D4: HTTP REST + mandatory async-from-day-1. All tool functions
share a single ``AsyncClient`` so the event loop can fan out parallel
Core calls via ``asyncio.gather`` (see cyber_lab_node).
"""

from __future__ import annotations

import os
from typing import Optional

import httpx


CORE_URL = os.environ.get("BOS_CORE_URL", "http://localhost:8000/api/v1")

# Conservative timeouts: connect fast, but allow long Core compute jobs.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    """Return the process-wide AsyncClient, creating it on first use."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
    return _client


def set_client(c: Optional[httpx.AsyncClient]) -> None:
    """Install a specific AsyncClient as the process-wide singleton.

    Used by the end-to-end tests in ``tests/e2e/test_phase_a_e2e.py`` to
    inject an ``httpx.ASGITransport``-backed client that routes
    in-process to BOS Core's FastAPI app — no real network. Pass
    ``None`` to clear the singleton (equivalent to ``close_client``
    without awaiting).
    """
    global _client
    _client = c


async def close_client() -> None:
    """Release the shared client (called from agent.server lifespan)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class ToolError(RuntimeError):
    """Raised when a Core call fails. Carries status code + body for
    auditing in tool_calls."""

    def __init__(self, tool: str, endpoint: str, status_code: int, body: str):
        self.tool = tool
        self.endpoint = endpoint
        self.status_code = status_code
        self.body = body
        super().__init__(f"{tool} {endpoint} -> HTTP {status_code}: {body[:200]}")
