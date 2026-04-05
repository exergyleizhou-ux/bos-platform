"""
BOS Pipeline v9.0 �� Anomaly Detection Engine

Detects anomalous batches using multiple methods:
  1. Isolation Forest     �� unsupervised, non-parametric
  2. Z-score             �� statistical, univariate
  3. IQR (Interquartile) �� robust to outliers
  4. Mahalanobis distance �� multivariate, accounts for correlations

Anomaly scores are normalized to [0, 1] where 1 = most anomalous.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Data Classes
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


@dataclass
class AnomalyInput:
    """Input for anomaly detection."""

    data: List[Dict[str, float]] = field(default_factory=list)  # List of feature dicts
    values: Optional[List[float]] = None  # Legacy single-series input
    features: Optional[List[str]] = None  # Which keys to use; None = all numeric
    method: str = "isolation_forest"  # isolation_forest, zscore, iqr, mahalanobis
    contamination: float = 0.05  # Expected fraction of anomalies (for IF)
    threshold: float = 3.0  # Z-score / Mahalanobis threshold
    zscore_threshold: Optional[float] = None  # Legacy alias for threshold
    n_trees: int = 100  # Isolation Forest trees
    seed: Optional[int] = None


@dataclass
class AnomalyResult:
    """Anomaly detection results."""

    scores: List[float] = field(default_factory=list)  # Anomaly scores [0, 1]
    labels: List[int] = field(default_factory=list)  # 1 = anomaly, 0 = normal
    anomalies: List[Dict[str, float | int]] = field(default_factory=list)  # Legacy anomaly detail list
    anomaly_indices: List[int] = field(default_factory=list)
    anomaly_count: int = 0
    anomaly_rate: float = 0.0
    mean: Optional[float] = None  # Legacy descriptive statistics
    std: Optional[float] = None
    median: Optional[float] = None
    feature_contributions: Optional[List[Dict[str, float]]] = None
    threshold_used: float = 0.0
    method: str = ""
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Isolation Forest (simplified pure-numpy implementation)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


class _IsolationTree:
    """Single isolation tree node."""

    def __init__(self, left=None, right=None, split_feature=None, split_value=None, size=0, depth=0):
        self.left = left
        self.right = right
        self.split_feature = split_feature
        self.split_value = split_value
        self.size = size
        self.depth = depth


def _build_tree(X: NDArray, rng: np.random.Generator, max_depth: int, current_depth: int = 0) -> _IsolationTree:
    """Recursively build an isolation tree."""
    n, d = X.shape

    if n <= 1 or current_depth >= max_depth:
        return _IsolationTree(size=n, depth=current_depth)

    feature = rng.integers(0, d)
    col = X[:, feature]
    min_val, max_val = col.min(), col.max()

    if min_val == max_val:
        return _IsolationTree(size=n, depth=current_depth)

    split = rng.uniform(min_val, max_val)
    left_mask = col < split
    right_mask = ~left_mask

    if left_mask.sum() == 0 or right_mask.sum() == 0:
        return _IsolationTree(size=n, depth=current_depth)

    return _IsolationTree(
        left=_build_tree(X[left_mask], rng, max_depth, current_depth + 1),
        right=_build_tree(X[right_mask], rng, max_depth, current_depth + 1),
        split_feature=int(feature),
        split_value=float(split),
        size=n,
        depth=current_depth,
    )


def _path_length(x: NDArray, tree: _IsolationTree) -> float:
    """Compute path length for a single observation."""
    if tree.left is None or tree.right is None:
        # External node �� estimate using average path length of BST
        return tree.depth + _c(tree.size)

    if x[tree.split_feature] < tree.split_value:
        return _path_length(x, tree.left)
    else:
        return _path_length(x, tree.right)


def _c(n: int) -> float:
    """Average path length of unsuccessful search in BST."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2.0 * (np.log(n - 1) + 0.5772156649) - 2.0 * (n - 1) / n


def _isolation_forest(X: NDArray, n_trees: int, contamination: float, rng: np.random.Generator) -> Tuple[NDArray, NDArray]:
    """Run Isolation Forest and return (scores, labels)."""
    n, d = X.shape
    max_depth = int(np.ceil(np.log2(max(n, 2))))
    sample_size = min(256, n)

    trees = []
    for _ in range(n_trees):
        idx = rng.choice(n, size=sample_size, replace=sample_size > n)
        tree = _build_tree(X[idx], rng, max_depth)
        trees.append(tree)

    # Compute anomaly scores
    avg_path_lengths = np.zeros(n)
    for i in range(n):
        paths = [_path_length(X[i], tree) for tree in trees]
        avg_path_lengths[i] = np.mean(paths)

    c_n = _c(sample_size)
    if c_n == 0:
        scores = np.zeros(n)
    else:
        scores = 2.0 ** (-avg_path_lengths / c_n)

    # Normalize to [0, 1]
    s_min, s_max = scores.min(), scores.max()
    if s_max > s_min:
        scores = (scores - s_min) / (s_max - s_min)

    # Threshold by contamination quantile
    threshold = float(np.quantile(scores, 1 - contamination))
    labels = (scores >= threshold).astype(int)

    return scores, labels


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Z-Score Method
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _zscore_detect(X: NDArray, threshold: float) -> Tuple[NDArray, NDArray]:
    """Detect anomalies using max absolute Z-score per row."""
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-10
    z = np.abs((X - mean) / std)
    max_z = z.max(axis=1)

    # Normalize scores
    s_max = max_z.max()
    scores = max_z / s_max if s_max > 0 else max_z
    labels = (max_z > threshold).astype(int)

    return scores, labels


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# IQR Method
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _modified_zscore_detect(X: NDArray, threshold: float) -> Tuple[NDArray, NDArray]:
    """Detect anomalies using MAD-based modified z-score."""
    median = np.median(X, axis=0)
    mad = np.median(np.abs(X - median), axis=0) + 1e-10
    mod_z = 0.6745 * (X - median) / mad
    max_mod_z = np.abs(mod_z).max(axis=1)

    s_max = max_mod_z.max()
    scores = max_mod_z / s_max if s_max > 0 else max_mod_z
    labels = (max_mod_z > threshold).astype(int)

    return scores, labels


