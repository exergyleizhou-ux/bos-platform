"""
BOS Pipeline v9.0 �� Sensitivity Analysis Engine

Performs global sensitivity analysis using:
  1. Sobol' indices (first-order, second-order, total)
  2. Morris screening (Elementary Effects)
  3. One-at-a-time (OAT) local sensitivity

Identifies which input parameters have the greatest influence on SER
and other outputs, guiding experimental design and uncertainty reduction.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from app.engine.ser_engine import SERInput, compute_ser

ENGINE_VERSION = "9.0.0"


@dataclass
class SensitivityInput:
    """Input for sensitivity analysis."""

    method: str = "sobol"  # sobol, morris, oat
    n_samples: int = 1024  # Number of samples (must be power of 2 for Sobol)
    parameters: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "dm_in": (5.0, 20.0),
        "dm_out": (1.0, 6.0),
        "n_in": (20.0, 80.0),
        "n_larvae": (10.0, 50.0),
        "n_frass": (5.0, 30.0),
    })
    output_name: str = "ser_value"  # Which output to analyze
    seed: Optional[int] = None


@dataclass
class SensitivityResult:
    """Sensitivity analysis results."""

    # Sobol indices
    first_order: Dict[str, float] = field(default_factory=dict)
    total_order: Dict[str, float] = field(default_factory=dict)
    second_order: Optional[Dict[str, float]] = None

    # Morris indices
    mu_star: Optional[Dict[str, float]] = None  # Mean absolute elementary effect
    sigma: Optional[Dict[str, float]] = None  # Std of elementary effects

    # Rankings
    parameter_ranking: List[str] = field(default_factory=list)

    # Metadata
    method: str = ""
    n_samples: int = 0
    n_model_evaluations: int = 0
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Sobol Sequence Generator (simplified)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _sobol_sample(n: int, d: int, rng: np.random.Generator) -> NDArray:
    """
    Generate quasi-random samples in [0,1]^d.
    Uses a simple stratified random approach as a Sobol proxy.
    For production, use scipy.stats.qmc.Sobol.
    """
    try:
        from scipy.stats.qmc import Sobol
        sampler = Sobol(d, scramble=True, seed=rng.integers(0, 2**31))
        return sampler.random(n)
    except ImportError:
        # Fallback: stratified random
        samples = np.zeros((n, d))
        for j in range(d):
            perm = rng.permutation(n)
            for i in range(n):
                samples[i, j] = (perm[i] + rng.random()) / n
        return samples


def _scale_samples(samples: NDArray, bounds: List[Tuple[float, float]]) -> NDArray:
    """Scale [0,1] samples to parameter bounds."""
    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])
    return samples * (upper - lower) + lower


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Model Evaluation
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _evaluate_ser(params_matrix: NDArray, param_names: List[str]) -> NDArray:
    """Evaluate SER for a matrix of parameter values."""
    n = params_matrix.shape[0]
    outputs = np.zeros(n)

    name_to_idx = {name: i for i, name in enumerate(param_names)}

    for i in range(n):
        row = params_matrix[i]
        inp = SERInput(
            dm_in=row[name_to_idx.get("dm_in", 0)] if "dm_in" in name_to_idx else 10.0,
            dm_out=row[name_to_idx.get("dm_out", 0)] if "dm_out" in name_to_idx else 2.5,
            n_in=row[name_to_idx.get("n_in", 0)] if "n_in" in name_to_idx else 50.0,
            n_larvae=row[name_to_idx.get("n_larvae", 0)] if "n_larvae" in name_to_idx else 30.0,
            n_frass=row[name_to_idx.get("n_frass", 0)] if "n_frass" in name_to_idx else 15.0,
        )
        result = compute_ser(inp)
        outputs[i] = result.ser_value

    return outputs


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Sobol Analysis
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _sobol_analysis(inp: SensitivityInput, rng: np.random.Generator) -> SensitivityResult:
    """Compute first-order and total-order Sobol indices."""
    param_names = list(inp.parameters.keys())
    bounds = list(inp.parameters.values())
    d = len(param_names)
    n = inp.n_samples

    # Generate two independent sample matrices A and B
    A_unit = _sobol_sample(n, d, rng)
    B_unit = _sobol_sample(n, d, rng)

    A = _scale_samples(A_unit, bounds)
    B = _scale_samples(B_unit, bounds)

    # Evaluate base matrices
    f_A = _evaluate_ser(A, param_names)
    f_B = _evaluate_ser(B, param_names)

    total_evals = 2 * n

    # Compute indices for each parameter
    first_order: Dict[str, float] = {}
    total_order: Dict[str, float] = {}
    f0_sq = np.mean(f_A) * np.mean(f_B)
    var_total = np.var(np.concatenate([f_A, f_B]))

    if var_total < 1e-15:
        # No variance �� all indices are zero
        for name in param_names:
            first_order[name] = 0.0
            total_order[name] = 0.0
    else:
        for j, name in enumerate(param_names):
            # C_j matrix: take column j from B, rest from A
            C_j = A.copy()
            C_j[:, j] = B[:, j]
            f_C = _evaluate_ser(C_j, param_names)
            total_evals += n

            # First-order: S_i = V[E[Y|X_i]] / V[Y]
            Vi = np.mean(f_B * (f_C - f_A))
            first_order[name] = round(float(max(Vi / var_total, 0)), 6)

            # Total-order: ST_i = E[V[Y|X_~i]] / V[Y]
            VTi = 0.5 * np.mean((f_A - f_C) ** 2)
            total_order[name] = round(float(max(VTi / var_total, 0)), 6)

    # Ranking by total-order
    ranking = sorted(param_names, key=lambda x: total_order.get(x, 0), reverse=True)

    return SensitivityResult(
        first_order=first_order,
        total_order=total_order,
        parameter_ranking=ranking,
        method="sobol",
        n_samples=n,
        n_model_evaluations=total_evals,
    )


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Morris Screening
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _morris_analysis(inp: SensitivityInput, rng: np.random.Generator) -> SensitivityResult:
    """Compute Morris elementary effects (mu*, sigma)."""
    param_names = list(inp.parameters.keys())
    bounds = list(inp.parameters.values())
    d = len(param_names)
    r = min(inp.n_samples, 100)  # Number of trajectories
    p = 4  # Number of levels
    delta = p / (2 * (p - 1))

    lower = np.array([b[0] for b in bounds])
    upper = np.array([b[1] for b in bounds])

    # Store elementary effects
    EE: Dict[str, List[float]] = {name: [] for name in param_names}
    total_evals = 0

    for _ in range(r):
        # Random base point (on grid)
        x_base = rng.choice(np.arange(0, 1, 1 / p), size=d)
        x_scaled = x_base * (upper - lower) + lower

        # Evaluate base
        f_base = float(_evaluate_ser(x_scaled.reshape(1, -1), param_names)[0])
        total_evals += 1

        # Random permutation of dimensions
        perm = rng.permutation(d)

        x_current = x_base.copy()
        f_current = f_base

        for j in perm:
            # Perturb dimension j
            x_new = x_current.copy()
            x_new[j] = x_new[j] + delta
            if x_new[j] > 1.0:
                x_new[j] = x_new[j] - 2 * delta

            x_new_scaled = x_new * (upper - lower) + lower
            f_new = float(_evaluate_ser(x_new_scaled.reshape(1, -1), param_names)[0])
            total_evals += 1

            # Elementary effect
            ee = (f_new - f_current) / delta
            EE[param_names[j]].append(ee)

            x_current = x_new
            f_current = f_new

    # Compute mu* and sigma
    mu_star: Dict[str, float] = {}
    sigma: Dict[str, float] = {}

    for name in param_names:
        effects = np.array(EE[name])
        mu_star[name] = round(float(np.mean(np.abs(effects))), 6)
        sigma[name] = round(float(np.std(effects)), 6)

    ranking = sorted(param_names, key=lambda x: mu_star.get(x, 0), reverse=True)

    return SensitivityResult(
        mu_star=mu_star,
        sigma=sigma,
        parameter_ranking=ranking,
        method="morris",
        n_samples=r,
        n_model_evaluations=total_evals,
    )


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# OAT (One-at-a-Time)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _oat_analysis(inp: SensitivityInput) -> SensitivityResult:
    """Simple one-at-a-time sensitivity around parameter midpoints."""
    param_names = list(inp.parameters.keys())
    bounds = list(inp.parameters.values())
    d = len(param_names)

    midpoints = np.array([(b[0] + b[1]) / 2 for b in bounds])

    # Base evaluation
    f_base = float(_evaluate_ser(midpoints.reshape(1, -1), param_names)[0])
    total_evals = 1

    first_order: Dict[str, float] = {}
    perturbation = 0.01  # 1% perturbation

    for j, name in enumerate(param_names):
        x_pert = midpoints.copy()
        dx = midpoints[j] * perturbation
        if dx == 0:
            dx = perturbation
        x_pert[j] += dx

        f_pert = float(_evaluate_ser(x_pert.reshape(1, -1), param_names)[0])
        total_evals += 1

        sensitivity = (f_pert - f_base) / dx * midpoints[j]  # Normalized
        first_order[name] = round(float(abs(sensitivity)), 6)

    ranking = sorted(param_names, key=lambda x: first_order.get(x, 0), reverse=True)

    return SensitivityResult(
        first_order=first_order,
        total_order=first_order,  # OAT doesn't distinguish
        parameter_ranking=ranking,
        method="oat",
        n_samples=1,
        n_model_evaluations=total_evals,
    )


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Main Entry Point
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def run_sensitivity_analysis(inp: SensitivityInput) -> SensitivityResult:
    """
    Run global sensitivity analysis.

    Parameters
    ----------
    inp : SensitivityInput
        Analysis configuration.

    Returns
    -------
    SensitivityResult
        Parameter importance rankings and indices.
    """
    start_time = time.perf_counter()
    rng = np.random.default_rng(inp.seed)

    if inp.method == "sobol":
        result = _sobol_analysis(inp, rng)
    elif inp.method == "morris":
        result = _morris_analysis(inp, rng)
    elif inp.method == "oat":
        result = _oat_analysis(inp)
    else:
        return SensitivityResult(errors=[f"Unknown method: {inp.method}"])

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
