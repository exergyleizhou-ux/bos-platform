"""ser_node - call ser_compute, write SER fields back to state."""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.ser import SerComputeRequest
from agent.state import BOSState
from agent.tools import ser_compute
from agent.tools.client import CORE_URL


def _build_request(state: BOSState) -> SerComputeRequest | None:
    """Pull SER inputs from state. Returns None if anything required is missing."""
    required = ("dm_in", "dm_out", "n_in", "n_rec", "d_prime", "g_prime")
    if any(state.get(k) is None for k in required):
        return None
    try:
        return SerComputeRequest(
            dm_in=float(state["dm_in"]),
            dm_out=float(state["dm_out"]),
            n_in=float(state["n_in"]),
            n_rec=float(state["n_rec"]),
            d_prime=float(state["d_prime"]),
            g_prime=float(state["g_prime"]),
            species_code=state.get("species_code") or "BSF_LARVA",
        )
    except Exception:
        return None


async def ser_node(state: BOSState) -> dict[str, Any]:
    """Call /api/v1/ser/compute and write SER + CI into the state."""
    req = _build_request(state)
    tool_calls = list(state.get("tool_calls") or [])

    if req is None:
        tool_calls.append({
            "tool": "ser_compute",
            "endpoint": f"{CORE_URL}/ser/compute",
            "status": "error",
            "error": "missing required state fields for SER request",
            "started_at": "",
            "duration_ms": 0.0,
        })
        return {"tool_calls": tool_calls}

    result, record = await call_tool_with_audit(
        tool="ser_compute",
        endpoint=f"{CORE_URL}/ser/compute",
        body=req.model_dump(mode="json"),
        func=lambda: ser_compute.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return {"tool_calls": tool_calls}

    out: dict[str, Any] = {
        "ser": result.ser_point,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
    if result.ser_ci_lower is not None and result.ser_ci_upper is not None:
        out["ser_ci"] = (result.ser_ci_lower, result.ser_ci_upper)
    return out
