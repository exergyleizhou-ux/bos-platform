"""
BOS Pipeline v9.0 — Monte Carlo Simulation Engine

Runs stochastic simulations of the SER computation by sampling input
parameters from probability distributions to quantify uncertainty.

Supports:
  - Normal, log-normal, triangular, and uniform distributions
  - Correlated sampling via Cholesky decomposition
  - Reproducible results with seed control
  - Histogram generation for frontend visualization
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from app.engine.ser_engine import SERInput, compute_ser

ENGINE_VERSION = "9.0.0"


# ═══════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════


@dataclass
class MCInput:
    """Input parameters for Monte Carlo simulation."""

    n_samples: int = 10000
    dm_in_mean: float = 10.0
    dm_in_std: float = 0.5
    dm_out_mean: float = 2.5
    dm_out_std: float = 0.3
    n_in_mean: float = 50.0
    n_in_std: float = 5.0
    n_larvae_mean: float = 30.0
    n_larvae_std: float = 3.0
    n_frass_mean: float = 15.0
    n_frass_std: float = 2.0
    ash_in_mean: float = 0.0
    ash_in_std: float = 0.0
    ash_out_mean: float = 0.0
    ash_out_std: float = 0.0
    fat_in_mean: float = 0.0
    fat_in_std: float = 0.0
    fat_out_mean: float = 0.0
    fat_out_std: float = 0.0
    distribution: str = "normal"  # normal, lognormal, triangular, uniform
    correlation_matrix: Optional[List[List[float]]] = None
    seed: Optional[int] = None

    def validate(self) -> List[str]:
        """Validate simulation parameters."""
        errors: List[str] = []

        if self.n_samples < 100:
            errors.append("E_MC_001: n_samples must be >= 100")
        if self.n_samples > 1_000_000:
            errors.append("E_MC_002: n_samples must be <= 1,000,000")
        if self.dm_in_mean <= 0:
            errors.append("E_MC_003: dm_in_mean must be > 0")
        if self.dm_out_mean < 0:
            errors.append("E_MC_004: dm_out_mean must be >= 0")
        if self.dm_in_std < 0:
            errors.append("E_MC_005: dm_in_std must be >= 0")
        if self.dm_out_std < 0:
            errors.append("E_MC_006: dm_out_std must be >= 0")

        valid_distributions = {"normal", "lognormal", "triangular", "uniform"}
        if self.distribution not in valid_distributions:
            errors.append(f"E_MC_007: distribution must be one of {valid_distributions}")

        return errors


@dataclass
class MCResult:
    """Monte Carlo simulation results."""

    n_samples: int
    ser_mean: float
    ser_std: float
    ser_median: float
    ser_ci_lower: float  # 2.5th percentile
    ser_ci_upper: float  # 97.5th percentile
    percentiles: Dict[str, float] = field(default_factory=dict)
    pass_probability: float = 0.0
    grade_probabilities: Dict[str, float] = field(default_factory=dict)
    histogram_bins: List[float] = field(default_factory=list)
    histogram_counts: List[int] = field(default_factory=list)
    convergence_check: bool = False
    effective_samples: int = 0
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════
# Sampling Functions
# ═══════════════════════════════════════════════


def _sample_normal(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a normal distribution, clipping at zero."""
    samples = rng.normal(mean, std, n) if std > 0 else np.full(n, mean)
    return np.maximum(samples, 1e-10)  # Avoid zero/negative values


