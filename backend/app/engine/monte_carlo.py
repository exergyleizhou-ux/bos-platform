"""Backward-compatible Monte Carlo module used by legacy tests."""

from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np


@dataclass
class MonteCarloInput:
    dm_in_mean: float
    dm_in_std: float
    dm_out_mean: float
    dm_out_std: float
    n_simulations: int = 1000
    seed: int | None = None


@dataclass
class MonteCarloResult:
    n_simulations: int
    ser_mean: float
    ser_std: float
    ser_p5: float
    ser_median: float
    ser_p95: float
    pass_probability: float
    histogram_bins: list[float]
    histogram_counts: list[int]
    computation_time_ms: float


def run_monte_carlo(inp: MonteCarloInput) -> MonteCarloResult:
    started = time.perf_counter()
    if inp.n_simulations <= 0:
        raise ValueError("n_simulations must be > 0")
    if inp.dm_in_std < 0 or inp.dm_out_std < 0:
        raise ValueError("std must be >= 0")
    if inp.dm_in_mean <= 0:
        raise ValueError("dm_in_mean must be > 0")

    rng = np.random.default_rng(inp.seed)
    dm_in = rng.normal(inp.dm_in_mean, inp.dm_in_std, inp.n_simulations)
    dm_out = rng.normal(inp.dm_out_mean, inp.dm_out_std, inp.n_simulations)
    dm_in = np.clip(dm_in, 1e-9, None)
    dm_out = np.clip(dm_out, 0.0, None)
    dm_out = np.minimum(dm_out, dm_in)

    # Legacy convention: lower is better.
    ser = (dm_in - dm_out) / dm_in

    counts, edges = np.histogram(ser, bins=30)
    bins = ((edges[:-1] + edges[1:]) / 2.0).tolist()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return MonteCarloResult(
        n_simulations=inp.n_simulations,
        ser_mean=float(np.mean(ser)),
        ser_std=float(np.std(ser)),
        ser_p5=float(np.percentile(ser, 5)),
        ser_median=float(np.percentile(ser, 50)),
        ser_p95=float(np.percentile(ser, 95)),
        pass_probability=float(np.mean(ser <= 0.30)),
        histogram_bins=[float(v) for v in bins],
        histogram_counts=[int(v) for v in counts.tolist()],
        computation_time_ms=elapsed_ms,
    )
