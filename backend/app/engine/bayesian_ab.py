"""Backward-compatible Bayesian A/B module used by legacy tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BayesianABInput:
    group_a: list[float]
    group_b: list[float]
    n_samples: int = 5000
    seed: int | None = 42


@dataclass
class BayesianABResult:
    mean_a: float
    mean_b: float
    prob_b_better: float
    decision: str
    posterior_a: list[float]
    posterior_b: list[float]
    confidence: float
    effect_size: float


def run_bayesian_ab(inp: BayesianABInput) -> BayesianABResult:
    if not inp.group_a or not inp.group_b:
        raise ValueError("group_a and group_b must not be empty")
    if inp.n_samples <= 0:
        raise ValueError("n_samples must be > 0")

    rng = np.random.default_rng(inp.seed)
    a = np.asarray(inp.group_a, dtype=float)
    b = np.asarray(inp.group_b, dtype=float)

    # Bootstrap posterior over means.
    posterior_a = rng.choice(a, size=(inp.n_samples, a.size), replace=True).mean(axis=1)
    posterior_b = rng.choice(b, size=(inp.n_samples, b.size), replace=True).mean(axis=1)

    # Legacy convention: lower is better.
    prob_b_better = float(np.mean(posterior_b < posterior_a))
    if prob_b_better > 0.95:
        decision = "B is better"
    elif prob_b_better < 0.05:
        decision = "A is better"
    else:
        decision = "No significant difference"

    confidence = max(prob_b_better, 1.0 - prob_b_better)
    effect_size = float(np.mean(posterior_b - posterior_a))

    return BayesianABResult(
        mean_a=float(np.mean(a)),
        mean_b=float(np.mean(b)),
        prob_b_better=prob_b_better,
        decision=decision,
        posterior_a=[float(v) for v in posterior_a.tolist()],
        posterior_b=[float(v) for v in posterior_b.tolist()],
        confidence=float(confidence),
        effect_size=effect_size,
    )
