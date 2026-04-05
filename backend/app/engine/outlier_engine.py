"""
BOS Pipeline v9.0 �� Statistical Outlier Detection Engine

Detects statistical outliers in individual fields using:
  1. Modified Z-score (MAD-based, robust)
  2. Grubbs' test (single outlier, assumes normality)
  3. Dixon's Q test (small samples, n < 25)
  4. Tukey's fences (IQR-based)

Unlike anomaly_engine (multivariate / row-level), this engine works
on individual columns for per-field quality checks.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

ENGINE_VERSION = "9.0.0"


@dataclass
class OutlierInput:
    """Input for per-field outlier detection."""

    values: List[float]
    field_name: str = "value"
    method: str = "modified_zscore"  # modified_zscore, grubbs, dixon, tukey
    threshold: float = 3.5  # For modified Z-score
    alpha: float = 0.05  # Significance level for Grubbs/Dixon
    iqr_factor: float = 1.5  # For Tukey's fences


@dataclass
class OutlierResult:
    """Per-field outlier detection results."""

    outlier_indices: List[int] = field(default_factory=list)
    outlier_values: List[float] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)  # Outlier score per value
    n_outliers: int = 0
    n_total: int = 0
    outlier_rate: float = 0.0

    # Distribution statistics
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    mad: float = 0.0  # Median Absolute Deviation
    q1: float = 0.0
    q3: float = 0.0
    iqr: float = 0.0
    lower_fence: float = 0.0
    upper_fence: float = 0.0

    method: str = ""
    field_name: str = ""
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def _modified_zscore(values: np.ndarray, threshold: float) -> Tuple[List[int], np.ndarray]:
    """Modified Z-score using Median Absolute Deviation (MAD)."""
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        mad = np.mean(np.abs(values - median))  # Fallback
    if mad == 0:
        return [], np.zeros(len(values))

    modified_z = 0.6745 * (values - median) / mad
    outlier_mask = np.abs(modified_z) > threshold
    return list(np.where(outlier_mask)[0]), modified_z


def _grubbs_test(values: np.ndarray, alpha: float) -> Tuple[List[int], np.ndarray]:
    """Grubbs' test for a single outlier (iterative)."""
    n = len(values)
    if n < 3:
        return [], np.zeros(n)

    outliers: List[int] = []
    remaining = values.copy()
    original_indices = list(range(n))

    while len(remaining) >= 3:
        n_r = len(remaining)
        mean = np.mean(remaining)
        std = np.std(remaining, ddof=1)
        if std == 0:
            break

        # Test statistic: max |x_i - mean| / std
        abs_dev = np.abs(remaining - mean)
        max_idx = int(np.argmax(abs_dev))
        G = abs_dev[max_idx] / std

        # Critical value
        t_crit = stats.t.ppf(1 - alpha / (2 * n_r), n_r - 2)
        G_crit = (n_r - 1) / np.sqrt(n_r) * np.sqrt(t_crit ** 2 / (n_r - 2 + t_crit ** 2))

        if G > G_crit:
            outliers.append(original_indices[max_idx])
            remaining = np.delete(remaining, max_idx)
            original_indices.pop(max_idx)
        else:
            break

    scores = np.abs(values - np.mean(values)) / (np.std(values, ddof=1) + 1e-10)
    return outliers, scores


def _dixon_q_test(values: np.ndarray, alpha: float) -> Tuple[List[int], np.ndarray]:
    """Dixon's Q test for outliers (best for n < 25)."""
    n = len(values)
    if n < 3 or n > 30:
        return [], np.zeros(n)

    # Critical values for Dixon's Q test (approximate)
    q_critical = {3: 0.941, 4: 0.765, 5: 0.642, 6: 0.560, 7: 0.507,
                  8: 0.468, 9: 0.437, 10: 0.412, 15: 0.338, 20: 0.300, 25: 0.277, 30: 0.260}

    q_crit = q_critical.get(n, 0.300)

    sorted_vals = np.sort(values)
    sorted_indices = np.argsort(values)

    outliers: List[int] = []

    # Test lowest
    data_range = sorted_vals[-1] - sorted_vals[0]
    if data_range > 0:
        q_low = (sorted_vals[1] - sorted_vals[0]) / data_range
        if q_low > q_crit:
            outliers.append(int(sorted_indices[0]))

        # Test highest
        q_high = (sorted_vals[-1] - sorted_vals[-2]) / data_range
        if q_high > q_crit:
            outliers.append(int(sorted_indices[-1]))

    scores = np.abs(values - np.median(values)) / (np.std(values) + 1e-10)
    return outliers, scores


def _tukey_fences(values: np.ndarray, factor: float) -> Tuple[List[int], np.ndarray]:
    """Tukey's fences (IQR method)."""
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1

    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    outlier_mask = (values < lower) | (values > upper)
    outlier_indices = list(np.where(outlier_mask)[0])

    # Score: distance from nearest fence, normalized by IQR
    scores = np.zeros(len(values))
    if iqr > 0:
        below = np.maximum(lower - values, 0) / iqr
        above = np.maximum(values - upper, 0) / iqr
        scores = below + above

    return outlier_indices, scores


def detect_outliers(inp: OutlierInput) -> OutlierResult:
    """
    Detect outliers in a single field.

    Parameters
    ----------
    inp : OutlierInput
        Values and detection method.

    Returns
    -------
    OutlierResult
        Outlier indices, scores, and distribution statistics.
    """
    start_time = time.perf_counter()
    result = OutlierResult(method=inp.method, field_name=inp.field_name)

    if len(inp.values) < 3:
        result.errors.append("Need at least 3 values for outlier detection")
        return result

    values = np.array(inp.values, dtype=np.float64)
    result.n_total = len(values)

    # Distribution stats
    result.mean = round(float(np.mean(values)), 6)
    result.median = round(float(np.median(values)), 6)
    result.std = round(float(np.std(values, ddof=1)), 6)
    result.mad = round(float(np.median(np.abs(values - np.median(values)))), 6)
    result.q1 = round(float(np.percentile(values, 25)), 6)
    result.q3 = round(float(np.percentile(values, 75)), 6)
    result.iqr = round(float(result.q3 - result.q1), 6)
    result.lower_fence = round(float(result.q1 - inp.iqr_factor * result.iqr), 6)
    result.upper_fence = round(float(result.q3 + inp.iqr_factor * result.iqr), 6)

    # Run detection
    if inp.method == "modified_zscore":
        outlier_idx, scores = _modified_zscore(values, inp.threshold)
    elif inp.method == "grubbs":
        outlier_idx, scores = _grubbs_test(values, inp.alpha)
    elif inp.method == "dixon":
        outlier_idx, scores = _dixon_q_test(values, inp.alpha)
    elif inp.method == "tukey":
        outlier_idx, scores = _tukey_fences(values, inp.iqr_factor)
    else:
        result.errors.append(f"Unknown method: {inp.method}")
        return result

    result.outlier_indices = sorted(outlier_idx)
    result.outlier_values = [round(float(values[i]), 6) for i in result.outlier_indices]
    result.scores = [round(float(s), 6) for s in scores]
    result.n_outliers = len(result.outlier_indices)
    result.outlier_rate = round(result.n_outliers / result.n_total, 4) if result.n_total > 0 else 0.0

    return result
