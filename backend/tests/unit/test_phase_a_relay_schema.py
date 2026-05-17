"""Phase A — strict Relay schema unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.relay import (
    BoundaryLedger,
    ControlProfile,
    RelayConfig,
    RelayHealth,
    RelaySimulateRequest,
    RelaySimulateResponse,
    SCHEMA_VERSION,
    TwinSnapshot,
    TwinState,
    Warning as RelayWarning,
)
from app.schemas.sfi import KDecayBand
from app.schemas.ser import MonteCarloConfig


# ---- helpers ---------------------------------------------------------


def _state(**o) -> dict:
    base = dict(
        biomass_kg=0.5,
        substrate_kg=10.0,
        temperature_c=28.0,
        moisture_pct=70.0,
        nitrogen_g=50.0,
        signal_activity_au=100.0,
    )
    base.update(o)
    return base


def _config(**o) -> dict:
    base = dict(tau_m2_h=24.0, s0=100.0, s_min=10.0)
    base.update(o)
    return base


def _request(**o) -> dict:
    base = dict(
        initial_state=_state(),
        relay_config=_config(),
        horizon_steps=12,
        dt_hours=1.0,
        species_code="BSF_LARVA",
    )
    base.update(o)
    return base


# ---- schema version + happy paths -----------------------------------


def test_schema_version_constant():
    assert SCHEMA_VERSION == "A.3"


def test_valid_request_passes():
    req = RelaySimulateRequest(**_request())
    assert req.species_code == "BSF_LARVA"
    assert req.horizon_steps == 12


def test_valid_request_with_mc_and_k_band_passes():
    """k_decay_band reused from sfi schema; MonteCarloConfig from ser."""
    req = RelaySimulateRequest(
        **_request(
            relay_config=_config(
                k_decay_band={"point": 0.045, "low": 0.030, "high": 0.060,
                              "source": "literature"},
            ),
            monte_carlo={
                "n_samples": 1000,
                "seed": 42,
                "distributions": {"dm_in": {"kind": "normal", "mean": 10.0, "std": 0.5}},
            },
        )
    )
    assert isinstance(req.relay_config.k_decay_band, KDecayBand)
    assert isinstance(req.monte_carlo, MonteCarloConfig)


# ---- RelayConfig validators -----------------------------------------


def test_relay_config_s_min_geq_s0_rejected():
    with pytest.raises(ValidationError, match="s_min < s0"):
        RelaySimulateRequest(**_request(relay_config=_config(s0=10.0, s_min=10.0)))


def test_relay_config_negative_tau_m2_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(relay_config=_config(tau_m2_h=-1.0)))


def test_relay_config_tau_m2_over_720_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(relay_config=_config(tau_m2_h=721.0)))


def test_relay_config_zero_s0_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(relay_config=_config(s0=0.0, s_min=0.0)))


# ---- horizon / dt constraints ---------------------------------------


def test_horizon_steps_zero_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(horizon_steps=0))


def test_horizon_steps_over_10000_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(horizon_steps=10_001))


def test_dt_hours_zero_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(dt_hours=0.0))


def test_dt_hours_over_24_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(dt_hours=25.0))


def test_horizon_exceeds_5x_tau_max_rejected():
    """sim_hours > 5 * tau_max should raise via @model_validator.

    The validator was widened from 3× to 5× tau_max (A1.3 fix) so the
    k_decay violation detector can actually be exercised. 100 h is
    still well over 5× ≈ 23 h, so this test still trips the validator.
    """
    # tau_max = ln(100/10) / 0.5 ≈ 4.605 h; 5× ≈ 23.03 h; sim_hours = 100 h.
    with pytest.raises(ValidationError, match="exceeds 5 \\* tau_max"):
        RelaySimulateRequest(**_request(
            horizon_steps=100,
            dt_hours=1.0,
            relay_config=_config(
                k_decay_band={"point": 0.5, "low": 0.4, "high": 0.6,
                              "source": "fitted"},
            ),
        ))


# ---- TwinState range constraints ------------------------------------


def test_twin_state_negative_biomass_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(initial_state=_state(biomass_kg=-1.0)))


def test_twin_state_temperature_over_100_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(initial_state=_state(temperature_c=120.0)))


def test_twin_state_moisture_over_100_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(initial_state=_state(moisture_pct=110.0)))


# ---- ControlProfile ------------------------------------------------


def test_control_profile_tolerance_over_1_rejected():
    with pytest.raises(ValidationError):
        ControlProfile(
            profile_type="constant",
            setpoints={"feed_rate": 0.05},
            tolerance=1.5,
        )


def test_control_profile_profile_type_literal_only():
    with pytest.raises(ValidationError):
        ControlProfile(
            profile_type="quantum",
            setpoints={"feed_rate": 0.05},
        )


# ---- KDecayBand reuse from sfi --------------------------------------


def test_k_decay_band_reused_from_sfi():
    """RelayConfig.k_decay_band uses the exact same class as SfiCheckRequest."""
    from app.schemas.sfi import KDecayBand as SfiKBand
    from app.schemas.relay import RelayConfig as RC
    # Class identity check.
    field = RC.model_fields["k_decay_band"]
    # The inner annotation should be Optional[KDecayBand] from sfi.
    assert SfiKBand is KDecayBand
    # Construct via dict; ensure it materialises as the sfi type.
    cfg = RC(**_config(k_decay_band={"point": 0.05, "low": 0.04,
                                      "high": 0.06, "source": "fitted"}))
    assert isinstance(cfg.k_decay_band, SfiKBand)


# ---- extra-fields-forbidden ----------------------------------------


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(rogue="oops"))


def test_relay_config_extra_field_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateRequest(**_request(relay_config=_config(rogue="bad")))


# ---- Response constraints ------------------------------------------


def _minimal_response_kwargs(**o) -> dict:
    base = dict(
        trajectory=[TwinSnapshot(
            step_index=0, stage="M1", cumulative_time_h=1.0,
            state=TwinState(**_state()),
        )],
        boundary_ledger=[
            BoundaryLedger(stage=s, mass_in_kg=10.5, mass_out_kg=10.5,
                           mass_residual_kg=0.0, nitrogen_in_g=50.0,
                           nitrogen_out_g=50.0, nitrogen_residual_g=0.0,
                           closure_pct=99.0)
            for s in ("M1", "M2", "M3")
        ],
        relay_health=RelayHealth(
            overall_status="nominal",
            stage_completion={"M1": 1.0, "M2": 1.0, "M3": 1.0},
            sfi_check_passed_at_each_stage={"M1": True, "M2": True, "M3": True},
        ),
        final_ser=0.25,
        engine_version="9.0.0",
        evidence_level="supported",
    )
    base.update(o)
    return base


def test_response_final_ser_in_unit_interval():
    RelaySimulateResponse(**_minimal_response_kwargs())


def test_response_final_ser_over_one_rejected():
    with pytest.raises(ValidationError):
        RelaySimulateResponse(**_minimal_response_kwargs(final_ser=1.5))


def test_boundary_ledger_three_stages_required():
    with pytest.raises(ValidationError, match="M1, M2, M3"):
        RelaySimulateResponse(**_minimal_response_kwargs(
            boundary_ledger=[
                BoundaryLedger(stage="M1", mass_in_kg=1.0, mass_out_kg=1.0,
                               mass_residual_kg=0.0, nitrogen_in_g=0.0,
                               nitrogen_out_g=0.0, nitrogen_residual_g=0.0,
                               closure_pct=99.0),
                BoundaryLedger(stage="M2", mass_in_kg=1.0, mass_out_kg=1.0,
                               mass_residual_kg=0.0, nitrogen_in_g=0.0,
                               nitrogen_out_g=0.0, nitrogen_residual_g=0.0,
                               closure_pct=99.0),
                # missing M3
            ],
        ))


def test_boundary_ledger_wrong_order_rejected():
    with pytest.raises(ValidationError, match="M1, M2, M3"):
        RelaySimulateResponse(**_minimal_response_kwargs(
            boundary_ledger=[
                BoundaryLedger(stage="M2", mass_in_kg=1.0, mass_out_kg=1.0,
                               mass_residual_kg=0.0, nitrogen_in_g=0.0,
                               nitrogen_out_g=0.0, nitrogen_residual_g=0.0,
                               closure_pct=99.0),
                BoundaryLedger(stage="M1", mass_in_kg=1.0, mass_out_kg=1.0,
                               mass_residual_kg=0.0, nitrogen_in_g=0.0,
                               nitrogen_out_g=0.0, nitrogen_residual_g=0.0,
                               closure_pct=99.0),
                BoundaryLedger(stage="M3", mass_in_kg=1.0, mass_out_kg=1.0,
                               mass_residual_kg=0.0, nitrogen_in_g=0.0,
                               nitrogen_out_g=0.0, nitrogen_residual_g=0.0,
                               closure_pct=99.0),
            ],
        ))


def test_evidence_level_literal_values():
    with pytest.raises(ValidationError):
        RelaySimulateResponse(**_minimal_response_kwargs(evidence_level="unknown"))


def test_response_engine_version_pattern():
    with pytest.raises(ValidationError):
        RelaySimulateResponse(**_minimal_response_kwargs(engine_version="v9"))


def test_relay_health_overall_status_literal_only():
    with pytest.raises(ValidationError):
        RelayHealth(
            overall_status="broken",
            stage_completion={"M1": 1.0, "M2": 1.0, "M3": 1.0},
            sfi_check_passed_at_each_stage={"M1": True, "M2": True, "M3": True},
        )


def test_relay_warning_severity_literal_only():
    with pytest.raises(ValidationError):
        RelayWarning(code="x", severity="meh", message="bad")
