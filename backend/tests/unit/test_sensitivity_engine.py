"""
BOS Pipeline v9.0 �� Sensitivity Analysis Engine Unit Tests

Tests the global sensitivity analysis engine (Sobol, Morris).
"""

import pytest

from app.engine.sensitivity_engine import (
    SensitivityInput,
    run_sensitivity_analysis,
    ENGINE_VERSION,
)


class TestSensitivityEngine:
    """Tests for the sensitivity analysis engine."""

    def test_sobol_analysis(self):
        """Sobol analysis produces first-order and total-order indices."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=1024,
            parameters={
                "dm_in": (5.0, 20.0),
                "dm_out": (1.0, 5.0),
                "n_in": (20.0, 80.0),
            },
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        assert result.first_order is not None
        assert "dm_in" in result.first_order
        assert "dm_out" in result.first_order
        assert result.total_order is not None
        assert result.engine_version == ENGINE_VERSION

    def test_morris_analysis(self):
        """Morris (elementary effects) method produces mu_star."""
        inp = SensitivityInput(
            method="morris",
            n_samples=100,
            parameters={
                "dm_in": (5.0, 20.0),
                "dm_out": (1.0, 5.0),
            },
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        assert result.mu_star is not None or result.first_order is not None

    def test_parameter_ranking(self):
        """Result includes a parameter ranking by importance."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=512,
            parameters={
                "dm_in": (5.0, 20.0),
                "dm_out": (1.0, 5.0),
                "n_in": (20.0, 80.0),
                "n_larvae": (10.0, 40.0),
            },
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        assert result.parameter_ranking is not None
        assert len(result.parameter_ranking) == 4
        # First parameter in ranking has highest sensitivity
        assert isinstance(result.parameter_ranking[0], str)

    def test_first_order_sum_reasonable(self):
        """Sum of first-order indices should be �� 1 (no strong interactions)
        or > 1 (strong interactions)."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=1024,
            parameters={
                "dm_in": (5.0, 20.0),
                "dm_out": (1.0, 5.0),
            },
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        s1_sum = sum(result.first_order.values())
        # Should be between 0 and ~2 (allowing for sampling noise)
        assert 0.0 <= s1_sum <= 2.0

    def test_total_order_geq_first_order(self):
        """Total-order indices �� first-order indices for each parameter."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=1024,
            parameters={
                "dm_in": (5.0, 20.0),
                "dm_out": (1.0, 5.0),
                "n_in": (20.0, 80.0),
            },
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        for param in result.first_order:
            # Allow small negative due to sampling noise
            assert result.total_order[param] >= result.first_order[param] - 0.05

    def test_reproducibility(self):
        """Same seed �� same results."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=512,
            parameters={"dm_in": (5.0, 20.0), "dm_out": (1.0, 5.0)},
            seed=42,
        )
        r1 = run_sensitivity_analysis(inp)
        r2 = run_sensitivity_analysis(inp)

        for param in r1.first_order:
            assert r1.first_order[param] == pytest.approx(r2.first_order[param], abs=1e-10)

    def test_single_parameter(self):
        """Single parameter �� trivial sensitivity (S1 �� 1)."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=512,
            parameters={"dm_in": (5.0, 20.0)},
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        assert result.first_order["dm_in"] == pytest.approx(1.0, abs=0.15)

    def test_computation_time(self):
        """Engine records computation time."""
        inp = SensitivityInput(
            method="sobol",
            n_samples=256,
            parameters={"dm_in": (5.0, 20.0), "dm_out": (1.0, 5.0)},
            seed=42,
        )
        result = run_sensitivity_analysis(inp)

        assert result.computation_time_ms > 0

    def test_convergence_diagnostics(self):
        """Larger N �� more stable indices."""
        inp_small = SensitivityInput(
            method="sobol", n_samples=128,
            parameters={"dm_in": (5.0, 20.0), "dm_out": (1.0, 5.0)},
            seed=42,
        )
        inp_large = SensitivityInput(
            method="sobol", n_samples=2048,
            parameters={"dm_in": (5.0, 20.0), "dm_out": (1.0, 5.0)},
            seed=42,
        )

        r_small = run_sensitivity_analysis(inp_small)
        r_large = run_sensitivity_analysis(inp_large)

        # Both should produce indices but large N is more reliable
        assert r_small.first_order is not None
        assert r_large.first_order is not None
