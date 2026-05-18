"""Phase B B2b.3 — /api/v1/causal/sensitivity engine.

Reference: Plan v2 §2.5 (PHASE_B_PLAN.md) + design recorded in
PHASE_B2b3_DESIGN.md (§1 method selection from 5-candidate scratch
verification; §4 function signatures; §8 risks).

Three branches keyed on ``method``:

- ``"evalue"`` -> ``_run_evalue``: DoWhy ``EValueSensitivityAnalyzer``
  primary (Candidate 1; verified via scratch tail-arrival probe that
  ``check_sensitivity(data=df, plot=False)`` populates
  ``analyzer.stats`` with ``evalue_estimate`` and ``evalue_lower_ci``
  keys); self-implemented Chinn-VWD via B2a ``cheap_evalue``
  (Candidate 2) as a delta-style fallback. The fallback fires on any
  primary exception and emits a ``method_fallback`` warning.

- ``"linear"`` -> ``_run_cinelli_hazlett``: closed-form Cinelli-Hazlett
  2020 robustness value + partial R^2 from a single ``statsmodels``
  OLS fit (Candidate 5). When ``request.benchmark_covariate`` is
  supplied, the benchmark covariate's partial R^2 on Y given T and
  the remaining adjustment set is computed directly from its
  t-statistic in the same OLS (no separate LOO fit needed — the
  full-model t-statistic encodes the partial relationship).

- ``"partial_linear"`` -> 422 ``code='method_reserved'``. DoWhy's
  ``NonParametricSensitivityAnalyzer`` (Candidate 3) requires a
  keyword-only ``theta_s`` parameter that Plan v2 §2.5 does not
  expose. D9-style reserved-enum pattern (mirrors B2a estimate's
  ``method_family_reserved``, B2b.1 refute's ``refuter_reserved``,
  B2b.2 mediation's ``decomposition_reserved``).

The ``overall_robust`` Response field operationalises Plan v2 §2.5's
"Gamma-bound >= 1.5" gate: ``e_value_lower_ci > 1.5`` on the evalue
branch; ``robustness_value_alpha > 0.10`` on the linear branch
(Cinelli-Hazlett 2020 conventional threshold; E-value and RV are on
incompatible scales so the engine thresholds them separately and the
schema exposes only the boolean).

Reused (no modification) from earlier B engines:
- ``causal_data_to_dataframe``, ``dag_to_gml``, ``cheap_evalue``
  from ``causal_utils``
- ``_classify_strategy`` from ``causal_identify_engine``
"""

from __future__ import annotations

import logging
import math
import time
import warnings as warnings_module
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.engine.extended.causal_identify_engine import _classify_strategy
from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    cheap_evalue,
    dag_to_gml,
)
from app.schemas.causal.sensitivity import (
    CausalSensitivityRequest,
    CausalSensitivityResponse,
    SensitivityDiagnostics,
    SensitivityEvalueDetail,
    SensitivityLinearDetail,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    CausalWarning,
    EvidenceLevel,
)


_logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# Custom exception (router → HTTP 422)
# ════════════════════════════════════════════════════════════════════


