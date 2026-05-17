"""Phase A — strict SFI schema unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.sfi import (
    Action,
    AxisStatus,
    ForecastBreach,
    KDecayBand,
    SCHEMA_VERSION,
    SetpointProfile,
    SfiCheckRequest,
    SfiCheckResponse,
    SfiMeasurements,
)


# ---- baseline fixtures ------------------------------------------------


def _measurements(**overrides) -> dict:
    m = dict(
        temperature_c=28.0,
        moisture_pct=65.0,
        density_kg_m3=680.0,
        ph=6.8,
        ammonia_ppm=120.0,
        oxygen_pct=19.5,
        co2_pct=2.5,
    )
    m.update(overrides)
    return m


def _payload(**overrides) -> dict:
    p = dict(
        species_code="BSF_LARVA",
        measurements=_measurements(),
        horizon_hours=24,
    )
    p.update(overrides)
    return p


def _k_band(**overrides) -> dict:
    k = dict(point=0.045, low=0.030, high=0.060, source="literature")
    k.update(overrides)
    return k


# ---- schema version ---------------------------------------------------


def test_schema_version_constant():
    assert SCHEMA_VERSION == "A.2"


# ---- request happy paths ----------------------------------------------


def test_valid_input_passes():
    req = SfiCheckRequest(**_payload())
    assert req.species_code == "BSF_LARVA"
    assert req.horizon_hours == 24
    assert req.k_decay_band is None


def test_request_with_k_decay_and_substrate_passes():
    req = SfiCheckRequest(
        **_payload(k_decay_band=_k_band(), s0=120.0, s_min=10.0)
    )
    assert req.k_decay_band.source == "literature"
    assert req.s0 == 120.0


# ---- measurements range constraints -----------------------------------


def test_temperature_out_of_range_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(temperature_c=200.0)))


def test_temperature_too_cold_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(temperature_c=-50.0)))


def test_moisture_over_100_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(moisture_pct=110.0)))


def test_ph_out_of_range_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(ph=15.0)))


def test_density_zero_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(density_kg_m3=0.0)))


def test_ammonia_negative_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(measurements=_measurements(ammonia_ppm=-1.0)))


# ---- KDecayBand validators --------------------------------------------


def test_k_decay_band_inconsistent_rejected():
    """low > high should fail @model_validator."""
    with pytest.raises(ValidationError, match="low <= point <= high"):
        SfiCheckRequest(
            **_payload(k_decay_band=_k_band(point=0.05, low=0.08, high=0.06))
        )


def test_k_decay_band_point_outside_band_rejected():
    with pytest.raises(ValidationError, match="low <= point <= high"):
        SfiCheckRequest(
            **_payload(k_decay_band=_k_band(point=0.07, low=0.03, high=0.05))
        )


def test_k_decay_band_zero_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(k_decay_band=_k_band(point=0.0)))


def test_k_decay_band_unknown_source_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(k_decay_band=_k_band(source="guess")))


# ---- horizon constraints ---------------------------------------------


def test_horizon_zero_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(horizon_hours=0))


def test_horizon_over_720_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(horizon_hours=721))


# ---- setpoint profile constraints ------------------------------------


def test_setpoint_tolerance_over_100_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(
            **_payload(setpoint_profile={"target_state": {"temperature_c": 28.0},
                                         "tolerance_pct": 150.0})
        )


def test_setpoint_empty_target_state_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(
            **_payload(setpoint_profile={"target_state": {}, "tolerance_pct": 10.0})
        )


# ---- substrate pair validation ---------------------------------------


def test_s0_without_s_min_rejected():
    with pytest.raises(ValidationError, match="must be provided together"):
        SfiCheckRequest(**_payload(s0=100.0))


def test_s_min_ge_s0_rejected():
    with pytest.raises(ValidationError, match="strictly less than s0"):
        SfiCheckRequest(**_payload(s0=10.0, s_min=10.0))


# ---- species code pattern --------------------------------------------


def test_species_code_pattern_invalid_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(species_code="bsf larva"))


# ---- extra-fields-forbidden ------------------------------------------


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        SfiCheckRequest(**_payload(rogue="oops"))


# ---- response invariants ---------------------------------------------


def test_response_composite_score_in_unit_interval():
    SfiCheckResponse(
        sfi_pass=True,
        zone="safe",
        composite_score=0.85,
        per_axis={
            "temperature_c": AxisStatus(
                axis="temperature_c", value=28.0, unit="degC",
                status="pass", margin_to_breach=5.0,
            )
        },
        evidence_level="supported",
        engine_version="9.0.0",
    )


def test_response_composite_score_over_one_rejected():
    with pytest.raises(ValidationError):
        SfiCheckResponse(
            sfi_pass=True,
            zone="safe",
            composite_score=1.5,
            per_axis={},
            evidence_level="supported",
            engine_version="9.0.0",
        )


def test_response_zone_literal_only():
    with pytest.raises(ValidationError):
        SfiCheckResponse(
            sfi_pass=False,
            zone="explosion",  # not in Literal set
            composite_score=0.0,
            per_axis={},
            evidence_level="planned",
            engine_version="9.0.0",
        )


def test_response_engine_version_pattern():
    with pytest.raises(ValidationError):
        SfiCheckResponse(
            sfi_pass=True,
            zone="safe",
            composite_score=0.9,
            per_axis={},
            evidence_level="supported",
            engine_version="v9",
        )


def test_action_urgency_literal_only():
    with pytest.raises(ValidationError):
        Action(action_type="cool_down", urgency="emergency", description="x")


def test_action_type_literal_only():
    with pytest.raises(ValidationError):
        Action(action_type="meditate", urgency="low", description="x")
