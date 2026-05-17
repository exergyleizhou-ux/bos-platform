"""relay_node - call relay_simulate, write simulation result to state."""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.relay import (
    RelayConfig,
    RelaySimulateRequest,
    TwinState as RelayTwinState,
)
from agent.state import BOSState
from agent.tools import relay_simulate
from agent.tools.client import CORE_URL


def _build_request(state: BOSState) -> RelaySimulateRequest | None:
    """Build a RelaySimulateRequest from state. Returns None on missing data."""
    init = state.get("simulation_result")
    if not isinstance(init, dict) or "initial_state" not in init:
        return None
    try:
        initial = RelayTwinState(**init["initial_state"])
        relay_cfg = RelayConfig(
            tau_m2_h=float(state.get("tau_m2") or 24.0),
            s0=float(state.get("s0") or 100.0),
            s_min=float(state.get("s_min") or 10.0),
        )
        return RelaySimulateRequest(
            initial_state=initial,
            relay_config=relay_cfg,
            horizon_steps=int(init.get("horizon_steps", 12)),
            dt_hours=float(init.get("dt_hours", 1.0)),
            species_code=state.get("species_code") or "BSF_LARVA",
        )
    except Exception:
        return None


async def relay_node(state: BOSState) -> dict[str, Any]:
    """Call /api/v1/relay/simulate and write summary back to state."""
    req = _build_request(state)
    tool_calls = list(state.get("tool_calls") or [])

    if req is None:
        tool_calls.append({
            "tool": "relay_simulate",
            "endpoint": f"{CORE_URL}/relay/simulate",
            "status": "error",
            "error": "missing relay inputs on BOSState",
            "started_at": "",
            "duration_ms": 0.0,
        })
        return {"tool_calls": tool_calls}

    result, record = await call_tool_with_audit(
        tool="relay_simulate",
        endpoint=f"{CORE_URL}/relay/simulate",
        body=req.model_dump(mode="json"),
        func=lambda: relay_simulate.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return {"tool_calls": tool_calls}

    return {
        "simulation_result": {
            "final_ser": result.final_ser,
            "relay_health": result.relay_health.model_dump(),
            "boundary_ledger": [b.model_dump() for b in result.boundary_ledger],
            "warnings": [w.model_dump() for w in result.warnings],
        },
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
