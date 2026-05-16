from app.engine.bos_simulation_lab import SimulationLabConfig, run_simulation_lab
from app.services import simulation_lab_service
from app.services.chronos_risk_service import ChronosRiskForecast


def _config(seed: int = 42) -> SimulationLabConfig:
    return SimulationLabConfig(
        simulation_id="SIM-UNIT-001",
        batch_id="VIRTUAL-BSF-001",
        species="BSF",
        feedstock="mixed_food_waste",
        scenario="moisture_drift",
        initial_state={
            "biomass": 0.5,
            "substrate": 10.0,
            "temperature": 28.0,
            "moisture": 70.0,
            "nitrogen": 50.0,
        },
        cycles=8,
        seed=seed,
    )


def _config_for_policy(policy: str, seed: int = 42) -> SimulationLabConfig:
    return SimulationLabConfig(
        simulation_id=f"SIM-UNIT-{policy}",
        batch_id="VIRTUAL-BSF-001",
        species="BSF",
        feedstock="mixed_food_waste",
        scenario="temperature_spike",
        initial_state={
            "biomass": 0.5,
            "substrate": 10.0,
            "temperature": 28.0,
            "moisture": 70.0,
            "nitrogen": 50.0,
        },
        cycles=8,
        seed=seed,
        policy=policy,
    )


def test_simulation_lab_outputs_complete_cycle_trace():
    result = run_simulation_lab(_config())

    assert result["summary"]["cycle_count"] == 8
    assert result["summary"]["audit_event_count"] == 8
    assert result["summary"]["scenario"] == "moisture_drift"
    assert len(result["cycles"]) == 8

    first_cycle = result["cycles"][0]
    assert {
        "state_before",
        "sensor_observation",
        "supervisor_decision",
        "risk_prediction",
        "agent_action",
        "actuator_result",
        "state_after",
        "audit_event",
    }.issubset(first_cycle)
    assert first_cycle["sensor_observation"]["sensor_quality"] == "synthetic"
    assert first_cycle["agent_action"]["recommended_action"] in {
        "feed",
        "aerate",
        "cool",
        "request_human_review",
    }
    assert first_cycle["actuator_result"]["hardware_execution"] is False
    assert "digital_twin_update" in first_cycle["audit_event"]["evidence_chain"]


def test_simulation_lab_is_deterministic_for_risk_and_actions():
    first = run_simulation_lab(_config(seed=99))
    second = run_simulation_lab(_config(seed=99))

    first_projection = [
        (
            cycle["sensor_observation"]["temperature"],
            cycle["sensor_observation"]["moisture"],
            cycle["risk_prediction"]["future_risk_score"],
            cycle["agent_action"]["recommended_action"],
            cycle["state_after"],
        )
        for cycle in first["cycles"]
    ]
    second_projection = [
        (
            cycle["sensor_observation"]["temperature"],
            cycle["sensor_observation"]["moisture"],
            cycle["risk_prediction"]["future_risk_score"],
            cycle["agent_action"]["recommended_action"],
            cycle["state_after"],
        )
        for cycle in second["cycles"]
    ]

    assert first_projection == second_projection


def test_simulation_lab_policy_runs_are_deterministic():
    first = run_simulation_lab(_config_for_policy("growth_optimized", seed=123))
    second = run_simulation_lab(_config_for_policy("growth_optimized", seed=123))

    assert first["summary"]["policy"] == "growth_optimized"
    assert [
        (
            cycle["agent_action"]["recommended_action"],
            cycle["agent_action"]["intensity"],
            cycle["state_after"],
        )
        for cycle in first["cycles"]
    ] == [
        (
            cycle["agent_action"]["recommended_action"],
            cycle["agent_action"]["intensity"],
            cycle["state_after"],
        )
        for cycle in second["cycles"]
    ]


def test_simulation_lab_policies_change_action_profile():
    policies = ["rule_based", "conservative", "growth_optimized", "risk_minimizing"]
    profiles = {
        policy: tuple(
            (cycle["agent_action"]["recommended_action"], cycle["agent_action"]["intensity"])
            for cycle in run_simulation_lab(_config_for_policy(policy, seed=55))["cycles"]
        )
        for policy in policies
    }

    assert len(set(profiles.values())) > 1
    assert all(
        cycle["agent_action"]["policy"] == policy
        for policy in policies
        for cycle in run_simulation_lab(_config_for_policy(policy, seed=55))["cycles"]
    )


def test_simulation_lab_risk_prediction_includes_deterministic_fallback_contract():
    result = run_simulation_lab(_config())
    risk = result["cycles"][0]["risk_prediction"]

    assert risk["source"] == "deterministic_proxy"
    assert risk["execution_mode"] == "fallback"
    assert risk["confidence_band"]["lower"] <= risk["confidence_band"]["median"] <= risk["confidence_band"]["upper"]


