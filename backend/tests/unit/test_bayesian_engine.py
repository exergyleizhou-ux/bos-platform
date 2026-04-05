"""
BOS Pipeline v9.0 �� Bayesian A/B Testing Engine Unit Tests

Tests the Bayesian hypothesis testing engine.
"""

import pytest

from app.engine.bayesian_engine import (
    BayesianABInput,
    run_bayesian_ab,
    ENGINE_VERSION,
)


class TestBayesianEngine:
    """Tests for the Bayesian A/B testing engine."""

    def test_normal_model_clear_winner(self):
        """Group B clearly better �� high P(B > A)."""
        inp = BayesianABInput(
            group_a_values=[0.15, 0.16, 0.14, 0.17, 0.15, 0.16, 0.14, 0.15, 0.16, 0.15],
            group_b_values=[0.25, 0.26, 0.24, 0.27, 0.25, 0.26, 0.24, 0.25, 0.26, 0.25],
            model="normal",
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert result.prob_b_better > 0.95
        assert result.effect_mean > 0
        assert result.confidence in ("high", "very_high")
        assert result.engine_version == ENGINE_VERSION

    def test_normal_model_no_difference(self):
        """Groups identical �� ~50% P(B > A)."""
        values = [0.20, 0.21, 0.19, 0.20, 0.21, 0.20, 0.19, 0.20, 0.21, 0.20]
        inp = BayesianABInput(
            group_a_values=values,
            group_b_values=values,
            model="normal",
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert 0.3 < result.prob_b_better < 0.7
        assert abs(result.effect_mean) < 0.02

    def test_beta_binomial_model(self):
        """Beta-binomial model with binary outcomes."""
        inp = BayesianABInput(
            group_a_successes=30,
            group_a_trials=100,
            group_b_successes=45,
            group_b_trials=100,
            model="beta_binomial",
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert result.prob_b_better > 0.90
        assert result.posterior_b_mean > result.posterior_a_mean

    def test_rope_region(self):
        """Practical equivalence region (ROPE) is computed."""
        inp = BayesianABInput(
            group_a_values=[0.20] * 20,
            group_b_values=[0.201] * 20,
            model="normal",
            rope_lower=-0.01,
            rope_upper=0.01,
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        # Very small difference �� high probability of practical equivalence
        assert result.prob_rope > 0.5

    def test_effect_ci(self):
        """Effect size has valid confidence interval."""
        inp = BayesianABInput(
            group_a_values=[0.15, 0.16, 0.14, 0.15, 0.16],
            group_b_values=[0.22, 0.23, 0.21, 0.22, 0.23],
            model="normal",
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert result.effect_ci_lower < result.effect_mean < result.effect_ci_upper

    def test_histogram_output(self):
        """Result includes effect distribution histogram."""
        inp = BayesianABInput(
            group_a_values=[0.15, 0.16, 0.14, 0.15],
            group_b_values=[0.22, 0.23, 0.21, 0.22],
            model="normal",
            n_posterior_samples=10_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert len(result.effect_histogram_bins) > 0
        assert len(result.effect_histogram_counts) > 0

    def test_reproducibility(self):
        """Same seed �� identical results."""
        inp = BayesianABInput(
            group_a_values=[0.15, 0.16, 0.14],
            group_b_values=[0.22, 0.23, 0.21],
            model="normal",
            n_posterior_samples=10_000,
            seed=42,
        )
        r1 = run_bayesian_ab(inp)
        r2 = run_bayesian_ab(inp)

        assert r1.prob_b_better == r2.prob_b_better
        assert r1.effect_mean == r2.effect_mean

    def test_recommendation_output(self):
        """Result includes a human-readable recommendation."""
        inp = BayesianABInput(
            group_a_values=[0.15, 0.16, 0.14, 0.15, 0.16],
            group_b_values=[0.25, 0.26, 0.24, 0.25, 0.26],
            model="normal",
            n_posterior_samples=50_000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert result.recommendation is not None
        assert len(result.recommendation) > 0

    def test_errors_on_invalid_input(self):
        """Missing required data returns errors."""
        inp = BayesianABInput(
            # No values or binary data provided
            model="normal",
            n_posterior_samples=1000,
            seed=42,
        )
        result = run_bayesian_ab(inp)

        assert len(result.errors) > 0
