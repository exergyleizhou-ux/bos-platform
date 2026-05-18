"""Phase B B2a — unit tests for causal_estimate_engine.

Covers seven behaviors:

1. linear_regression recovers true ATE on a synthetic linear bench.
2. dml (EconML LinearDML) recovers true ATE on the same bench.
3. dml with no continuous covariate -> CausalEstimateError(
   code='no_continuous_covariate').
4. Reserved method_family (causal_forest_dml) -> CausalEstimateError(
   code='method_family_reserved').
5. Small n (< n_min_per_stratum) -> evidence_level='planned'
   + 'small_sample' warning.
6. precomputed_estimand handle is used (used_precomputed_estimand=True).
7. estimate_handle round-trips dag / treatment / outcome / method.

Synthetic benches use np.random.default_rng(42); DML fits with n=80,
linear_regression with n=200 — both should finish well under 5 s.
"""

from __future__ import annotations

import hashlib
import warnings

import numpy as np
import pandas as pd
import pytest

from app.engine.extended.causal_estimate_engine import (
    CausalEstimateError,
    run_estimate,
)
from app.engine.extended.causal_identify_engine import run_identify
from app.schemas.causal.estimate import (
    CausalEstimateRequest,
)
from app.schemas.causal.identify import CausalIdentifyRequest
from app.schemas.causal_common import (
    CausalData,
    DagEdge,
    DagNode,
    DagSpec,
    DmlParams,
    MethodParams,
)


# ════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════


def _fingerprint(columns, n):
    cols = ",".join(sorted(columns))
    return hashlib.sha256(f"{cols}|n={n}".encode("utf-8")).hexdigest()[:32]


def _confounded_dag():
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


def _synthetic_linear_bench(n: int, true_ate: float = 2.0, seed: int = 42):
    """Linear data with Z confounding T and Y. True ATE of T on Y = 2.0."""
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


def _build_estimate_request(
    rows,
    fingerprint,
    *,
    method_family: str = "linear_regression",
    method_params: MethodParams | None = None,
    precomputed_estimand=None,
    n_min: int = 30,
    dag: DagSpec | None = None,
):
    return CausalEstimateRequest(
        dag=dag if dag is not None else _confounded_dag(),
        treatment="T",
        outcome="Y",
        data=CausalData(inline=rows, fingerprint=fingerprint),
        method_family=method_family,
        method_params=method_params or MethodParams(),
        precomputed_estimand=precomputed_estimand,
        seed=42,
        n_min_per_stratum=n_min,
    )


# ════════════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════════════


def test_estimate_linear_regression_recovers_ate():
    """OLS on n=200 should recover true ATE=2.0 within ±0.25."""
    rows, fp = _synthetic_linear_bench(n=200, true_ate=2.0)
    request = _build_estimate_request(
        rows, fp, method_family="linear_regression",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_estimate(request)
    assert abs(response.point_estimate - 2.0) < 0.25
    assert response.ci_lower <= response.point_estimate <= response.ci_upper
    assert response.method_used.startswith("linear_regression")
    assert response.diagnostics.n_samples == 200


def test_estimate_dml_recovers_ate():
    """LinearDML on n=80 should recover true ATE=2.0 within ±0.5."""
    rows, fp = _synthetic_linear_bench(n=80, true_ate=2.0)
    request = _build_estimate_request(
        rows, fp,
        method_family="dml",
        method_params=MethodParams(dml=DmlParams(random_state=42)),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_estimate(request)
    # DML on n=80 is noisier; widen tolerance.
    assert abs(response.point_estimate - 2.0) < 0.5
    assert response.ci_lower <= response.point_estimate <= response.ci_upper
    assert response.method_used.startswith("dml")


def test_estimate_dml_requires_continuous_covariate():
    """method_family='dml' with no continuous adjustment_set entry
    must raise CausalEstimateError(code='no_continuous_covariate')."""
    # Build a DAG where Z is treated by the engine as discrete (boolean).
    dag = DagSpec(
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
    n = 80
    rng = np.random.default_rng(42)
    # Z is integer-encoded with only 2 unique values -> classified as discrete.
    Z = rng.integers(0, 2, n)
    T = 0.4 * Z + rng.normal(0, 1, n)
    Y = 2.0 * T + 0.6 * Z + rng.normal(0, 1, n)
    rows = [
        {"T": float(T[i]), "Y": float(Y[i]), "Z": int(Z[i])}
        for i in range(n)
    ]
    fp = _fingerprint(["T", "Y", "Z"], n)
    request = CausalEstimateRequest(
        dag=dag, treatment="T", outcome="Y",
        data=CausalData(inline=rows, fingerprint=fp),
        method_family="dml",
        method_params=MethodParams(dml=DmlParams(random_state=42)),
        seed=42,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(CausalEstimateError) as ei:
            run_estimate(request)
    assert ei.value.code == "no_continuous_covariate"


def test_estimate_reserved_method_raises_422():
    """Reserved method_family raises CausalEstimateError(
    code='method_family_reserved')."""
    rows, fp = _synthetic_linear_bench(n=50)
    request = _build_estimate_request(
        rows, fp, method_family="causal_forest_dml",
    )
    with pytest.raises(CausalEstimateError) as ei:
        run_estimate(request)
    assert ei.value.code == "method_family_reserved"


def test_estimate_small_n_clamps_to_planned():
    """n=20 < n_min_per_stratum=30 -> evidence_level='planned'
    + 'small_sample' warning. No error raised."""
    rows, fp = _synthetic_linear_bench(n=20)
    request = _build_estimate_request(
        rows, fp,
        method_family="linear_regression",
        n_min=30,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_estimate(request)
    assert response.evidence_level == "planned"
    codes = [w.code for w in response.warnings]
    assert "small_sample" in codes


def test_estimate_uses_precomputed_estimand():
    """When precomputed_estimand is provided, /estimate should NOT
    re-identify; diagnostics.used_precomputed_estimand must be True."""
    rows, fp = _synthetic_linear_bench(n=80)
    # First, run /identify to get a handle.
    id_request = CausalIdentifyRequest(
        dag=_confounded_dag(),
        treatment="T",
        outcome="Y",
        dataset_fingerprint=fp,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        id_response = run_identify(id_request)
    # Now feed the handle into /estimate.
    est_request = _build_estimate_request(
        rows, fp,
        method_family="linear_regression",
        precomputed_estimand=id_response.estimand_handle,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_estimate(est_request)
    assert response.diagnostics.used_precomputed_estimand is True


def test_estimate_handle_roundtrips_request():
    """The returned estimate_handle echoes dag / treatment / outcome /
    method_family so /refute can re-fit identically."""
    rows, fp = _synthetic_linear_bench(n=50)
    request = _build_estimate_request(
        rows, fp, method_family="linear_regression",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        response = run_estimate(request)
    h = response.estimate_handle
    assert h.treatment == "T"
    assert h.outcome == "Y"
    assert h.method_family == "linear_regression"
    assert len(h.dag.nodes) == 3
    assert h.data.fingerprint == fp
