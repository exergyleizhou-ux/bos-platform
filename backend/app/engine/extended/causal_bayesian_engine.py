"""Phase C C1 — /api/v1/causal/bayesian_estimate engine.

Wraps PyMC 5.x NUTS sampler to compute posterior over the treatment-
effect coefficient under backdoor adjustment. Complements Phase B
B2a LinearDML by providing full posterior characterisation
(HDI + samples) instead of frequentist point + CI.

Reference: _reports/PHASE_C_PLAN.md §2.1 + _reports/PHASE_C_C1_DESIGN.md.

Method dispatch:
- ``bayesian_backdoor`` → ``_run_bayesian_backdoor``: PyMC linear
  regression with weakly informative priors over (beta_T, beta_X,
  sigma_y). Posterior on beta_T is interpreted as the ATE posterior.
- ``bayesian_dml`` → 422-rejected with ``code='method_reserved'``
  (mirrors B2a's ``method_family_reserved`` pattern). Reserved for
  a future Phase C C2+ ship that pairs Double Machine Learning with
  Bayesian uncertainty.

PyMC version pinned to 5.10+ (numpy 2.x compatible). PyTensor
backend may fall back to pure-Python evaluation if a C++ compiler
is unavailable — sampling will be slower (~30-60s per call instead
of ~10s) but mathematically identical.
"""

from __future__ import annotations

import time
import warnings as warnings_module
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    count_per_stratum,
)
from app.schemas.causal_common import (
    CausalWarning,
    EvidenceLevel,
    IdentifiedEstimandHandle,
)
from app.schemas.causal.bayesian import (
    BayesianDiagnostics,
    BayesianEstimateRequest,
    BayesianEstimateResponse,
    BayesianMethod,
)


# ════════════════════════════════════════════════════════════════════
# Public entry point
# ════════════════════════════════════════════════════════════════════


def estimate_ate_bayesian(
    request: BayesianEstimateRequest,
) -> Tuple[BayesianEstimateResponse, List[CausalWarning]]:
    """Estimate ATE posterior via PyMC backdoor regression.

    Returns:
        (response, warnings_list)

    Raises:
        ``CausalBayesianError`` with ``code='method_reserved'`` when
        the request specifies a reserved method (e.g. ``bayesian_dml``).
    """
    warnings_list: List[CausalWarning] = []

    # Method dispatch: reject reserved methods
    if request.method == "bayesian_dml":
        raise CausalBayesianError(
            code="method_reserved",
            message=(
                "method=bayesian_dml is reserved for Phase C C2+ and "
                "not implemented in C1. Use method=bayesian_backdoor "
                "instead, or wait for the Bayesian-DML extension in a "
                "future release."
            ),
        )

    if request.method != "bayesian_backdoor":
        raise CausalBayesianError(
            code="method_unknown",
            message=f"Unknown method: {request.method!r}",
        )

    # Dispatch to bayesian_backdoor implementation
    return _run_bayesian_backdoor(request, warnings_list)


# ════════════════════════════════════════════════════════════════════
# Exception class
# ════════════════════════════════════════════════════════════════════


