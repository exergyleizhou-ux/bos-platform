"""
BOS Pipeline v9.0 -Simulation Engine Unit Tests

Tests for Monte Carlo, Sensitivity, Bayesian A/B, and Forecast engines.
"""

import math
import pytest
import numpy as np

from app.engine.monte_carlo import run_monte_carlo, MonteCarloInput
from app.engine.sensitivity import run_sensitivity, SensitivityInput
from app.engine.bayesian_ab import run_bayesian_ab, BayesianABInput
from app.engine.forecast import run_forecast, ForecastInput


class TestMonteCarlo:
    """Tests for Monte Carlo SER simulation."""

    def test_basic_run(self):
        result = run_monte_carlo(
            MonteCarloInput(
                dm_in_mean=10.0,
                dm_in_std=0.5,
                dm_out_mean=8.5,
                dm_out_std=0.3,
                n_simulations=1000,
                seed=42,
            )
        )
        assert result.n_simulations == 1000
        assert 0 < result.ser_mean < 1
        assert result.ser_std > 0
        assert result.ser_p5 < result.ser_median < result.ser_p95
        assert 0 <= result.pass_probability <= 1
        assert len(result.histogram_bins) > 0
        assert len(result.histogram_counts) == len(result.histogram_bins)
        assert result.computation_time_ms >= 0

    def test_deterministic_with_seed(self):
        """Same seed - same results."""
        inp = MonteCarloInput(
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=8.5,
            dm_out_std=0.3,
            n_simulations=500,
            seed=123,
        )
        r1 = run_monte_carlo(inp)
        r2 = run_monte_carlo(inp)
        assert math.isclose(r1.ser_mean, r2.ser_mean, rel_tol=1e-9)
        assert math.isclose(r1.ser_std, r2.ser_std, rel_tol=1e-9)

    def test_large_simulation(self):
        result = run_monte_carlo(
            MonteCarloInput(
                dm_in_mean=10.0,
                dm_in_std=1.0,
                dm_out_mean=7.0,
                dm_out_std=0.8,
                n_simulations=10_000,
                seed=42,
            )
        )
        assert result.n_simulations == 10_000
        # With large N, std of mean should be small
        assert result.ser_std > 0

    def test_zero_std(self):
        """Zero std - all simulations identical."""
        result = run_monte_carlo(
            MonteCarloInput(
                dm_in_mean=10.0,
                dm_in_std=0.0,
                dm_out_mean=8.0,
                dm_out_std=0.0,
                n_simulations=100,
                seed=42,
            )
        )
        assert math.isclose(result.ser_std, 0.0, abs_tol=1e-9)
        expected = (10.0 - 8.0) / 10.0
        assert math.isclose(result.ser_mean, expected, rel_tol=1e-6)

    def test_invalid_n_simulations(self):
        with pytest.raises(ValueError):
            run_monte_carlo(
                MonteCarloInput(
                    dm_in_mean=10.0,
                    dm_in_std=0.5,
                    dm_out_mean=8.0,
                    dm_out_std=0.3,
                    n_simulations=0,
                )
            )


class TestSensitivity:
    """Tests for sensitivity analysis."""

    def test_basic_sensitivity(self):
        result = run_sensitivity(
            SensitivityInput(
                dm_in=10.0,
                dm_out=8.5,
                variation_pct=0.2,
                n_steps=10,
            )
        )
        assert result.base_ser > 0
        assert len(result.parameter_ranking) > 0
        assert len(result.impact_scores) > 0
        assert len(result.sweep_results) > 0

    def test_sweep_points_count(self):
        n_steps = 15
        result = run_sensitivity(
            SensitivityInput(
                dm_in=10.0,
                dm_out=8.0,
                variation_pct=0.1,
                n_steps=n_steps,
            )
        )
        for param, points in result.sweep_results.items():
            assert len(points) == n_steps

    def test_ranking_ordered_by_impact(self):
        result = run_sensitivity(
            SensitivityInput(
                dm_in=10.0,
                dm_out=8.0,
                n_in=0.5,
                variation_pct=0.2,
                n_steps=10,
            )
        )
        scores = [result.impact_scores[p] for p in result.parameter_ranking]
        assert scores == sorted(scores, reverse=True)


