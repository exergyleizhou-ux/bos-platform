"""Phase A — strict MC propagation schema unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.mc import (
    McDiagnostics,
    McInput,
    McPropagateRequest,
    McPropagateResponse,
    SCHEMA_VERSION,
    SobolIndices,
)


# ---- helpers --------------------------------------------------------


def _payload(**o) -> dict:
    base = dict(
        inputs={
            "dm_in": {"kind": "normal", "mean": 10.0, "std": 0.5},
            "dm_out": {"kind": "normal", "mean": 2.5, "std": 0.3},
        },
        target_func="ser",
        target_func_config={"constants": {"n_in": 50.0, "n_larvae": 30.0}},
        n_samples=1000,
        seed=42,
    )
    base.update(o)
    return base


# ---- version --------------------------------------------------------


def test_schema_version_constant():
    assert SCHEMA_VERSION == "A.4"


# ---- request happy paths -------------------------------------------


def test_valid_input_passes():
    req = McPropagateRequest(**_payload())
    assert req.target_func == "ser"
    assert req.n_samples == 1000
    assert req.return_samples is False
    assert req.compute_sobol is False


def test_all_distribution_kinds_pass():
    for kind in ("normal", "lognormal", "triangular", "uniform"):
        req = McPropagateRequest(**_payload(
            inputs={"x": {"kind": kind, "mean": 1.0, "std": 0.1}},
        ))
        assert next(iter(req.inputs.values())).kind == kind


# ---- McInput range constraints -------------------------------------


def test_input_negative_std_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(
            inputs={"x": {"kind": "normal", "mean": 1.0, "std": -0.1}},
        ))


def test_input_unknown_distribution_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(
            inputs={"x": {"kind": "weibull", "mean": 1.0, "std": 0.1}},
        ))


def test_input_extra_field_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(
            inputs={"x": {"kind": "normal", "mean": 1.0, "std": 0.1, "rogue": "x"}},
        ))


# ---- inputs collection constraints ---------------------------------


def test_inputs_empty_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(inputs={}))


def test_inputs_too_many_keys_rejected():
    too_many = {
        f"v{i}": {"kind": "normal", "mean": 0.0, "std": 1.0} for i in range(65)
    }
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(inputs=too_many))


# ---- target_func constraints ---------------------------------------


def test_target_func_literal_only():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(target_func="phlogiston"))


def test_target_func_config_empty_rejected():
    with pytest.raises(ValidationError, match="target_func_config must not be empty"):
        McPropagateRequest(**_payload(target_func_config={}))


# ---- n_samples / seed constraints ----------------------------------


def test_n_samples_below_100_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(n_samples=50))


def test_n_samples_over_200k_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(n_samples=200_001))


def test_seed_negative_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(seed=-1))


def test_seed_over_u32_max_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(seed=2**32))


# ---- extra-fields-forbidden ---------------------------------------


def test_request_extra_field_rejected():
    with pytest.raises(ValidationError):
        McPropagateRequest(**_payload(rogue="oops"))


# ---- response invariants ------------------------------------------


def _minimal_response(**o) -> dict:
    base = dict(
        target_mean=0.25,
        target_std=0.03,
        ci_lower=0.18,
        ci_upper=0.32,
        diagnostics=McDiagnostics(
            n_samples=1000,
            effective_samples=1000,
            seed=42,
            distribution_kinds={"dm_in": "normal"},
            computation_time_ms=15.5,
            convergence_check=False,
        ),
        evidence_level="supported",
        engine_version="9.0.0",
    )
    base.update(o)
    return base


def test_response_valid_passes():
    McPropagateResponse(**_minimal_response())


def test_response_ci_order_validator():
    with pytest.raises(ValidationError, match="ci_lower"):
        McPropagateResponse(**_minimal_response(ci_lower=0.5, ci_upper=0.2))


def test_response_negative_std_rejected():
    with pytest.raises(ValidationError):
        McPropagateResponse(**_minimal_response(target_std=-0.1))


def test_response_evidence_level_literal_only():
    with pytest.raises(ValidationError):
        McPropagateResponse(**_minimal_response(evidence_level="ironclad"))


def test_response_engine_version_pattern():
    with pytest.raises(ValidationError):
        McPropagateResponse(**_minimal_response(engine_version="v9"))


# ---- SobolIndices invariants --------------------------------------


def test_sobol_indices_valid():
    SobolIndices(
        first_order={"x": 0.3, "y": 0.5},
        total={"x": 0.4, "y": 0.6},
    )


def test_sobol_first_order_out_of_band_rejected():
    with pytest.raises(ValidationError, match="outside"):
        SobolIndices(
            first_order={"x": 1.5},
            total={"x": 0.5},
        )


def test_sobol_total_out_of_band_rejected():
    with pytest.raises(ValidationError, match="outside"):
        SobolIndices(
            first_order={"x": 0.5},
            total={"x": -0.5},
        )


def test_sobol_key_mismatch_rejected():
    with pytest.raises(ValidationError, match="same keys"):
        SobolIndices(
            first_order={"x": 0.3, "y": 0.5},
            total={"x": 0.4},  # missing y
        )


# ---- McDiagnostics invariants -------------------------------------


def test_diagnostics_negative_effective_samples_rejected():
    with pytest.raises(ValidationError):
        McDiagnostics(
            n_samples=1000,
            effective_samples=-1,
            distribution_kinds={},
            computation_time_ms=15.5,
        )