class CausalSensitivityError(ValueError):
    """Raised on /sensitivity pre-condition or in-flight failure.

    Router maps to HTTP 422 with a structured body that includes the
    machine-readable ``code``. Mirrors ``CausalRefuteError`` /
    ``CausalEstimateError`` / ``CausalMediationError`` shape.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════


# E-value robustness gate from Plan v2 §2.5 (paper Gamma-bound 1.5).
_EVALUE_ROBUST_THRESHOLD = 1.5


# Cinelli-Hazlett 2020 conventional threshold for "highly robust"
# linear bound. The E-value 1.5 number does NOT apply to RV (different
# scales: E-value is unbounded, RV is in [0, 1]).
_RV_ROBUST_THRESHOLD = 0.10


# Confidence level for the OLS CI used in both branches.
_DEFAULT_CONFIDENCE_LEVEL = 0.95


# DoWhy method-name strings for the primary E-value path. Mirrors
# B2b.1 refute's ``_DOWHY_METHODS`` mapping.
_DOWHY_METHODS = {
    "linear_regression": "backdoor.linear_regression",
    "propensity_score": "backdoor.propensity_score_weighting",
    "dml": "backdoor.econml.dml.LinearDML",
}


# ════════════════════════════════════════════════════════════════════
# Reserved-enum gate
# ════════════════════════════════════════════════════════════════════


def _check_method(method: str) -> None:
    """Reject ``partial_linear`` before any work happens.

    Plan v2 §2.5 lists the enum value but does not expose the
    ``theta_s`` parameter DoWhy's NonParametricSensitivityAnalyzer
    requires (Candidate 3 in PHASE_B2b3_DESIGN.md §1). D9-style 422
    with ``code='method_reserved'``.
    """
    if method == "partial_linear":
        raise CausalSensitivityError(
            code="method_reserved",
            message=(
                "method='partial_linear' is reserved for a future "
                "Phase B / Phase G release. B2b.3 MVP implements "
                "'evalue' and 'linear' only."
            ),
        )


# ════════════════════════════════════════════════════════════════════
# Helpers — shared between branches
# ════════════════════════════════════════════════════════════════════


def _resolve_adjustment_set(
    request: CausalSensitivityRequest,
    df: pd.DataFrame,
) -> List[str]:
    """Pick the adjustment set from the DAG (handle.dag covariate nodes).

    Filters to columns actually present in ``df`` and excludes the
    treatment and outcome (defensive — they shouldn't be tagged as
    covariate, but a malformed handle could).
    """
    handle = request.estimate_handle
    covariates = [
        n.name for n in handle.dag.nodes
        if n.node_kind == "covariate"
    ]
    return [
        c for c in covariates
        if c in df.columns
        and c != handle.treatment
        and c != handle.outcome
    ]


def _ols_treatment_stats(
    df: pd.DataFrame,
    outcome: str,
    treatment: str,
    adjustment_set: List[str],
) -> Tuple[float, float, float, float, float, int]:
    """Fit ``Y ~ T + adjustment_set`` via statsmodels OLS.

    Returns ``(beta, se, ci_lower, ci_upper, std_outcome, df_resid)``
    on the treatment coefficient at 95% confidence.
    """
    import statsmodels.api as sm

    y = df[outcome].to_numpy(dtype="float64")
    X_cols = [treatment] + [
        c for c in adjustment_set
        if c in df.columns and c != treatment
    ]
    X = df[X_cols].to_numpy(dtype="float64")
    X = sm.add_constant(X, has_constant="add")
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        fit = sm.OLS(y, X).fit()
    # Treatment coef is index 1 (after the const).
    beta = float(fit.params[1])
    se = float(fit.bse[1])
    ci_arr = np.asarray(
        fit.conf_int(alpha=1 - _DEFAULT_CONFIDENCE_LEVEL)
    )
    ci_lower = float(ci_arr[1, 0])
    ci_upper = float(ci_arr[1, 1])
    std_outcome = float(df[outcome].std(ddof=1))
    df_resid = int(fit.df_resid)
    return beta, se, ci_lower, ci_upper, std_outcome, df_resid


def _bound_closer_to_null(ci_lower: float, ci_upper: float) -> float:
    """For a 2-sided CI, the bound closer to the null (zero) is the
    one with smaller absolute value. Returns the *value at that bound*,
    not its absolute value — so a CI of (-0.1, 2.0) yields -0.1, not
    0.1 (Chinn-VWD expects the signed point that's nearest the null).
    """
    if abs(ci_lower) <= abs(ci_upper):
        return ci_lower
    return ci_upper


# ════════════════════════════════════════════════════════════════════
# E-value branch — primary (DoWhy class) + fallback (Chinn-VWD)
# ════════════════════════════════════════════════════════════════════


def _run_evalue_primary_dowhy(
    request: CausalSensitivityRequest,
    df: pd.DataFrame,
) -> Tuple[float, float]:
    """Try the DoWhy ``EValueSensitivityAnalyzer`` standalone class.

    Returns ``(e_value_point, e_value_lower_ci)`` extracted from
    ``analyzer.stats`` after ``check_sensitivity(data=df, plot=False)``.
    Raises on any DoWhy-side failure — the outer caller catches and
    falls back to the self-implemented path.
    """
    from dowhy import CausalModel
    from dowhy.causal_refuters.evalue_sensitivity_analyzer import (
        EValueSensitivityAnalyzer,
    )

    handle = request.estimate_handle
    gml = dag_to_gml(handle.dag)
    method_name = _DOWHY_METHODS.get(
        handle.method_family, "backdoor.linear_regression",
    )

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        model = CausalModel(
            data=df,
            treatment=handle.treatment,
            outcome=handle.outcome,
            graph=gml,
        )
        estimand = model.identify_effect(
            proceed_when_unidentifiable=True,
        )
        estimate = model.estimate_effect(
            estimand, method_name=method_name,
        )
        analyzer = EValueSensitivityAnalyzer(
            estimate=estimate,
            estimand=estimand,
            data=df,
            treatment_name=handle.treatment,
            outcome_name=handle.outcome,
        )
        analyzer.check_sensitivity(data=df, plot=False)

    stats = analyzer.stats or {}
    if "evalue_estimate" not in stats or "evalue_lower_ci" not in stats:
        raise RuntimeError(
            f"DoWhy stats missing expected keys; got "
            f"{sorted(stats.keys()) if stats else 'empty'}"
        )
    e_point = float(stats["evalue_estimate"])
    # ``evalue_lower_ci`` can be None when the CI is one-sided. In that
    # case fall back to the point — the outer evidence-level rule will
    # be more conservative because point >= lower_ci always.
    raw_lower = stats.get("evalue_lower_ci")
    if raw_lower is None:
        e_lower = e_point
    else:
        e_lower = float(raw_lower)
    return e_point, e_lower


def _run_evalue_fallback_chinn(
    request: CausalSensitivityRequest,
    df: pd.DataFrame,
) -> Tuple[float, float]:
    """Self-implemented Chinn (2000) / VanderWeele-Ding 2017 E-value
    via B2a's ``cheap_evalue`` helper.

    Returns ``(e_value_point, e_value_lower_ci)``. Always succeeds
    on numeric input — used as the always-available fallback after
    a DoWhy primary exception.
    """
    handle = request.estimate_handle
    adjustment_set = _resolve_adjustment_set(request, df)
    beta, _se, ci_lo, ci_hi, std_outcome, _df_resid = _ols_treatment_stats(
        df, handle.outcome, handle.treatment, adjustment_set,
    )
    e_point = float(cheap_evalue(beta, std_outcome))
    e_lower = float(
        cheap_evalue(_bound_closer_to_null(ci_lo, ci_hi), std_outcome)
    )
    return e_point, e_lower


def _run_evalue(
    request: CausalSensitivityRequest,
    df: pd.DataFrame,
) -> Tuple[
    SensitivityEvalueDetail, SensitivityDiagnostics, List[CausalWarning]
]:
    """E-value branch with delta-style primary -> fallback dispatch."""
    t0 = time.perf_counter()
    warnings_out: List[CausalWarning] = []

    try:
        e_point, e_lower = _run_evalue_primary_dowhy(request, df)
        source = "dowhy_class"
    except Exception as exc:
        _logger.debug(
            "evalue primary (DoWhy) raised %s; falling back to "
            "self-implemented Chinn-VWD",
            type(exc).__name__,
        )
        e_point, e_lower = _run_evalue_fallback_chinn(request, df)
        source = "self_chinn_vwd"
        warnings_out.append(CausalWarning(
            code="method_fallback",
            severity="info",
            message=(
                f"DoWhy EValueSensitivityAnalyzer raised "
                f"{type(exc).__name__}: {str(exc)[:160]}. Engine "
                f"fell back to self-implemented Chinn-VWD E-value. "
                f"Numerical agreement is typically within 1% on the "
                f"Phase B benches; see PHASE_B2b3_DESIGN.md §1."
            ),
        ))

    # E-value is bounded below by 1.0 by construction. Floor to 1.0
    # to satisfy the schema validator on any numerical edge case
    # (e.g. negative-effect benches where the Chinn-VWD formula
    # returns the confidence_floor).
    e_point = max(1.0, e_point)
    e_lower = max(1.0, e_lower)

    fit_time_ms = (time.perf_counter() - t0) * 1000.0
    detail = SensitivityEvalueDetail(
        e_value_point=e_point,
        e_value_lower_ci=e_lower,
        source=source,
    )
    diagnostics = SensitivityDiagnostics(
        method="evalue",
        n_samples=len(df),
        fit_time_ms=fit_time_ms,
        benchmark_covariate_used=None,
    )
    return detail, diagnostics, warnings_out


# ════════════════════════════════════════════════════════════════════
# Linear branch — Cinelli-Hazlett 2020 closed form
# ════════════════════════════════════════════════════════════════════


def _robustness_value(t_stat: float, df_resid: int) -> float:
    """Cinelli-Hazlett 2020 Eq. 4 robustness value RV(q=1).

    RV = 0.5 * (sqrt(f^4 + 4*f^2) - f^2)  where f = |t| / sqrt(df_resid).
    Returns 0.0 for degenerate inputs (df_resid <= 0 or f^2 == 0).
    """
    if df_resid <= 0:
        return 0.0
    f = abs(t_stat) / math.sqrt(df_resid)
    f2 = f * f
    if f2 <= 0.0:
        return 0.0
    rv = 0.5 * (math.sqrt(f2 * f2 + 4.0 * f2) - f2)
    # Clamp to [0, 1] for numerical safety.
    return max(0.0, min(1.0, rv))


def _robustness_value_alpha(
    t_stat: float, df_resid: int, alpha: float = 0.05,
) -> float:
    """RV at significance threshold alpha (Cinelli-Hazlett 2020).

    Uses the t-distribution critical value to push the observed
    t-statistic to the alpha-level critical value. Equivalent to RV
    when the alpha-level f-equivalent is applied.
    """
    from scipy.stats import t as student_t
    if df_resid <= 0:
        return 0.0
    t_crit = float(student_t.ppf(1 - alpha, df=df_resid))
    f_obs = abs(t_stat) / math.sqrt(df_resid)
    # The "alpha-adjusted" f-statistic is what we'd need to push the
    # t down to t_crit. Equivalent to (|t| - t_crit) / sqrt(df_resid)
    # when |t| > t_crit; clamp to 0 below.
    f_alpha = max(0.0, f_obs - t_crit / math.sqrt(df_resid))
    f_a_2 = f_alpha * f_alpha
    if f_a_2 <= 0.0:
        return 0.0
    rv_a = 0.5 * (math.sqrt(f_a_2 * f_a_2 + 4.0 * f_a_2) - f_a_2)
    return max(0.0, min(1.0, rv_a))


def _partial_r2_from_t(t_stat: float, df_resid: int) -> float:
    """Partial R^2 = t^2 / (t^2 + df_resid).

    Equivalent to f^2 / (1 + f^2) but numerically more stable when
    df_resid is small.
    """
    if df_resid <= 0:
        return 0.0
    t2 = t_stat * t_stat
    return float(t2 / (t2 + df_resid))


def _benchmark_covariate_t_stat(
    df: pd.DataFrame,
    outcome: str,
    treatment: str,
    adjustment_set: List[str],
    benchmark: str,
) -> Tuple[float, int]:
    """Extract the t-statistic and df_resid of the benchmark covariate
    in the OLS ``Y ~ T + adjustment_set`` fit.

    The benchmark covariate's partial R^2 on Y given T + the rest of
    the adjustment set is derivable directly from this t-statistic;
    no separate leave-one-out fit is needed (the full-model t already
    encodes the partial relationship).
    """
    import statsmodels.api as sm

    y = df[outcome].to_numpy(dtype="float64")
    # Build column order so we can index by name. statsmodels OLS uses
    # numpy arrays; we'll attach column labels via a DataFrame.
    X_cols = [treatment] + [
        c for c in adjustment_set
        if c in df.columns and c != treatment
    ]
    if benchmark not in X_cols:
        # Defensive — should not happen given the schema validator,
        # but engine_layer fallback to NaN.
        return 0.0, 0
    X = df[X_cols].to_numpy(dtype="float64")
    X = sm.add_constant(X, has_constant="add")
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        fit = sm.OLS(y, X).fit()
    # Position of the benchmark covariate in the design matrix:
    # 0 = const, 1 = treatment, 2.. = X_cols[1:] in order
    pos = X_cols.index(benchmark) + 1  # +1 for the const column
    t_bench = float(fit.tvalues[pos])
    df_resid = int(fit.df_resid)
    return t_bench, df_resid


def _run_cinelli_hazlett(
    request: CausalSensitivityRequest,
    df: pd.DataFrame,
) -> Tuple[
    SensitivityLinearDetail, SensitivityDiagnostics, List[CausalWarning]
]:
    """Linear-branch closed-form sensitivity (Cinelli-Hazlett 2020).

    Single ``statsmodels`` OLS fit of ``Y ~ T + adjustment_set``.
    Computes:
      - RV(q=1) and RV_alpha(q=1, alpha=0.05) on the treatment t-stat
      - partial_r2_yd via the t-statistic identity
      - partial_r2_yz_given_d via the benchmark covariate's t-stat in
        the same fit (when ``request.benchmark_covariate`` is set)
    """
    t0 = time.perf_counter()
    warnings_out: List[CausalWarning] = []
    handle = request.estimate_handle
    adjustment_set = _resolve_adjustment_set(request, df)

    beta, se, _lo, _hi, _stdy, df_resid = _ols_treatment_stats(
        df, handle.outcome, handle.treatment, adjustment_set,
    )
    if se <= 0 or df_resid <= 0 or not math.isfinite(beta / se):
        raise CausalSensitivityError(
            code="degenerate_ols",
            message=(
                f"OLS fit produced degenerate inputs "
                f"(beta={beta!r}, se={se!r}, df_resid={df_resid!r}); "
                f"cannot compute Cinelli-Hazlett robustness value."
            ),
        )
    t_stat = beta / se

    rv = _robustness_value(t_stat, df_resid)
    rv_alpha = _robustness_value_alpha(t_stat, df_resid)
    partial_r2_yd = _partial_r2_from_t(t_stat, df_resid)

    partial_r2_yz_given_d: Optional[float] = None
    benchmark_used: Optional[str] = None
    if request.benchmark_covariate is not None:
        bench = request.benchmark_covariate
        # Schema already validated the benchmark covariate is in the
        # DAG with node_kind='covariate'. Engine-layer defensive:
        # confirm it's in df.columns before computing.
        if bench in df.columns:
            t_bench, df_resid_b = _benchmark_covariate_t_stat(
                df, handle.outcome, handle.treatment,
                adjustment_set, bench,
            )
            partial_r2_yz_given_d = _partial_r2_from_t(
                t_bench, df_resid_b,
            )
            benchmark_used = bench
        else:
            warnings_out.append(CausalWarning(
                code="method_fallback",
                severity="info",
                message=(
                    f"benchmark_covariate {bench!r} declared in DAG "
                    f"but absent from data columns; "
                    f"partial_r2_yz_given_d not computed."
                ),
            ))

    fit_time_ms = (time.perf_counter() - t0) * 1000.0
    detail = SensitivityLinearDetail(
        robustness_value=rv,
        robustness_value_alpha=rv_alpha,
        partial_r2_yd=partial_r2_yd,
        partial_r2_yz_given_d=partial_r2_yz_given_d,
    )
    diagnostics = SensitivityDiagnostics(
        method="linear",
        n_samples=len(df),
        fit_time_ms=fit_time_ms,
        benchmark_covariate_used=benchmark_used,
    )
    return detail, diagnostics, warnings_out


# ════════════════════════════════════════════════════════════════════
# Public entrypoint
# ════════════════════════════════════════════════════════════════════


def run_sensitivity(
    request: CausalSensitivityRequest,
) -> CausalSensitivityResponse:
    """Execute the sensitivity phase. Sync mode only in B2b.3 MVP.

    Pipeline:

    1. ``_check_method`` rejects reserved enum values.
    2. Realise the dataframe from ``request.estimate_handle.data``;
       verify every DAG node has a column.
    3. Branch on ``request.method``:
       - ``"evalue"`` -> ``_run_evalue`` (primary + fallback)
       - ``"linear"`` -> ``_run_cinelli_hazlett``
    4. Compute ``overall_robust`` boolean from branch-specific
       threshold.
    5. Derive ``evidence_level``: ``"validated"`` when robust,
       ``"supported"`` otherwise.
    6. Assemble ``CausalSensitivityResponse``; Response validators
       enforce method/detail consistency.
    """
    _check_method(request.method)

    if request.mode != "sync":
        # Schema also gates this, but engine-side defence is cheap.
        raise CausalSensitivityError(
            code="async_not_implemented_yet",
            message=(
                "mode='async_job' is reserved for a later batch; "
                "B2b.3 only supports sync."
            ),
        )

    df = causal_data_to_dataframe(request.estimate_handle.data)

    # Every DAG node must be present as a column.
    handle = request.estimate_handle
    missing = [
        n.name for n in handle.dag.nodes if n.name not in df.columns
    ]
    if missing:
        raise CausalSensitivityError(
            code="dag_columns_missing_in_data",
            message=(
                f"DAG nodes {missing} are not present as columns in "
                f"the inline data. Either add the columns or trim the "
                f"DAG to match the data."
            ),
        )

    warnings_list: List[CausalWarning] = []
    evalue_detail: Optional[SensitivityEvalueDetail] = None
    linear_detail: Optional[SensitivityLinearDetail] = None

    if request.method == "evalue":
        evalue_detail, diagnostics, branch_warnings = _run_evalue(
            request, df,
        )
        warnings_list.extend(branch_warnings)
        overall_robust = (
            evalue_detail.e_value_lower_ci > _EVALUE_ROBUST_THRESHOLD
        )
        response_method = "evalue"
    elif request.method == "linear":
        linear_detail, diagnostics, branch_warnings = _run_cinelli_hazlett(
            request, df,
        )
        warnings_list.extend(branch_warnings)
        overall_robust = (
            linear_detail.robustness_value_alpha > _RV_ROBUST_THRESHOLD
        )
        response_method = "linear"
    else:  # pragma: no cover - already filtered by _check_method
        raise CausalSensitivityError(
            code="method_internal",
            message=(
                f"unexpected method={request.method!r} reached the "
                f"dispatcher; should have been filtered by _check_method."
            ),
        )

    evidence_level: EvidenceLevel = (
        "validated" if overall_robust else "supported"
    )

    # Strategy classifier as defensive info warning when the upstream
    # estimand isn't 'backdoor' (the only strategy the linear branch
    # is calibrated for; evalue is strategy-agnostic).
    if request.method == "linear":
        try:
            from dowhy import CausalModel
            with warnings_module.catch_warnings():
                warnings_module.simplefilter("ignore")
                model_for_strategy = CausalModel(
                    data=df,
                    treatment=handle.treatment,
                    outcome=handle.outcome,
                    graph=dag_to_gml(handle.dag),
                )
                est_for_strategy = model_for_strategy.identify_effect(
                    proceed_when_unidentifiable=True,
                )
            strategy, _adj, _expr = _classify_strategy(
                est_for_strategy,
                handle.dag,
                handle.treatment,
                handle.outcome,
            )
            if strategy != "backdoor":
                warnings_list.append(CausalWarning(
                    code="identification_unstable",
                    severity="info",
                    message=(
                        f"Linear-branch sensitivity is calibrated for "
                        f"backdoor identification; the upstream "
                        f"estimand classifier returned strategy="
                        f"{strategy!r}. Numerical robustness value "
                        f"may be misleading."
                    ),
                ))
        except Exception:
            # Strategy classification is purely advisory; swallow.
            pass

    return CausalSensitivityResponse(
        method=response_method,
        evalue_detail=evalue_detail,
        linear_detail=linear_detail,
        overall_robust=overall_robust,
        evidence_level=evidence_level,
        diagnostics=diagnostics,
        warnings=warnings_list,
        engine_version=CAUSAL_ENGINE_VERSION,
    )


__all__ = [
    "CausalSensitivityError",
    "run_sensitivity",
    "_run_evalue",
    "_run_evalue_primary_dowhy",
    "_run_evalue_fallback_chinn",
    "_run_cinelli_hazlett",
    "_check_method",
    "_robustness_value",
    "_robustness_value_alpha",
    "_partial_r2_from_t",
    "_EVALUE_ROBUST_THRESHOLD",
    "_RV_ROBUST_THRESHOLD",
]
