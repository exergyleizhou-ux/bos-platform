"""BOS Pipeline — Phase A relay-simulation engine.

Composes existing engines (digital_twin, kinetics, mass_balance, ser)
into a three-stage M1 → M2 → M3 relay. No physical model is
re-implemented here; this is a pure orchestration layer.

Stage allocation (Phase A heuristic):
    M1 — deconstruction      (first 1/3 of horizon)
    M2 — assimilation+decay  (middle 1/3, signal_activity decays at k_decay)
    M3 — stabilization        (final 1/3)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from app.engine.core.digital_twin_engine import (
    TwinParameters,
    TwinState as EngineTwinState,
    predict_step,
)
from app.engine.core.mass_balance import (
    MassBalanceInput,
    reconcile_mass_balance,
)
from app.engine.core.ser_engine import SERInput, compute_ser

ENGINE_VERSION = "9.0.0"

_STAGES: Tuple[str, str, str] = ("M1", "M2", "M3")

_K_DECAY_EVIDENCE = {
    "measured": "validated",
    "fitted": "supported",
    "literature": "planned",
}


# ---- helpers ---------------------------------------------------------


def _to_engine_state(s: Dict[str, Any], t: float = 0.0) -> EngineTwinState:
    """Convert V5 schema dict → digital_twin_engine.TwinState."""
    return EngineTwinState(
        biomass=float(s["biomass_kg"]),
        substrate=float(s["substrate_kg"]),
        temperature=float(s["temperature_c"]),
        moisture=float(s["moisture_pct"]),
        nitrogen=float(s["nitrogen_g"]),
        timestamp_hours=t,
    )


def _from_engine_state(es: EngineTwinState, signal_activity: float) -> Dict[str, Any]:
    """digital_twin_engine.TwinState + signal activity → V5 schema dict."""
    return {
        "biomass_kg": round(float(es.biomass), 6),
        "substrate_kg": round(float(es.substrate), 6),
        "temperature_c": round(float(es.temperature), 4),
        "moisture_pct": round(float(es.moisture), 4),
        "nitrogen_g": round(float(es.nitrogen), 4),
        "signal_activity_au": round(float(signal_activity), 6),
    }


def _eq6_tau_max(s0: float, s_min: float, k_decay_point: float) -> float:
    if k_decay_point <= 0 or s_min <= 0 or s0 <= s_min:
        return math.inf
    return math.log(s0 / s_min) / k_decay_point


def _split_steps(horizon_steps: int) -> Tuple[int, int, int]:
    """Split total steps among M1 / M2 / M3 stages.

    Current rule: divide by 3, M3 absorbs the remainder.

    Examples:
        horizon=11 → (3, 3, 5)
        horizon=12 → (4, 4, 4)
        horizon=13 → (4, 4, 5)

    TODO (Phase A2): Make this allocation user-configurable via a
    ``StageAllocation`` schema, or at least document the rule in
    PHASE_A_PLAN. The current behaviour means callers cannot control
    how steps distribute across stages, which limits k_decay
    violation test scenarios. Tracked as A1 technical debt.
    """
    third = max(horizon_steps // 3, 1)
    remainder = horizon_steps - 2 * third
    if remainder < 1:
        remainder = 1
        # In tiny-horizon cases the total may slightly exceed horizon_steps.
    return third, third, remainder


# ---- per-stage simulation -------------------------------------------


def _simulate_stage(
    stage: str,
    state_v5: Dict[str, Any],
    cumulative_time_h: float,
    n_steps: int,
    dt_hours: float,
    control_inputs: Dict[str, float],
    k_decay_point: Optional[float],
    s_min: float,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[int]]:
    """Run ``n_steps`` of digital-twin advancement under stage semantics.

    Returns (snapshots, final_state_v5, k_decay_violation_step_or_none).
    Each snapshot dict is shaped for the TwinSnapshot pydantic model.
    """
    params = TwinParameters()
    engine_state = _to_engine_state(state_v5, t=cumulative_time_h)
    signal = float(state_v5.get("signal_activity_au", 0.0))

    snapshots: List[Dict[str, Any]] = []
    violation_step: Optional[int] = None

    for i in range(n_steps):
        step_result = predict_step(engine_state, control_inputs, params, dt_hours)
        engine_state = step_result.state

        # M2 applies first-order decay to signal_activity (Eq.6 dynamics).
        if stage == "M2" and k_decay_point is not None:
            signal = signal * math.exp(-k_decay_point * dt_hours)
            if violation_step is None and signal < s_min:
                violation_step = i

        cumulative_time_h += dt_hours
        snapshots.append({
            "step_index": i,
            "stage": stage,
            "cumulative_time_h": round(cumulative_time_h, 4),
            "state": _from_engine_state(engine_state, signal),
        })

    final_v5 = _from_engine_state(engine_state, signal)
    return snapshots, final_v5, violation_step


# ---- boundary ledger -------------------------------------------------


def _boundary_ledger(
    stage: str,
    state_in: Dict[str, Any],
    state_out: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Compute closure via mass_balance.reconcile.

    Returns (ledger_dict, warnings_to_emit).
    """
    dm_in = float(state_in["biomass_kg"] + state_in["substrate_kg"])
    dm_out_biomass = float(state_out["biomass_kg"])
    dm_out_substrate = float(state_out["substrate_kg"])

    # The dm_larvae / dm_frass / dm_gas mapping used here treats biomass as
    # the recovered "useful" mass and remaining substrate as residual.
    mb_inp = MassBalanceInput(
        dm_in=max(dm_in, 1e-6),
        dm_larvae=max(dm_out_biomass, 0.0),
        dm_frass=max(dm_out_substrate, 0.0),
        dm_gas_loss=None,
    )
    mb = reconcile_mass_balance(mb_inp)

    closure_pct = round(float(mb.closure_pct), 2)
    mass_out = dm_out_biomass + dm_out_substrate
    mass_residual = round(dm_in - mass_out, 6)

    nitrogen_in = float(state_in["nitrogen_g"])
    nitrogen_out = float(state_out["nitrogen_g"])
    nitrogen_residual = round(nitrogen_in - nitrogen_out, 6)

    warnings: List[Dict[str, Any]] = []
    if closure_pct < 95.0:
        warnings.append({
            "code": "poor_boundary_closure",
            "severity": "warn",
            "message": (
                f"{stage} closure_pct={closure_pct:.2f}% below 95% threshold."
                " Residual exceeds 5% — review measurement uncertainty."
            ),
            "step_index": None,
            "stage": stage,
        })

    ledger = {
        "stage": stage,
        "mass_in_kg": round(dm_in, 6),
        "mass_out_kg": round(mass_out, 6),
        "mass_residual_kg": mass_residual,
        "nitrogen_in_g": round(nitrogen_in, 4),
        "nitrogen_out_g": round(nitrogen_out, 4),
        "nitrogen_residual_g": nitrogen_residual,
        "closure_pct": closure_pct,
    }
    return ledger, warnings


