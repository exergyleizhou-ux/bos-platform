"""
BOS Pipeline v9.0 �� Gaussian Process Calibration Engine

Uses Gaussian Process Regression (GPR) to calibrate bioconversion models
against observed data. The GP provides:
  - Non-parametric, flexible curve fitting
  - Uncertainty quantification (posterior variance)
  - Automatic relevance determination (ARD) for feature selection

Use cases:
  - Calibrate SER predictions to site-specific data
  - Build surrogate models for expensive simulations
  - Bayesian optimization of operating parameters
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

ENGINE_VERSION = "9.0.0"


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Kernel Functions
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def rbf_kernel(X1: NDArray, X2: NDArray, length_scale: float, variance: float) -> NDArray:
    """Radial Basis Function (Squared Exponential) kernel."""
    dists = cdist(X1, X2, metric="sqeuclidean")
    return variance * np.exp(-0.5 * dists / (length_scale ** 2))


def matern52_kernel(X1: NDArray, X2: NDArray, length_scale: float, variance: float) -> NDArray:
    """Mat��rn 5/2 kernel �� smoother than RBF, more realistic for physical processes."""
    dists = cdist(X1, X2, metric="euclidean") / length_scale
    sqrt5_d = np.sqrt(5.0) * dists
    return variance * (1.0 + sqrt5_d + 5.0 / 3.0 * dists ** 2) * np.exp(-sqrt5_d)


def ard_kernel(X1: NDArray, X2: NDArray, length_scales: NDArray, variance: float) -> NDArray:
    """ARD (Automatic Relevance Determination) RBF kernel �� per-dimension length scales."""
    X1_scaled = X1 / length_scales
    X2_scaled = X2 / length_scales
    dists = cdist(X1_scaled, X2_scaled, metric="sqeuclidean")
    return variance * np.exp(-0.5 * dists)


KERNELS = {
    "rbf": rbf_kernel,
    "matern52": matern52_kernel,
}


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Data Classes
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


@dataclass
class GPInput:
    """Input for GP calibration."""

    X_train: List[List[float]]  # Training features (n_samples �� n_features)
    y_train: List[float]  # Training targets (n_samples,)
    X_predict: Optional[List[List[float]]] = None  # Prediction points
    kernel: str = "matern52"  # "rbf" or "matern52"
    noise_variance: float = 0.01  # Observation noise ��2_n
    optimize_hyperparams: bool = True
    n_restarts: int = 5


@dataclass
class GPResult:
    """GP calibration results."""

    # Predictions
    y_pred_mean: List[float] = field(default_factory=list)
    y_pred_std: List[float] = field(default_factory=list)
    y_pred_ci_lower: List[float] = field(default_factory=list)
    y_pred_ci_upper: List[float] = field(default_factory=list)

    # Hyperparameters
    length_scale: float = 1.0
    signal_variance: float = 1.0
    noise_variance: float = 0.01
    log_marginal_likelihood: float = 0.0

    # Model quality
    r_squared: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None

    # Feature importance (for ARD)
    feature_importance: Optional[Dict[str, float]] = None

    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# GP Core
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _log_marginal_likelihood(
    params: NDArray,
    X: NDArray,
    y: NDArray,
    kernel_func,
) -> float:
    """Negative log marginal likelihood for hyperparameter optimization."""
    length_scale = np.exp(params[0])
    signal_var = np.exp(params[1])
    noise_var = np.exp(params[2])

    n = X.shape[0]
    K = kernel_func(X, X, length_scale, signal_var)
    K += noise_var * np.eye(n) + 1e-8 * np.eye(n)  # Jitter for numerical stability

    try:
        L = np.linalg.cholesky(K)
    except np.linalg.LinAlgError:
        return 1e10

    alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))

    nll = 0.5 * y.T @ alpha + np.sum(np.log(np.diag(L))) + 0.5 * n * np.log(2 * np.pi)
    return float(nll)


def fit_gp(inp: GPInput) -> GPResult:
    """
    Fit a Gaussian Process model and make predictions.

    Parameters
    ----------
    inp : GPInput
        Training data, prediction points, and kernel choice.

    Returns
    -------
    GPResult
        Predictions with uncertainty and model quality metrics.
    """
    start_time = time.perf_counter()
    result = GPResult()

    # Validate input
    if len(inp.X_train) < 2:
        result.errors.append("Need at least 2 training points")
        return result

    if len(inp.X_train) != len(inp.y_train):
        result.errors.append("X_train and y_train must have same length")
        return result

    X = np.array(inp.X_train, dtype=np.float64)
    y = np.array(inp.y_train, dtype=np.float64)
    n, d = X.shape

    # Normalize inputs
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-8
    X_norm = (X - X_mean) / X_std

    y_mean = y.mean()
    y_std = y.std() + 1e-8
    y_norm = (y - y_mean) / y_std

    # Select kernel
    kernel_func = KERNELS.get(inp.kernel, matern52_kernel)

    # Optimize hyperparameters
    best_params = np.array([0.0, 0.0, np.log(inp.noise_variance)])
    best_nll = float("inf")

    if inp.optimize_hyperparams:
        rng = np.random.default_rng(42)
        for _ in range(inp.n_restarts):
            x0 = rng.normal(0, 1, 3)
            try:
                opt = minimize(
                    _log_marginal_likelihood,
                    x0,
                    args=(X_norm, y_norm, kernel_func),
                    method="L-BFGS-B",
                    bounds=[(-5, 5), (-5, 5), (-10, 2)],
                )
                if opt.fun < best_nll:
                    best_nll = opt.fun
                    best_params = opt.x
            except Exception:
                continue

    length_scale = float(np.exp(best_params[0]))
    signal_var = float(np.exp(best_params[1]))
    noise_var = float(np.exp(best_params[2]))

    result.length_scale = round(length_scale, 6)
    result.signal_variance = round(signal_var, 6)
    result.noise_variance = round(noise_var, 6)
    result.log_marginal_likelihood = round(-best_nll, 4)

    # Build posterior
    K = kernel_func(X_norm, X_norm, length_scale, signal_var)
    K += noise_var * np.eye(n) + 1e-8 * np.eye(n)

    try:
        L = np.linalg.cholesky(K)
    except np.linalg.LinAlgError:
        result.errors.append("Cholesky decomposition failed. Data may be ill-conditioned.")
        return result

    alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_norm))

    # Predictions
    X_pred = inp.X_predict if inp.X_predict else inp.X_train
    Xs = np.array(X_pred, dtype=np.float64)
    Xs_norm = (Xs - X_mean) / X_std

    K_star = kernel_func(Xs_norm, X_norm, length_scale, signal_var)
    K_ss = kernel_func(Xs_norm, Xs_norm, length_scale, signal_var)

    # Posterior mean
    f_mean = K_star @ alpha
    # Posterior variance
    v = np.linalg.solve(L, K_star.T)
    f_var = np.diag(K_ss) - np.sum(v ** 2, axis=0)
    f_var = np.maximum(f_var, 0)  # Numerical floor
    f_std = np.sqrt(f_var)

    # Denormalize
    pred_mean = f_mean * y_std + y_mean
    pred_std = f_std * y_std

    result.y_pred_mean = [round(float(v), 6) for v in pred_mean]
    result.y_pred_std = [round(float(v), 6) for v in pred_std]
    result.y_pred_ci_lower = [round(float(m - 1.96 * s), 6) for m, s in zip(pred_mean, pred_std)]
    result.y_pred_ci_upper = [round(float(m + 1.96 * s), 6) for m, s in zip(pred_mean, pred_std)]

    # Model quality (on training data)
    if inp.X_predict is None or inp.X_predict == inp.X_train:
        ss_res = np.sum((y - pred_mean) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        if ss_tot > 0:
            result.r_squared = round(float(1 - ss_res / ss_tot), 6)
        result.rmse = round(float(np.sqrt(np.mean((y - pred_mean) ** 2))), 6)
        result.mae = round(float(np.mean(np.abs(y - pred_mean))), 6)

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return result
