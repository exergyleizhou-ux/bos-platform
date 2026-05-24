"""Phase C C2 — /api/v1/causal/conformal_predict engine.

Custom split-conformal + Mondrian-conformal implementation (no
mapie/crepes dependency). The full algorithm is ~50 LOC of numpy;
Mondrian extension adds ~30 LOC.

Reference:
- Lei & Wasserman 2014 (split conformal)
- Vovk et al. 2005 (Mondrian conformal)
- _reports/PHASE_C_PLAN.md §2.2
- _reports/PHASE_C_C2_DESIGN.md

Algorithm:
1. Split data into train (1-f) + calibration (f).
2. Fit internal OLS regressor on train.
3. Compute |residuals| on calibration.
4. q = (1-α) quantile of residuals (with finite-sample
   ``method='higher'`` correction).
5. For new x: Ĉ(x) = [μ̂(x) - q, μ̂(x) + q].

Mondrian extension: step 4 stratifies by stratum_variable, giving
per-stratum quantiles. Step 5 looks up the new observation's
stratum and uses its quantile.

Coverage guarantee: P(Y ∈ Ĉ(X)) ≥ 1 - α (marginal, finite-sample,
distribution-free under exchangeability assumption between train
and calibration).
"""

from __future__ import annotations

import time
import warnings as warnings_module
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
)
from app.schemas.causal_common import (
    CausalWarning,
    EvidenceLevel,
)
from app.schemas.causal.conformal import (
    ConformalMethod,
    ConformalPrediction,
    ConformalPredictRequest,
    ConformalPredictResponse,
)


# ════════════════════════════════════════════════════════════════════
# Public entry point
# ════════════════════════════════════════════════════════════════════


def predict_conformal(
    request: ConformalPredictRequest,
) -> Tuple[ConformalPredictResponse, List[CausalWarning]]:
    """Compute conformal prediction intervals for new observations.

    Returns ``(response, warnings_list)``.

    Raises ``CausalConformalError`` with ``code`` attribute on
    domain failures (mapped to HTTP 422 at the API layer).
    """
    warnings_list: List[CausalWarning] = []

    # 1. Load data
    df = causal_data_to_dataframe(request.data)

    # 2. Backdoor variable selection (parents-of-{T,Y} from DAG)
    backdoor_vars = _select_backdoor_variables(request)

    # 3. Validate required columns
    required = {request.treatment, request.outcome} | set(backdoor_vars)
    if request.method == "mondrian_conformal":
        required.add(request.stratum_variable)
    missing = required - set(df.columns)
    if missing:
        raise CausalConformalError(
            code="data_columns_missing",
            message=(
                f"Data missing required columns: {sorted(missing)}."
            ),
        )

    # 4. Extract arrays. X_full includes treatment + backdoor as features.
    X_cols = [request.treatment] + backdoor_vars
    X_full = df[X_cols].to_numpy(dtype=float)
    Y_full = df[request.outcome].to_numpy(dtype=float)

    n = len(df)
    if n < 10:
        raise CausalConformalError(
            code="data_too_small",
            message=(
                f"Need at least 10 rows for conformal split; got n={n}."
            ),
        )

    # 5. Split train + calibration
    rng = np.random.default_rng(request.random_seed)
    indices = rng.permutation(n)
    n_cal = max(2, int(n * request.calibration_fraction))
    n_train = n - n_cal
    if n_train < 2:
        raise CausalConformalError(
            code="train_split_too_small",
            message=(
                f"Train split has only {n_train} rows after "
                f"calibration_fraction={request.calibration_fraction}; "
                f"need ≥ 2 for OLS."
            ),
        )

    cal_idx = indices[:n_cal]
    train_idx = indices[n_cal:]

    X_train, Y_train = X_full[train_idx], Y_full[train_idx]
    X_cal, Y_cal = X_full[cal_idx], Y_full[cal_idx]

    # 6. Fit internal OLS (add intercept column)
    beta_hat, intercept_hat = _fit_internal_ols(X_train, Y_train)

    # 7. Calibration residuals (absolute)
    Y_cal_pred = X_cal @ beta_hat + intercept_hat
    residuals = np.abs(Y_cal - Y_cal_pred)

    # 8. Compute quantile(s)
    coverage = 1.0 - request.alpha

    # Marginal quantile (used always; Mondrian uses per-stratum)
    marginal_q = float(np.quantile(
        residuals,
        coverage,
        method="higher",  # finite-sample correction
    ))

    per_stratum_quantiles: Optional[Dict[str, float]] = None
    strata_used: Optional[Dict[str, int]] = None

    if request.method == "mondrian_conformal":
        strata_col_full = df[request.stratum_variable].to_numpy()
        strata_cal = strata_col_full[cal_idx]
        per_stratum_quantiles = {}
        strata_used = {}
        for stratum in np.unique(strata_cal):
            mask = strata_cal == stratum
            n_in_stratum = int(mask.sum())
            stratum_key = str(stratum)
            strata_used[stratum_key] = n_in_stratum
            if n_in_stratum >= request.n_min_per_stratum:
                per_stratum_quantiles[stratum_key] = float(np.quantile(
                    residuals[mask], coverage, method="higher",
                ))
            else:
                # Fall back to marginal for small strata
                per_stratum_quantiles[stratum_key] = marginal_q
                warnings_list.append(
                    CausalWarning(
                        code="method_fallback",
                        message=(
                            f"Mondrian small_stratum: stratum "
                            f"{stratum_key!r} has only "
                            f"{n_in_stratum} cal samples "
                            f"(< n_min_per_stratum="
                            f"{request.n_min_per_stratum}); "
                            f"falling back to marginal quantile."
                        ),
                    )
                )

    # 9. Predict on new_observations
    predictions: List[ConformalPrediction] = []
    interval_widths: List[float] = []
    if request.new_observations:
        for obs in request.new_observations:
            # Validate required columns in obs
            missing_obs = set(X_cols) - set(obs.keys())
            if missing_obs:
                raise CausalConformalError(
                    code="new_obs_columns_missing",
                    message=(
                        f"New observation missing columns: "
                        f"{sorted(missing_obs)}."
                    ),
                )
            x_new = np.array([obs[c] for c in X_cols], dtype=float)
            y_hat = float(x_new @ beta_hat + intercept_hat)

            if request.method == "split_conformal":
                q = marginal_q
                stratum_val: Optional[str] = None
            else:
                # Mondrian
                stratum_obs = obs.get(request.stratum_variable)
                if stratum_obs is None:
                    raise CausalConformalError(
                        code="new_obs_stratum_missing",
                        message=(
                            f"Mondrian method requires "
                            f"{request.stratum_variable!r} in each "
                            f"new observation."
                        ),
                    )
                stratum_val = str(stratum_obs)
                q = (
                    per_stratum_quantiles.get(stratum_val, marginal_q)
                    if per_stratum_quantiles
                    else marginal_q
                )

            predictions.append(ConformalPrediction(
                point=y_hat,
                interval_low=y_hat - q,
                interval_high=y_hat + q,
                stratum=stratum_val,
            ))
            interval_widths.append(2 * q)

    # 10. Evidence-level classification
    evidence_level = _classify_evidence(
        n_cal=n_cal,
        method=request.method,
        per_stratum_n=strata_used,
        n_min_per_stratum=request.n_min_per_stratum,
        marginal_quantile=marginal_q,
        outcome_std=float(np.std(Y_full)),
    )

    median_width: Optional[float] = (
        float(np.median(interval_widths)) if interval_widths else None
    )

    # 11. Build response
    response = ConformalPredictResponse(
        predictions=predictions,
        coverage_guarantee=coverage,
        n_calibration_samples=n_cal,
        n_training_samples=n_train,
        marginal_quantile=marginal_q,
        median_interval_width=median_width,
        strata_used=strata_used,
        per_stratum_quantiles=per_stratum_quantiles,
        method=request.method,
        alpha=request.alpha,
        random_seed=request.random_seed,
        evidence_level=evidence_level,
        warnings=warnings_list,
        treatment=request.treatment,
        outcome=request.outcome,
        backdoor_variables=backdoor_vars,
    )

    return response, warnings_list