class TestBayesianAB:
    """Tests for Bayesian A/B testing."""

    def test_basic_ab(self):
        result = run_bayesian_ab(
            BayesianABInput(
                group_a=[0.15, 0.16, 0.14, 0.17, 0.13],
                group_b=[0.12, 0.11, 0.10, 0.13, 0.09],
                n_samples=5000,
            )
        )
        assert result.mean_a > 0
        assert result.mean_b > 0
        assert 0 <= result.prob_b_better <= 1
        assert result.decision in {
            "B is better",
            "A is better",
            "No significant difference",
        }
        assert len(result.posterior_a) == 5000
        assert len(result.posterior_b) == 5000
        assert result.confidence >= 0

    def test_identical_groups(self):
        """Identical data - ~50% probability, no significant difference."""
        vals = [0.15, 0.14, 0.16, 0.15, 0.14]
        result = run_bayesian_ab(
            BayesianABInput(
                group_a=vals,
                group_b=vals,
                n_samples=5000,
            )
        )
        assert 0.3 < result.prob_b_better < 0.7
        assert abs(result.effect_size) < 0.05

    def test_clearly_different_groups(self):
        """Obviously different - high confidence."""
        result = run_bayesian_ab(
            BayesianABInput(
                group_a=[0.30, 0.31, 0.29, 0.32, 0.28],
                group_b=[0.05, 0.06, 0.04, 0.07, 0.03],
                n_samples=5000,
            )
        )
        assert result.prob_b_better > 0.95
        assert result.decision == "B is better"

    def test_empty_group_raises(self):
        with pytest.raises(ValueError):
            run_bayesian_ab(
                BayesianABInput(
                    group_a=[],
                    group_b=[0.1, 0.2],
                    n_samples=1000,
                )
            )


class TestForecast:
    """Tests for time-series forecasting."""

    def test_sma_forecast(self):
        values = [
            0.15,
            0.14,
            0.16,
            0.13,
            0.17,
            0.12,
            0.15,
            0.14,
        ]
        result = run_forecast(
            ForecastInput(
                values=values,
                method="sma",
                horizon=3,
                window=3,
            )
        )
        assert len(result.forecast) == 3
        assert len(result.ci_lower) == 3
        assert len(result.ci_upper) == 3
        assert result.method == "sma"
        assert result.horizon == 3

    def test_ewma_forecast(self):
        values = [
            0.20,
            0.18,
            0.19,
            0.17,
            0.16,
            0.15,
            0.14,
            0.13,
        ]
        result = run_forecast(
            ForecastInput(
                values=values,
                method="ewma",
                horizon=5,
                alpha=0.3,
            )
        )
        assert len(result.forecast) == 5
        assert result.method == "ewma"
        # Downward trend: EWMA smooths rather than extrapolates, so it lags the
        # trend - the forecast tracks below the starting value but sits at or
        # above the most recent (lowest) point.
        assert values[-1] <= result.forecast[0] <= values[0]

    def test_holt_winters_forecast(
        self,
    ):
        # Simulate simple trend data
        values = [0.20 - i * 0.01 for i in range(12)]
        result = run_forecast(
            ForecastInput(
                values=values,
                method="holt_winters",
                horizon=4,
                alpha=0.3,
                beta=0.1,
            )
        )
        assert len(result.forecast) == 4
        assert result.method == "holt_winters"

    def test_ci_bounds_order(self):
        values = [
            0.15,
            0.14,
            0.16,
            0.13,
            0.17,
            0.12,
        ]
        result = run_forecast(
            ForecastInput(
                values=values,
                method="sma",
                horizon=3,
                window=3,
            )
        )
        for lo, hi in zip(
            result.ci_lower,
            result.ci_upper,
        ):
            assert lo <= hi

    def test_too_few_values_raises(
        self,
    ):
        with pytest.raises(ValueError):
            run_forecast(
                ForecastInput(
                    values=[0.15],
                    method="sma",
                    horizon=3,
                    window=3,
                )
            )

    def test_mape_and_rmse(
        self,
    ):
        values = [
            0.15,
            0.14,
            0.16,
            0.13,
            0.17,
            0.12,
            0.15,
            0.14,
        ]
        result = run_forecast(
            ForecastInput(
                values=values,
                method="sma",
                horizon=2,
                window=3,
            )
        )
        # MAPE and RMSE may be None if no holdout, but if present, must be >= 0
        if result.mape is not None:
            assert result.mape >= 0
            if result.rmse is not None:
                assert result.rmse >= 0
