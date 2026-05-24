"""Phase C C4 — /api/v1/causal/uncertainty_pipeline engine.

End-to-end SER uncertainty propagation: takes posterior samples on
D' and G' (typically from /bayesian_estimate C1 runs) and propagates
through SER = sqrt(D' × G') via Monte Carlo. Returns a credibility
band on SER.

Reference: _reports/PHASE_C_PLAN.md §2.4.

Operationalises Paper 1 §3.6's 2×10^5 Monte Carlo propagation of
component-level uncertainty in D' and G' through the geometric-
mean SER aggregator. The Phase B B2a engine reports SER cheaply
via point estimate + CI on a single fit; this C4 engine takes
**posterior samples** as input and gives a **posterior** on SER
as output.

Two propagation methods:
- ``monte_carlo_resample`` (default): resample N independent draws
  from each input posterior, combine pointwise. Robust to
  different sample sizes between D' and G'.
- ``pairwise_alignment``: treats the i-th draw of each input as a
  joint sample. Requires len(D') == len(G'). Use when D' and G'
  came from the same joint posterior (rare).

Negative samples of D' or G' (which can arise in posterior tails
when the prior allows) yield NaN under sqrt(D' × G') if the
product is negative. We drop those samples and report the count
in diagnostics.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np

from app.schemas.causal_common import (
    CausalWarning,
    EvidenceLevel,
)
from app.schemas.causal.uncertainty import (
    CredibilityBand,
    PropagationMethod,
    UncertaintyPipelineDiagnostics,
    UncertaintyPipelineRequest,
    UncertaintyPipelineResponse,
)


# ════════════════════════════════════════════════════════════════════
# Public entry point
# ════════════════════════════════════════════════════════════════════


def propagate_uncertainty(
    request: UncertaintyPipelineRequest,
) -> Tuple[UncertaintyPipelineResponse, List[CausalWarning]]:
    """Propagate D' / G' / mediation uncertainty to SER posterior.

    Returns ``(response, warnings_list)``.

    Raises ``CausalUncertaintyError`` on domain failures (mapped to
    HTTP 422 at the router layer).
    """
    warnings_list: List[CausalWarning] = []
    t0 = time.perf_counter()

    d_samples = np.asarray(request.d_prime_posterior, dtype=float)
    g_samples = np.asarray(request.g_prime_posterior, dtype=float)

    # 1. Propagation
    if request.method == "monte_carlo_resample":
        rng = np.random.default_rng(request.random_seed)
        n_draws = request.n_propagated_samples
        d_draws = rng.choice(d_samples, size=n_draws, replace=True)
        g_draws = rng.choice(g_samples, size=n_draws, replace=True)
    elif request.method == "pairwise_alignment":
        # Length parity already enforced by the schema validator.
        d_draws = d_samples
        g_draws = g_samples
    else:
        raise CausalUncertaintyError(
            code="method_unknown",
            message=f"Unknown propagation method: {request.method!r}",
        )

    # 2. SER computation; drop invalid samples (negative product)
    product = d_draws * g_draws
    invalid_mask = product < 0.0
    n_invalid = int(invalid_mask.sum())
    if n_invalid > 0:
        warnings_list.append(
            CausalWarning(
                code="ci_wider_than_estimate",
                message=(
                    f"Dropped {n_invalid} propagated samples with "
                    f"negative D'×G' product (cannot take sqrt). "
                    f"Tail behaviour of the input posteriors."
                ),
            )
        )
        valid_mask = ~invalid_mask
        d_draws = d_draws[valid_mask]
        g_draws = g_draws[valid_mask]
        product = product[valid_mask]

    ser_samples = np.sqrt(product)

    if len(ser_samples) == 0:
        raise CausalUncertaintyError(
            code="all_samples_invalid",
            message=(
                "All propagated samples had negative D'×G' product; "
                "no valid SER samples remain. Check input posteriors "
                "for sign / scale issues."
            ),
        )

    # 3. SER point + band
    ser_point = float(np.mean(ser_samples))
    alpha = request.alpha
    ser_low = float(np.quantile(ser_samples, alpha / 2))
    ser_median = float(np.quantile(ser_samples, 0.5))
    ser_high = float(np.quantile(ser_samples, 1 - alpha / 2))

    # Defensive: enforce ordering when quantile estimates collapse
    # on degenerate posteriors (e.g. all samples equal). The
    # CredibilityBand validator would otherwise reject.
    ser_median = max(ser_low, min(ser_high, ser_median))

    ser_band = CredibilityBand(
        low=ser_low, median=ser_median, high=ser_high
    )

    # 4. Optional mediation band
    mediation_band: Optional[CredibilityBand] = None
    pearl_residual: Optional[float] = None
    if request.mediation_proportion_posterior is not None:
        m_samples = np.asarray(
            request.mediation_proportion_posterior, dtype=float
        )
        # Drop NaN / inf which can arise when raw NIE/total
        # divides by zero in the upstream mediation engine
        m_samples = m_samples[np.isfinite(m_samples)]
        if len(m_samples) == 0:
            warnings_list.append(
                CausalWarning(
                    code="ci_wider_than_estimate",
                    message=(
                        "mediation_proportion_posterior had no "
                        "finite values; proportion_mediated_band "
                        "omitted."
                    ),
                )
            )
        else:
            m_low = float(np.quantile(m_samples, alpha / 2))
            m_median = float(np.quantile(m_samples, 0.5))
            m_high = float(np.quantile(m_samples, 1 - alpha / 2))
            m_median = max(m_low, min(m_high, m_median))
            mediation_band = CredibilityBand(
                low=m_low, median=m_median, high=m_high
            )
            # Pearl consistency: posterior mean of
            # proportion_mediated. Just report; not enforce.
            pearl_residual = abs(
                float(np.mean(m_samples)) - m_median
            )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # 5. Diagnostics + evidence level
    diagnostics = UncertaintyPipelineDiagnostics(
        n_d_prime_input=len(d_samples),
        n_g_prime_input=len(g_samples),
        n_mediation_input=(
            len(request.mediation_proportion_posterior)
            if request.mediation_proportion_posterior is not None
            else None
        ),
        n_propagated=len(ser_samples),
        method=request.method,
        propagation_time_ms=elapsed_ms,
        invalid_samples_dropped=n_invalid,
    )

    evidence_level: EvidenceLevel = _classify_evidence(
        n_d=len(d_samples),
        n_g=len(g_samples),
        n_propagated=len(ser_samples),
        ser_low=ser_low,
        ser_high=ser_high,
    )

    response = UncertaintyPipelineResponse(
        final_ser_point=ser_point,
        final_ser_credibility_band=ser_band,
        final_ser_posterior_samples=ser_samples.tolist(),
        proportion_mediated_band=mediation_band,
        pearl_consistency_residual=pearl_residual,
        diagnostics=diagnostics,
        alpha=alpha,
        method=request.method,
        random_seed=request.random_seed,
        evidence_level=evidence_level,
        warnings=warnings_list,
    )
    return response, warnings_list


# ════════════════════════════════════════════════════════════════════
# Exception
# ════════════════════════════════════════════════════════════════════


class CausalUncertaintyError(Exception):
    """Domain exception for uncertainty-pipeline failures."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════


def _classify_evidence(
    n_d: int,
    n_g: int,
    n_propagated: int,
    ser_low: float,
    ser_high: float,
) -> EvidenceLevel:
    """Evidence classification for C4 uncertainty pipeline.

    - validated: n_d ≥ 500 AND n_g ≥ 500 AND n_propagated ≥ 5000
      AND credibility band excludes 0
    - supported: n_d ≥ 100 AND n_g ≥ 100 AND ser_low > 0
    - planned: otherwise (small inputs or band crossing 0)
    """
    band_excludes_zero = ser_low > 0.0  # SER is in [0, 1] by construction

    if (
        n_d >= 500
        and n_g >= 500
        and n_propagated >= 5000
        and band_excludes_zero
    ):
        return "validated"
    if n_d >= 100 and n_g >= 100 and band_excludes_zero:
        return "supported"
    return "planned"
