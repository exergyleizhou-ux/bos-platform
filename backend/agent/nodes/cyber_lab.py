"""cyber_lab_node - compose multiple Core calls in parallel.

Phase A Flow B (Plan v2 paragraph 3.2): baseline ser_compute + an
mc_propagate sensitivity sweep around the same SER target. Parallel
fan-out via asyncio.gather; partial failures recorded but do not abort.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.mc import McPropagateRequest
from agent.schemas.ser import SerComputeRequest
from agent.state import BOSState
from agent.tools import mc_propagate, ser_compute
from agent.tools.client import CORE_URL


def _build_ser_request(state: BOSState) -> SerComputeRequest | None:
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


def _build_mc_request(state: BOSState) -> McPropagateRequest | None:
    if state.get("dm_in") is None or state.get("dm_out") is None:
        return None
    try:
        return McPropagateRequest(
            inputs={
                "dm_in": {
                    "kind": "normal",
                    "mean": float(state["dm_in"]),
                    "std": float(state["dm_in"]) * 0.05,
                },
                "dm_out": {
                    "kind": "normal",
                    "mean": float(state["dm_out"]),
                    "std": float(state["dm_out"]) * 0.05,
                },
            },
            target_func="ser",
            target_func_config={
                "constants": {
                    "n_in": float(state.get("n_in") or 0.0),
                    "n_larvae": float(state.get("n_rec") or 0.0),
                },
            },
            n_samples=500,
            seed=42,
        )
    except Exception:
        return None


async def cyber_lab_node(state: BOSState) -> dict[str, Any]:
    """Run the baseline SER + a small MC sweep in parallel."""
    ser_req = _build_ser_request(state)
    mc_req = _build_mc_request(state)

    tool_calls = list(state.get("tool_calls") or [])

    async def _ser_branch():
        if ser_req is None:
            return None, {
                "tool": "ser_compute",
                "endpoint": f"{CORE_URL}/ser/compute",
                "status": "error",
                "error": "missing SER inputs",
                "started_at": "",
                "duration_ms": 0.0,
            }
        return await call_tool_with_audit(
            tool="ser_compute",
            endpoint=f"{CORE_URL}/ser/compute",
            body=ser_req.model_dump(mode="json"),
            func=lambda: ser_compute.ainvoke({"req": ser_req}),
        )

    async def _mc_branch():
        if mc_req is None:
            return None, {
                "tool": "mc_propagate",
                "endpoint": f"{CORE_URL}/mc/propagate",
                "status": "error",
                "error": "missing MC inputs",
                "started_at": "",
                "duration_ms": 0.0,
            }
        return await call_tool_with_audit(
            tool="mc_propagate",
            endpoint=f"{CORE_URL}/mc/propagate",
            body=mc_req.model_dump(mode="json"),
            func=lambda: mc_propagate.ainvoke({"req": mc_req}),
        )

    ser_pair, mc_pair = await asyncio.gather(_ser_branch(), _mc_branch())
    ser_result, ser_record = ser_pair
    mc_result, mc_record = mc_pair
    tool_calls.append(ser_record)
    tool_calls.append(mc_record)

    cyber: dict[str, Any] = {}
    if ser_result is not None:
        cyber["baseline_ser"] = ser_result.ser_point
    if mc_result is not None:
        cyber["mc_target_mean"] = mc_result.target_mean
        cyber["mc_ci"] = (mc_result.ci_lower, mc_result.ci_upper)
        cyber["mc_evidence"] = mc_result.evidence_level

    out: dict[str, Any] = {
        "cyber_experiment": cyber,
        "tool_calls": tool_calls,
    }
    if ser_result is not None:
        out["ser"] = ser_result.ser_point
    if mc_result is not None:
        # If we have an MC CI, prefer it over the deterministic point.
        out["ser_ci"] = (mc_result.ci_lower, mc_result.ci_upper)
    return out
