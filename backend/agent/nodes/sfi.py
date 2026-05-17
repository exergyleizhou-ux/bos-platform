"""sfi_node - call sfi_check, write zone / pass into state."""

from __future__ import annotations

from typing import Any

from agent.nodes._audit import call_tool_with_audit
from agent.schemas.sfi import SfiCheckRequest, SfiMeasurements
from agent.state import BOSState
from agent.tools import sfi_check
from agent.tools.client import CORE_URL


def _measurements_from_state(state: BOSState) -> SfiMeasurements | None:
    """Phase A: pull measurements from a state["sfi_measurements"] hint dict.

    This node is intentionally tolerant; production wiring will build
    measurements from real sensor streams in Phase D.
    """
    hint = state.get("simulation_result")  # opportunistic; may be None
    if isinstance(hint, dict) and "measurements" in hint:
        try:
            return SfiMeasurements(**hint["measurements"])
        except Exception:
            return None
    return None


async def sfi_node(state: BOSState) -> dict[str, Any]:
    """Call /api/v1/sfi/check and write zone + pass back to state."""
    measurements = _measurements_from_state(state)
    tool_calls = list(state.get("tool_calls") or [])

    if measurements is None:
        # Cannot construct a meaningful request without measurements;
        # record an error and return without mutating sfi_* fields.
        tool_calls.append({
            "tool": "sfi_check",
            "endpoint": f"{CORE_URL}/sfi/check",
            "status": "error",
            "error": "no measurements available on BOSState",
            "started_at": "",
            "duration_ms": 0.0,
        })
        return {"tool_calls": tool_calls}

    req = SfiCheckRequest(
        species_code=state.get("species_code") or "BSF_LARVA",
        measurements=measurements,
    )

    result, record = await call_tool_with_audit(
        tool="sfi_check",
        endpoint=f"{CORE_URL}/sfi/check",
        body=req.model_dump(mode="json"),
        func=lambda: sfi_check.ainvoke({"req": req}),
    )
    tool_calls.append(record)

    if result is None:
        return {"tool_calls": tool_calls}

    return {
        "sfi_pass": result.sfi_pass,
        "sfi_zone": result.zone,
        "tool_calls": tool_calls,
        "evidence_level": result.evidence_level,
    }
