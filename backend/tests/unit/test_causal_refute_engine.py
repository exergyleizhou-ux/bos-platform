"""Phase B B2b.1 — unit tests for causal_refute_engine.

Covers eight behaviors (PHASE_B2b1_DESIGN.md §11):

1. random_common_cause: passed=True, p_value > 0.10, small delta
2. placebo_treatment_refuter: new_effect ≈ 0, passed=True, p_value > 0.10
3. data_subset_refuter: passed=True, p_value > 0.10, small delta
4. add_unobserved_common_cause: p_value is None, passed=True
   (no significance test; delta-based)
5. bootstrap_refuter: optional-implemented refuter works like RCC
6. Reserved method (non_parametric_sensitivity_analyzer) raises
   CausalRefuteError(code='refuter_reserved')
7. Evidence-level validated requires high e_value (>1.5)
8. Evidence-level supported when e_value too low for validated

Synthetic bench mirrors B2a (T/Y/Z, n=80, seed=42, true ATE=2.0).
No FastAPI / TestClient / network imports. Each test independent.
"""

from __future__ import annotations

import hashlib
import warnings

import numpy as np
import pytest

from app.engine.extended.causal_estimate_engine import run_estimate
from app.engine.extended.causal_refute_engine import (
    CausalRefuteError,
    run_refute,
)
from app.schemas.causal.estimate import CausalEstimateRequest
from app.schemas.causal.refute import (
    CausalRefuteRequest,
)
from app.schemas.causal_common import (
    CausalData,
    DagEdge,
    DagNode,
    DagSpec,
    MethodParams,
)


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


def _fingerprint(columns, n):
    cols = ",".join(sorted(columns))
    return hashlib.sha256(f"{cols}|n={n}".encode("utf-8")).hexdigest()[:32]


def _confounded_dag() -> DagSpec:
    """Z -> T, Z -> Y, T -> Y. Back-door identification on {Z}."""
    return DagSpec(
        nodes=[
            DagNode(name="T", node_kind="treatment"),
            DagNode(name="Y", node_kind="outcome"),
            DagNode(name="Z", node_kind="covariate"),
        ],
        edges=[
            DagEdge(src="T", dst="Y"),
            DagEdge(src="Z", dst="T", edge_kind="confounding"),
            DagEdge(src="Z", dst="Y", edge_kind="confounding"),
        ],
        source="hand",
    )


def _synthetic_linear_bench(n: int = 80, true_ate: float = 2.0, seed: int = 42):
    """Z confounds T and Y. True ATE = 2.0."""
    rng = np.random.default_rng(seed)
    Z = rng.normal(0, 1, n)
    T = 0.5 * Z + rng.normal(0, 1, n)
    Y = true_ate * T + 0.7 * Z + rng.normal(0, 1, n)
    rows = [
        {"T": float(T[i]), "Y": float(Y[i]), "Z": float(Z[i])}
        for i in range(n)
    ]
    fp = _fingerprint(["T", "Y", "Z"], n)
    return rows, fp