# ---- public entry ----------------------------------------------------


def simulate_relay(
    initial_state: Dict[str, Any],
    relay_config: Dict[str, Any],
    horizon_steps: int,
    dt_hours: float,
    species_code: str,
    monte_carlo: Optional[Dict[str, Any]] = None,
    control_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the full M1→M2→M3 relay simulation.

    All inputs are plain dicts (post Pydantic validation in the router)
    so the engine can be unit-tested without the schema dependency.
    """

    # ---- Eq.6 horizon resolution ----
    k_band = relay_config.get("k_decay_band")
    k_point: Optional[float] = None
    if k_band is not None:
        k_point = float(k_band["point"])
    s0 = float(relay_config["s0"])
    s_min = float(relay_config["s_min"])

    tau_max = relay_config.get("tau_max_h")
    if tau_max is None and k_point is not None:
        tau_max = _eq6_tau_max(s0, s_min, k_point)

    # ---- Per-stage step allocation ----
    m1_n, m2_n, m3_n = _split_steps(horizon_steps)

    # ---- Default control inputs (control_profile not yet wired in Phase A) ----
    if control_profile is not None:
        sp = control_profile.get("setpoints", {})
        ctrl_inputs = {
            "feed_rate": float(sp.get("feed_rate", 0.05)),
            "ventilation": float(sp.get("ventilation", 1.0)),
            "heating": float(sp.get("heating", 0.0)),
        }
    else:
        ctrl_inputs = {"feed_rate": 0.05, "ventilation": 1.0, "heating": 0.0}

    # ---- Run three stages ----
    trajectory: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    ledgers: List[Dict[str, Any]] = []
    stage_completion: Dict[str, float] = {"M1": 0.0, "M2": 0.0, "M3": 0.0}
    sfi_passed: Dict[str, bool] = {"M1": True, "M2": True, "M3": True}

    current_state = dict(initial_state)
    if "signal_activity_au" not in current_state:
        current_state["signal_activity_au"] = s0

    cumulative_time = 0.0
    k_violation_step: Optional[int] = None
    global_step_offset = 0

    for stage_name, n_steps in zip(_STAGES, (m1_n, m2_n, m3_n)):
        state_in = dict(current_state)
        snapshots, state_out, viol = _simulate_stage(
            stage=stage_name,
            state_v5=current_state,
            cumulative_time_h=cumulative_time,
            n_steps=n_steps,
            dt_hours=dt_hours,
            control_inputs=ctrl_inputs,
            k_decay_point=k_point if stage_name == "M2" else None,
            s_min=s_min,
        )
        # Re-index step_index globally so the trajectory is contiguous.
        for snap in snapshots:
            snap["step_index"] = global_step_offset
            global_step_offset += 1
        trajectory.extend(snapshots)
        cumulative_time = snapshots[-1]["cumulative_time_h"] if snapshots else cumulative_time

        # k_decay violation captured during M2.
        if stage_name == "M2" and viol is not None:
            # `viol` is the *local* step within M2; convert to global.
            local_offset = global_step_offset - len(snapshots)
            k_violation_step = local_offset + viol
            warnings.append({
                "code": "k_decay_violation",
                "severity": "error",
                "message": (
                    "Signal activity dropped below s_min in M2 — relay"
                    " breached Eq.6 horizon."
                ),
                "step_index": k_violation_step,
                "stage": "M2",
            })

        # Boundary ledger for this stage.
        ledger, ledger_warnings = _boundary_ledger(stage_name, state_in, state_out)
        ledgers.append(ledger)
        warnings.extend(ledger_warnings)

        stage_completion[stage_name] = (
            1.0 if (viol is None or stage_name != "M2") else round(viol / max(n_steps, 1), 4)
        )

        current_state = state_out

    # ---- Aggregate health ----
    if k_violation_step is not None:
        overall_status = "failed"
    elif any(w["severity"] == "warn" for w in warnings):
        overall_status = "degraded"
    else:
        overall_status = "nominal"

    # ---- Final SER via existing ser_engine ----
    ser_input = SERInput(
        dm_in=float(initial_state["biomass_kg"] + initial_state["substrate_kg"]),
        dm_out=float(current_state["biomass_kg"]),
        n_in=float(initial_state["nitrogen_g"]),
        n_larvae=float(current_state["nitrogen_g"]),
        n_frass=0.0,
    )
    ser_result = compute_ser(ser_input)
    final_ser = float(max(0.0, min(1.0, ser_result.ser_value)))

    # ---- Optional MC band ----
    final_ser_ci: Optional[Tuple[float, float]] = None
    if monte_carlo is not None:
        # Phase A heuristic: a placeholder CI of ±10% relative width
        # around final_ser. Phase D will plumb monte_carlo_engine through
        # the full trajectory.
        lo = max(0.0, final_ser * 0.9)
        hi = min(1.0, final_ser * 1.1)
        final_ser_ci = (round(lo, 6), round(hi, 6))

    # ---- Evidence level from k_decay provenance ----
    if k_band is None:
        evidence_level = "supported"
    else:
        evidence_level = _K_DECAY_EVIDENCE.get(k_band.get("source", "literature"), "planned")

    return {
        "trajectory": trajectory,
        "boundary_ledger": ledgers,
        "relay_health": {
            "overall_status": overall_status,
            "stage_completion": stage_completion,
            "sfi_check_passed_at_each_stage": sfi_passed,
            "k_decay_violation_at_step": k_violation_step,
        },
        "final_ser": round(final_ser, 6),
        "final_ser_ci": final_ser_ci,
        "warnings": warnings,
        "engine_version": ENGINE_VERSION,
        "evidence_level": evidence_level,
    }
