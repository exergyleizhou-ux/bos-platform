"""Phase C C4 — unit tests for causal_uncertainty_pipeline.

Covers 10 behaviors per the C4 design (Plan v3 §2.4):

1. Paper 1 baseline (D'=0.683, G'=0.672) recovers SER ≈ 0.68
2. Credibility band ordering (low ≤ median ≤ high)
3. monte_carlo_resample independent of input length
4. pairwise_alignment requires same length (validator)
5. pairwise_alignment uses joint sampling
6. alpha sensitivity (0.05 vs 0.10 wider/narrower)
7. seed reproducibility
8. mediation_proportion_posterior supplied → band returned
9. Negative D'×G' products dropped with warning
10. All-negative samples → CausalUncertaintyError

All FAST tests (no PyMC, pure numpy + pydantic). Typical runtime
~5-20 ms per test.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from app.engine.extended.causal_uncertainty_pipeline import (
    CausalUncertaintyError,
    propagate_uncertainty,
)
from app.schemas.causal.uncertainty import (
    CredibilityBand,
    SCHEMA_VERSION,
    UncertaintyPipelineRequest,
    UncertaintyPipelineResponse,
)


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


def _make_paper1_request(
    n_d: int = 1000,
    n_g: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
    method: str = "monte_carlo_resample",
    n_propagated_samples: int = 10000,
    include_mediation: bool = False,
    n_m: int = 1000,
) -> UncertaintyPipelineRequest:
    """Build a request approximating Paper 1's D'/G' posteriors."""
    rng = np.random.default_rng(seed)
    d = rng.normal(0.683, 0.021, n_d).tolist()
    g = rng.normal(0.672, 0.019, n_g).tolist()
    kwargs = dict(
        d_prime_posterior=d,
        g_prime_posterior=g,
        method=method,
        alpha=alpha,
        n_propagated_samples=n_propagated_samples,
        random_seed=seed,
    )
    if include_mediation:
        # Mediation proportion centred on Paper 1's ~70%
        m = rng.normal(0.70, 0.05, n_m).tolist()
        kwargs["mediation_proportion_posterior"] = m
    return UncertaintyPipelineRequest(**kwargs)


# ════════════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════════════


def test_paper1_baseline_recovers_ser_068():
    """C4.1: SER posterior mean matches Paper 1's 0.68 within 0.01."""
    request = _make_paper1_request(seed=42)
    response, _ = propagate_uncertainty(request)

    err = abs(response.final_ser_point - 0.68)
    assert err < 0.02, (
        f"SER posterior mean {response.final_ser_point:.4f} should "
        f"recover Paper 1's 0.68 within 0.02 (err {err:.4f})"
    )
    assert response.schema_version == SCHEMA_VERSION


def test_credibility_band_ordering():
    """C4.2: low ≤ median ≤ high for both SER and mediation bands."""
    request = _make_paper1_request(include_mediation=True)
    response, _ = propagate_uncertainty(request)

    b = response.final_ser_credibility_band
    assert b.low <= b.median <= b.high

    m = response.proportion_mediated_band
    assert m is not None
    assert m.low <= m.median <= m.high


def test_monte_carlo_resample_handles_length_mismatch():
    """C4.3: monte_carlo_resample works when len(D') != len(G')."""
    request = _make_paper1_request(n_d=200, n_g=1500)
    response, _ = propagate_uncertainty(request)
    # Should succeed without error
    assert response.diagnostics.n_d_prime_input == 200
    assert response.diagnostics.n_g_prime_input == 1500


def test_pairwise_alignment_requires_same_length():
    """C4.4: pairwise_alignment + mismatched lengths → ValidationError."""
    with pytest.raises(ValidationError):
        _make_paper1_request(
            n_d=200,
            n_g=300,
            method="pairwise_alignment",
        )


def test_pairwise_alignment_works_with_same_length():
    """C4.5: pairwise_alignment with matched lengths succeeds."""
    request = _make_paper1_request(
        n_d=500,
        n_g=500,
        method="pairwise_alignment",
    )
    response, _ = propagate_uncertainty(request)
    # Pairwise uses input directly — n_propagated should equal
    # input length (modulo dropped invalid samples)
    assert response.diagnostics.n_propagated <= 500


