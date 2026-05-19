"""causal_identify_node — call /api/v1/causal/identify, write the
estimand handle into ``state.causal.identify_result``.

Plan v2 §3.3 partial-failure: identify is a prerequisite. Failure
here writes an entry to ``state.causal.errors`` (NOT raise — the
graph's conditional edge checks errors and short-circuits to render).

Phase A 3-layer pattern: this node uses ``call_tool_with_audit`` to
write the per-call ``ToolCallRecord`` into ``state.tool_calls``.
"""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.causal.identify import CausalIdentifyRequest
from agent.state import BOSState
from agent.tools.causal import causal_identify
from agent.tools.client import CORE_URL


def _build_request(state: BOSState) -> CausalIdentifyRequest | None:
    """Pull identify inputs from ``state.causal``. Returns None if any
    required field is missing — caller surfaces that as an
    ``errors`` entry rather than a Pydantic validation error."""
    causal = state.get("causal") or {}
    required = ("dag", "treatment", "outcome", "data")
    if any(causal.get(k) is None for k in required):
        return None
    try:
        return CausalIdentifyRequest(
            dag=causal["dag"],
            treatment=causal["treatment"],
            outcome=causal["outcome"],
            dataset_fingerprint=causal["data"].fingerprint,
            proceed_when_unidentifiable=False,
        )
    except Exception:
        return None


async def causal_identify_node(state: BOSState) -> dict[str, Any]:
    """Run identify; write result into state.causal.identify_result."""
    causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    req = _build_request(state)

    if req is None:
        causal_errors = list(causal.get("errors") or [])
        causal_errors.append(
            "identify failed: missing required fields "
            "(dag / treatment / outcome / data) in state.causal"
        )
        causal["errors"] = causal_errors
        return {"causal": causal, "tool_calls": tool_calls}

    result, record = await call_tool_with_audit(
        tool="causal_identify",
        endpoint=f"{CORE_URL}/causal/identify",
        body=req.model_dump(mode="json"),
        func=lambda: causal_identify.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        causal_errors = list(causal.get("errors") or [])
        causal_errors.append(
            f"identify failed: {record.get('error', 'unknown error')}"
        )
        causal["errors"] = causal_errors
        return {"causal": causal, "tool_calls": tool_calls}

    causal["identify_result"] = result
    return {
        "causal": causal,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
