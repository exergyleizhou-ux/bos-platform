"""
BOS Pipeline v9.0 �� Risk Assessment Engine Unit Tests

Tests the contaminant risk assessment engine.
"""

import pytest

from app.engine.risk_engine import (
    ContaminantReading,
    RiskInput,
    assess_risk,
    ENGINE_VERSION,
)


class TestRiskEngine:
    """Tests for the contaminant risk assessment engine."""

    def test_all_safe(self):
        """All contaminants well below limits �� overall safe."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=0.1, unit="mg/kg", category="heavy_metal"),
                ContaminantReading(name="cadmium", value=0.05, unit="mg/kg", category="heavy_metal"),
                ContaminantReading(name="arsenic", value=0.02, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert result.overall_safe is True
        assert result.overall_risk in ("low", "negligible")
        assert result.critical_count == 0
        assert result.engine_version == ENGINE_VERSION

    def test_single_exceedance(self):
        """One contaminant exceeding limit �� not overall safe."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=100.0, unit="mg/kg", category="heavy_metal"),
                ContaminantReading(name="cadmium", value=0.05, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert result.overall_safe is False
        assert result.critical_count >= 1 or result.high_count >= 1

    def test_check_details(self):
        """Each contaminant produces a check with name, value, limit, ratio."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=0.1, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert len(result.checks) == 1
        check = result.checks[0]
        assert check.name == "lead"
        assert check.value == 0.1
        assert check.limit > 0
        assert check.ratio == pytest.approx(0.1 / check.limit, rel=1e-4)
        assert check.risk_level in ("negligible", "low", "medium", "high", "critical")

    def test_ratio_ordering(self):
        """Higher value relative to limit �� higher ratio."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=1.0, unit="mg/kg", category="heavy_metal"),
                ContaminantReading(name="cadmium", value=0.01, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        lead_check = next(c for c in result.checks if c.name == "lead")
        cd_check = next(c for c in result.checks if c.name == "cadmium")

        assert lead_check.ratio > cd_check.ratio

    def test_food_stricter_than_feed(self):
        """Food-grade limits should be stricter than feed-grade."""
        contaminants = [
            ContaminantReading(name="lead", value=0.5, unit="mg/kg", category="heavy_metal"),
        ]

        result_feed = assess_risk(RiskInput(contaminants=contaminants, product_use="feed"))
        result_food = assess_risk(RiskInput(contaminants=contaminants, product_use="food"))

        lead_feed = next(c for c in result_feed.checks if c.name == "lead")
        lead_food = next(c for c in result_food.checks if c.name == "lead")

        # Food limit should be lower �� ratio should be higher for same value
        assert lead_food.ratio >= lead_feed.ratio

    def test_pesticide_category(self):
        """Pesticide contaminants are assessed correctly."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="chlorpyrifos", value=0.001, unit="mg/kg", category="pesticide"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert len(result.checks) == 1
        assert result.checks[0].category == "pesticide"

    def test_mycotoxin_category(self):
        """Mycotoxin contaminants are assessed."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="aflatoxin_b1", value=0.005, unit="mg/kg", category="mycotoxin"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert len(result.checks) == 1
        assert result.checks[0].category == "mycotoxin"

    def test_recommendations_on_exceedance(self):
        """Recommendations are provided when contaminants are elevated."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=50.0, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        result = assess_risk(inp)

        assert len(result.recommendations) > 0

    def test_empty_contaminants(self):
        """No contaminants �� trivially safe."""
        inp = RiskInput(contaminants=[], species="BSF", product_use="feed")
        result = assess_risk(inp)

        assert result.overall_safe is True
        assert result.critical_count == 0
        assert len(result.checks) == 0

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = RiskInput(
            contaminants=[
                ContaminantReading(name="lead", value=0.3, unit="mg/kg", category="heavy_metal"),
            ],
            species="BSF",
            product_use="feed",
        )
        r1 = assess_risk(inp)
        r2 = assess_risk(inp)

        assert r1.overall_safe == r2.overall_safe
        assert r1.checks[0].ratio == r2.checks[0].ratio
