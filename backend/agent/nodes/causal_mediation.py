"""causal_mediation_node — call /api/v1/causal/mediation; write the
mediation result into ``state.causal.mediation_result``.

Plan v2 §3.3 partial-failure: mediation is optional. Failure writes
a warning and sets ``state.causal.mediation_result = None``.

D14: NOT Baron-Kenny. Mediation re-fits estimation internally; pass
``identify_result.estimand_handle`` as ``precomputed_estimand``
(Mod 4) but NOT ``estimate_handle`` (mediation does not consume
that).

Mod 8: defaults ``assumptions_acknowledged`` to ``["consistency"]``
(weakest sufficient Pearl-style assumption). Phase G can route a
full four-item checklist via routing-aware prompts.
"""

from __future__ import annotations

from typing import Any, List

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.causal.mediation import (
    AssumptionAck,
    CausalMediationRequest,
    DecompositionType,
)
from agent.state import BOSState
from agent.tools.causal import causal_mediation
from agent.tools.client import CORE_URL


_DEFAULT_ASSUMPTIONS_ACK: List[AssumptionAck] = ["consistency"]
_DEFAULT_DECOMPOSITION: DecompositionType = "natural"
_DEFAULT_N_BOOTSTRAP = 200


def _build_request(state: BOSState) -> CausalMediationRequest | None:
    causal = state.get("causal") or {}
    required = ("dag", "treatment", "outcome", "data", "mediators")
    if any(causal.get(k) is None for k in required):
        return None
    if not causal["mediators"]:
        return None
    identify_result = causal.get("identify_result")
    precomputed = (
        identify_result.estimand_handle if identify_result is not None
        else None
    )
    try:
        return CausalMediationRequest(
            dag=causal["dag"],
            treatment=causal["treatment"],
            outcome=causal["outcome"],
            mediators=list(causal["mediators"]),
            data=causal["data"],
            decomposition=_DEFAULT_DECOMPOSITION,
            n_bootstrap=_DEFAULT_N_BOOTSTRAP,
            assumptions_acknowledged=list(_DEFAULT_ASSUMPTIONS_ACK),
            precomputed_estimand=precomputed,
        )
    except Exception:
        return None


async def causal_mediation_node(state: BOSState) -> dict[str, Any]:
    """Run mediation; warn-and-continue on failure."""
    causal = dict(state.get("causal") or {})
    tool_calls = list(state.get("tool_calls") or [])
    req = _build_request(state)

    def _warn(msg: str) -> dict[str, Any]:
        warnings = list(causal.get("warnings") or [])
        warnings.append(f"mediation failed: {msg[:200]}")
        causal["warnings"] = warnings
        causal["mediation_result"] = None
        return {"causal": causal, "tool_calls": tool_calls}

    if req is None:
        return _warn(
            "prereq missing (dag / treatment / outcome / data / "
            "mediators) or schema rejected"
        )

    result, record = await call_tool_with_audit(
        tool="causal_mediation",
        endpoint=f"{CORE_URL}/causal/mediation",
        body=req.model_dump(mode="json"),
        func=lambda: causal_mediation.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return _warn(record.get("error", "unknown error"))

    causal["mediation_result"] = result
    return {
        "causal": causal,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
