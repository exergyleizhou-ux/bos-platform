"""Phase B B2b.3 — unit tests for causal_sensitivity_engine.

Ten behaviors covering the engine and schema validators
(PHASE_B2b3_DESIGN.md §5):

 1. evalue branch primary path (DoWhy class) recovers e_value > 1.5
    on the B2a backdoor bench.
 2. evalue branch fallback fires when the DoWhy primary raises;
    ``source='self_chinn_vwd'`` and a method_fallback warning are
    surfaced.
 3. evalue fallback's e_value_point matches B2a ``cheap_evalue`` on
    the same beta + std(Y) to 1e-6.
 4. linear branch recovers RV(q=1) within 0.05 of the Step 1
    scratch number (0.8326 on n=200 seed=42 backdoor bench).
 5. linear branch populates ``partial_r2_yd`` in [0, 1].
 6. linear branch with ``benchmark_covariate`` set populates
    ``partial_r2_yz_given_d`` and echoes the input in
    ``diagnostics.benchmark_covariate_used``.
 7. method='partial_linear' raises CausalSensitivityError
    (code='method_reserved') at the engine layer.
 8. benchmark_covariate not in DAG -> schema ValidationError.
 9. overall_robust flips on a weak-effect bench (true ATE = 0.05);
    the strong-effect bench shows overall_robust=True.
10. Response cross-field validator rejects method='evalue' +
    linear_detail not None.

No FastAPI / TestClient. Each test independent; warnings suppressed.
"""

from __future__ import annotations

import hashlib
import warnings

import numpy as np
import pytest
from pydantic import ValidationError

from app.engine.extended import causal_sensitivity_engine as engine_mod
from app.engine.extended.causal_sensitivity_engine import (
    CausalSensitivityError,
    run_sensitivity,
)
from app.engine.extended.causal_utils import cheap_evalue
from app.schemas.causal.sensitivity import (
    CausalSensitivityRequest,
    CausalSensitivityResponse,
    SensitivityDiagnostics,
    SensitivityEvalueDetail,
    SensitivityLinearDetail,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    CausalData,
    DagEdge,
    DagNode,
    DagSpec,
    EstimateHandle,
)


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


def _fingerprint(columns, n):
    cols = ",".join(sorted(columns))
    return hashlib.sha256(f"{cols}|n={n}".encode("utf-8")).hexdigest()[:32]


def _backdoor_dag() -> DagSpec:
    """Z -> T, Z -> Y, T -> Y. Backdoor on {Z}."""
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


def _backdoor_bench(n: int = 200, true_ate: float = 2.0, seed: int = 42):
    """Strong-effect backdoor bench (Step 1 scratch parameters)."""
    rng = np.random.default_rng(seed)
    Z = rng.normal(0, 1, n)
    T = 0.5 * Z + rng.normal(0, 1, n)
    Y = true_ate * T + 0.7 * Z + rng.normal(0, 1, n)
    rows = [
        {"T": float(T[i]), "Y": float(Y[i]), "Z": float(Z[i])}
        for i in range(n)
    ]
    return rows, _fingerprint(["T", "Y", "Z"], n)


def _build_handle(rows, fp, seed: int = 42) -> EstimateHandle:
    return EstimateHandle(
        dag=_backdoor_dag(),
        treatment="T",
        outcome="Y",
        method_family="linear_regression",
        method_params={},
        data=CausalData(inline=rows, fingerprint=fp),
        seed=seed,
    )


def _build_request(
    *,
    method: str = "evalue",
    benchmark_covariate=None,
    true_ate: float = 2.0,
    n: int = 200,
    seed: int = 42,
) -> CausalSensitivityRequest:
    rows, fp = _backdoor_bench(n=n, true_ate=true_ate, seed=seed)
    return CausalSensitivityRequest(
        estimate_handle=_build_handle(rows, fp, seed=seed),
        method=method,
        benchmark_covariate=benchmark_covariate,
        seed=seed,
        mode="sync",
    )