def test_simulation_lab_outputs_visual_observation_mock():
    result = run_simulation_lab(_config())
    first_cycle = result["cycles"][0]

    visual = first_cycle["visual_observation"]
    assert visual["source"] == "synthetic_visual_mock"
    assert visual["frame_id"] == "SIM-UNIT-001-CYCLE-001"
    assert visual["ultralytics_dry_run"] is True
    assert visual["hardware_camera_used"] is False
    assert visual["anomaly_labels"]
    assert "synthetic_visual_observation" in first_cycle["audit_event"]["evidence_chain"]
    assert first_cycle["audit_event"]["visual_observation"] == visual


def test_simulation_lab_service_adds_labsim_sludge_governance_sources():
    profile = simulation_lab_service._labsim_profile(
        species="BSF",
        feedstock="municipal_sludge_heavy_metal_screen",
    )
    sources = simulation_lab_service._labsim_scenario_sources(
        species="BSF",
        feedstock="municipal_sludge_heavy_metal_screen",
    )

    assert profile["profile_id"] == "bsf_sludge_heavy_metal_redline"
    assert profile["heavy_metal_gate"] == "redline"
    assert profile["product_use_lock"] == "research_simulation_only"
    assert any(source["field"] == "heavy_metal_gate" for source in sources)
    assert any(source["source_kind"] == "official_standard" for source in sources)


def test_simulation_lab_service_builds_labsim_assay_comparison():
    profile = simulation_lab_service._labsim_profile(species="BSF", feedstock="distillers_grain")
    comparison = simulation_lab_service._labsim_assay_comparison(
        cycle_payload={
            "state_after": {
                "biomass": 1.02,
                "substrate": 4.7,
                "moisture": 69.2,
            }
        },
        lab_profile=profile,
    )

    assert comparison["source_kind"] == "manuscript_campaign"
    assert comparison["source_ref"] == "labsim_assay_anchor:bsf_distillers_grain_lane"
    assert comparison["predicted"]["heavy_metal_index"] == profile["max_heavy_metal_risk"]
    assert comparison["measured_anchor"]["biomass"] == 1.08
    assert comparison["calibration_status"] in {"within_screening_band", "review_required"}


def test_simulation_lab_service_allows_operator_entered_assay_measurements():
    profile = simulation_lab_service._labsim_profile(species="BSF", feedstock="distillers_grain")
    comparison = simulation_lab_service._labsim_assay_comparison(
        cycle_payload={
            "state_after": {
                "biomass": 0.91,
                "substrate": 4.4,
                "moisture": 66.8,
            }
        },
        lab_profile=profile,
        measurements={
            "biomass": 0.9,
            "substrate": 4.5,
            "moisture": 67.0,
            "heavy_metal_index": 0.11,
        },
    )

    assert comparison["measurement_mode"] == "operator_entered"
    assert comparison["source_ref"] == "operator_entered_lab_assay_measurements"
    assert comparison["measured_anchor"]["biomass"] == 0.9
    assert comparison["measured_anchor"]["heavy_metal_index"] == 0.11


def test_simulation_lab_service_extracts_reference_assay_measurements():
    measurements = simulation_lab_service._reference_lab_assay_measurements(
        {
            "observed_outputs": {
                "lab_assay_measurements": {
                    "biomass": 0.93,
                    "substrate": 4.25,
                    "moisture": 66.4,
                    "heavy_metal_index": 12.0,
                },
            },
        }
    )

    assert measurements == {
        "biomass": 0.93,
        "substrate": 4.25,
        "moisture": 66.4,
        "heavy_metal_index": 0.12,
    }


def test_simulation_lab_chronos_success_enriches_risk_contract(monkeypatch):
    def fake_forecast_with_chronos_or_fallback(**_kwargs):
        return ChronosRiskForecast(
            model_name="chronos_bolt",
            execution_mode="chronos_bolt_live",
            fallback_used=False,
            forecast=[0.4, 0.42, 0.44],
            confidence_band=(0.35, 0.5),
            warnings=[],
            raw_result={},
        )

    monkeypatch.setattr(simulation_lab_service, "forecast_with_chronos_or_fallback", fake_forecast_with_chronos_or_fallback)

    result = simulation_lab_service._apply_chronos_risk_contract(run_simulation_lab(_config()))
    risk = result["cycles"][0]["risk_prediction"]

    assert risk["source"] == "chronos"
    assert risk["execution_mode"] == "chronos_bolt_live"
    assert risk["model_name"] == "chronos_bolt"
    assert risk["confidence_band"]["median"] == risk["future_risk_score"]
    assert risk["deterministic_fallback"]["future_risk_score"] > 0


def test_simulation_lab_chronos_failure_preserves_deterministic_proxy(monkeypatch):
    def failing_forecast(**_kwargs):
        raise RuntimeError("chronos offline")

    monkeypatch.setattr(simulation_lab_service, "forecast_with_chronos_or_fallback", failing_forecast)

    base = run_simulation_lab(_config())
    original_score = base["cycles"][0]["risk_prediction"]["future_risk_score"]
    result = simulation_lab_service._apply_chronos_risk_contract(base)
    risk = result["cycles"][0]["risk_prediction"]

    assert risk["source"] == "deterministic_proxy"
    assert risk["execution_mode"] == "fallback"
    assert risk["future_risk_score"] == original_score
    assert "Chronos adapter failed" in risk["chronos_warning"]
