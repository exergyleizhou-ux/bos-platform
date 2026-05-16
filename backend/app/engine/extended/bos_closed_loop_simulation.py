"""
Closed-loop simulation helpers for BOS + PhyAgentOS-style protocol evidence.

This module intentionally stays separate from the persisted BOS release flow.
It provides a deterministic, in-memory simulation harness that can be used for
paper evidence, demonstrations, and protocol-chain inspection without
pretending to be a production deployment trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
from typing import Any

from app.engine.bos_mechanistic_engine import compute_c_di_ser
from app.engine.digital_twin_engine import TwinConfig, TwinState, predict_step, update_step


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class ClosedLoopSimulationConfig:
    num_cycles: int = 5
    seed: int = 7
    feed_amount_g: float = 25.0
    response_time_floor_ms: float = 32.0
    response_time_ceiling_ms: float = 48.0
    watchdog_probability: float = 0.05
    cycle_hours: float = 1.0
    task_name: str = "feed_larvae"


def _simulate_protocol_execution(
    rng: random.Random,
    *,
    batch_code: str,
    cycle: int,
    feed_amount_g: float,
    task_name: str,
    density: float,
    temperature: float,
    moisture: float,
    config: ClosedLoopSimulationConfig,
) -> dict[str, Any]:
    response_time_ms = round(
        rng.uniform(config.response_time_floor_ms, config.response_time_ceiling_ms),
        1,
    )
    watchdog_triggered = rng.random() < config.watchdog_probability

    return {
        "mode": "simulation",
        "status": "success",
        "task": task_name,
        "batch_id": batch_code,
        "cycle": cycle,
        "command": {
            "amount_g": round(feed_amount_g, 2),
            "target_density": round(density, 3),
        },
        "response_time_ms": response_time_ms,
        "watchdog_triggered": watchdog_triggered,
        "watchdog_status": "tripped" if watchdog_triggered else "nominal",
        "sensor_feedback": {
            "temperature_C": round(temperature, 2),
            "moisture_pct": round(moisture, 2),
            "larvae_density": round(density, 3),
        },
        "protocol_trace": [
            "ACTION.md emitted",
            "watchdog polled",
            "driver executed",
            "ENVIRONMENT.md refreshed",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_closed_loop_simulation(
    *,
    batch_code: str,
    species: str,
    substrate: str | None = None,
    dm_in: float | None = None,
    dm_out: float | None = None,
    temperature: float | None = None,
    moisture: float | None = None,
    density: float | None = None,
    mechanistic_context: dict[str, Any] | None = None,
    config: ClosedLoopSimulationConfig | None = None,
) -> dict[str, Any]:
    simulation_config = config or ClosedLoopSimulationConfig()
    rng = random.Random(simulation_config.seed)

    measured_temperature = float(temperature) if temperature is not None else 28.0
    measured_moisture = float(moisture) if moisture is not None else 70.0
    measured_density = float(density) if density is not None else 1.0
    initial_substrate = max(float(dm_in) if dm_in is not None else 10.0, 0.1)
    estimated_biomass = max((float(dm_out) if dm_out is not None else initial_substrate * 0.2), 0.1)

    twin_config = TwinConfig(T_env=measured_temperature, M_env=measured_moisture)
    twin_state = TwinState(
        biomass=estimated_biomass,
        substrate=initial_substrate,
        temperature=measured_temperature,
        moisture=measured_moisture,
        nitrogen=50.0,
    )

    mechanistic_payload = mechanistic_context if isinstance(mechanistic_context, dict) else {}
    c_di_ser_context = mechanistic_payload.get("c_di_ser") or {}
    baseline_information_loss = float(c_di_ser_context.get("information_loss", 0.12))

    cycles: list[dict[str, Any]] = []
    response_times_ms: list[float] = []
    watchdog_events = 0

    for cycle_index in range(1, simulation_config.num_cycles + 1):
        density_delta = rng.uniform(-0.08, 0.08)
        stage = rng.choice(["L2", "L3", "prepupae"])
        vision_density = round(_clamp(measured_density + density_delta, 0.65, 1.35), 3)
        predicted_feed_rate = max(simulation_config.feed_amount_g / 1000.0, 0.001)

        predicted_step = predict_step(
            twin_state,
            {
                "feed_rate": predicted_feed_rate,
                "ventilation": round(rng.uniform(0.05, 0.18), 3),
                "heating": round(rng.uniform(0.0, 0.12), 3),
            },
            twin_config,
            dt=simulation_config.cycle_hours,
        )

        observed_weight = predicted_step.state.biomass + predicted_step.state.substrate + rng.uniform(-0.15, 0.15)
        observed_temperature = predicted_step.state.temperature + rng.uniform(-0.4, 0.4)
        observed_moisture = predicted_step.state.moisture + rng.uniform(-1.2, 1.2)
        updated_step = update_step(
            predicted_step.state,
            {
                "weight": observed_weight,
                "temperature": observed_temperature,
                "moisture": observed_moisture,
            },
            twin_config,
        )
        twin_state = updated_step.state

        d_prime = _clamp(predicted_step.ser_instantaneous, 0.05, 1.5)
        g_prime = _clamp(
            0.45 + (twin_state.substrate / max(initial_substrate, 1e-6)) * 0.4,
            0.1,
            1.2,
        )
        information_loss = _clamp(baseline_information_loss + abs(density_delta) * 0.6, 0.0, 0.95)
        ser_diagnostics = compute_c_di_ser(
            d_prime=d_prime,
            g_prime=g_prime,
            information_loss=information_loss,
        )

        protocol_execution = _simulate_protocol_execution(
            rng,
            batch_code=batch_code,
            cycle=cycle_index,
            feed_amount_g=simulation_config.feed_amount_g,
            task_name=simulation_config.task_name,
            density=vision_density,
            temperature=observed_temperature,
            moisture=observed_moisture,
            config=simulation_config,
        )
        response_times_ms.append(protocol_execution["response_time_ms"])
        watchdog_events += int(protocol_execution["watchdog_triggered"])

        cycles.append(
            {
                "cycle": cycle_index,
                "ser": {
                    "score": ser_diagnostics.c_di_ser,
                    "alpha_s": ser_diagnostics.alpha_s,
                    "beta_s": ser_diagnostics.beta_s,
                    "information_loss": ser_diagnostics.information_loss,
                },
                "vision": {
                    "larvae_count": int(round(100 * vision_density)),
                    "density": vision_density,
                    "stage": stage,
                },
                "prediction": {
                    "decomp_72h_percent": round(_clamp(74 + predicted_step.ser_instantaneous * 10, 60, 95), 1),
                    "instantaneous_ser_proxy": predicted_step.ser_instantaneous,
                    "growth_rate": predicted_step.growth_rate,
                },
                "digital_twin": {
                    "biomass": round(twin_state.biomass, 4),
                    "substrate": round(twin_state.substrate, 4),
                    "temperature": round(twin_state.temperature, 3),
                    "moisture": round(twin_state.moisture, 3),
                    "innovation": updated_step.innovation or [],
                },
                "phy_execution": protocol_execution,
                "audit": {
                    "mode": "simulation",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "module": "closed_loop_simulation",
                    "assumption_profile": {
                        "seed": simulation_config.seed,
                        "cycle_hours": simulation_config.cycle_hours,
                        "watchdog_probability": simulation_config.watchdog_probability,
                    },
                },
            }
        )

    avg_response_time_ms = sum(response_times_ms) / max(len(response_times_ms), 1)
    ser_scores = [cycle["ser"]["score"] for cycle in cycles]

    return {
        "mode": "simulation",
        "batch": {
            "batch_id": batch_code,
            "species": species,
            "substrate": substrate,
        },
        "configuration": {
            "num_cycles": simulation_config.num_cycles,
            "seed": simulation_config.seed,
            "task_name": simulation_config.task_name,
            "feed_amount_g": simulation_config.feed_amount_g,
        },
        "summary": {
            "cycle_count": len(cycles),
            "avg_response_time_ms": round(avg_response_time_ms, 3),
            "max_response_time_ms": round(max(response_times_ms), 3),
            "watchdog_event_count": watchdog_events,
            "ser_min": round(min(ser_scores), 4),
            "ser_max": round(max(ser_scores), 4),
        },
        "cycles": cycles,
        "disclaimer": (
            "This endpoint returns in-memory simulation evidence for protocol-chain "
            "inspection. It is not a persisted industrial runtime trace."
        ),
    }


def build_closed_loop_table_rows(simulation_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten cycle outputs into supplementary-table-friendly rows."""
    batch = simulation_result.get("batch") or {}
    rows: list[dict[str, Any]] = []
    for cycle in simulation_result.get("cycles") or []:
        ser = cycle.get("ser") or {}
        vision = cycle.get("vision") or {}
        prediction = cycle.get("prediction") or {}
        digital_twin = cycle.get("digital_twin") or {}
        phy_execution = cycle.get("phy_execution") or {}
        sensor_feedback = phy_execution.get("sensor_feedback") or {}
        audit = cycle.get("audit") or {}

        rows.append(
            {
                "batch_id": batch.get("batch_id"),
                "species": batch.get("species"),
                "cycle": cycle.get("cycle"),
                "ser_score": ser.get("score"),
                "ser_information_loss": ser.get("information_loss"),
                "larvae_count": vision.get("larvae_count"),
                "larvae_density": vision.get("density"),
                "stage": vision.get("stage"),
                "decomp_72h_percent": prediction.get("decomp_72h_percent"),
                "instantaneous_ser_proxy": prediction.get("instantaneous_ser_proxy"),
                "growth_rate": prediction.get("growth_rate"),
                "twin_biomass": digital_twin.get("biomass"),
                "twin_substrate": digital_twin.get("substrate"),
                "twin_temperature": digital_twin.get("temperature"),
                "twin_moisture": digital_twin.get("moisture"),
                "response_time_ms": phy_execution.get("response_time_ms"),
                "watchdog_triggered": phy_execution.get("watchdog_triggered"),
                "watchdog_status": phy_execution.get("watchdog_status"),
                "sensor_temperature_C": sensor_feedback.get("temperature_C"),
                "sensor_moisture_pct": sensor_feedback.get("moisture_pct"),
                "sensor_larvae_density": sensor_feedback.get("larvae_density"),
                "audit_mode": audit.get("mode"),
                "audit_recorded_at": audit.get("recorded_at"),
            }
        )
    return rows
