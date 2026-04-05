"""
BOS Pipeline v9.0 �� Bayesian A/B Testing Engine

Performs Bayesian hypothesis testing for comparing two process
configurations (e.g., two substrates, two temperature regimes).

Advantages over frequentist t-test:
  - Direct probability of superiority
  - No multiple testing corrections needed
  - Works well with small sample sizes
  - Rich posterior distributions for decision-making

Models:
  - Beta-Binomial (for pass/fail rates)
  - Normal-Normal (for continuous outcomes like SER)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

ENGINE_VERSION = "9.0.0"


@dataclass
class BayesianABInput:
    """Input for Bayesian A/B test."""

    # Continuous outcomes (e.g., SER values)
    group_a_values: Optional[List[float]] = None
    group_b_values: Optional[List[float]] = None

    # Binary outcomes (pass/fail)
    group_a_successes: Optional[int] = None
    group_a_trials: Optional[int] = None
    group_b_successes: Optional[int] = None
    group_b_trials: Optional[int] = None

    # Test configuration
    model: str = "normal"  # "normal" or "beta_binomial"
    n_posterior_samples: int = 100_000
    rope_lower: float = -0.01  # Region of Practical Equivalence
    rope_upper: float = 0.01
    group_a_name: str = "Control"
    group_b_name: str = "Treatment"
    metric_name: str = "SER"
    seed: Optional[int] = None


@dataclass
class BayesianABResult:
    """Bayesian A/B test results."""

    # Probability of superiority
    prob_b_better: float = 0.0  # P(B > A)
    prob_a_better: float = 0.0  # P(A > B)
    prob_rope: float = 0.0  # P(|B - A| within ROPE)

    # Effect size distribution
    effect_mean: float = 0.0  # E[B - A]
    effect_std: float = 0.0
    effect_ci_lower: float = 0.0  # 2.5th percentile
    effect_ci_upper: float = 0.0  # 97.5th percentile

    # Posterior summaries
    posterior_a_mean: float = 0.0
    posterior_a_std: float = 0.0
    posterior_b_mean: float = 0.0
    posterior_b_std: float = 0.0

    # Decision
    recommendation: str = ""
    confidence: str = ""  # "strong", "moderate", "weak", "inconclusive"

    # Histogram data for visualization
    effect_histogram_bins: List[float] = field(default_factory=list)
    effect_histogram_counts: List[int] = field(default_factory=list)

    # Metadata
    model: str = ""
    group_a_name: str = ""
    group_b_name: str = ""
    metric_name: str = ""
    n_samples: int = 0
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def run_bayesian_ab(inp: BayesianABInput) -> BayesianABResult:
    """
    Run Bayesian A/B test.

    Parameters
    ----------
    inp : BayesianABInput
        Group data and test configuration.

    Returns
    -------
    BayesianABResult
        Posterior probabilities and decision recommendation.
    """
    start_time = time.perf_counter()
    rng = np.random.default_rng(inp.seed)
    result = BayesianABResult(
        model=inp.model,
        group_a_name=inp.group_a_name,
        group_b_name=inp.group_b_name,
        metric_name=inp.metric_name,
        n_samples=inp.n_posterior_samples,
    )

    n = inp.n_posterior_samples

    if inp.model == "beta_binomial":
        # ���� Beta-Binomial Model ����
        if any(v is None for v in [inp.group_a_successes, inp.group_a_trials, inp.group_b_successes, inp.group_b_trials]):
            result.errors.append("Beta-binomial model requires successes and trials for both groups")
            return result

        # Prior: Beta(1, 1) = Uniform
        alpha_a = 1 + inp.group_a_successes
        beta_a = 1 + inp.group_a_trials - inp.group_a_successes
        alpha_b = 1 + inp.group_b_successes
        beta_b = 1 + inp.group_b_trials - inp.group_b_successes

        # Sample from posteriors
        samples_a = rng.beta(alpha_a, beta_a, n)
        samples_b = rng.beta(alpha_b, beta_b, n)

    elif inp.model == "normal":
        # ���� Normal-Normal Model ����
        if inp.group_a_values is None or inp.group_b_values is None:
            result.errors.append("Normal model requires group_a_values and group_b_values")
            return result

        if len(inp.group_a_values) < 2 or len(inp.group_b_values) < 2:
            result.errors.append("Each group needs at least 2 observations")
            return result

        a = np.array(inp.group_a_values, dtype=np.float64)
        b = np.array(inp.group_b_values, dtype=np.float64)

        # Posterior with non-informative prior (Jeffrey's)
        n_a, n_b = len(a), len(b)
        mean_a, mean_b = a.mean(), b.mean()
        var_a, var_b = a.var(ddof=1), b.var(ddof=1)

        # Sample from t-distribution posteriors (conjugate)
        # More accurate than normal approximation for small samples
        samples_a = rng.standard_t(df=max(n_a - 1, 1), size=n) * np.sqrt(var_a / n_a) + mean_a
        samples_b = rng.standard_t(df=max(n_b - 1, 1), size=n) * np.sqrt(var_b / n_b) + mean_b

    else:
        result.errors.append(f"Unknown model: {inp.model}")
        return result

    # ���� Compute probabilities ����
    effect = samples_b - samples_a

    result.prob_b_better = round(float(np.mean(effect > 0)), 6)
    result.prob_a_better = round(float(np.mean(effect < 0)), 6)
    result.prob_rope = round(float(np.mean((effect >= inp.rope_lower) & (effect <= inp.rope_upper))), 6)

    result.effect_mean = round(float(np.mean(effect)), 6)
    result.effect_std = round(float(np.std(effect)), 6)
    result.effect_ci_lower = round(float(np.percentile(effect, 2.5)), 6)
    result.effect_ci_upper = round(float(np.percentile(effect, 97.5)), 6)

    result.posterior_a_mean = round(float(np.mean(samples_a)), 6)
    result.posterior_a_std = round(float(np.std(samples_a)), 6)
    result.posterior_b_mean = round(float(np.mean(samples_b)), 6)
    result.posterior_b_std = round(float(np.std(samples_b)), 6)

    # ���� Decision Logic ����
    max_prob = max(result.prob_b_better, result.prob_a_better)
    winner = inp.group_b_name if result.prob_b_better > result.prob_a_better else inp.group_a_name

    if max_prob >= 0.99:
        result.confidence = "very_high"
        result.recommendation = f"Strong evidence that {winner} is superior ({max_prob:.1%} probability)."
    elif max_prob >= 0.95:
        result.confidence = "high"
        result.recommendation = f"Strong evidence that {winner} is superior ({max_prob:.1%} probability)."
    elif max_prob >= 0.90:
        result.confidence = "moderate"
        result.recommendation = f"Moderate evidence favoring {winner} ({max_prob:.1%} probability)."
    elif max_prob >= 0.75:
        result.confidence = "weak"
        result.recommendation = f"Weak evidence favoring {winner} ({max_prob:.1%}). Collect more data."
    else:
        result.confidence = "inconclusive"
        result.recommendation = f"Inconclusive. Groups are similar ({result.prob_rope:.1%} within ROPE)."

    # ���� Histogram ����
    hist_counts, hist_edges = np.histogram(effect, bins=50)
    result.effect_histogram_bins = [
        round(float((hist_edges[i] + hist_edges[i + 1]) / 2), 6)
        for i in range(len(hist_counts))
    ]
    result.effect_histogram_counts = [int(c) for c in hist_counts]

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return result

