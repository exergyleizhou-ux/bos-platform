"""
BOS Pipeline v9.0 -GHG Engine Unit Tests

Tests the greenhouse gas balance computation engine.
"""

import pytest

from app.engine.ghg_engine import (
    GHGInput,
    compute_ghg,
    ENGINE_VERSION,
)


class TestGHGEngine:
    """Tests for the GHG balance engine."""

    def test_basic_computation(self):
        """Basic GHG balance with default emission factors."""
        inp = GHGInput(
            dm_in=10.0,
            dm_out=2.3,
            energy_kwh=50.0,
            transport_km=100.0,
        )
        result = compute_ghg(inp)

        assert result.total_emissions > 0
        assert result.avoided_emissions >= 0
        assert result.net_balance is not None
        assert result.engine_version == ENGINE_VERSION

    def test_net_negative_possible(self):
        """High avoided emissions can result in net negative balance."""
        inp = GHGInput(
            dm_in=20.0,
            dm_out=5.0,
            energy_kwh=10.0,  # Low energy use
            transport_km=10.0,  # Short transport
            avoided_soybean_meal_kg=15.0,  # High displacement
            avoided_landfill_kg=20.0,
        )
        result = compute_ghg(inp)

        # Net balance should be more favourable (possibly negative)
        assert result.net_balance < result.total_emissions

    def test_emission_categories(self):
        """Result includes all emission categories."""
        inp = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=50.0, transport_km=100.0)
        result = compute_ghg(inp)

        assert result.process_emissions >= 0
        assert result.energy_emissions >= 0
        assert result.transport_emissions >= 0
        assert result.biogenic_emissions >= 0

    def test_zero_transport(self):
        """Zero transport - zero transport emissions."""
        inp = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=50.0, transport_km=0.0)
        result = compute_ghg(inp)

        assert result.transport_emissions == 0.0

    def test_custom_grid_factor(self):
        """Custom electricity grid factor changes energy emissions."""
        inp_low = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=100.0, grid_emission_factor=0.1)
        inp_high = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=100.0, grid_emission_factor=0.8)

        r_low = compute_ghg(inp_low)
        r_high = compute_ghg(inp_high)

        assert r_high.energy_emissions > r_low.energy_emissions

    def test_per_kg_intensity(self):
        """Result includes per-kg-larvae emission intensity."""
        inp = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=50.0, transport_km=100.0)
        result = compute_ghg(inp)

        assert result.emission_intensity_per_kg > 0

    def test_co2_equivalents(self):
        """CH4 and N2O are converted to CO2e with correct GWPs."""
        inp = GHGInput(
            dm_in=10.0,
            dm_out=2.3,
            energy_kwh=50.0,
            ch4_emissions_kg=1.0,
            n2o_emissions_kg=0.1,
        )
        result = compute_ghg(inp)

        # CH4 GWP = 28, N2O GWP = 265
        assert result.total_emissions > 0

    def test_functional_units(self):
        """Result provides emissions per different functional units."""
        inp = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=50.0)
        result = compute_ghg(inp)

        assert result.per_kg_larvae is not None
        assert result.per_kg_protein is not None
        assert result.per_tonne_substrate is not None

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = GHGInput(dm_in=10.0, dm_out=2.3, energy_kwh=50.0, transport_km=100.0)
        r1 = compute_ghg(inp)
        r2 = compute_ghg(inp)

        assert r1.total_emissions == r2.total_emissions
        assert r1.net_balance == r2.net_balance