# ════════════════════════════════════════════════════════════════════
# 1. evalue primary path (DoWhy class)
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_evalue_primary_path():
    request = _build_request(method="evalue")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    assert response.method == "evalue"
    assert response.evalue_detail is not None
    assert response.linear_detail is None
    # On the strong-effect bench (true ATE=2.0) we expect a clearly
    # robust E-value. Source should be the DoWhy primary (Step 1
    # scratch tail-arrival confirmed check_sensitivity works).
    assert response.evalue_detail.source == "dowhy_class", (
        f"expected primary path; got source="
        f"{response.evalue_detail.source!r}"
    )
    assert response.evalue_detail.e_value_point > 1.5, (
        f"e_value_point {response.evalue_detail.e_value_point} not "
        f"> 1.5 on strong-effect bench"
    )
    assert response.evalue_detail.e_value_lower_ci > 1.5, (
        f"e_value_lower_ci {response.evalue_detail.e_value_lower_ci} "
        f"not > 1.5 on strong-effect bench"
    )
    assert response.diagnostics.method == "evalue"


# ════════════════════════════════════════════════════════════════════
# 2. evalue fallback when primary raises
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_evalue_fallback_on_dowhy_failure(monkeypatch):
    """Monkeypatch the primary to raise; fallback must engage."""

    def _force_failure(_request, _df):
        raise RuntimeError("simulated DoWhy class failure")

    monkeypatch.setattr(
        engine_mod,
        "_run_evalue_primary_dowhy",
        _force_failure,
    )

    request = _build_request(method="evalue")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    assert response.evalue_detail is not None
    assert response.evalue_detail.source == "self_chinn_vwd", (
        f"expected fallback path; got source="
        f"{response.evalue_detail.source!r}"
    )
    codes = [w.code for w in response.warnings]
    assert "method_fallback" in codes, (
        f"expected method_fallback warning; got codes {codes}"
    )
    msgs = " ".join(w.message for w in response.warnings)
    assert "RuntimeError" in msgs or "simulated DoWhy" in msgs, (
        f"warning should record the primary exception; got {msgs!r}"
    )


