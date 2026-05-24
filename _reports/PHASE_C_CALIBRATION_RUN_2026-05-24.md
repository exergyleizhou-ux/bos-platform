# Phase C — Calibration Run Report

**Generated:** 2026-05-24 06:11:05 UTC

Operator-side calibration of Phase C engines (Bayesian, Conformal, Uncertainty pipeline) against synthetic data with known truth. Produced by ``backend/scripts/run_phase_c_calibration.py``.

**Anchor:** This run is informational. The Phase C OpenAPI snapshot gate (``test_phase_c_openapi.py``) and the per-engine unit tests in ``tests/unit/`` are the authoritative drift gates; this report is for Paper 3 §"Validation" section figures and operator spot-checks.

## Summary table

| Engine | n_trials | Target | Empirical | Pass? |
|---|---|---|---|---|
| C2 Conformal | 20 | 95.00% | 95.40% | ✓ |
| C4 Uncertainty pipeline | 20 | — | point_err 0.0028 | ✓ |

## Detailed results

### C2 Conformal

- **n_trials**: 20
- **total_predictions**: 2000
- **target_coverage**: 0.9500
- **empirical_coverage**: 0.9540
- **median_interval_width**: 4.1059
- **passes**: True

### C4 Uncertainty pipeline

- **n_trials**: 20
- **mean_point_error**: 0.0010
- **max_point_error**: 0.0028
- **median_band_width**: 0.0938
- **passes**: True

## Operator notes

- C2 Conformal coverage is the most directly interpretable: empirical coverage on held-out synthetic test points should match the (1-α) guarantee within Monte Carlo noise.
- C4 Uncertainty pipeline 'pass' criterion uses point-error tolerance (0.05); this is a sanity check that the geometric-mean propagation does not introduce systematic bias.
- C1 Bayesian coverage at small n_trials is noisy. For publication-grade figures, re-run with ``--n-trials 50`` or higher. The default 5 keeps the operator's wall-clock at ~5-10 minutes without a C++ compiler (each PyMC run takes 30-90s).
- C3 Bayesian mediation is intentionally NOT included in this calibration run: it would require ~5-10 PyMC runs at ~150s each. Use C1 calibration as a proxy for C3 sampler health; for full C3 calibration, write a separate offline campaign.
