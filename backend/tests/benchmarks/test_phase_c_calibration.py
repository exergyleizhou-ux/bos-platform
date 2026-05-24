"""Phase C C5 — calibration benchmark tests.

Compact pytest version of the operator CLI in
``backend/scripts/run_phase_c_calibration.py``. Runs at smaller
N to fit a CI-friendly time budget.

Tests are marked ``@pytest.mark.slow`` and skipped by default
in fast CI loops. Run with::

    pytest tests/benchmarks/test_phase_c_calibration.py -m slow

Or directly::

    pytest tests/benchmarks/test_phase_c_calibration.py

Coverage check tolerance:
- Coverage ≥ (1-α) * 0.85 — allows ~10% Monte Carlo slack at
  small N. At n_trials=30, binomial 95% CI on a true 0.95
  proportion is roughly [0.87, 0.99], so we set the lower bar
  at 0.85 (slightly looser) to avoid flaky tests.
- Larger campaigns in the CLI use tighter tolerances naturally
  via larger sample sizes.

Reference: PHASE_C_PLAN.md §2.5; CLI in
``scripts/run_phase_c_calibration.py``.
"""

from __future__ import annotations

import pytest

# Reuse the calibration runners from the operator CLI
# (avoids duplication; the CLI module is importable as a
# library because main() is __name__ == "__main__"-guarded)
import scripts.run_phase_c_calibration as cal_cli


@pytest.mark.slow
def test_c2_conformal_coverage_meets_target():
    """C5.1: split-conformal empirical coverage ≥ (1-α) * 0.85."""
    result = cal_cli.run_c2_conformal_coverage(
        n_trials=30,
        n_per_trial=200,
    )
    target = result["target_coverage"]
    empirical = result["empirical_coverage"]
    assert empirical >= target * 0.85, (
        f"Conformal coverage {empirical:.3f} below "
        f"{target * 0.85:.3f} = {target} × 0.85; "
        f"target was {target}"
    )


@pytest.mark.slow
def test_c4_uncertainty_pipeline_no_systematic_bias():
    """C5.2: SER point error < 0.05 across 30 random regimes."""
    result = cal_cli.run_c4_uncertainty_pipeline_sanity(n_trials=30)
    max_err = result["max_point_error"]
    assert max_err < 0.05, (
        f"C4 point error {max_err:.4f} > 0.05 tolerance"
    )


@pytest.mark.slow
def test_c1_bayesian_coverage_small_trial():
    """C5.3: C1 HDI covers truth in ≥ 70% of 5 trials.

    Bar is 70% (not 95%) because at n_trials=5, binomial
    sampling noise is too high to assert 95% coverage. The
    operator CLI run at n_trials=50+ is the authoritative
    coverage check for paper figures.
    """
    result = cal_cli.run_c1_bayesian_coverage(
        n_trials=5,
        n_per_trial=80,
        n_draws=200,
        n_tune=200,
    )
    empirical = result["empirical_coverage"]
    assert empirical >= 0.7, (
        f"C1 HDI coverage at small trial count = "
        f"{empirical:.2f}; want ≥ 0.70"
    )