# ════════════════════════════════════════════════════════════════════
# 3. evalue fallback matches B2a cheap_evalue numerically
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_evalue_fallback_matches_cheap_evalue(monkeypatch):
    """The Chinn-VWD fallback's e_value_point should equal what
    cheap_evalue would return on the same (beta, std_outcome). This
    confirms the engine and the helper share the same math."""
    import statsmodels.api as sm

    def _force_failure(_request, _df):
        raise RuntimeError("force fallback")

    monkeypatch.setattr(
        engine_mod, "_run_evalue_primary_dowhy", _force_failure,
    )

    rows, fp = _backdoor_bench(n=200, true_ate=2.0, seed=42)
    request = CausalSensitivityRequest(
        estimate_handle=_build_handle(rows, fp),
        method="evalue",
        seed=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    # Recompute the expected cheap_evalue independently on the same
    # OLS-derived (beta, std_outcome) the engine would have used.
    import pandas as pd
    df = pd.DataFrame(rows)
    X = sm.add_constant(df[["T", "Z"]].to_numpy(dtype="float64"))
    y = df["Y"].to_numpy(dtype="float64")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = sm.OLS(y, X).fit()
    beta = float(fit.params[1])
    std_y = float(df["Y"].std(ddof=1))
    expected_point = float(cheap_evalue(beta, std_y))

    assert (
        abs(response.evalue_detail.e_value_point - expected_point)
        < 1e-6
    ), (
        f"engine e_value_point {response.evalue_detail.e_value_point} "
        f"differs from cheap_evalue({beta}, {std_y}) = {expected_point}"
    )


# ════════════════════════════════════════════════════════════════════
# 4. linear branch recovers RV
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_linear_recovers_rv():
    """On the n=200 seed=42 backdoor bench, Step 1 scratch saw
    RV(q=1) = 0.8326. The engine must reproduce this within 0.05."""
    request = _build_request(method="linear")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    assert response.method == "linear"
    assert response.linear_detail is not None
    assert response.evalue_detail is None
    rv = response.linear_detail.robustness_value
    assert abs(rv - 0.8326) < 0.05, (
        f"robustness_value {rv} not within 0.05 of scratch baseline "
        f"0.8326"
    )
    rv_a = response.linear_detail.robustness_value_alpha
    assert abs(rv_a - 0.8180) < 0.05, (
        f"robustness_value_alpha {rv_a} not within 0.05 of scratch "
        f"baseline 0.8180"
    )


# ════════════════════════════════════════════════════════════════════
# 5. linear partial_r2_yd field
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_linear_partial_r2_field():
    request = _build_request(method="linear")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    pr2 = response.linear_detail.partial_r2_yd
    assert 0.0 <= pr2 <= 1.0, (
        f"partial_r2_yd {pr2} out of [0, 1]"
    )
    # On the strong-effect bench the partial R^2 should be high (~0.80
    # per scratch). Allow a wide band.
    assert pr2 > 0.5, (
        f"partial_r2_yd {pr2} unexpectedly low on strong-effect bench"
    )


# ════════════════════════════════════════════════════════════════════
# 6. benchmark_covariate populates partial_r2_yz_given_d
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_benchmark_covariate_present():
    request = _build_request(method="linear", benchmark_covariate="Z")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_sensitivity(request)

    assert response.diagnostics.benchmark_covariate_used == "Z"
    pr2_yz = response.linear_detail.partial_r2_yz_given_d
    assert pr2_yz is not None, (
        "partial_r2_yz_given_d should be populated when "
        "benchmark_covariate is supplied"
    )
    assert 0.0 <= pr2_yz <= 1.0, (
        f"partial_r2_yz_given_d {pr2_yz} out of [0, 1]"
    )


# ════════════════════════════════════════════════════════════════════
# 7. partial_linear -> 422
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_partial_linear_raises_422():
    request = _build_request(method="partial_linear")
    with pytest.raises(CausalSensitivityError) as exc_info:
        run_sensitivity(request)
    assert exc_info.value.code == "method_reserved", (
        f"expected code='method_reserved'; got {exc_info.value.code!r}"
    )


# ════════════════════════════════════════════════════════════════════
# 8. benchmark_covariate not in DAG -> schema ValidationError
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_benchmark_covariate_not_in_dag_raises_422():
    rows, fp = _backdoor_bench(n=20)
    payload = {
        "estimate_handle": _build_handle(rows, fp).model_dump(),
        "method": "linear",
        "benchmark_covariate": "unknown",  # not in DAG
        "seed": 42,
        "mode": "sync",
    }
    with pytest.raises(ValidationError) as exc_info:
        CausalSensitivityRequest(**payload)
    msg = str(exc_info.value)
    assert "unknown" in msg, (
        f"ValidationError should mention the rejected covariate: {msg}"
    )


# ════════════════════════════════════════════════════════════════════
# 9. overall_robust flips on weak-effect bench
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_overall_robust_field():
    """Strong-effect (true ATE=2.0): overall_robust=True for linear.
    Weak-effect (true ATE=0.05): overall_robust=False for linear."""
    strong = _build_request(method="linear", true_ate=2.0)
    weak = _build_request(method="linear", true_ate=0.05)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r_strong = run_sensitivity(strong)
        r_weak = run_sensitivity(weak)

    assert r_strong.overall_robust is True, (
        f"strong-effect bench should be robust; got "
        f"overall_robust={r_strong.overall_robust}, "
        f"RV_alpha={r_strong.linear_detail.robustness_value_alpha}"
    )
    assert r_weak.overall_robust is False, (
        f"weak-effect bench should not be robust; got "
        f"overall_robust={r_weak.overall_robust}, "
        f"RV_alpha={r_weak.linear_detail.robustness_value_alpha}"
    )
    assert r_strong.evidence_level == "validated"
    assert r_weak.evidence_level == "supported"


# ════════════════════════════════════════════════════════════════════
# 10. Response cross-field validator
# ════════════════════════════════════════════════════════════════════


def test_sensitivity_response_validator_method_detail_consistency():
    """Build a Response with method='evalue' but linear_detail set;
    the cross-field validator must reject."""
    bad_evalue = SensitivityEvalueDetail(
        e_value_point=2.0,
        e_value_lower_ci=1.8,
        source="dowhy_class",
    )
    spurious_linear = SensitivityLinearDetail(
        robustness_value=0.5,
        robustness_value_alpha=0.4,
        partial_r2_yd=0.3,
    )
    diag = SensitivityDiagnostics(
        method="evalue",
        n_samples=100,
        fit_time_ms=10.0,
    )
    with pytest.raises(ValidationError) as exc_info:
        CausalSensitivityResponse(
            method="evalue",
            evalue_detail=bad_evalue,
            linear_detail=spurious_linear,  # must be None when evalue
            overall_robust=True,
            evidence_level="validated",
            diagnostics=diag,
            warnings=[],
            engine_version=CAUSAL_ENGINE_VERSION,
        )
    msg = str(exc_info.value)
    assert "linear_detail" in msg, (
        f"expected cross-field validator to mention linear_detail; "
        f"got: {msg}"
    )
