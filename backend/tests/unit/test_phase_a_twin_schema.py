"""Phase A — strict Twin /run schema unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.twin import (
    InnovationStats,
    SCHEMA_VERSION,
    TwinConfig,
    TwinInputStep,
    TwinObservation,
    TwinRunRequest,
    TwinRunResponse,
    TwinSnapshot,
    TwinState,
)


# ---- helpers --------------------------------------------------------


def _state(**o) -> dict:
    base = dict(
        biomass_kg=0.5,
        substrate_kg=10.0,
        temperature_c=28.0,
        moisture_pct=70.0,
        nitrogen_kg=0.05,
    )
    base.update(o)
    return base


def _inputs(n: int = 3, dt: float = 1.0) -> list[dict]:
    return [dict(dt_hours=dt, feed_rate_kg_h=0.05) for _ in range(n)]


def _payload(**o) -> dict:
    base = dict(
        initial_state=_state(),
        inputs=_inputs(3),
    )
    base.update(o)
    return base


# ---- version + happy paths -----------------------------------------


def test_schema_version_constant():
    assert SCHEMA_VERSION == "A.5"


def test_valid_request_passes():
    req = TwinRunRequest(**_payload())
    assert req.enable_ekf is True
    assert req.config.mu_max == 0.025
    assert len(req.inputs) == 3


def test_request_with_observations_passes():
    req = TwinRunRequest(**_payload(
        inputs=_inputs(2),
        observations=[
            {"weight_kg": 10.4, "temperature_c": 28.5, "moisture_pct": 69.0},
            {"weight_kg": 10.7, "temperature_c": 28.7, "moisture_pct": 68.5},
        ],
    ))
    assert req.observations is not None
    assert len(req.observations) == 2


# ---- TwinState range constraints -----------------------------------


def test_state_negative_biomass_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(initial_state=_state(biomass_kg=-1.0)))


def test_state_temperature_too_hot_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(initial_state=_state(temperature_c=120.0)))


def test_state_moisture_over_100_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(initial_state=_state(moisture_pct=110.0)))


def test_state_negative_nitrogen_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(initial_state=_state(nitrogen_kg=-0.01)))


# ---- TwinConfig range constraints ----------------------------------


def test_config_negative_mu_max_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(config={"mu_max": -0.1}))


def test_config_yield_over_one_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(config={"Y": 1.5}))


def test_config_extra_field_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(config={"rogue": 1.0}))


# ---- TwinInputStep range constraints -------------------------------


def test_input_dt_zero_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[dict(dt_hours=0.0)]))


def test_input_dt_over_24_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[dict(dt_hours=25.0)]))


def test_input_negative_feed_rate_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[
            dict(dt_hours=1.0, feed_rate_kg_h=-0.1)
        ]))


def test_input_extra_field_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[
            dict(dt_hours=1.0, rogue=1.0)
        ]))


# ---- inputs collection constraints ---------------------------------


def test_inputs_empty_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[]))


def test_inputs_over_10000_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(inputs=[dict(dt_hours=1.0)] * 10_001))


# ---- observations length validator ---------------------------------


def test_observations_length_mismatch_rejected():
    with pytest.raises(ValidationError, match="observations length"):
        TwinRunRequest(**_payload(
            inputs=_inputs(3),
            observations=[
                {"weight_kg": 10.4},
                {"weight_kg": 10.5},  # only 2 vs 3 inputs
            ],
        ))


def test_observations_none_does_not_raise():
    req = TwinRunRequest(**_payload(inputs=_inputs(3), observations=None))
    assert req.observations is None


def test_observation_extra_field_rejected():
    with pytest.raises(ValidationError):
        TwinObservation(weight_kg=10.0, rogue=1.0)


# ---- species_code pattern ------------------------------------------


def test_species_code_pattern_invalid_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(species_code="bsf larva"))


# ---- extra-fields-forbidden ----------------------------------------


def test_request_extra_field_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(rogue="oops"))


def test_state_extra_field_rejected():
    with pytest.raises(ValidationError):
        TwinRunRequest(**_payload(initial_state={**_state(), "rogue": 1.0}))


# ---- response invariants -------------------------------------------


def _minimal_response(**o) -> dict:
    base = dict(
        trajectory=[TwinSnapshot(
            step_index=0, cumulative_time_h=1.0,
            state=TwinState(**_state()),
        )],
        estimated_states=[TwinState(**_state())],
        final_state=TwinState(**_state()),
        innovation_stats=InnovationStats(n_updates=0),
        evidence_level="supported",
        engine_version="9.0.0",
    )
    base.update(o)
    return base


def test_response_valid_passes():
    TwinRunResponse(**_minimal_response())


def test_response_trajectory_estimated_length_mismatch_rejected():
    with pytest.raises(ValidationError, match="equal length"):
        TwinRunResponse(**_minimal_response(
            estimated_states=[TwinState(**_state()), TwinState(**_state())],
        ))


def test_response_engine_version_pattern():
    with pytest.raises(ValidationError):
        TwinRunResponse(**_minimal_response(engine_version="v9"))


def test_response_evidence_level_literal_only():
    with pytest.raises(ValidationError):
        TwinRunResponse(**_minimal_response(evidence_level="vibes"))
