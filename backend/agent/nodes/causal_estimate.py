"""causal_estimate_node — call /api/v1/causal/estimate; write the
estimate handle into ``state.causal.estimate_result``.

Plan v2 §3.3 partial-failure: estimate is a prerequisite. Failure
here writes an entry to ``state.causal.errors`` (refute / mediation /
sensitivity all depend on the estimate_handle).

Mod 4: passes ``state.causal.identify_result.estimand_handle`` as
``precomputed_estimand`` so /estimate skips re-identification.
"""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.causal.common import MethodParams
from agent.schemas.causal.estimate import CausalEstimateRequest
from agent.state import BOSState
from agent.tools.causal import causal_estimate
from agent.tools.client import CORE_URL


_DEFAULT_METHOD_FAMILY = "linear_regression"
"""B4 v2 agent default. Operator-routed method selection is a Phase
G enhancement once the agent supports method-aware prompts."""


def _build_request(state: BOSState) -> CausalEstimateRequest | None:
    causal = state.get("causal") or {}
    required = ("dag", "treatment", "outcome", "data", "identify_result")
    if any(causal.get(k) is None for k in required):
        return None
    try:
        return CausalEstimateRequest(
            dag=causal["dag"],
            treatment=causal["treatment"],
            outcome=causal["outcome"],
            data=causal["data"],
            method_family=_DEFAULT_METHOD_FAMILY,
            method_params=MethodParams(),
            precomputed_estimand=causal["identify_result"].estimand_handle,
        )
    except Exception:
        return None


async def causal_estimate_node(state: BOSState) -> dict[str, Any]:
    """Run estimate; write result into state.causal.estimate_result."""
    causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    req = _build_request(state)

    if req is None:
        causal_errors = list(causal.get("errors") or [])
        causal_errors.append(
            "estimate failed: missing required fields in state.causal "
            "(dag / treatment / outcome / data / identify_result)"
        )
        causal["errors"] = causal_errors
        return {"causal": causal, "tool_calls": tool_calls}

    result, record = await call_tool_with_audit(
        tool="causal_estimate",
        endpoint=f"{CORE_URL}/causal/estimate",
        body=req.model_dump(mode="json"),
        func=lambda: causal_estimate.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        causal_errors = list(causal.get("errors") or [])
        causal_errors.append(
            f"estimate failed: {record.get('error', 'unknown error')}"
        )
        causal["errors"] = causal_errors
        return {"causal": causal, "tool_calls": tool_calls}

    causal["estimate_result"] = result
    return {
        "causal": causal,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
