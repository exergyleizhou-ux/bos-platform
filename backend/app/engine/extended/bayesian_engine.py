"""
BOS Pipeline v9.0 Bayesian A/B testing engine.
"""

import time
from dataclasses import dataclass, field

import numpy as np

ENGINE_VERSION = "9.0.0"


@dataclass
class BayesianABInput:
    """Input for Bayesian A/B testing."""

    group_a_values: list[float] | None = None
    group_b_values: list[float] | None = None
    group_a_successes: int | None = None
    group_a_trials: int | None = None
    group_b_successes: int | None = None
    group_b_trials: int | None = None
    model: str = "normal"
    n_posterior_samples: int = 100_000
    rope_lower: float = -0.01
    rope_upper: float = 0.01
    group_a_name: str = "Control"
    group_b_name: str = "Treatment"
    metric_name: str = "SER"
    seed: int | None = None


@dataclass
class BayesianABResult:
    """Bayesian A/B test results."""

    prob_b_better: float = 0.0
    prob_a_better: float = 0.0
    prob_rope: float = 0.0
    effect_mean: float = 0.0
    effect_std: float = 0.0
    effect_ci_lower: float = 0.0
    effect_ci_upper: float = 0.0
    posterior_a_mean: float = 0.0
    posterior_a_std: float = 0.0
    posterior_b_mean: float = 0.0
    posterior_b_std: float = 0.0
    recommendation: str = ""
    confidence: str = ""
    effect_histogram_bins: list[float] = field(default_factory=list)
    effect_histogram_counts: list[int] = field(default_factory=list)
    model: str = ""
    group_a_name: str = ""
    group_b_name: str = ""
    metric_name: str = ""
    n_samples: int = 0
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: list[str] = field(default_factory=list)


def _confidence_label(probability: float) -> str:
    if probability >= 0.99:
        return "very_high"
    if probability >= 0.95:
        return "high"
    if probability >= 0.8:
        return "moderate"
    if probability >= 0.6:
        return "weak"
    return "inconclusive"


def run_bayesian_ab(inp: BayesianABInput) -> BayesianABResult:
    """Run a Bayesian A/B test."""
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
        required = [
            inp.group_a_successes,
            inp.group_a_trials,
            inp.group_b_successes,
            inp.group_b_trials,
        ]
        if any(v is None for v in required):
            result.errors.append("Beta-binomial model requires successes and trials for both groups")
            return result

        alpha_a = 1 + inp.group_a_successes
        beta_a = 1 + inp.group_a_trials - inp.group_a_successes
        alpha_b = 1 + inp.group_b_successes
        beta_b = 1 + inp.group_b_trials - inp.group_b_successes

        samples_a = rng.beta(alpha_a, beta_a, n)
        samples_b = rng.beta(alpha_b, beta_b, n)
    elif inp.model == "normal":
        if inp.group_a_values is None or inp.group_b_values is None:
            result.errors.append("Normal model requires group_a_values and group_b_values")
            return result
        if len(inp.group_a_values) < 2 or len(inp.group_b_values) < 2:
            result.errors.append("Each group needs at least 2 observations")
            return result

        a = np.array(inp.group_a_values, dtype=np.float64)
        b = np.array(inp.group_b_values, dtype=np.float64)

        n_a, n_b = len(a), len(b)
        mean_a, mean_b = a.mean(), b.mean()
        var_a, var_b = a.var(ddof=1), b.var(ddof=1)

        samples_a = rng.standard_t(df=max(n_a - 1, 1), size=n) * np.sqrt(var_a / n_a) + mean_a
        samples_b = rng.standard_t(df=max(n_b - 1, 1), size=n) * np.sqrt(var_b / n_b) + mean_b
    else:
        result.errors.append(f"Unknown model: {inp.model}")
        return result

    effect = samples_b - samples_a

    result.prob_b_better = round(float(np.mean(effect > 0)), 6)
    result.prob_a_better = round(float(np.mean(effect < 0)), 6)
    result.prob_rope = round(
        float(np.mean((effect >= inp.rope_lower) & (effect <= inp.rope_upper))),
        6,
    )
    result.effect_mean = round(float(np.mean(effect)), 6)
    result.effect_std = round(float(np.std(effect)), 6)
    result.effect_ci_lower = round(float(np.percentile(effect, 2.5)), 6)
    result.effect_ci_upper = round(float(np.percentile(effect, 97.5)), 6)
    result.posterior_a_mean = round(float(np.mean(samples_a)), 6)
    result.posterior_a_std = round(float(np.std(samples_a)), 6)
    result.posterior_b_mean = round(float(np.mean(samples_b)), 6)
    result.posterior_b_std = round(float(np.std(samples_b)), 6)

    max_prob = max(result.prob_a_better, result.prob_b_better)
    winner = inp.group_b_name if result.prob_b_better >= result.prob_a_better else inp.group_a_name
    result.confidence = _confidence_label(max_prob)

    if result.prob_rope >= 0.5:
        result.confidence = "inconclusive"
        result.recommendation = (
            f"Inconclusive. Groups are similar ({result.prob_rope:.1%} within ROPE)."
        )
    elif max_prob >= 0.95:
        result.recommendation = f"Strong evidence favoring {winner} ({max_prob:.1%})."
    elif max_prob >= 0.8:
        result.recommendation = f"Moderate evidence favoring {winner} ({max_prob:.1%})."
    else:
        result.recommendation = f"Weak evidence favoring {winner} ({max_prob:.1%}). Collect more data."

    hist_counts, hist_edges = np.histogram(effect, bins=50)
    result.effect_histogram_bins = [
        round(float((hist_edges[i] + hist_edges[i + 1]) / 2), 6)
        for i in range(len(hist_counts))
    ]
    result.effect_histogram_counts = [int(c) for c in hist_counts]
    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return result
