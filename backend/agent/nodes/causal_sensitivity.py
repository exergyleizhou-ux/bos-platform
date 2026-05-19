"""causal_sensitivity_node — call /api/v1/causal/sensitivity; write
the sensitivity result into ``state.causal.sensitivity_result``.

Plan v2 §3.3 partial-failure: sensitivity is optional. Failure
writes a warning and sets ``state.causal.sensitivity_result = None``.

Default method is ``evalue`` (Plan v2 §2.5 default; cheap + paper-
Gamma-bound aligned). ``linear`` (Cinelli-Hazlett RV) is available;
``partial_linear`` is reserved at the engine.
"""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.causal.sensitivity import (
    CausalSensitivityRequest,
    SensitivityMethod,
)
from agent.state import BOSState
from agent.tools.causal import causal_sensitivity
from agent.tools.client import CORE_URL


_DEFAULT_METHOD: SensitivityMethod = "evalue"


def _build_request(state: BOSState) -> CausalSensitivityRequest | None:
    causal = state.get("causal") or {}
    if causal.get("estimate_result") is None:
        return None
    try:
        return CausalSensitivityRequest(
            estimate_handle=causal["estimate_result"].estimate_handle,
            method=_DEFAULT_METHOD,
            benchmark_covariate=None,
        )
    except Exception:
        return None


async def causal_sensitivity_node(state: BOSState) -> dict[str, Any]:
    """Run sensitivity; warn-and-continue on failure."""
    causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    req = _build_request(state)

    def _warn(msg: str) -> dict[str, Any]:
        warnings = list(causal.get("warnings") or [])
        warnings.append(f"sensitivity failed: {msg[:200]}")
        causal["warnings"] = warnings
        causal["sensitivity_result"] = None
        return {"causal": causal, "tool_calls": tool_calls}

    if req is None:
        return _warn("prereq missing (state.causal.estimate_result)")

    result, record = await call_tool_with_audit(
        tool="causal_sensitivity",
        endpoint=f"{CORE_URL}/causal/sensitivity",
        body=req.model_dump(mode="json"),
        func=lambda: causal_sensitivity.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return _warn(record.get("error", "unknown error"))

    causal["sensitivity_result"] = result
    return {
        "causal": causal,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