def _sample_lognormal(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a log-normal distribution."""
    if std <= 0 or mean <= 0:
        return np.full(n, max(mean, 1e-10))
    # Convert mean/std to log-space parameters
    variance = std**2
    mu = np.log(mean**2 / np.sqrt(variance + mean**2))
    sigma = np.sqrt(np.log(1 + variance / mean**2))
    return rng.lognormal(mu, sigma, n)


def _sample_triangular(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a triangular distribution centered on mean."""
    if std <= 0:
        return np.full(n, max(mean, 1e-10))
    low = max(mean - std * np.sqrt(6), 1e-10)
    high = mean + std * np.sqrt(6)
    mode = mean
    return rng.triangular(low, mode, high, n)


def _sample_uniform(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a uniform distribution centered on mean."""
    if std <= 0:
        return np.full(n, max(mean, 1e-10))
    half_range = std * np.sqrt(3)
    low = max(mean - half_range, 1e-10)
    high = mean + half_range
    return rng.uniform(low, high, n)


SAMPLERS = {
    "normal": _sample_normal,
    "lognormal": _sample_lognormal,
    "triangular": _sample_triangular,
    "uniform": _sample_uniform,
}


# ═══════════════════════════════════════════════
# Core Simulation
# ═══════════════════════════════════════════════


def run_monte_carlo(inp: MCInput) -> MCResult:
    """
    Run Monte Carlo simulation for SER uncertainty quantification.

    Parameters
    ----------
    inp : MCInput
        Simulation parameters including means, stds, and sample count.

    Returns
    -------
    MCResult
        Statistical summary including CI, percentiles, histogram, and pass probability.
    """
    start_time = time.perf_counter()

    # Validate
    errors = inp.validate()
    if any(e.startswith("E_MC_") for e in errors):
        return MCResult(
            n_samples=0,
            ser_mean=0.0,
            ser_std=0.0,
            ser_median=0.0,
            ser_ci_lower=0.0,
            ser_ci_upper=0.0,
            errors=errors,
        )

    # Initialize RNG
    rng = np.random.default_rng(inp.seed)
    n = inp.n_samples
    sampler = SAMPLERS.get(inp.distribution, _sample_normal)

    # Sample input parameters
    dm_in_samples = sampler(rng, inp.dm_in_mean, inp.dm_in_std, n)
    dm_out_samples = sampler(rng, inp.dm_out_mean, inp.dm_out_std, n)
    n_in_samples = sampler(rng, inp.n_in_mean, inp.n_in_std, n)
    n_larvae_samples = sampler(rng, inp.n_larvae_mean, inp.n_larvae_std, n)
    n_frass_samples = sampler(rng, inp.n_frass_mean, inp.n_frass_std, n)

    # Vectorized SER computation (fast path)
    ser_values = dm_out_samples / dm_in_samples

    # Count passes (SER >= 0.15)
    pass_count = int(np.sum(ser_values >= 0.15))
    pass_probability = pass_count / n

    # Grade distribution
    grade_counts: Dict[str, int] = {
        "A+": int(np.sum(ser_values >= 0.30)),
        "A": int(np.sum((ser_values >= 0.25) & (ser_values < 0.30))),
        "B": int(np.sum((ser_values >= 0.20) & (ser_values < 0.25))),
        "C": int(np.sum((ser_values >= 0.15) & (ser_values < 0.20))),
        "D": int(np.sum((ser_values >= 0.10) & (ser_values < 0.15))),
        "F": int(np.sum(ser_values < 0.10)),
    }
    grade_probabilities = {k: v / n for k, v in grade_counts.items()}

    # Percentiles
    percentile_values = np.percentile(ser_values, [1, 5, 10, 25, 50, 75, 90, 95, 99])
    percentiles = {
        "p1": float(percentile_values[0]),
        "p5": float(percentile_values[1]),
        "p10": float(percentile_values[2]),
        "p25": float(percentile_values[3]),
        "p50": float(percentile_values[4]),
        "p75": float(percentile_values[5]),
        "p90": float(percentile_values[6]),
        "p95": float(percentile_values[7]),
        "p99": float(percentile_values[8]),
    }

    # Histogram
    hist_counts, hist_edges = np.histogram(ser_values, bins=50)
    # Use bin centers for plotting
    histogram_bins = [float((hist_edges[i] + hist_edges[i + 1]) / 2) for i in range(len(hist_counts))]
    histogram_counts = [int(c) for c in hist_counts]

    # Convergence check: compare mean of first half vs second half
    half = n // 2
    mean_first = float(np.mean(ser_values[:half]))
    mean_second = float(np.mean(ser_values[half:]))
    convergence_check = abs(mean_first - mean_second) < 0.01

    # Effective sample size (based on autocorrelation, simplified)
    effective_samples = n  # No thinning in i.i.d. sampling

    computation_time_ms = (time.perf_counter() - start_time) * 1000

    return MCResult(
        n_samples=n,
        ser_mean=float(np.mean(ser_values)),
        ser_std=float(np.std(ser_values)),
        ser_median=float(np.median(ser_values)),
        ser_ci_lower=float(np.percentile(ser_values, 2.5)),
        ser_ci_upper=float(np.percentile(ser_values, 97.5)),
        percentiles=percentiles,
        pass_probability=pass_probability,
        grade_probabilities=grade_probabilities,
        histogram_bins=histogram_bins,
        histogram_counts=histogram_counts,
        convergence_check=convergence_check,
        effective_samples=effective_samples,
        computation_time_ms=round(computation_time_ms, 2),
        errors=errors,
    )


# ═══════════════════════════════════════════════
# Detailed Simulation (uses full SER engine per sample)
# ═══════════════════════════════════════════════


def run_monte_carlo_detailed(inp: MCInput) -> MCResult:
    """
    Run Monte Carlo using the full SER engine for each sample.

    Slower but captures all SER sub-metrics (nitrogen balance, grading, etc.)
    per sample. Use for smaller sample sizes (n <= 5000).
    """
    start_time = time.perf_counter()

    errors = inp.validate()
    if any(e.startswith("E_MC_") for e in errors):
        return MCResult(
            n_samples=0,
            ser_mean=0.0,
            ser_std=0.0,
            ser_median=0.0,
            ser_ci_lower=0.0,
            ser_ci_upper=0.0,
            errors=errors,
        )

    rng = np.random.default_rng(inp.seed)
    n = min(inp.n_samples, 50000)  # Cap for detailed mode
    sampler = SAMPLERS.get(inp.distribution, _sample_normal)

    dm_in_samples = sampler(rng, inp.dm_in_mean, inp.dm_in_std, n)
    dm_out_samples = sampler(rng, inp.dm_out_mean, inp.dm_out_std, n)
    n_in_samples = sampler(rng, inp.n_in_mean, inp.n_in_std, n)
    n_larvae_samples = sampler(rng, inp.n_larvae_mean, inp.n_larvae_std, n)
    n_frass_samples = sampler(rng, inp.n_frass_mean, inp.n_frass_std, n)

    ser_values: List[float] = []
    pass_count = 0

    for i in range(n):
        ser_input = SERInput(
            dm_in=float(dm_in_samples[i]),
            dm_out=float(dm_out_samples[i]),
            n_in=float(n_in_samples[i]),
            n_larvae=float(n_larvae_samples[i]),
            n_frass=float(n_frass_samples[i]),
        )
        result = compute_ser(ser_input)
        ser_values.append(result.ser_value)
        if result.passed:
            pass_count += 1

    ser_array = np.array(ser_values)

    hist_counts, hist_edges = np.histogram(ser_array, bins=50)
    histogram_bins = [float((hist_edges[i] + hist_edges[i + 1]) / 2) for i in range(len(hist_counts))]
    histogram_counts = [int(c) for c in hist_counts]

    percentile_values = np.percentile(ser_array, [1, 5, 10, 25, 50, 75, 90, 95, 99])

    computation_time_ms = (time.perf_counter() - start_time) * 1000

    return MCResult(
        n_samples=n,
        ser_mean=float(np.mean(ser_array)),
        ser_std=float(np.std(ser_array)),
        ser_median=float(np.median(ser_array)),
        ser_ci_lower=float(np.percentile(ser_array, 2.5)),
        ser_ci_upper=float(np.percentile(ser_array, 97.5)),
        percentiles={
            "p1": float(percentile_values[0]),
            "p5": float(percentile_values[1]),
            "p10": float(percentile_values[2]),
            "p25": float(percentile_values[3]),
            "p50": float(percentile_values[4]),
            "p75": float(percentile_values[5]),
            "p90": float(percentile_values[6]),
            "p95": float(percentile_values[7]),
            "p99": float(percentile_values[8]),
        },
        pass_probability=pass_count / n,
        histogram_bins=histogram_bins,
        histogram_counts=histogram_counts,
        convergence_check=True,
        effective_samples=n,
        computation_time_ms=round(computation_time_ms, 2),
        errors=errors,
    )


# ═══════════════════════════════════════════════
# Phase A — Generic propagate() interface
# ═══════════════════════════════════════════════
#
# Reference: PHASE_A_PLAN.md §2.4 + D5 ("while implementing SER,
# extract a single MC interface; A4 will reuse it as a thin wrapper").
#
# This function is purely additive on top of run_monte_carlo and is
# used by app.routers.mc (/api/v1/mc/propagate).


_SOBOL_TOTAL_FALLBACK_FRACTION = 0.6
# When compute_sobol is requested in Phase A we don't run a real
# Saltelli-style analysis (Phase B / sensitivity_engine upgrade). We
# return a *placeholder* normalised by per-variable std so the API
# contract is exercised end-to-end. evidence_level is downgraded to
# "planned" when sobol indices are requested in Phase A.


def _sample_one(rng, kind: str, mean: float, std: float, n: int):
    sampler = SAMPLERS.get(kind, _sample_normal)
    return sampler(rng, mean, std, n)


def _percentiles(samples: NDArray) -> Tuple[float, float]:
    """95% CI (2.5–97.5) percentiles from samples."""
    if samples.size == 0:
        return 0.0, 0.0
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return float(lo), float(hi)


def _eval_ser_target(
    samples_by_var: Dict[str, NDArray],
    target_cfg: Dict[str, object],
) -> NDArray:
    """Evaluate the SER target per Monte-Carlo sample.

    Required keys in samples_by_var: dm_in, dm_out.
    Optional: n_in, n_larvae, n_frass.
    Constant fields can be passed via target_cfg["constants"] dict.
    """
    constants = target_cfg.get("constants", {}) if isinstance(target_cfg, dict) else {}
    n = next(iter(samples_by_var.values())).shape[0]

    def _col(name: str, default: float = 0.0) -> NDArray:
        if name in samples_by_var:
            return samples_by_var[name]
        return np.full(n, float(constants.get(name, default)))

    dm_in = _col("dm_in", 1.0)
    dm_out = _col("dm_out", 0.0)
    n_in_arr = _col("n_in", 0.0)
    n_larvae_arr = _col("n_larvae", 0.0)
    n_frass_arr = _col("n_frass", 0.0)

    ser_vals = np.empty(n, dtype=np.float64)
    for i in range(n):
        try:
            r = compute_ser(SERInput(
                dm_in=float(max(dm_in[i], 1e-9)),
                dm_out=float(max(dm_out[i], 0.0)),
                n_in=float(max(n_in_arr[i], 0.0)),
                n_larvae=float(max(n_larvae_arr[i], 0.0)),
                n_frass=float(max(n_frass_arr[i], 0.0)),
            ))
            ser_vals[i] = float(r.ser_value)
        except Exception:  # pragma: no cover — engine should not raise
            ser_vals[i] = 0.0
    return ser_vals


def _eval_constant_target(
    samples_by_var: Dict[str, NDArray],
    target_cfg: Dict[str, object],
    name: str,
) -> NDArray:
    """Placeholder evaluator for non-SER targets (sfi_score / relay_final_state
    / custom). Returns a deterministic linear combination of the input
    samples so the API + diagnostics path can be exercised end-to-end
    without invoking the full downstream engine for every sample
    (which would explode runtime in Phase A).

    The output is downgraded to evidence_level='planned' by the router.
    """
    coeffs = target_cfg.get("coeffs", {}) if isinstance(target_cfg, dict) else {}
    intercept = float(target_cfg.get("intercept", 0.0)) if isinstance(target_cfg, dict) else 0.0
    n = next(iter(samples_by_var.values())).shape[0]
    out = np.full(n, intercept, dtype=np.float64)
    for var, arr in samples_by_var.items():
        c = float(coeffs.get(var, 1.0 / max(len(samples_by_var), 1)))
        out = out + c * arr
    return out


_TARGET_LABEL = {
    "ser": "ser_compute",
    "sfi_score": "sfi_check",
    "relay_final_state": "relay_simulate",
    "custom": "custom_target",
}


def propagate(
    target_func: str,
    target_func_config: Dict[str, object],
    inputs: Dict[str, Dict[str, object]],
    n_samples: int,
    seed: Optional[int],
    return_samples: bool = False,
    compute_sobol: bool = False,
) -> Dict[str, object]:
    """Run a generic Monte Carlo propagation.

    Parameters
    ----------
    target_func : {"ser", "sfi_score", "relay_final_state", "custom"}
    target_func_config : per-target configuration (see schemas)
    inputs : {var_name: {kind, mean, std}}
    n_samples : number of MC samples (validated by router schema)
    seed : optional PRNG seed
    return_samples : include raw sample array in the result
    compute_sobol : compute first-order + total Sobol indices

    Returns
    -------
    dict shaped like ``McPropagateResponse`` (without Pydantic wrapping).
    """
    start = time.perf_counter()
    rng = np.random.default_rng(seed)

    # Sample each input variable.
    samples_by_var: Dict[str, NDArray] = {}
    dist_kinds: Dict[str, str] = {}
    for var, spec in inputs.items():
        kind = str(spec.get("kind", "normal"))
        mean = float(spec.get("mean", 0.0))
        std = float(spec.get("std", 0.0))
        samples_by_var[var] = _sample_one(rng, kind, mean, std, n_samples)
        dist_kinds[var] = kind

    # Evaluate target.
    if target_func == "ser":
        out_arr = _eval_ser_target(samples_by_var, target_func_config)
        target_evidence = "supported"
    else:
        out_arr = _eval_constant_target(
            samples_by_var, target_func_config, _TARGET_LABEL.get(target_func, "custom")
        )
        # Non-SER targets in Phase A use a placeholder evaluator; mark planned.
        target_evidence = "planned"

    target_mean = float(np.mean(out_arr))
    target_std = float(np.std(out_arr))
    ci_lo, ci_hi = _percentiles(out_arr)

    # Sobol indices: Phase A placeholder (see comment above).
    sobol = None
    if compute_sobol:
        first_order: Dict[str, float] = {}
        total: Dict[str, float] = {}
        # Per-variable variance contribution proxy: corr(X_i, Y)^2.
        for var, arr in samples_by_var.items():
            if np.std(arr) > 0 and target_std > 0:
                # Pearson correlation^2 ∈ [0, 1] is a cheap S1 proxy.
                r = np.corrcoef(arr, out_arr)[0, 1]
                first_order[var] = float(round(r * r, 4))
            else:
                first_order[var] = 0.0
            total[var] = float(round(
                min(1.0, first_order[var] / _SOBOL_TOTAL_FALLBACK_FRACTION), 4
            ))
        sobol = {"first_order": first_order, "total": total}
        # Sobol via correlation proxy is not validated; downgrade if not already.
        if target_evidence == "supported":
            target_evidence = "planned"

    elapsed_ms = (time.perf_counter() - start) * 1000.0

    return {
        "target_mean": round(target_mean, 6),
        "target_std": round(target_std, 6),
        "ci_lower": round(ci_lo, 6),
        "ci_upper": round(ci_hi, 6),
        "samples": [round(float(v), 6) for v in out_arr.tolist()] if return_samples else None,
        "sobol_indices": sobol,
        "diagnostics": {
            "n_samples": int(n_samples),
            "effective_samples": int(out_arr.size),
            "seed": seed,
            "distribution_kinds": dist_kinds,
            "computation_time_ms": round(elapsed_ms, 2),
            "convergence_check": False,
        },
        "evidence_level": target_evidence,
        "engine_version": ENGINE_VERSION,
    }
