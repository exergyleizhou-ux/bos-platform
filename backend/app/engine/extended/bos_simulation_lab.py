"""Deterministic virtual closed-loop simulation for BOS Simulation Lab."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Any

from app.engine.bos_supervisor_engine import evaluate_bos_supervisor_state
from app.engine.digital_twin_engine import TwinConfig, TwinState, predict_step, update_step


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class SimulationLabConfig:
    simulation_id: str
    batch_id: str
    species: str
    feedstock: str
    scenario: str
    initial_state: dict[str, float]
    cycles: int
    seed: int
    policy: str = "rule_based"
    cycle_hours: float = 1.0


def _state_dict(state: TwinState) -> dict[str, float]:
    return {
        "biomass": round(state.biomass, 4),
        "substrate": round(state.substrate, 4),
        "temperature": round(state.temperature, 3),
        "moisture": round(state.moisture, 3),
        "nitrogen": round(state.nitrogen, 3),
    }


def _scenario_inputs(scenario: str, cycle: int, total_cycles: int) -> dict[str, float]:
    progress = cycle / max(total_cycles, 1)
    inputs = {"feed_rate": 0.025, "ventilation": 0.08, "heating": 0.02}
    if scenario == "moisture_drift":
        inputs["ventilation"] = 0.12 + progress * 0.08
    elif scenario == "temperature_spike":
        inputs["heating"] = 0.25 if cycle in {2, 3, 4} else 0.04
        inputs["ventilation"] = 0.05
    elif scenario == "underfeeding":
        inputs["feed_rate"] = 0.006
    return inputs


def _synthesize_sensor(
    rng: random.Random,
    *,
    state: TwinState,
    scenario: str,
    cycle: int,
    timestamp: datetime,
) -> dict[str, Any]:
    drift = cycle * 0.28 if scenario == "moisture_drift" else 0.0
    temp_spike = 2.2 if scenario == "temperature_spike" and cycle in {2, 3, 4} else 0.0
    underfeed_weight_penalty = cycle * 0.04 if scenario == "underfeeding" else 0.0

    temperature = state.temperature + temp_spike + rng.uniform(-0.25, 0.25)
    moisture = state.moisture - drift + rng.uniform(-0.7, 0.7)
    substrate_remaining = max(state.substrate + rng.uniform(-0.08, 0.08), 0)
    weight = max(state.biomass + state.substrate - underfeed_weight_penalty + rng.uniform(-0.12, 0.12), 0)
    do_value = _clamp(6.8 - max(temperature - 28.0, 0) * 0.18 - rng.uniform(0.0, 0.4), 1.0, 8.5)
    co2 = _clamp(650 + max(temperature - 28.0, 0) * 55 + cycle * 12 + rng.uniform(-35, 35), 350, 1800)
    nh3 = _clamp(1.8 + max(moisture - 72, 0) * 0.08 + rng.uniform(-0.15, 0.35), 0.1, 9.0)

    return {
        "simulation_id": "",
        "cycle": cycle,
        "timestamp": timestamp.isoformat(),
        "temperature": round(_clamp(temperature, 0, 60), 2),
        "moisture": round(_clamp(moisture, 0, 100), 2),
        "ph": round(_clamp(7.05 - max(nh3 - 3, 0) * 0.03 + rng.uniform(-0.08, 0.08), 5.5, 8.8), 2),
        "do": round(do_value, 2),
        "co2": round(co2, 1),
        "nh3": round(nh3, 2),
        "weight": round(weight, 3),
        "larvae_density": round(_clamp(state.biomass / max(state.substrate, 0.1), 0.05, 2.5), 3),
        "substrate_remaining": round(substrate_remaining, 3),
        "sensor_quality": "synthetic",
    }


def _risk_prediction(sensor: dict[str, Any], state: TwinState, scenario: str) -> dict[str, Any]:
    moisture_risk = abs(float(sensor["moisture"]) - 68.0) / 35.0
    temperature_risk = abs(float(sensor["temperature"]) - 28.0) / 20.0
    oxygen_risk = max(0.0, (4.5 - float(sensor["do"])) / 4.5)
    substrate_risk = max(0.0, (2.5 - state.substrate) / 2.5)
    scenario_bias = {"normal": 0.02, "moisture_drift": 0.08, "temperature_spike": 0.1, "underfeeding": 0.09}[scenario]
    score = _clamp(
        0.22
        + scenario_bias
        + moisture_risk * 0.25
        + temperature_risk * 0.22
        + oxygen_risk * 0.2
        + substrate_risk * 0.18,
        0,
        1,
    )
    return {
        "future_risk_score": round(score, 3),
        "release_warning_score": round(_clamp(score + max(0.0, 0.55 - state.substrate / 10.0) * 0.12, 0, 1), 3),
        "forecast_window": "next_6_cycles",
        "model_name": "simulation_lab_deterministic_proxy",
        "source": "deterministic_proxy",
        "execution_mode": "fallback",
        "confidence_band": {
            "lower": round(_clamp(score - 0.05, 0, 1), 3),
            "median": round(score, 3),
            "upper": round(_clamp(score + 0.05, 0, 1), 3),
        },
        "driver_features": {
            "moisture_deviation": round(moisture_risk, 3),
            "temperature_deviation": round(temperature_risk, 3),
            "oxygen_risk": round(oxygen_risk, 3),
            "substrate_risk": round(substrate_risk, 3),
        },
    }


def _synthesize_visual_observation(
    *,
    simulation_id: str,
    cycle: int,
    sensor: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    anomaly_labels: list[str] = []
    if float(sensor["moisture"]) < 62:
        anomaly_labels.append("surface_dryness")
    if float(sensor["moisture"]) > 78:
        anomaly_labels.append("surface_wetness")
    if float(sensor["temperature"]) > 31:
        anomaly_labels.append("thermal_hotspot")
    if float(sensor["co2"]) > 950 or float(sensor["do"]) < 4.8:
        anomaly_labels.append("aeration_stress")
    if float(risk["future_risk_score"]) > 0.72:
        anomaly_labels.append("risk_threshold_visual_review")
    if not anomaly_labels:
        anomaly_labels.append("nominal_surface_texture")

    confidence = _clamp(0.58 + float(risk["future_risk_score"]) * 0.25 + len(anomaly_labels) * 0.035, 0.55, 0.9)
    return {
        "source": "synthetic_visual_mock",
        "frame_id": f"{simulation_id}-CYCLE-{cycle:03d}",
        "anomaly_labels": anomaly_labels,
        "confidence": round(confidence, 3),
        "ultralytics_dry_run": True,
        "hardware_camera_used": False,
    }


def _choose_action(sensor: dict[str, Any], risk: dict[str, Any], state: TwinState, policy: str) -> dict[str, Any]:
    reason_codes: list[str] = []
    risk_score = float(risk["future_risk_score"])
    do_value = float(sensor["do"])
    co2 = float(sensor["co2"])
    temperature = float(sensor["temperature"])

    if policy == "growth_optimized":
        if do_value < 4.2 or co2 > 1125:
            action = "aerate"
            reason_codes.append("growth_guardrail_air_quality")
            intensity = 0.55
        elif temperature > 32.5:
            action = "cool"
            reason_codes.append("growth_guardrail_temperature")
            intensity = 0.45
        elif risk_score > 0.86:
            action = "request_human_review"
            reason_codes.append("growth_policy_risk_ceiling")
            intensity = 1.0
        else:
            action = "feed"
            reason_codes.append("biomass_gain_priority")
            intensity = 0.85 if state.substrate < 6.5 else 0.65
    elif policy == "risk_minimizing":
        if risk_score > 0.74:
            action = "request_human_review"
            reason_codes.append("risk_minimizing_review_threshold")
            intensity = 1.0
        elif do_value < 5.8 or co2 > 780:
            action = "aerate"
            reason_codes.append("risk_minimizing_air_quality")
            intensity = 0.9
        elif temperature > 29.4:
            action = "cool"
            reason_codes.append("risk_minimizing_temperature")
            intensity = 0.85
        elif state.substrate < 2.8:
            action = "feed"
            reason_codes.append("risk_minimizing_substrate_floor")
            intensity = 0.25
        else:
            action = "aerate"
            reason_codes.append("preventive_risk_reduction")
            intensity = 0.35
    elif policy == "conservative":
        if do_value < 5.3 or co2 > 850:
            action = "aerate"
            reason_codes.append("conservative_air_quality")
            intensity = 0.75
        elif temperature > 30.2:
            action = "cool"
            reason_codes.append("conservative_temperature")
            intensity = 0.7
        elif risk_score > 0.68:
            action = "request_human_review"
            reason_codes.append("conservative_risk_threshold")
            intensity = 1.0
        elif state.substrate < 3.6:
            action = "feed"
            reason_codes.append("conservative_substrate_floor")
            intensity = 0.4
        else:
            action = "feed"
            reason_codes.append("conservative_growth_support")
            intensity = 0.18
    elif do_value < 4.8 or co2 > 950:
        action = "aerate"
        if do_value < 4.8:
            reason_codes.append("low_do")
        if co2 > 950:
            reason_codes.append("rising_co2")
        intensity = 0.7
    elif temperature > 31.0:
        action = "cool"
        reason_codes.append("temperature_high")
        intensity = 0.6
    elif state.substrate < 4.0:
        action = "feed"
        reason_codes.append("substrate_low")
        intensity = 0.55
    elif risk_score > 0.72:
        action = "request_human_review"
        reason_codes.append("risk_threshold")
        intensity = 1.0
    else:
        action = "feed"
        reason_codes.append("nominal_growth_support")
        intensity = 0.25

    return {
        "policy": policy,
        "recommended_action": action,
        "intensity": round(intensity, 2),
        "duration_minutes": 15 if action in {"aerate", "cool"} else 5,
        "reason_codes": reason_codes,
        "confidence": round(_clamp(0.82 - risk_score * 0.18, 0.55, 0.92), 3),
        "expected_risk_reduction": round(0.04 + intensity * 0.14, 3),
    }


def _simulate_actuator(action: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    name = action["recommended_action"]
    intensity = float(action["intensity"])
    if name == "aerate":
        effects = {"feed_rate": 0.0, "ventilation": 0.16 * intensity, "heating": -0.015 * intensity}
        expected = {"do": "+0.6", "co2": "-120", "temperature": "-0.2"}
    elif name == "cool":
        effects = {"feed_rate": 0.0, "ventilation": 0.1 * intensity, "heating": -0.08 * intensity}
        expected = {"temperature": "-0.8", "moisture": "-0.1"}
    elif name == "feed":
        effects = {"feed_rate": 0.035 * intensity, "ventilation": 0.03, "heating": 0.0}
        expected = {"substrate": "+0.2", "biomass": "+0.03"}
    else:
        effects = {"feed_rate": 0.0, "ventilation": 0.0, "heating": 0.0}
        expected = {"operator_review": "requested"}

    return (
        {
            "action": name,
            "status": "simulated_success" if name != "request_human_review" else "review_requested",
            "expected_effect": expected,
            "actual_effect": expected,
            "hardware_execution": False,
        },
        effects,
    )


def run_simulation_lab(config: SimulationLabConfig) -> dict[str, Any]:
    rng = random.Random(config.seed)
    state = TwinState(**config.initial_state)
    twin_config = TwinConfig(T_env=config.initial_state["temperature"], M_env=config.initial_state["moisture"])
    start_time = datetime.now(timezone.utc).replace(microsecond=0)
    cycles: list[dict[str, Any]] = []

    previous_c_signal_hat: float | None = None
    previous_elapsed_hours: float | None = None
    previous_dc_dt_hat: float | None = None
    negative_slope_streak = 0

    for cycle in range(1, config.cycles + 1):
        timestamp = start_time + timedelta(hours=(cycle - 1) * config.cycle_hours)
        state_before = _state_dict(state)
        predicted = predict_step(state, _scenario_inputs(config.scenario, cycle, config.cycles), twin_config, dt=config.cycle_hours)
        sensor = _synthesize_sensor(rng, state=predicted.state, scenario=config.scenario, cycle=cycle, timestamp=timestamp)
        sensor["simulation_id"] = config.simulation_id

        supervisor = evaluate_bos_supervisor_state(
            uv254=None,
            od280=None,
            do_value=float(sensor["do"]),
            ph=float(sensor["ph"]),
            elapsed_hours=(cycle - 1) * config.cycle_hours,
            previous_c_signal_hat=previous_c_signal_hat,
            previous_elapsed_hours=previous_elapsed_hours,
            previous_dc_dt_hat=previous_dc_dt_hat,
            previous_negative_slope_streak=negative_slope_streak,
        )
        previous_c_signal_hat = supervisor.c_signal_hat
        previous_elapsed_hours = (cycle - 1) * config.cycle_hours
        previous_dc_dt_hat = supervisor.dc_dt_hat
        negative_slope_streak = supervisor.negative_slope_streak

        updated = update_step(
            predicted.state,
            {"weight": sensor["weight"], "temperature": sensor["temperature"], "moisture": sensor["moisture"]},
            twin_config,
        )
        risk = _risk_prediction(sensor, updated.state, config.scenario)
        visual_observation = _synthesize_visual_observation(
            simulation_id=config.simulation_id,
            cycle=cycle,
            sensor=sensor,
            risk=risk,
        )
        action = _choose_action(sensor, risk, updated.state, config.policy)
        actuator_result, actuator_inputs = _simulate_actuator(action)
        state = predict_step(updated.state, actuator_inputs, twin_config, dt=config.cycle_hours).state

        supervisor_payload = {
            "c_signal_hat": round(supervisor.c_signal_hat, 4),
            "dc_dt_hat": round(supervisor.dc_dt_hat, 4) if supervisor.dc_dt_hat is not None else None,
            "confidence": round(supervisor.confidence, 3),
            "missing_channels": supervisor.missing_channels,
            "channels_used": supervisor.channels_used,
            "recommended_handover": supervisor.recommended_handover,
            "trigger_reason": supervisor.trigger_reason,
            "observability_score": round(supervisor.observability_score, 3),
            "information_loss": round(supervisor.information_loss, 3),
        }
        audit_event = {
            "simulation_id": config.simulation_id,
            "cycle": cycle,
            "recorded_at": timestamp.isoformat(),
            "event_type": "simulation_lab_cycle",
            "policy": config.policy,
            "evidence_chain": [
                "virtual_batch",
                "synthetic_sensor",
                "synthetic_visual_observation",
                "supervisor_decision",
                "risk_proxy",
                "virtual_actuator",
                "digital_twin_update",
            ],
            "hardware_execution": False,
            "operator_review_required": action["recommended_action"] == "request_human_review",
            "visual_observation": visual_observation,
        }

        cycles.append(
            {
                "cycle": cycle,
                "timestamp": timestamp,
                "state_before": state_before,
                "sensor_observation": sensor,
                "supervisor_decision": supervisor_payload,
                "risk_prediction": risk,
                "visual_observation": visual_observation,
                "agent_action": action,
                "actuator_result": actuator_result,
                "state_after": _state_dict(state),
                "audit_event": audit_event,
            }
        )

    risks = [float(cycle["risk_prediction"]["future_risk_score"]) for cycle in cycles]
    summary = {
        "simulation_id": config.simulation_id,
        "cycle_count": len(cycles),
        "scenario": config.scenario,
        "policy": config.policy,
        "starting_risk": round(risks[0], 3),
        "ending_risk": round(risks[-1], 3),
        "risk_delta": round(risks[-1] - risks[0], 3),
        "action_count": len(cycles),
        "audit_event_count": len(cycles),
        "final_state": cycles[-1]["state_after"] if cycles else _state_dict(state),
    }
    return {"summary": summary, "cycles": cycles}
