"""causal_refute_node — call /api/v1/causal/refute; write the refute
result into ``state.causal.refute_result``.

Plan v2 §3.3 partial-failure: refute is optional. Failure writes a
warning string into ``state.causal.warnings`` and sets
``state.causal.refute_result = None``. The graph's conditional edge
treats the estimate as still valid; render will downgrade
``evidence_level`` to ``planned`` per the §3.3 rule.

Default refuter set is the four mandatory refuters from Plan v2
§2.3 (patched). ``bootstrap_refuter`` is the optional implemented
refuter; ``non_parametric_sensitivity_analyzer`` is reserved.
"""

from __future__ import annotations

from typing import Any, List

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.causal.refute import (
    CausalRefuteRequest,
    RefuterName,
)
from agent.state import BOSState
from agent.tools.causal import causal_refute
from agent.tools.client import CORE_URL


_DEFAULT_REFUTERS: List[RefuterName] = [
    "random_common_cause",
    "placebo_treatment_refuter",
    "data_subset_refuter",
    "add_unobserved_common_cause",
]


def _build_request(state: BOSState) -> CausalRefuteRequest | None:
    causal = state.get("causal") or {}
    if causal.get("estimate_result") is None:
        return None
    try:
        return CausalRefuteRequest(
            estimate_handle=causal["estimate_result"].estimate_handle,
            refuters=list(_DEFAULT_REFUTERS),
            original_e_value=causal["estimate_result"].e_value_cheap,
        )
    except Exception:
        return None


async def causal_refute_node(state: BOSState) -> dict[str, Any]:
    """Run refute; warn-and-continue on failure."""
    causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    req = _build_request(state)

    def _warn(msg: str) -> dict[str, Any]:
        warnings = list(causal.get("warnings") or [])
        warnings.append(f"refute failed: {msg[:200]}")
        causal["warnings"] = warnings
        causal["refute_result"] = None
        return {"causal": causal, "tool_calls": tool_calls}

    if req is None:
        return _warn("prereq missing (state.causal.estimate_result)")

    result, record = await call_tool_with_audit(
        tool="causal_refute",
        endpoint=f"{CORE_URL}/causal/refute",
        body=req.model_dump(mode="json"),
        func=lambda: causal_refute.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return _warn(record.get("error", "unknown error"))

    causal["refute_result"] = result
    return {
        "causal": causal,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