def _iqr_detect(X: NDArray, factor: float = 1.5) -> Tuple[NDArray, NDArray]:
    """Detect anomalies using IQR method per feature."""
    q1 = np.percentile(X, 25, axis=0)
    q3 = np.percentile(X, 75, axis=0)
    iqr = q3 - q1 + 1e-10

    lower = q1 - factor * iqr
    upper = q3 + factor * iqr

    # Count how many features are out of bounds per sample
    out_of_bounds = ((X < lower) | (X > upper)).sum(axis=1)
    scores = out_of_bounds / X.shape[1]
    labels = (out_of_bounds > 0).astype(int)

    return scores.astype(float), labels


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Mahalanobis Distance
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def _mahalanobis_detect(X: NDArray, threshold: float) -> Tuple[NDArray, NDArray]:
    """Detect anomalies using Mahalanobis distance."""
    mean = X.mean(axis=0)
    cov = np.cov(X, rowvar=False)

    # Regularize covariance
    cov += 1e-6 * np.eye(cov.shape[0])

    try:
        cov_inv = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        cov_inv = np.linalg.pinv(cov)

    diff = X - mean
    md = np.sqrt(np.sum(diff @ cov_inv * diff, axis=1))

    # Normalize
    md_max = md.max()
    scores = md / md_max if md_max > 0 else md
    labels = (md > threshold).astype(int)

    return scores, labels


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Main Detection Function
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def detect_anomalies(inp: AnomalyInput) -> AnomalyResult:
    """
    Detect anomalous batches in the dataset.

    Parameters
    ----------
    inp : AnomalyInput
        Data and detection method parameters.

    Returns
    -------
    AnomalyResult
        Anomaly scores, labels, and summary statistics.
    """
    start_time = time.perf_counter()
    result = AnomalyResult(method=inp.method)

    data_rows = inp.data
    if not data_rows and inp.values is not None:
        data_rows = [{"value": float(v)} for v in inp.values]

    if len(data_rows) < 3:
        result.errors.append("Need at least 3 data points for anomaly detection")
        return result

    # Extract feature matrix
    if inp.features:
        feature_names = inp.features
    else:
        feature_names = sorted(
            k for k in data_rows[0].keys()
            if isinstance(data_rows[0].get(k), (int, float))
        )

    if not feature_names:
        result.errors.append("No numeric features found")
        return result

    X = np.array([
        [row.get(f, 0.0) for f in feature_names]
        for row in data_rows
    ], dtype=np.float64)

    # Handle NaN / Inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    rng = np.random.default_rng(inp.seed)

    # Run detection
    threshold = inp.zscore_threshold if inp.zscore_threshold is not None else inp.threshold
    if inp.method == "isolation_forest":
        scores, labels = _isolation_forest(X, inp.n_trees, inp.contamination, rng)
        result.threshold_used = float(np.quantile(scores, 1 - inp.contamination))
    elif inp.method == "zscore":
        scores, labels = _zscore_detect(X, threshold)
        result.threshold_used = threshold
    elif inp.method == "modified_zscore":
        scores, labels = _modified_zscore_detect(X, threshold)
        result.threshold_used = threshold
    elif inp.method == "iqr":
        scores, labels = _iqr_detect(X, factor=threshold)
        result.threshold_used = threshold
    elif inp.method == "mahalanobis":
        scores, labels = _mahalanobis_detect(X, threshold)
        result.threshold_used = threshold
    else:
        result.errors.append(f"Unknown method: {inp.method}")
        return result

    result.scores = [round(float(s), 6) for s in scores]
    result.labels = [int(l) for l in labels]
    result.anomaly_indices = [i for i, l in enumerate(labels) if l == 1]
    result.anomaly_count = int(labels.sum())
    result.anomaly_rate = round(result.anomaly_count / len(labels), 4)
    primary_feature = X[:, 0]
    result.mean = round(float(np.mean(primary_feature)), 6)
    result.std = round(float(np.std(primary_feature)), 6)
    result.median = round(float(np.median(primary_feature)), 6)
    result.anomalies = [
        {
            "index": i,
            "value": round(float(primary_feature[i]), 6),
            "score": round(float(scores[i]), 6),
        }
        for i in result.anomaly_indices
    ]

    # Feature contributions (for anomalous points)
    if result.anomaly_count > 0 and inp.method in ("zscore", "iqr"):
        mean = X.mean(axis=0)
        std = X.std(axis=0) + 1e-10
        z_all = np.abs((X - mean) / std)

        contributions = []
        for i in result.anomaly_indices:
            contrib = {feature_names[j]: round(float(z_all[i, j]), 4) for j in range(len(feature_names))}
            contributions.append(contrib)
        result.feature_contributions = contributions

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return result