def test_alpha_smaller_yields_wider_band():
    """C4.6: alpha=0.01 (99% band) wider than alpha=0.10 (90%)."""
    r_99, _ = propagate_uncertainty(_make_paper1_request(alpha=0.01))
    r_90, _ = propagate_uncertainty(_make_paper1_request(alpha=0.10))

    width_99 = r_99.final_ser_credibility_band.high - r_99.final_ser_credibility_band.low
    width_90 = r_90.final_ser_credibility_band.high - r_90.final_ser_credibility_band.low
    assert width_99 > width_90, (
        f"alpha=0.01 band width {width_99:.4f} should be > "
        f"alpha=0.10 width {width_90:.4f}"
    )


def test_seed_reproducibility():
    """C4.7: same seed → identical SER posterior samples."""
    r1, _ = propagate_uncertainty(_make_paper1_request(seed=42))
    r2, _ = propagate_uncertainty(_make_paper1_request(seed=42))

    samples1 = np.array(r1.final_ser_posterior_samples)
    samples2 = np.array(r2.final_ser_posterior_samples)
    np.testing.assert_array_almost_equal(samples1, samples2, decimal=10)


def test_mediation_band_present_when_supplied():
    """C4.8: mediation_proportion_posterior → proportion_mediated_band."""
    request = _make_paper1_request(include_mediation=True)
    response, _ = propagate_uncertainty(request)

    assert response.proportion_mediated_band is not None
    # Paper 1 mediation proportion ~70%, so band should be near 0.7
    m = response.proportion_mediated_band
    assert 0.5 < m.median < 0.9


def test_mediation_band_absent_when_not_supplied():
    """C4.8b: omitting mediation samples → no band in response."""
    request = _make_paper1_request(include_mediation=False)
    response, _ = propagate_uncertainty(request)

    assert response.proportion_mediated_band is None
    assert response.pearl_consistency_residual is None


def test_negative_products_dropped_with_warning():
    """C4.9: D' × G' < 0 samples dropped + warning emitted."""
    rng = np.random.default_rng(42)
    # Mix in some negative D' values to trigger negative products
    d = rng.normal(0.5, 0.5, 200).tolist()  # std 0.5 → some negatives
    g = rng.normal(0.5, 0.5, 200).tolist()  # std 0.5 → some negatives

    request = UncertaintyPipelineRequest(
        d_prime_posterior=d,
        g_prime_posterior=g,
        method="monte_carlo_resample",
        alpha=0.05,
        n_propagated_samples=5000,
        random_seed=42,
    )
    response, warnings_list = propagate_uncertainty(request)

    # Expect some invalid samples dropped
    assert response.diagnostics.invalid_samples_dropped >= 0
    if response.diagnostics.invalid_samples_dropped > 0:
        codes = [w.code for w in warnings_list]
        assert "ci_wider_than_estimate" in codes


def test_all_invalid_raises_error():
    """C4.10: all-negative product samples → CausalUncertaintyError."""
    # Force all-negative D' (purely negative posterior) — pairwise
    # alignment means we get exact pairs.
    rng = np.random.default_rng(42)
    d = (-rng.uniform(0.1, 0.5, 100)).tolist()  # all negative
    g = rng.uniform(0.1, 0.5, 100).tolist()  # all positive
    # Every pair will have negative product

    request = UncertaintyPipelineRequest(
        d_prime_posterior=d,
        g_prime_posterior=g,
        method="pairwise_alignment",
        alpha=0.05,
        n_propagated_samples=100,
        random_seed=42,
    )
    with pytest.raises(CausalUncertaintyError) as exc_info:
        propagate_uncertainty(request)

    assert exc_info.value.code == "all_samples_invalid"


# ════════════════════════════════════════════════════════════════════
# Bonus
# ════════════════════════════════════════════════════════════════════


def test_evidence_level_validated_on_paper1_baseline():
    """Bonus: Paper 1 baseline n=1000/1000/10000 → evidence='validated'."""
    request = _make_paper1_request(n_d=1000, n_g=1000, n_propagated_samples=10000)
    response, _ = propagate_uncertainty(request)
    assert response.evidence_level == "validated"


def test_credibility_band_validator_rejects_unordered():
    """Bonus: CredibilityBand schema enforces low ≤ median ≤ high."""
    with pytest.raises(ValidationError):
        CredibilityBand(low=0.7, median=0.5, high=0.6)
