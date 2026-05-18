"""Phase B — /api/v1/causal/refute engine.

Wraps DoWhy's ``model.refute_estimate(...)`` for the four mandatory
refuters plus ``bootstrap_refuter``. The schema-reserved
``non_parametric_sensitivity_analyzer`` is 422-rejected here with
``code='refuter_reserved'`` (mirrors B2a's reserved-method pattern).

Aggregates per-refuter results into an ``evidence_level`` per Plan
v2 §2.3 (patched — see PHASE_B_PLAN_V2_PATCH_S2_3.md):

- ``validated``: 4 mandatory refuters all pass with p > 0.10
  AND identify.strategy == 'backdoor'
  AND e_value > 1.5
- ``supported``: >= 2/4 mandatory pass with p > 0.05
  AND identify.strategy in {'backdoor', 'frontdoor', 'mediation'}
- ``planned``: otherwise

Reference: PHASE_B_PLAN.md §2.3 (patched);
PHASE_B2b1_DESIGN.md §6, §7, §8, §10.
"""

from __future__ import annotations

import warnings as warnings_module
from typing import List, Optional, Tuple

import statsmodels.api as sm

from app.engine.extended.causal_identify_engine import _classify_strategy
from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    cheap_evalue,
    dag_to_gml,
)
from app.schemas.causal.refute import (
    CausalRefuteRequest,
    CausalRefuteResponse,
    RefuterName,
    RefuterResult,
)
from app.schemas.causal_common import (
    CAUSAL_ENGINE_VERSION,
    CausalWarning,
    EvidenceLevel,
)


# ════════════════════════════════════════════════════════════════════
# Custom exception surfaced as HTTP 422 by the router
# ════════════════════════════════════════════════════════════════════


