"""Phase A — strict SER schema unit tests.

Coverage:
- Every Field range/pattern constraint has a positive + negative case.
- Both @model_validator triggers (mass conservation, N conservation).
- Both nested submodels (MonteCarloConfig / DistSpec) constraints.
- Response invariants (ser_point in [0,1], CI ordering).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ser import (
    DistSpec,
    McSummary,
    MonteCarloConfig,
    SCHEMA_VERSION,
    SerComputeRequest,
    SerComputeResponse,
)


# ---------- Phase A baseline fixture ------------------------------------


def _valid_payload(**overrides):
    payload = dict(
        dm_in=120.0,
        dm_out=36.0,
        n_in=2.8,
        n_rec=0.91,
        d_prime=0.72,
        g_prime=0.65,
        species_code="BSF_LARVA",
        feedstock_code="FOOD_WASTE_MIXED",
    )
    payload.update(overrides)
    return payload


# ---------- Sanity ------------------------------------------------------


def test_schema_version_constant():
    assert SCHEMA_VERSION == "A.1"


def test_valid_input_passes():
    req = SerComputeRequest(**_valid_payload())
    assert req.dm_in == 120.0
    assert req.species_code == "BSF_LARVA"
    assert req.monte_carlo is None


# ---------- Conservation @model_validators -------------------------------


def test_dm_out_exceeds_dm_in_rejected():
    with pytest.raises(ValidationError, match="mass conservation"):
        SerComputeRequest(**_valid_payload(dm_in=10.0, dm_out=11.0))


def test_n_rec_exceeds_n_in_rejected():
    with pytest.raises(ValidationError, match="N conservation"):
        SerComputeRequest(**_valid_payload(n_in=1.0, n_rec=2.0))


# ---------- Numeric range constraints -----------------------------------


def test_d_prime_over_one_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(d_prime=1.01))


def test_g_prime_over_one_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(g_prime=1.5))


def test_d_prime_negative_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(d_prime=-0.01))


def test_negative_n_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(n_in=-0.1))


def test_zero_dm_in_rejected():
    """Field(..., gt=0) — exactly zero must fail."""
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(dm_in=0.0))


def test_dm_in_over_1e6_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(dm_in=1e6 + 1))


def test_dm_out_zero_rejected():
    """dm_out is gt=0 (engine cannot return SER==0 from a degenerate)."""
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(dm_out=0.0))


# ---------- Species / feedstock pattern ---------------------------------


def test_species_code_pattern_invalid_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(species_code="bsf larva"))  # lowercase + space


def test_species_code_too_long_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(species_code="X" * 65))


def test_species_code_empty_rejected():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(species_code=""))


def test_feedstock_code_optional_omit_ok():
    payload = _valid_payload()
    payload.pop("feedstock_code")
    SerComputeRequest(**payload)


# ---------- MonteCarloConfig --------------------------------------------


def _mc(**overrides):
    cfg = dict(
        n_samples=10_000,
        seed=42,
        distributions={
            "dm_in": {"kind": "normal", "mean": 120.0, "std": 5.0},
            "dm_out": {"kind": "normal", "mean": 36.0, "std": 2.0},
        },
    )
    cfg.update(overrides)
    return cfg


def test_mc_n_samples_too_low_rejected():
    with pytest.raises(ValidationError):
        MonteCarloConfig(**_mc(n_samples=99))


def test_mc_n_samples_too_high_rejected():
    with pytest.raises(ValidationError):
        MonteCarloConfig(**_mc(n_samples=100_001))


def test_mc_negative_seed_rejected():
    with pytest.raises(ValidationError):
        MonteCarloConfig(**_mc(seed=-1))


def test_mc_distspec_unknown_kind_rejected():
    with pytest.raises(ValidationError):
        MonteCarloConfig(
            **_mc(distributions={"dm_in": {"kind": "cauchy", "mean": 1, "std": 1}})
        )


def test_mc_distspec_negative_std_rejected():
    with pytest.raises(ValidationError):
        MonteCarloConfig(
            **_mc(distributions={"dm_in": {"kind": "normal", "mean": 1, "std": -1}})
        )


def test_request_with_mc_block_passes():
    req = SerComputeRequest(**_valid_payload(monte_carlo=_mc()))
    assert req.monte_carlo is not None
    assert req.monte_carlo.n_samples == 10_000


# ---------- Response invariants -----------------------------------------


def test_response_ser_point_in_unit_interval():
    SerComputeResponse(
        ser_point=0.30,
        engine_version="9.0.0",
        evidence_level="supported",
    )


def test_response_ser_point_over_one_rejected():
    with pytest.raises(ValidationError):
        SerComputeResponse(
            ser_point=1.01,
            engine_version="9.0.0",
            evidence_level="supported",
        )


def test_response_ci_order_validated():
    with pytest.raises(ValidationError, match="ci_lower must be <= ser_ci_upper"):
        SerComputeResponse(
            ser_point=0.3,
            ser_ci_lower=0.5,
            ser_ci_upper=0.2,
            engine_version="9.0.0",
            evidence_level="supported",
        )


def test_response_engine_version_pattern():
    with pytest.raises(ValidationError):
        SerComputeResponse(
            ser_point=0.3,
            engine_version="v9",
            evidence_level="supported",
        )


def test_response_invalid_evidence_level_rejected():
    with pytest.raises(ValidationError):
        SerComputeResponse(
            ser_point=0.3,
            engine_version="9.0.0",
            evidence_level="unknown",
        )


# ---------- Extra-fields-forbidden --------------------------------------


def test_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SerComputeRequest(**_valid_payload(extra_field="should fail"))
