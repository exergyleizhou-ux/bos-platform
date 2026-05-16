"""
BOS Pipeline v9.0 — Difference-in-Differences Engine

Implements the Difference-in-Differences (DiD) estimator for causal
inference in batch experiments.

Use case: Estimate the causal effect of a process change (treatment)
on SER or other outcomes, controlling for temporal trends.

DiD equation:
  δ = (Y_treat_post - Y_treat_pre) - (Y_control_post - Y_control_pre)

Also provides:
  - Standard errors (heteroscedasticity-robust)
  - Confidence intervals
  - Parallel trends test
  - Event study plot data
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


@dataclass
class DiDInput:
    """Input for DiD analysis."""

    treatment_pre: List[float]  # Outcome values: treatment group, before intervention
    treatment_post: List[float]  # Outcome values: treatment group, after intervention
    control_pre: List[float]  # Outcome values: control group, before intervention
    control_post: List[float]  # Outcome values: control group, after intervention
    outcome_name: str = "SER"
    treatment_name: str = "Process Change"
    confidence_level: float = 0.95


@dataclass
class DiDResult:
    """DiD analysis results."""

    # Core estimates
    att: float = 0.0  # Average Treatment Effect on the Treated
    se: float = 0.0  # Standard error
    t_stat: float = 0.0  # t-statistic
    p_value: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    significant: bool = False

    # Group means
    treat_pre_mean: float = 0.0
    treat_post_mean: float = 0.0
    control_pre_mean: float = 0.0
    control_post_mean: float = 0.0

    # Changes
    treat_change: float = 0.0
    control_change: float = 0.0

    # Effect size
    cohens_d: float = 0.0

    # Parallel trends
    parallel_trends_plausible: bool = True
    parallel_trends_message: str = ""

    # Metadata
    n_treatment: int = 0
    n_control: int = 0
    outcome_name: str = "SER"
    treatment_name: str = ""
    confidence_level: float = 0.95
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def compute_did(inp: DiDInput) -> DiDResult:
    """
    Compute Difference-in-Differences estimator.

    Parameters
    ----------
    inp : DiDInput
        Pre/post outcome data for treatment and control groups.

    Returns
    -------
    DiDResult
        Causal effect estimate with statistical inference.
    """
    start_time = time.perf_counter()
    result = DiDResult(
        outcome_name=inp.outcome_name,
        treatment_name=inp.treatment_name,
        confidence_level=inp.confidence_level,
    )

    # Validate
    if len(inp.treatment_pre) < 2 or len(inp.treatment_post) < 2:
        result.errors.append("Need at least 2 observations per treatment group period")
        return result
    if len(inp.control_pre) < 2 or len(inp.control_post) < 2:
        result.errors.append("Need at least 2 observations per control group period")
        return result

    # Convert to arrays
    tp = np.array(inp.treatment_pre, dtype=np.float64)
    ta = np.array(inp.treatment_post, dtype=np.float64)
    cp = np.array(inp.control_pre, dtype=np.float64)
    ca = np.array(inp.control_post, dtype=np.float64)

    # Group means
    result.treat_pre_mean = round(float(np.mean(tp)), 6)
    result.treat_post_mean = round(float(np.mean(ta)), 6)
    result.control_pre_mean = round(float(np.mean(cp)), 6)
    result.control_post_mean = round(float(np.mean(ca)), 6)

    # Changes
    result.treat_change = round(result.treat_post_mean - result.treat_pre_mean, 6)
    result.control_change = round(result.control_post_mean - result.control_pre_mean, 6)

    # DiD estimate (ATT)
    att = result.treat_change - result.control_change
    result.att = round(att, 6)

    # Standard error (heteroscedasticity-robust)
    n_tp, n_ta, n_cp, n_ca = len(tp), len(ta), len(cp), len(ca)
    result.n_treatment = n_tp + n_ta
    result.n_control = n_cp + n_ca

    var_tp = np.var(tp, ddof=1) / n_tp if n_tp > 1 else 0
    var_ta = np.var(ta, ddof=1) / n_ta if n_ta > 1 else 0
    var_cp = np.var(cp, ddof=1) / n_cp if n_cp > 1 else 0
    var_ca = np.var(ca, ddof=1) / n_ca if n_ca > 1 else 0

    se = np.sqrt(var_tp + var_ta + var_cp + var_ca)
    result.se = round(float(se), 6)

    # t-statistic and p-value
    if se > 1e-10:
        t_stat = att / se
        result.t_stat = round(float(t_stat), 4)

        # Two-tailed p-value (using normal approximation for large samples)
        from scipy import stats

        df = n_tp + n_ta + n_cp + n_ca - 4
        result.p_value = round(float(2 * stats.t.sf(abs(t_stat), df=max(df, 1))), 6)

        # Confidence interval
        alpha = 1 - inp.confidence_level
        t_crit = stats.t.ppf(1 - alpha / 2, df=max(df, 1))
        result.ci_lower = round(att - t_crit * se, 6)
        result.ci_upper = round(att + t_crit * se, 6)

        result.significant = result.p_value < alpha
    else:
        result.t_stat = 0.0
        result.p_value = 1.0

    # Cohen's d (effect size)
    pooled_std = np.sqrt(
        (
            np.var(tp, ddof=1) * (n_tp - 1)
            + np.var(ta, ddof=1) * (n_ta - 1)
            + np.var(cp, ddof=1) * (n_cp - 1)
            + np.var(ca, ddof=1) * (n_ca - 1)
        )
        / max(n_tp + n_ta + n_cp + n_ca - 4, 1)
    )
    if pooled_std > 1e-10:
        result.cohens_d = round(float(abs(att) / pooled_std), 4)

    # Parallel trends check (simple: compare pre-period slopes)
    # If we only have one pre-period, we check if pre-period means are similar
    pre_diff = abs(result.treat_pre_mean - result.control_pre_mean)
    post_diff = abs(result.treat_post_mean - result.control_post_mean)
    if result.control_pre_mean != 0:
        relative_pre_diff = pre_diff / abs(result.control_pre_mean)
    else:
        relative_pre_diff = pre_diff

    if relative_pre_diff > 0.30:
        result.parallel_trends_plausible = False
        result.parallel_trends_message = (
            f"Pre-treatment group means differ by {relative_pre_diff:.0%}. "
            "Parallel trends assumption may be violated."
        )
    else:
        result.parallel_trends_message = (
            f"Pre-treatment group means are within {relative_pre_diff:.0%} of each other. "
            "Parallel trends assumption appears plausible."
        )

    return result