class CausalBayesianError(Exception):
    """Domain exception for Bayesian estimation failures.

    The ``code`` attribute is exposed to the API layer as HTTP 422
    response code. The ``message`` is the human-readable explanation.
    Mirrors Phase B engine exception conventions.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ════════════════════════════════════════════════════════════════════
# Backdoor variable selection
# ════════════════════════════════════════════════════════════════════


def _select_backdoor_variables(
    request: BayesianEstimateRequest,
) -> List[str]:
    """Derive the backdoor adjustment set.

    Strategy:
    1. If ``precomputed_estimand`` provided: use its adjustment_set
       verbatim (matches B2a estimate pattern).
    2. Else: derive from DAG topology — all non-descendants of
       treatment that are parents of either treatment or outcome.

    The C1 implementation uses a simple "parents-of-treatment-and-
    outcome" heuristic since DoWhy is not invoked here (avoiding a
    second sampling-phase dependency). Operators wanting full DoWhy
    identification semantics should first call /identify and pass
    the result via ``precomputed_estimand``.
    """
    # Path 1: precomputed_estimand
    if request.precomputed_estimand is not None:
        return list(request.precomputed_estimand.adjustment_set)

    # Path 2: derive from DAG topology (simplified)
    dag = request.dag
    treatment = request.treatment
    outcome = request.outcome

    # Find direct parents of treatment + direct parents of outcome.
    # Exclude treatment/outcome themselves.
    # DagEdge schema uses ``src`` / ``dst`` (not ``source`` / ``target``).
    parents_t = set()
    parents_y = set()
    for edge in dag.edges:
        if edge.dst == treatment:
            parents_t.add(edge.src)
        if edge.dst == outcome:
            parents_y.add(edge.src)

    backdoor = (parents_t | parents_y) - {treatment, outcome}

    # Sort for determinism
    return sorted(backdoor)


# ════════════════════════════════════════════════════════════════════
# Bayesian backdoor implementation
# ════════════════════════════════════════════════════════════════════


def _run_bayesian_backdoor(
    request: BayesianEstimateRequest,
    warnings_list: List[CausalWarning],
) -> Tuple[BayesianEstimateResponse, List[CausalWarning]]:
    """Run PyMC NUTS sampler on a linear backdoor regression.

    Model:
        beta_T ~ Normal(prior_treatment_mean, prior_treatment_sd**2)
        beta_X ~ Normal(0, prior_covariate_sd**2)   (one per covariate)
        sigma_y ~ HalfNormal(prior_noise_sd)
        Y | T, X ~ Normal(beta_T * T + beta_X · X, sigma_y**2)

    The posterior p(beta_T | data) is interpreted as the ATE posterior.
    """
    # Lazy imports — keep PyMC out of module-import path so that
    # other engines don't pay the ~5-10 second import cost just by
    # importing this module.
    import pymc as pm
    import arviz as az

    start_time = time.time()

    # 1. Realise the data envelope into a DataFrame
    df = causal_data_to_dataframe(request.data)

    # 2. Backdoor adjustment set
    backdoor_vars = _select_backdoor_variables(request)

    # 3. Validate that required columns are present
    required_cols = {request.treatment, request.outcome} | set(backdoor_vars)
    missing = required_cols - set(df.columns)
    if missing:
        raise CausalBayesianError(
            code="data_columns_missing",
            message=(
                f"Data is missing required columns: "
                f"{sorted(missing)}. Required: "
                f"{sorted(required_cols)}; "
                f"Available: {sorted(df.columns)}."
            ),
        )

    # 4. Extract arrays
    T = df[request.treatment].to_numpy(dtype=float)
    Y = df[request.outcome].to_numpy(dtype=float)
    if backdoor_vars:
        X = df[backdoor_vars].to_numpy(dtype=float)
    else:
        X = np.zeros((len(df), 0), dtype=float)

    n_samples_observed = len(df)

    # 5. Honest-power floor check (mirrors B2a)
    if n_samples_observed < request.n_min_per_stratum:
        warnings_list.append(
            CausalWarning(
                code="small_sample",
                message=(
                    f"n={n_samples_observed} < "
                    f"n_min_per_stratum={request.n_min_per_stratum}; "
                    f"evidence_level forced to 'planned'."
                ),
            )
        )

    # 6. Build PyMC model
    with pm.Model() as model:
        # Treatment coefficient (the parameter of interest)
        beta_T = pm.Normal(
            "beta_T",
            mu=request.prior_treatment_mean,
            sigma=request.prior_treatment_sd,
        )

        # Covariate coefficients (if any)
        if X.shape[1] > 0:
            beta_X = pm.Normal(
                "beta_X",
                mu=0.0,
                sigma=request.prior_covariate_sd,
                shape=X.shape[1],
            )
            mu_lin = beta_T * T + pm.math.dot(X, beta_X)
        else:
            mu_lin = beta_T * T

        # Noise
        sigma_y = pm.HalfNormal(
            "sigma_y",
            sigma=request.prior_noise_sd,
        )

        # Likelihood
        pm.Normal("Y_obs", mu=mu_lin, sigma=sigma_y, observed=Y)

        # Sample (suppress pytensor compile + sampler verbose noise)
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("ignore")
            idata = pm.sample(
                draws=request.n_draws,
                tune=request.n_tune,
                chains=request.n_chains,
                target_accept=request.target_accept,
                random_seed=request.random_seed,
                progressbar=False,
                return_inferencedata=True,
                compute_convergence_checks=False,
            )

    sampling_time = time.time() - start_time

    # 7. Extract posterior samples for the treatment coefficient
    # Shape: (n_chains, n_draws). Flatten for downstream use.
    posterior_array = idata.posterior["beta_T"].values
    posterior_samples = posterior_array.flatten()

    posterior_mean = float(np.mean(posterior_samples))
    posterior_sd = float(np.std(posterior_samples, ddof=1))

    # 8. HDI computation
    hdi_prob = request.confidence_level
    hdi_low, hdi_high = _compute_hdi(posterior_samples, hdi_prob)

    # 9. Diagnostics
    try:
        summary = az.summary(
            idata,
            var_names=["beta_T"],
            stat_focus="mean",
        )
        r_hat = float(summary["r_hat"].iloc[0])
        ess = float(summary["ess_bulk"].iloc[0])
    except Exception as exc:  # pragma: no cover — defensive
        warnings_list.append(
            CausalWarning(
                code="arviz_summary_failed",
                message=f"arviz.summary raised: {exc}",
            )
        )
        r_hat = float("nan")
        ess = 0.0

    # Divergent transitions
    n_divergent = 0
    try:
        n_divergent = int(
            idata.sample_stats["diverging"].sum().item()
        )
    except (KeyError, AttributeError):
        # Older PyMC / different inference data format
        pass

    if n_divergent > 0:
        warnings_list.append(
            CausalWarning(
                code="sampler_divergent",
                message=(
                    f"NUTS sampler reported {n_divergent} divergent "
                    f"transition(s). Often indicates prior "
                    f"misspecification or model identification issues. "
                    f"Consider widening priors or increasing "
                    f"target_accept."
                ),
            )
        )

    diagnostics = BayesianDiagnostics(
        r_hat=r_hat,
        effective_sample_size=ess,
        n_divergent=n_divergent,
        n_chains=request.n_chains,
        n_draws_per_chain=request.n_draws,
        n_tune=request.n_tune,
        sampling_time_seconds=sampling_time,
    )

    # 10. Evidence-level classification (per C1 Design §3.4)
    hdi_excludes_zero = (hdi_low > 0.0) or (hdi_high < 0.0)

    small_sample = (
        n_samples_observed < request.n_min_per_stratum
    )

    if small_sample:
        evidence_level: EvidenceLevel = "planned"
    elif (
        r_hat < 1.01
        and ess > 400.0
        and n_divergent == 0
        and hdi_excludes_zero
        and len(backdoor_vars) > 0
    ):
        evidence_level = "validated"
    elif (
        not np.isnan(r_hat)
        and r_hat < 1.05
        and ess > 100.0
        and hdi_excludes_zero
    ):
        evidence_level = "supported"
    else:
        evidence_level = "planned"

    # 11. Build response
    response = BayesianEstimateResponse(
        ate_point=posterior_mean,
        ate_posterior_mean=posterior_mean,
        ate_hdi_low=hdi_low,
        ate_hdi_high=hdi_high,
        ate_posterior_sd=posterior_sd,
        ate_posterior_samples=posterior_samples.tolist(),
        diagnostics=diagnostics,
        evidence_level=evidence_level,
        warnings=warnings_list,
        method="bayesian_backdoor",
        random_seed=request.random_seed,
        treatment=request.treatment,
        outcome=request.outcome,
        n_samples_observed=n_samples_observed,
        backdoor_variables=backdoor_vars,
    )

    return response, warnings_list


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


def _compute_hdi(
    samples: np.ndarray, hdi_prob: float
) -> Tuple[float, float]:
    """Compute the Highest Density Interval at the given probability.

    Uses ArviZ's hdi function when available; falls back to a quantile-
    based approximation otherwise.

    Returns:
        (low, high) tuple of floats.
    """
    # Try ArviZ first (preferred — correctly handles multimodal posteriors)
    try:
        import arviz as az

        hdi = az.hdi(samples, hdi_prob=hdi_prob)
        # ArviZ returns an ndarray of shape (2,) when input is 1-D
        return float(hdi[0]), float(hdi[1])
    except Exception:  # pragma: no cover — defensive
        # Fallback: symmetric quantile interval
        alpha = 1.0 - hdi_prob
        low = float(np.quantile(samples, alpha / 2.0))
        high = float(np.quantile(samples, 1.0 - alpha / 2.0))
        return low, high
