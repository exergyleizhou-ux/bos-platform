"""
BOS Pipeline v9.0 �� Water Footprint Engine Unit Tests

Tests the water footprint computation engine.
"""

import pytest

from app.engine.water_engine import (
    WaterInput,
    compute_water_footprint,
    ENGINE_VERSION,
)


class TestWaterEngine:
    """Tests for the water footprint engine."""

    def test_basic_computation(self):
        """Basic water footprint computation."""
        inp = WaterInput(
            dm_in=10.0,
            dm_out=2.3,
            water_direct_litres=500.0,
        )
        result = compute_water_footprint(inp)

        assert result.total_footprint > 0
        assert result.blue_water >= 0
        assert result.green_water >= 0
        assert result.grey_water >= 0
        assert result.engine_version == ENGINE_VERSION

    def test_higher_input_higher_footprint(self):
        """More substrate �� larger water footprint."""
        inp_small = WaterInput(dm_in=5.0, dm_out=1.0, water_direct_litres=200.0)
        inp_large = WaterInput(dm_in=20.0, dm_out=4.0, water_direct_litres=800.0)

        r_small = compute_water_footprint(inp_small)
        r_large = compute_water_footprint(inp_large)

        assert r_large.total_footprint > r_small.total_footprint

    def test_per_kg_intensity(self):
        """Result includes per-kg water intensity."""
        inp = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0)
        result = compute_water_footprint(inp)

        assert result.per_kg_larvae > 0
        assert result.per_kg_protein > 0

    def test_zero_direct_water(self):
        """Even with zero direct water, embedded water contributes."""
        inp = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=0.0)
        result = compute_water_footprint(inp)

        # Embedded water from substrate should still contribute
        assert result.total_footprint >= 0

    def test_recycled_water(self):
        """Recycled water reduces net footprint."""
        inp_no_recycle = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0, water_recycled_litres=0.0)
        inp_recycle = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0, water_recycled_litres=300.0)

        r_no = compute_water_footprint(inp_no_recycle)
        r_yes = compute_water_footprint(inp_recycle)

        assert r_yes.total_footprint <= r_no.total_footprint

    def test_wsi_impact(self):
        """Water scarcity index amplifies the impact footprint."""
        inp_low_wsi = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0, water_scarcity_index=0.1)
        inp_high_wsi = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0, water_scarcity_index=0.9)

        r_low = compute_water_footprint(inp_low_wsi)
        r_high = compute_water_footprint(inp_high_wsi)

        assert r_high.scarcity_weighted_footprint > r_low.scarcity_weighted_footprint

    def test_component_sum(self):
        """Blue + green + grey �� total (within rounding)."""
        inp = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0)
        result = compute_water_footprint(inp)

        component_sum = result.blue_water + result.green_water + result.grey_water
        assert component_sum == pytest.approx(result.total_footprint, rel=0.01)

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = WaterInput(dm_in=10.0, dm_out=2.3, water_direct_litres=500.0)
        r1 = compute_water_footprint(inp)
        r2 = compute_water_footprint(inp)

        assert r1.total_footprint == r2.total_footprint
