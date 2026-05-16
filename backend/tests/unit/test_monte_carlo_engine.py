"""
BOS Pipeline v9.0 -Monte Carlo Engine Unit Tests

Tests the Monte Carlo simulation engine for SER uncertainty quantification.
"""

import pytest

from app.engine.monte_carlo_engine import (
    MCInput,
    run_monte_carlo,
    ENGINE_VERSION,
)


class TestMonteCarloEngine:
    """Tests for the Monte Carlo simulation engine."""

    def test_basic_simulation(self):
        """Run a basic MC simulation with default params."""
        inp = MCInput(
            n_samples=10_000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.n_samples == 10_000
        assert result.ser_mean == pytest.approx(0.23, abs=0.02)
        assert result.ser_std > 0
        assert result.ser_median > 0
        assert result.ser_ci_lower < result.ser_mean < result.ser_ci_upper
        assert 0.0 <= result.pass_probability <= 1.0

    def test_reproducibility_with_seed(self):
        """Same seed produces identical results."""
        inp = MCInput(
            n_samples=5000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=123,
        )
        r1 = run_monte_carlo(inp)
        r2 = run_monte_carlo(inp)

        assert r1.ser_mean == r2.ser_mean
        assert r1.ser_std == r2.ser_std
        assert r1.pass_probability == r2.pass_probability

    def test_different_seeds_differ(self):
        """Different seeds produce different results (statistically)."""
        inp1 = MCInput(n_samples=5000, dm_in_mean=10.0, dm_in_std=0.5, dm_out_mean=2.3, dm_out_std=0.15, seed=1)
        inp2 = MCInput(n_samples=5000, dm_in_mean=10.0, dm_in_std=0.5, dm_out_mean=2.3, dm_out_std=0.15, seed=999)

        r1 = run_monte_carlo(inp1)
        r2 = run_monte_carlo(inp2)

        # Means should be close but not identical
        assert r1.ser_mean != r2.ser_mean

    def test_zero_std(self):
        """Zero std - deterministic output, zero variance."""
        inp = MCInput(
            n_samples=1000,
            dm_in_mean=10.0,
            dm_in_std=0.0,
            dm_out_mean=2.3,
            dm_out_std=0.0,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.ser_mean == pytest.approx(0.23, rel=1e-6)
        assert result.ser_std == pytest.approx(0.0, abs=1e-10)
        assert result.pass_probability == 1.0  # deterministic pass

    def test_high_uncertainty(self):
        """High std - wider CI."""
        inp_low = MCInput(n_samples=10000, dm_in_mean=10.0, dm_in_std=0.1, dm_out_mean=2.3, dm_out_std=0.05, seed=42)
        inp_high = MCInput(n_samples=10000, dm_in_mean=10.0, dm_in_std=2.0, dm_out_mean=2.3, dm_out_std=1.0, seed=42)

        r_low = run_monte_carlo(inp_low)
        r_high = run_monte_carlo(inp_high)

        ci_width_low = r_low.ser_ci_upper - r_low.ser_ci_lower
        ci_width_high = r_high.ser_ci_upper - r_high.ser_ci_lower

        assert ci_width_high > ci_width_low

    def test_histogram_output(self):
        """MC result includes histogram bins and counts."""
        inp = MCInput(
            n_samples=5000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert len(result.histogram_bins) > 0
        assert len(result.histogram_counts) > 0
        assert sum(result.histogram_counts) == 5000

    def test_percentiles_output(self):
        """MC result includes standard percentiles."""
        inp = MCInput(
            n_samples=10000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert "p5" in result.percentiles
        assert "p25" in result.percentiles
        assert "p50" in result.percentiles
        assert "p75" in result.percentiles
        assert "p95" in result.percentiles
        assert result.percentiles["p5"] < result.percentiles["p95"]

    def test_pass_probability_failing_batch(self):
        """Batch with very low efficiency has low pass probability."""
        inp = MCInput(
            n_samples=10000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=0.5,  # Very low output
            dm_out_std=0.1,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.pass_probability < 0.1  # Almost certainly fails

    def test_computation_time_recorded(self):
        """Engine records computation time."""
        inp = MCInput(
            n_samples=1000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.computation_time_ms > 0

    def test_engine_version(self):
        """Engine version is set."""
        inp = MCInput(
            n_samples=100,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.engine_version == ENGINE_VERSION

    def test_large_sample_count(self):
        """Engine handles 100k samples."""
        inp = MCInput(
            n_samples=100_000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.n_samples == 100_000
        assert result.ser_mean == pytest.approx(0.23, abs=0.01)

    def test_with_nitrogen(self):
        """MC with nitrogen parameters included."""
        inp = MCInput(
            n_samples=5000,
            dm_in_mean=10.0,
            dm_in_std=0.5,
            dm_out_mean=2.3,
            dm_out_std=0.15,
            n_in_mean=50.0,
            n_in_std=5.0,
            n_larvae_mean=30.0,
            n_larvae_std=3.0,
            n_frass_mean=15.0,
            n_frass_std=2.0,
            seed=42,
        )
        result = run_monte_carlo(inp)

        assert result.ser_mean > 0
        assert result.n_samples == 5000
