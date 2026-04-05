"""
BOS Pipeline v9.0 �� SER Engine Unit Tests

Tests the core Substrate Efficiency Ratio computation engine.
"""

import math
import pytest

from app.engine.ser_engine import (
    SERInput,
    compute_ser,
    grade_ser,
    PASS_THRESHOLD,
    ENGINE_VERSION,
)


class TestComputeSER:
    """Tests for the main compute_ser function."""

    def test_basic_computation(self):
        """SER = dm_out / dm_in for the simplest case."""
        inp = SERInput(dm_in=10.0, dm_out=2.3)
        result = compute_ser(inp)

        assert result.ser_value == pytest.approx(0.23, rel=1e-4)
        assert result.eer == pytest.approx(0.23, rel=1e-4)
        assert result.passed is True
        assert result.grade == "A"
        assert result.engine_version == ENGINE_VERSION

    def test_high_efficiency(self):
        """SER > 0.25 �� A+ grade."""
        inp = SERInput(dm_in=10.0, dm_out=3.0)
        result = compute_ser(inp)

        assert result.ser_value == pytest.approx(0.30, rel=1e-4)
        assert result.grade == "A+"
        assert result.passed is True
        assert len(result.fail_codes) == 0

    def test_low_efficiency(self):
        """SER < 0.10 �� F grade, fails."""
        inp = SERInput(dm_in=10.0, dm_out=0.5)
        result = compute_ser(inp)

        assert result.ser_value == pytest.approx(0.05, rel=1e-4)
        assert result.grade == "F"
        assert result.passed is False

    def test_marginal_pass(self):
        """SER at exactly the pass threshold."""
        dm_out = PASS_THRESHOLD * 10.0  # exactly at threshold
        inp = SERInput(dm_in=10.0, dm_out=dm_out)
        result = compute_ser(inp)

        assert result.ser_value == pytest.approx(PASS_THRESHOLD, rel=1e-4)
        assert result.passed is True

    def test_marginal_fail(self):
        """SER just below the pass threshold."""
        dm_out = (PASS_THRESHOLD - 0.001) * 10.0
        inp = SERInput(dm_in=10.0, dm_out=dm_out)
        result = compute_ser(inp)

        assert result.passed is False

    def test_with_nitrogen_balance(self):
        """SER includes nitrogen balance when N values provided."""
        inp = SERInput(
            dm_in=10.0,
            dm_out=2.3,
            n_in=50.0,
            n_larvae=30.0,
            n_frass=15.0,
        )
        result = compute_ser(inp)

        assert result.ser_value > 0
        assert result.nitrogen_balance == pytest.approx(
            (30.0 + 15.0) / 50.0, rel=1e-4
        )

    def test_with_ash_balance(self):
        """Ash balance is computed when ash values provided."""
        inp = SERInput(
            dm_in=10.0,
            dm_out=2.3,
            ash_in=1.0,
            ash_out=0.8,
        )
        result = compute_ser(inp)

        assert result.ash_balance is not None
        assert result.ash_balance == pytest.approx(0.8 / 1.0, rel=1e-4)

    def test_with_fat_balance(self):
        """Fat balance is computed when fat values provided."""
        inp = SERInput(
            dm_in=10.0,
            dm_out=2.3,
            fat_in=2.0,
            fat_out=1.5,
        )
        result = compute_ser(inp)

        assert result.fat_balance is not None
        assert result.fat_balance == pytest.approx(1.5 / 2.0, rel=1e-4)

    def test_full_input(self):
        """SER with all optional fields populated."""
        inp = SERInput(
            dm_in=12.0,
            dm_out=2.8,
            n_in=60.0,
            n_larvae=35.0,
            n_frass=18.0,
            ash_in=1.5,
            ash_out=1.2,
            fat_in=2.5,
            fat_out=2.0,
        )
        result = compute_ser(inp)

        assert result.ser_value > 0
        assert result.eer > 0
        assert result.mcr > 0
        assert result.bcr > 0
        assert result.nitrogen_balance is not None
        assert result.ash_balance is not None
        assert result.fat_balance is not None
        assert isinstance(result.recommendations, list)

    def test_zero_dm_out(self):
        """Zero output �� SER = 0, fails."""
        inp = SERInput(dm_in=10.0, dm_out=0.0)
        result = compute_ser(inp)

        assert result.ser_value == 0.0
        assert result.passed is False
        assert result.grade == "F"

    def test_dm_out_exceeds_dm_in(self):
        """dm_out > dm_in �� SER > 1, still computes but flags warning."""
        inp = SERInput(dm_in=5.0, dm_out=6.0)
        result = compute_ser(inp)

        assert result.ser_value > 1.0
        assert "SER_ABOVE_1" in result.fail_codes or len(result.recommendations) > 0

    def test_nitrogen_imbalance(self):
        """Nitrogen out > nitrogen in �� flag N_IMBALANCE."""
        inp = SERInput(
            dm_in=10.0,
            dm_out=2.3,
            n_in=30.0,
            n_larvae=25.0,
            n_frass=15.0,
        )
        result = compute_ser(inp)

        # N_out = 25 + 15 = 40 > 30 = N_in �� imbalance
        assert result.nitrogen_balance > 1.0
        assert "N_IMBALANCE" in result.fail_codes

    def test_deterministic_results(self):
        """Same input always produces same output."""
        inp = SERInput(dm_in=10.0, dm_out=2.3)
        r1 = compute_ser(inp)
        r2 = compute_ser(inp)

        assert r1.ser_value == r2.ser_value
        assert r1.grade == r2.grade
        assert r1.passed == r2.passed


class TestGradeSER:
    """Tests for the grade_ser helper function."""

    def test_a_plus(self):
        assert grade_ser(0.30) == "A+"

    def test_a(self):
        assert grade_ser(0.22) == "A"

    def test_b(self):
        assert grade_ser(0.18) == "B"

    def test_c(self):
        assert grade_ser(0.13) == "C"

    def test_d(self):
        assert grade_ser(0.08) == "D"

    def test_f(self):
        assert grade_ser(0.03) == "F"

    def test_zero(self):
        assert grade_ser(0.0) == "F"

    def test_boundary_a_plus(self):
        """Exact boundary at 0.25."""
        assert grade_ser(0.25) == "A+"

    def test_boundary_a(self):
        """Exact boundary at 0.20."""
        assert grade_ser(0.20) == "A"

    def test_boundary_b(self):
        """Exact boundary at 0.15."""
        assert grade_ser(0.15) == "B"

    def test_boundary_c(self):
        """Exact boundary at 0.10."""
        assert grade_ser(0.10) == "C"

    def test_boundary_d(self):
        """Exact boundary at 0.05."""
        assert grade_ser(0.05) == "D"
