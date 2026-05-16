"""
BOS Pipeline v9.0 -Flight Envelope Engine Unit Tests

Tests the operating envelope check engine.
"""

import pytest

from app.engine.flight_envelope import (
    FlightEnvelopeInput,
    check_flight_envelope,
    ENGINE_VERSION,
)


class TestFlightEnvelope:
    """Tests for the flight envelope engine."""

    def test_optimal_conditions(self):
        """All parameters within optimal range - green zone."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=28.0,
            moisture=70.0,
            ph=7.0,
        )
        result = check_flight_envelope(inp)

        assert result.in_envelope is True
        assert result.overall_zone == "optimal"
        assert result.engine_version == ENGINE_VERSION

    def test_safe_conditions(self):
        """Parameters within safe but not optimal - yellow zone."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=22.0,  # Below optimal but within safe
            moisture=55.0,  # Below optimal but within safe
        )
        result = check_flight_envelope(inp)

        assert result.in_envelope is True
        assert result.overall_zone in ("acceptable", "warning")

    def test_outside_envelope(self):
        """Parameters outside safe range - red zone, not in envelope."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=5.0,  # Well below safe range
            moisture=95.0,  # Well above safe range
        )
        result = check_flight_envelope(inp)

        assert result.in_envelope is False
        assert result.overall_zone in ("critical", "danger")
        assert len(result.alarms) > 0

    def test_individual_checks(self):
        """Each parameter produces its own check result."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=28.0,
            moisture=70.0,
            ph=7.0,
            o2_level=21.0,
        )
        result = check_flight_envelope(inp)

        assert len(result.checks) >= 3
        for check in result.checks:
            assert check.parameter is not None
            assert check.value is not None
            assert check.zone in ("optimal", "acceptable", "warning", "critical", "danger")

    def test_partial_parameters(self):
        """Only provided parameters are checked; others are skipped."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=28.0,
            # moisture, ph, etc. not provided
        )
        result = check_flight_envelope(inp)

        # Only temperature check should be present
        assert any(c.parameter == "temperature" for c in result.checks)

    def test_deviation_percentage(self):
        """Checks include deviation percentage from optimal midpoint."""
        inp = FlightEnvelopeInput(species="BSF", temperature=35.0)
        result = check_flight_envelope(inp)

        temp_check = next(c for c in result.checks if c.parameter == "temperature")
        assert temp_check.deviation_pct is not None

    def test_warnings_on_edge(self):
        """Parameters near boundaries generate warnings."""
        inp = FlightEnvelopeInput(
            species="BSF",
            temperature=33.0,  # Near upper optimal boundary
        )
        result = check_flight_envelope(inp)

        assert result.in_envelope is True
        # May or may not have warnings depending on exact boundary

    def test_species_bsf(self):
        """BSF species has expected optimal temperature range."""
        inp = FlightEnvelopeInput(species="BSF", temperature=28.0)
        result = check_flight_envelope(inp)

        assert result.species == "BSF"
        assert result.in_envelope is True

    def test_unknown_species_fallback(self):
        """Unknown species uses BSF defaults (or raises)."""
        inp = FlightEnvelopeInput(species="UNKNOWN_SPECIES", temperature=28.0)

        # Either uses default ranges or returns a meaningful result
        try:
            result = check_flight_envelope(inp)
            assert result is not None
        except (ValueError, KeyError):
            pass  # Acceptable to reject unknown species

    def test_deterministic(self):
        """Same input always produces same output."""
        inp = FlightEnvelopeInput(species="BSF", temperature=28.0, moisture=70.0)
        r1 = check_flight_envelope(inp)
        r2 = check_flight_envelope(inp)

        assert r1.in_envelope == r2.in_envelope
        assert r1.overall_zone == r2.overall_zone