# ════════════════════════════════════════════════════════════════════
# Exception
# ════════════════════════════════════════════════════════════════════


class CausalConformalError(Exception):
    """Domain exception for conformal-prediction failures.

    Maps to HTTP 422 with ``{code, message}`` detail at the router
    layer (mirrors B2a / C1 engine exception conventions).
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ════════════════════════════════════════════════════════════════════
# Internal helpers
# ════════════════════════════════════════════════════════════════════


def _select_backdoor_variables(
    request: ConformalPredictRequest,
) -> List[str]:
    """Parents-of-(T ∪ Y) heuristic from the DAG, mirroring C1."""
    dag = request.dag
    treatment = request.treatment
    outcome = request.outcome

    parents = set()
    for edge in dag.edges:
        if edge.dst == treatment:
            parents.add(edge.src)
        if edge.dst == outcome:
            parents.add(edge.src)

    backdoor = (parents - {treatment, outcome})
    return sorted(backdoor)


def _fit_internal_ols(
    X: np.ndarray, Y: np.ndarray
) -> Tuple[np.ndarray, float]:
    """Fit y = X @ beta + intercept via least squares.

    Returns (beta_hat, intercept_hat) where beta_hat has shape
    (n_features,) and intercept_hat is a scalar.

    Uses np.linalg.lstsq on the augmented [X | 1] design matrix.
    """
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D, got shape {X.shape}")
    n, p = X.shape
    X_aug = np.column_stack([X, np.ones(n)])
    coef, _residuals, _rank, _sv = np.linalg.lstsq(X_aug, Y, rcond=None)
    beta_hat = coef[:p]
    intercept_hat = float(coef[p])
    return beta_hat, intercept_hat


def _classify_evidence(
    n_cal: int,
    method: ConformalMethod,
    per_stratum_n: Optional[Dict[str, int]],
    n_min_per_stratum: int,
    marginal_quantile: float,
    outcome_std: float,
) -> EvidenceLevel:
    """C2 evidence-level rules (per C2 Design §3.4).

    - validated: cal n ≥ 30; Mondrian: all strata n ≥ 20;
      marginal quantile < 50% of outcome std
    - supported: cal n ≥ 10
    - planned: otherwise
    """
    if n_cal < 10:
        return "planned"

    # For Mondrian, check stratum sizes
    if method == "mondrian_conformal" and per_stratum_n:
        small_strata = [
            s for s, n in per_stratum_n.items()
            if n < n_min_per_stratum
        ]
        if small_strata:
            return "supported"

    if n_cal < 30:
        return "supported"

    # validated: interval informative (< 50% of outcome std)
    if outcome_std > 0 and marginal_quantile < 0.5 * outcome_std:
        return "validated"

    return "supported"
