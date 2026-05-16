"""
BOS Pipeline v9.0 -Mass Balance Engine Unit Tests

Tests the mass balance reconciliation engine.
"""

import pytest

from app.engine.mass_balance import (
    MassBalanceInput,
    reconcile_mass_balance,
    ENGINE_VERSION,
)


class TestMassBalance:
    """Tests for the mass balance reconciliation engine."""

    def test_already_balanced(self):
        """Input already balanced - minimal adjustments."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.3,
            dm_frass=6.5,
            dm_gas_loss=1.2,
            sigma_dm_in=0.3,
            sigma_dm_larvae=0.15,
            sigma_dm_frass=0.3,
            sigma_dm_gas=0.5,
        )
        result = reconcile_mass_balance(inp)

        # Sum - 10.0, minimal adjustment needed
        assert result.closure_pct == pytest.approx(100.0, abs=5.0)
        assert result.engine_version == ENGINE_VERSION

    def test_unbalanced_reconciliation(self):
        """Input with imbalance - reconciliation adjusts values."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.3,
            dm_frass=6.5,
            dm_gas_loss=2.5,  # Sum outputs = 11.3, but input = 10.0
            sigma_dm_in=0.3,
            sigma_dm_larvae=0.15,
            sigma_dm_frass=0.3,
            sigma_dm_gas=0.5,
        )
        result = reconcile_mass_balance(inp)

        # Reconciled values should close the gap
        assert result.reconciled_balance_error < result.raw_balance_error

    def test_reconciled_closure(self):
        """After reconciliation, inputs - outputs."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.0,
            dm_frass=5.0,
            dm_gas_loss=1.0,
            sigma_dm_in=0.3,
            sigma_dm_larvae=0.15,
            sigma_dm_frass=0.3,
            sigma_dm_gas=0.5,
        )
        result = reconcile_mass_balance(inp)

        # Reconciled closure should be close to 100%
        assert result.closure_pct == pytest.approx(100.0, abs=1.0)

    def test_adjustments_bounded(self):
        """Adjustments should not exceed max_adjustment_pct."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.0,
            dm_frass=5.0,
            dm_gas_loss=1.0,
            max_adjustment_pct=10.0,
        )
        result = reconcile_mass_balance(inp)

        for key, pct in result.adjustment_pct.items():
            assert abs(pct) <= 10.0 + 0.1  # Small tolerance for rounding

    def test_chi_squared_statistic(self):
        """Result includes chi-squared goodness-of-fit."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.3,
            dm_frass=6.5,
            dm_gas_loss=1.2,
        )
        result = reconcile_mass_balance(inp)

        assert result.chi_squared >= 0
        assert result.degrees_of_freedom >= 0
        assert isinstance(result.chi_squared_acceptable, bool)

    def test_estimated_gas_loss(self):
        """When gas loss not provided, it is estimated."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.3,
            dm_frass=6.5,
            # dm_gas_loss not provided - engine estimates
        )
        result = reconcile_mass_balance(inp)

        assert result.estimated_gas_loss is not None
        assert result.estimated_gas_loss >= 0

    def test_wastewater_component(self):
        """Wastewater output stream is included in balance."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=2.0,
            dm_frass=5.0,
            dm_gas_loss=1.0,
            dm_wastewater=0.5,
            sigma_dm_wastewater=0.1,
        )
        result = reconcile_mass_balance(inp)

        assert "dm_wastewater" in result.reconciled

    def test_original_values_preserved(self):
        """Result includes original (pre-reconciliation) values."""
        inp = MassBalanceInput(dm_in=10.0, dm_larvae=2.3, dm_frass=6.5, dm_gas_loss=1.2)
        result = reconcile_mass_balance(inp)

        assert result.original["dm_in"] == 10.0
        assert result.original["dm_larvae"] == 2.3

    def test_warnings_on_large_imbalance(self):
        """Large imbalance triggers warnings."""
        inp = MassBalanceInput(
            dm_in=10.0,
            dm_larvae=1.0,
            dm_frass=2.0,
            dm_gas_loss=0.5,  # Total outputs = 3.5, huge gap
        )
        result = reconcile_mass_balance(inp)

        assert len(result.warnings) > 0

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = MassBalanceInput(dm_in=10.0, dm_larvae=2.3, dm_frass=6.5, dm_gas_loss=1.2)
        r1 = reconcile_mass_balance(inp)
        r2 = reconcile_mass_balance(inp)

        assert r1.closure_pct == r2.closure_pct
        assert r1.chi_squared == r2.chi_squared
