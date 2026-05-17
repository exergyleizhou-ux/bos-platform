"""Shared helpers for node audit-trail recording."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from agent.tools.client import ToolError


async def call_tool_with_audit(
    tool: str,
    endpoint: str,
    body: dict[str, Any],
    func: Callable[[], Awaitable[Any]],
) -> tuple[Any | None, dict[str, Any]]:
    """Invoke ``func``, record a ToolCallRecord, return (result, record)."""
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    record: dict[str, Any] = {
        "tool": tool,
        "endpoint": endpoint,
        "started_at": started,
    }
    try:
        result = await func()
        record["status"] = "ok"
        record["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        evidence = getattr(result, "evidence_level", None)
        if evidence is not None:
            record["evidence_level"] = evidence
        return result, record
    except ToolError as exc:
        record["status"] = "error"
        record["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        record["error"] = f"HTTP {exc.status_code}: {exc.body[:200]}"
        return None, record
    except Exception as exc:  # network / serialization failure
        record["status"] = "error"
        record["duration_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        record["error"] = repr(exc)[:300]
        return None, record
