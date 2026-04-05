"""
BOS Pipeline v9.0 �� Energy Balance Engine Unit Tests

Tests the energy balance computation engine.
"""

import pytest

from app.engine.energy_engine import (
    EnergyInput,
    compute_energy_balance,
    ENGINE_VERSION,
)


class TestEnergyEngine:
    """Tests for the energy balance engine."""

    def test_basic_computation(self):
        """Basic energy balance computation."""
        inp = EnergyInput(
            dm_in=10.0,
            dm_out=2.3,
            electricity_kwh=30.0,
            heating_kwh=20.0,
        )
        result = compute_energy_balance(inp)

        assert result.total_input_energy > 0
        assert result.total_output_energy >= 0
        assert result.net_energy is not None
        assert result.eroi > 0
        assert result.engine_version == ENGINE_VERSION

    def test_eroi_calculation(self):
        """EROI = energy in product / energy consumed."""
        inp = EnergyInput(
            dm_in=10.0,
            dm_out=2.3,
            electricity_kwh=30.0,
            heating_kwh=20.0,
        )
        result = compute_energy_balance(inp)

        assert result.eroi == pytest.approx(
            result.total_output_energy / result.total_input_energy, rel=1e-4
        )

    def test_more_output_higher_eroi(self):
        """Higher dm_out (more product) �� better EROI."""
        inp_low = EnergyInput(dm_in=10.0, dm_out=1.0, electricity_kwh=30.0, heating_kwh=20.0)
        inp_high = EnergyInput(dm_in=10.0, dm_out=3.0, electricity_kwh=30.0, heating_kwh=20.0)

        r_low = compute_energy_balance(inp_low)
        r_high = compute_energy_balance(inp_high)

        assert r_high.eroi > r_low.eroi

    def test_renewable_fraction(self):
        """Renewable energy reduces fossil energy dependency."""
        inp = EnergyInput(
            dm_in=10.0,
            dm_out=2.3,
            electricity_kwh=30.0,
            heating_kwh=20.0,
            renewable_fraction=0.8,
        )
        result = compute_energy_balance(inp)

        assert result.fossil_energy < result.total_input_energy
        assert result.renewable_energy > 0

    def test_energy_categories(self):
        """Result includes electrical, thermal, and mechanical energy."""
        inp = EnergyInput(
            dm_in=10.0,
            dm_out=2.3,
            electricity_kwh=30.0,
            heating_kwh=20.0,
            mechanical_kwh=5.0,
        )
        result = compute_energy_balance(inp)

        assert result.electrical_energy > 0
        assert result.thermal_energy > 0
        assert result.mechanical_energy > 0

    def test_per_kg_intensity(self):
        """Result includes per-kg energy intensity."""
        inp = EnergyInput(dm_in=10.0, dm_out=2.3, electricity_kwh=30.0, heating_kwh=20.0)
        result = compute_energy_balance(inp)

        assert result.per_kg_larvae > 0

    def test_zero_energy_input(self):
        """Zero energy input �� EROI undefined or special case."""
        inp = EnergyInput(dm_in=10.0, dm_out=2.3, electricity_kwh=0.0, heating_kwh=0.0)
        result = compute_energy_balance(inp)

        # Should handle gracefully (no division by zero)
        assert result is not None

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = EnergyInput(dm_in=10.0, dm_out=2.3, electricity_kwh=30.0, heating_kwh=20.0)
        r1 = compute_energy_balance(inp)
        r2 = compute_energy_balance(inp)

        assert r1.total_input_energy == r2.total_input_energy
        assert r1.eroi == r2.eroi