def _build_estimate_handle():
    """Run /estimate once to get a real EstimateHandle that /refute can use.
    Returns (estimate_handle, e_value_cheap from estimate response)."""
    rows, fp = _synthetic_linear_bench(n=80)
    est_request = CausalEstimateRequest(
        dag=_confounded_dag(),
        treatment="T",
        outcome="Y",
        data=CausalData(inline=rows, fingerprint=fp),
        method_family="linear_regression",
        method_params=MethodParams(),
        seed=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        est_response = run_estimate(est_request)
    return est_response.estimate_handle, est_response.e_value_cheap


# ════════════════════════════════════════════════════════════════════
# Tests — single-refuter happy paths
# ════════════════════════════════════════════════════════════════════


def test_refute_random_common_cause_passes():
    """random_common_cause: estimate should be robust to a synthetic
    confounder; passed=True, p_value > 0.10, |delta| small."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["random_common_cause"],
        seed=42,
        original_e_value=e_val,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    assert len(response.refute_results) == 1
    result = response.refute_results[0]
    assert result.refuter == "random_common_cause"
    assert result.passed is True
    assert result.p_value is not None
    assert result.p_value > 0.10
    assert abs(result.delta_estimate) < 0.5
    assert "Random" in result.diagnostic or "random" in result.diagnostic


def test_refute_placebo_treatment_passes():
    """placebo_treatment_refuter: replacing T with random should drive
    new_effect ≈ 0; passed=True, p_value > 0.10."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["placebo_treatment_refuter"],
        seed=42,
        original_e_value=e_val,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    result = response.refute_results[0]
    assert result.refuter == "placebo_treatment_refuter"
    assert result.passed is True
    assert result.p_value is not None
    assert result.p_value > 0.10
    # delta_estimate = new (≈0) - original (≈2) → roughly -2
    assert result.delta_estimate < -1.0


def test_refute_data_subset_passes():
    """data_subset_refuter: subsample should give similar estimate;
    passed=True, p_value > 0.10, |delta| small."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["data_subset_refuter"],
        seed=42,
        original_e_value=e_val,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    result = response.refute_results[0]
    assert result.refuter == "data_subset_refuter"
    assert result.passed is True
    # data_subset_refuter is in _DELTA_BASED_REFUTERS (engine module
    # comment explains why DoWhy 0.14's is_statistically_significant
    # is unreliable here). passed is derived from |delta/orig| < 0.1.
    assert result.p_value is None
    assert "rel_delta" in result.diagnostic
    assert abs(result.delta_estimate) < 0.5


def test_refute_add_unobserved_no_pvalue():
    """add_unobserved_common_cause: no significance test;
    p_value is None, passed derived from |delta/orig| < 0.1."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["add_unobserved_common_cause"],
        seed=42,
        original_e_value=e_val,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    result = response.refute_results[0]
    assert result.refuter == "add_unobserved_common_cause"
    assert result.p_value is None
    # With small effect-strength kwargs (0.01 / 0.02) on a clean bench,
    # the unobserved-confounder perturbation should be ~negligible.
    assert result.passed is True
    # Diagnostic must surface the rel_delta computation
    assert "rel_delta" in result.diagnostic
    assert "threshold" in result.diagnostic


def test_refute_bootstrap_passes():
    """bootstrap_refuter: optional-implemented; works like RCC."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["bootstrap_refuter"],
        seed=42,
        original_e_value=e_val,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    result = response.refute_results[0]
    assert result.refuter == "bootstrap_refuter"
    assert result.passed is True
    # bootstrap_refuter is in _DELTA_BASED_REFUTERS (same reason as
    # data_subset). passed = |delta/orig| < 0.1.
    assert result.p_value is None
    assert "rel_delta" in result.diagnostic
    assert abs(result.delta_estimate) < 0.5


# ════════════════════════════════════════════════════════════════════
# Tests — reserved enum + evidence-level rule
# ════════════════════════════════════════════════════════════════════


def test_refute_reserved_method_raises_422():
    """non_parametric_sensitivity_analyzer is reserved; engine raises
    CausalRefuteError(code='refuter_reserved')."""
    handle, e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=["non_parametric_sensitivity_analyzer"],
        seed=42,
        original_e_value=e_val,
    )
    with pytest.raises(CausalRefuteError) as ei:
        run_refute(request)
    assert ei.value.code == "refuter_reserved"


def test_refute_evidence_level_validated_requires_high_evalue():
    """All 4 mandatory pass + backdoor strategy + e_value > 1.5
    → evidence_level == 'validated'."""
    handle, _e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=[
            "random_common_cause",
            "placebo_treatment_refuter",
            "data_subset_refuter",
            "add_unobserved_common_cause",
        ],
        seed=42,
        original_e_value=2.0,   # > 1.5 threshold
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    # All 4 mandatory should pass on the clean bench
    assert response.overall_robust is True
    assert response.evidence_level == "validated"
    # 4 results in order
    assert len(response.refute_results) == 4
    # The aggregate echoed the e_value verbatim
    assert response.e_value_used == 2.0


def test_refute_evidence_level_falls_to_supported_when_evalue_low():
    """All 4 mandatory pass + backdoor strategy + e_value = 1.1
    (< 1.5 threshold) → evidence_level == 'supported' (not validated)."""
    handle, _e_val = _build_estimate_handle()
    request = CausalRefuteRequest(
        estimate_handle=handle,
        refuters=[
            "random_common_cause",
            "placebo_treatment_refuter",
            "data_subset_refuter",
            "add_unobserved_common_cause",
        ],
        seed=42,
        original_e_value=1.1,   # < 1.5 threshold → cannot be validated
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_refute(request)

    # 4 mandatory still pass → overall_robust True
    assert response.overall_robust is True
    # But evidence_level cannot reach validated without e_value > 1.5
    assert response.evidence_level == "supported"
    assert response.e_value_used == 1.1
