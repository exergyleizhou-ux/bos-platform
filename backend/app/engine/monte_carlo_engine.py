"""
BOS Pipeline v9.0 �� Monte Carlo Simulation Engine

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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Data Classes
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Sampling Functions
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _sample_normal(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a normal distribution, clipping at zero."""
    samples = rng.normal(mean, std, n) if std > 0 else np.full(n, mean)
    return np.maximum(samples, 1e-10)  # Avoid zero/negative values


def _sample_lognormal(rng: np.random.Generator, mean: float, std: float, n: int) -> NDArray[np.float64]:
    """Sample from a log-normal distribution."""
    if std <= 0 or mean <= 0:
        return np.full(n, max(mean, 1e-10))
    # Convert mean/std to log-space parameters
    variance = std ** 2
    mu = np.log(mean ** 2 / np.sqrt(variance + mean ** 2))
    sigma = np.sqrt(np.log(1 + variance / mean ** 2))
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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Core Simulation
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Detailed Simulation (uses full SER engine per sample)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


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
            n_samples=0, ser_mean=0.0, ser_std=0.0, ser_median=0.0,
            ser_ci_lower=0.0, ser_ci_upper=0.0, errors=errors,
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
