"""
BOS Pipeline v9.0 �� SER Engine Unit Tests

Tests for SER calculation logic, grading, edge cases, and nitrogen balance.
"""

import math
import pytest

from app.engine.ser_calculator import (
    compute_ser,
    compute_nitrogen_balance,
    score_to_grade,
    SERInput,
    SERResult,
)


class TestComputeSER:
    """Tests for the core SER computation."""

    def test_basic_computation(self):
        """SER should equal (dm_in - dm_out) / dm_in for simple case."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=8.5))
        assert isinstance(result, SERResult)
        expected = (10.0 - 8.5) / 10.0
        assert math.isclose(result.ser_value, expected, rel_tol=1e-6)

    def test_perfect_conversion(self):
        """All input consumed �� SER = 1.0."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=0.0))
        assert math.isclose(result.ser_value, 1.0, rel_tol=1e-6)

    def test_no_conversion(self):
        """No conversion �� SER = 0.0."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=10.0))
        assert math.isclose(result.ser_value, 0.0, abs_tol=1e-9)

    def test_with_nitrogen(self):
        """SER with nitrogen fractions should differ from simple DM ratio."""
        result_simple = compute_ser(SERInput(dm_in=10.0, dm_out=8.0))
        result_n = compute_ser(
            SERInput(
                dm_in=10.0,
                dm_out=8.0,
                n_in=0.5,
                n_larvae=0.3,
                n_frass=0.15,
            )
        )
        # With nitrogen data, result should be adjusted
        assert result_n.ser_value != result_simple.ser_value
        assert result_n.nitrogen_balance is not None

    def test_negative_dm_out_raises(self):
        """Negative dm_out should raise ValueError."""
        with pytest.raises(ValueError, match="dm_out"):
            compute_ser(SERInput(dm_in=10.0, dm_out=-1.0))

    def test_zero_dm_in_raises(self):
        """Zero dm_in should raise ValueError (division by zero)."""
        with pytest.raises(ValueError, match="dm_in"):
            compute_ser(SERInput(dm_in=0.0, dm_out=5.0))

    def test_dm_out_greater_than_dm_in_raises(self):
        """dm_out > dm_in should raise ValueError."""
        with pytest.raises(ValueError, match="dm_out.*dm_in"):
            compute_ser(SERInput(dm_in=5.0, dm_out=10.0))

    def test_result_has_grade(self):
        """Result should include a grade string."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=8.5))
        assert result.grade in {"A+", "A", "B", "C", "D", "F"}

    def test_result_has_pass_flag(self):
        """Result should include pass/fail boolean."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=8.5))
        assert isinstance(result.passed, bool)

    def test_computation_time_tracked(self):
        """Result should report computation time."""
        result = compute_ser(SERInput(dm_in=10.0, dm_out=8.5))
        assert result.computation_time_ms >= 0


class TestNitrogenBalance:
    """Tests for nitrogen balance calculation."""

    def test_basic_balance(self):
        """Sum of outputs should be <= input (conservation)."""
        balance = compute_nitrogen_balance(
            n_in=0.5, n_larvae=0.3, n_frass=0.15
        )
        assert balance.n_loss >= 0
        assert math.isclose(
            balance.n_in,
            balance.n_larvae + balance.n_frass + balance.n_loss,
            rel_tol=1e-6,
        )

    def test_perfect_recovery(self):
        """All nitrogen recovered �� n_loss �� 0."""
        balance = compute_nitrogen_balance(
            n_in=1.0, n_larvae=0.6, n_frass=0.4
        )
        assert math.isclose(balance.n_loss, 0.0, abs_tol=1e-9)
        assert math.isclose(balance.recovery_pct, 1.0, rel_tol=1e-6)

    def test_zero_input_raises(self):
        """Zero n_in should raise ValueError."""
        with pytest.raises(ValueError, match="n_in"):
            compute_nitrogen_balance(n_in=0.0, n_larvae=0.1, n_frass=0.1)


class TestScoreToGrade:
    """Tests for grade assignment from SER score."""

    @pytest.mark.parametrize(
        "score,expected_grade",
        [
            (0.05, "A+"),
            (0.08, "A+"),
            (0.10, "A"),
            (0.12, "A"),
            (0.15, "B"),
            (0.20, "B"),
            (0.25, "C"),
            (0.30, "C"),
            (0.35, "D"),
            (0.40, "D"),
            (0.50, "F"),
            (1.00, "F"),
        ],
    )
    def test_grade_boundaries(self, score: float, expected_grade: str):
        grade = score_to_grade(score)
        assert grade == expected_grade, f"score={score} �� got {grade}, expected {expected_grade}"

    def test_zero_score(self):
        """Zero SER should get A+."""
        assert score_to_grade(0.0) == "A+"

    def test_negative_score_raises(self):
        """Negative SER should raise ValueError."""
        with pytest.raises(ValueError):
            score_to_grade(-0.1)