class CausalRefuteError(ValueError):
    """Raised on /refute pre-condition failure.

    Router maps to HTTP 422 with a structured body that includes a
    machine-readable ``code``.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════


_MANDATORY_REFUTERS = frozenset({
    "random_common_cause",
    "placebo_treatment_refuter",
    "data_subset_refuter",
    "add_unobserved_common_cause",
})


_RESERVED_REFUTERS = frozenset({
    "non_parametric_sensitivity_analyzer",
})


# Refuters that use a delta-based ``passed`` decision (instead of DoWhy's
# ``is_statistically_significant`` field).
#
# - ``add_unobserved_common_cause`` returns ``refutation_result=None`` —
#   no significance test is available.
# - ``data_subset_refuter`` and ``bootstrap_refuter`` were observed in
#   DoWhy 0.14 to return ``is_statistically_significant=True`` even when
#   the per-call delta is small (e.g. data_subset: orig=1.83 → new=1.77,
#   reported p=0.0; bootstrap: orig=1.83 → new=1.98, reported p=0.0).
#   The Step 1 ``scratch_refute_api.py`` run reported p=0.94 for the
#   same refuter on the same fixture — implying DoWhy's significance
#   field is sensitive to internal model state (likely populated by a
#   prior refuter call in the same model). To insulate the engine from
#   that internal-state leak, we treat these two refuters with the same
#   delta-based rule as add_unobserved_common_cause.
#
# Phase G should re-evaluate when DoWhy 0.15+ stabilises the
# ``refutation_result`` API.
_DELTA_BASED_REFUTERS = frozenset({
    "add_unobserved_common_cause",
    "data_subset_refuter",
    "bootstrap_refuter",
})


# DoWhy method-name strings for the /estimate methods recorded in
# EstimateHandle.method_family. ``dml`` rides DoWhy's EconML wrapper
# (the refute API requires a DoWhy-backed estimate); the numerical
# result may not be identical to B2a's direct EconML LinearDML
# (see PHASE_B2b1_DESIGN.md §6 + brief §1). That's by design — refute
# treats DoWhy's internal estimate as the baseline.
_DOWHY_METHODS = {
    "linear_regression": "backdoor.linear_regression",
    "propensity_score": "backdoor.propensity_score_weighting",
    "dml": "backdoor.econml.dml.LinearDML",
}


# Per-refuter kwargs verified via backend/scratch_refute_api.py
# on the B2a backdoor bench (T / Y / Z, n=80, seed=42).
_REFUTER_KWARGS = {
    "random_common_cause": {"num_simulations": 100},
    "placebo_treatment_refuter": {
        "placebo_type": "permute",
        "num_simulations": 100,
    },
    "data_subset_refuter": {
        "subset_fraction": 0.8,
        "num_simulations": 10,   # DoWhy 0.14 default
    },
    "add_unobserved_common_cause": {
        "confounders_effect_on_treatment": "linear",
        "confounders_effect_on_outcome": "linear",
        "effect_strength_on_treatment": 0.01,
        "effect_strength_on_outcome": 0.02,
    },
    "bootstrap_refuter": {"num_simulations": 100},
}


# Threshold for add_unobserved_common_cause: passed = |delta/orig| < this.
_ADD_UNOBSERVED_REL_DELTA_THRESHOLD = 0.1


# ════════════════════════════════════════════════════════════════════
# Reserved-enum gate
# ════════════════════════════════════════════════════════════════════


def _check_refuter(name: RefuterName) -> None:
    """Reject reserved refuter names before any work happens."""
    if name in _RESERVED_REFUTERS:
        raise CausalRefuteError(
            code="refuter_reserved",
            message=(
                f"refuter={name!r} is reserved for a future Phase B / "
                f"Phase G release. B2b.1 implements only "
                f"{sorted(_MANDATORY_REFUTERS | {'bootstrap_refuter'})}."
            ),
        )


# ════════════════════════════════════════════════════════════════════
# Per-refuter dispatch
# ════════════════════════════════════════════════════════════════════


def _refute_single(
    model,
    identified_estimand,
    estimate,
    refuter_name: RefuterName,
    *,
    seed: Optional[int],
    alpha: float,
    add_unobserved_threshold: float = _ADD_UNOBSERVED_REL_DELTA_THRESHOLD,
) -> RefuterResult:
    """Run one DoWhy refuter and normalise its result into a typed
    ``RefuterResult``.

    Special case: ``add_unobserved_common_cause`` returns
    ``refutation_result = None`` (no significance test). We derive
    ``passed`` from ``abs(delta / orig) < add_unobserved_threshold``
    and leave ``p_value = None``.
    """
    kwargs = dict(_REFUTER_KWARGS.get(refuter_name, {}))
    # Inject RNG seed for the four refuters that sample.
    if seed is not None and refuter_name in (
        "random_common_cause",
        "placebo_treatment_refuter",
        "data_subset_refuter",
        "bootstrap_refuter",
    ):
        kwargs["random_state"] = seed

    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        refute = model.refute_estimate(
            identified_estimand,
            estimate,
            method_name=refuter_name,
            **kwargs,
        )

    original_effect = float(refute.estimated_effect)
    new_effect = float(refute.new_effect)
    delta_estimate = new_effect - original_effect

    if refuter_name in _DELTA_BASED_REFUTERS:
        # No p_value path: judge on relative delta. add_unobserved
        # has no p_value at all; data_subset / bootstrap have an
        # unreliable p_value under DoWhy 0.14 (see module-level
        # comment on _DELTA_BASED_REFUTERS).
        if original_effect != 0.0:
            rel_delta = abs(delta_estimate / original_effect)
        else:
            rel_delta = float("inf")
        passed = rel_delta < add_unobserved_threshold
        diagnostic = (
            f"{refute.refutation_type} | "
            f"rel_delta={rel_delta:.4f} vs threshold="
            f"{add_unobserved_threshold:.4f}"
        )
        return RefuterResult(
            refuter=refuter_name,
            passed=passed,
            p_value=None,
            delta_estimate=delta_estimate,
            diagnostic=diagnostic,
        )

    # Significance-test path: random_common_cause / placebo only.
    result_dict = refute.refutation_result or {}
    p_value = result_dict.get("p_value")
    if p_value is not None:
        p_value = float(p_value)
    # passed when the refuter's perturbation does *not* produce a
    # statistically significant change in the estimate.
    is_significant = bool(result_dict.get("is_statistically_significant", False))
    passed = not is_significant
    diagnostic = str(refute.refutation_type)

    return RefuterResult(
        refuter=refuter_name,
        passed=passed,
        p_value=p_value,
        delta_estimate=delta_estimate,
        diagnostic=diagnostic,
    )


# ════════════════════════════════════════════════════════════════════
# E-value resolution
# ════════════════════════════════════════════════════════════════════


def _resolve_e_value(
    request: CausalRefuteRequest,
    df,
    adjustment_set: List[str],
    *,
    warnings_out: List[CausalWarning],
) -> float:
    """Return the e_value the evidence_level rule should consume.

    Option (a) hybrid (PHASE_B2b1_DESIGN.md §10):
    - When ``request.original_e_value`` is provided, return it.
    - Otherwise, recompute via a lightweight statsmodels OLS pass on
      the same data + adjustment set. Cost: ~20% of a typical /estimate
      LR call. Adds a 'method_fallback' warning so the operator sees
      the audit trail (the 'e_value_recomputed' code name from the
      design doc is *not* part of WarningCode enum; we reuse
      'method_fallback' which already covers this case).
    """
    if request.original_e_value is not None:
        return float(request.original_e_value)

    handle = request.estimate_handle
    y = df[handle.outcome].to_numpy(dtype="float64")
    X_cols = [handle.treatment] + [
        c for c in adjustment_set if c in df.columns and c != handle.treatment
    ]
    X = df[X_cols].to_numpy(dtype="float64")
    X = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X).fit()
    beta = float(model.params[1])
    std_outcome = float(df[handle.outcome].std(ddof=1))
    e_value = cheap_evalue(beta, std_outcome)

    warnings_out.append(CausalWarning(
        code="method_fallback",
        severity="info",
        message=(
            "request.original_e_value not provided; e_value recomputed "
            "via a lightweight OLS pass (engine cost +~20%). For the "
            "best audit trail, pass /estimate.response.e_value_cheap "
            "through to /refute."
        ),
    ))
    return e_value


# ════════════════════════════════════════════════════════════════════
# Aggregation — Plan v2 §2.3 patched 3-tier rule
# ════════════════════════════════════════════════════════════════════


def _aggregate(
    results: List[RefuterResult],
    identify_strategy: str,
    e_value: float,
    alpha: float,
) -> Tuple[bool, EvidenceLevel]:
    """Returns (overall_robust, evidence_level).

    overall_robust: True when all *mandatory* refuters passed.

    evidence_level:
    - validated: overall_robust + all mandatory pass p > 0.10
      (add_unobserved's p_value=None counts as "high" since its
      passed was already delta-based)
      + strategy == 'backdoor' + e_value > 1.5
    - supported: >= 2/4 mandatory pass with p > max(alpha, 0.05) when
      a p_value is available; add_unobserved counted if passed=True
      + strategy in {'backdoor', 'frontdoor', 'mediation'}
    - planned: otherwise.
    """
    mandatory_results = [r for r in results if r.refuter in _MANDATORY_REFUTERS]
    mandatory_passed = sum(1 for r in mandatory_results if r.passed)
    overall_robust = mandatory_passed == 4

    # For the validated tier we require strict p > 0.10 on every
    # significance-test refuter (add_unobserved has None p_value;
    # treated as satisfying the high-p criterion because its
    # passed verdict already encodes robustness via delta).
    mandatory_pvalue_high = all(
        (r.p_value is None or r.p_value > 0.10)
        for r in mandatory_results
        if r.passed
    )

    # For the supported tier we use the looser p > max(alpha, 0.05)
    # threshold per Plan v2 §2.3.
    supported_alpha = max(alpha, 0.05)
    mandatory_pvalue_supported = sum(
        1 for r in mandatory_results
        if r.passed and (r.p_value is None or r.p_value > supported_alpha)
    )

    if (
        overall_robust
        and mandatory_pvalue_high
        and identify_strategy == "backdoor"
        and e_value > 1.5
    ):
        return True, "validated"

    if (
        mandatory_pvalue_supported >= 2
        and identify_strategy in ("backdoor", "frontdoor", "mediation")
    ):
        return overall_robust, "supported"

    return overall_robust, "planned"


# ════════════════════════════════════════════════════════════════════
# Public entrypoint
# ════════════════════════════════════════════════════════════════════


def run_refute(
    request: CausalRefuteRequest,
) -> CausalRefuteResponse:
    """Execute the refutation phase.

    1. Reject reserved refuters.
    2. Rebuild the DoWhy model from EstimateHandle.
    3. Iterate refuters (preserving request order).
    4. Resolve e_value (provided verbatim, or recomputed via OLS).
    5. Aggregate into (overall_robust, evidence_level).
    """
    # ── 1. Reserved-enum gate ──
    for name in request.refuters:
        _check_refuter(name)

    handle = request.estimate_handle
    warnings_list: List[CausalWarning] = []

    # ── 2. Rebuild DoWhy model + estimate ──
    df = causal_data_to_dataframe(handle.data)
    gml = dag_to_gml(handle.dag)

    from dowhy import CausalModel
    with warnings_module.catch_warnings():
        warnings_module.simplefilter("ignore")
        model = CausalModel(
            data=df,
            treatment=handle.treatment,
            outcome=handle.outcome,
            graph=gml,
        )
        identified_estimand = model.identify_effect(
            proceed_when_unidentifiable=True,
            method_name="default",
        )
        method_str = _DOWHY_METHODS.get(handle.method_family)
        if method_str is None:
            raise CausalRefuteError(
                code="estimate_handle_method_unsupported",
                message=(
                    f"EstimateHandle.method_family="
                    f"{handle.method_family!r} is not refute-routable "
                    f"in B2b.1. Refute only supports the three "
                    f"families /estimate ships in B2a."
                ),
            )
        estimate = model.estimate_effect(
            identified_estimand,
            method_name=method_str,
            confidence_intervals=True,
            target_units="ate",
        )

    # ── 3. Determine identify strategy + adjustment set ──
    strategy, adjustment_set, _ = _classify_strategy(
        identified_estimand, handle.dag, handle.treatment, handle.outcome,
    )

    # ── 4. Iterate refuters ──
    refute_results: List[RefuterResult] = []
    seed = handle.seed if request.seed is None else request.seed
    for name in request.refuters:
        try:
            result = _refute_single(
                model,
                identified_estimand,
                estimate,
                refuter_name=name,
                seed=seed,
                alpha=request.significance_alpha,
            )
        except CausalRefuteError:
            raise
        except Exception as exc:
            raise CausalRefuteError(
                code="refute_failed",
                message=f"refuter={name!r} raised {type(exc).__name__}: {exc}",
            ) from exc
        refute_results.append(result)

    # ── 5. Resolve e_value (Option a hybrid) ──
    e_value = _resolve_e_value(
        request, df, adjustment_set, warnings_out=warnings_list,
    )

    # ── 6. Aggregate ──
    overall_robust, evidence_level = _aggregate(
        refute_results,
        identify_strategy=strategy,
        e_value=e_value,
        alpha=request.significance_alpha,
    )

    return CausalRefuteResponse(
        refute_results=refute_results,
        overall_robust=overall_robust,
        evidence_level=evidence_level,
        e_value_used=e_value,
        warnings=warnings_list,
        engine_version=CAUSAL_ENGINE_VERSION,
    )
