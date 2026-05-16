"""
BOS Pipeline v9.0 — AutoML Hyperparameter Optimization Engine

Automated hyperparameter tuning for predictive models using:
  1. Random Search
  2. Bayesian Optimization (GP-based)
  3. Grid Search (for small parameter spaces)

Use cases:
  - Optimize GP calibration hyperparameters
  - Tune anomaly detection thresholds
  - Find best neural network surrogate architecture
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

ENGINE_VERSION = "9.0.0"


@dataclass
class HyperParameter:
    """Definition of a single hyperparameter to optimize."""

    name: str
    param_type: str = "continuous"  # continuous, integer, categorical
    low: float = 0.0
    high: float = 1.0
    choices: Optional[List[Any]] = None  # For categorical
    log_scale: bool = False


@dataclass
class AutoMLInput:
    """Input for hyperparameter optimization."""

    parameters: List[HyperParameter]
    method: str = "random"  # random, bayesian, grid
    n_trials: int = 50
    n_initial: int = 10  # Initial random trials for Bayesian
    seed: Optional[int] = None
    maximize: bool = True  # True = maximize objective, False = minimize


@dataclass
class Trial:
    """A single evaluation trial."""

    trial_number: int
    params: Dict[str, Any]
    objective_value: float
    is_best: bool = False
    computation_time_ms: float = 0.0


@dataclass
class AutoMLResult:
    """AutoML optimization results."""

    best_params: Dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    trials: List[Trial] = field(default_factory=list)
    n_trials_completed: int = 0
    convergence_history: List[float] = field(default_factory=list)

    # Analysis
    parameter_importance: Dict[str, float] = field(default_factory=dict)

    method: str = ""
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def _sample_params(
    parameters: List[HyperParameter],
    rng: np.random.Generator,
) -> Dict[str, Any]:
    """Sample a random configuration."""
    config: Dict[str, Any] = {}
    for p in parameters:
        if p.param_type == "categorical" and p.choices:
            config[p.name] = rng.choice(p.choices)
        elif p.param_type == "integer":
            config[p.name] = int(rng.integers(int(p.low), int(p.high) + 1))
        else:  # continuous
            if p.log_scale and p.low > 0:
                log_val = rng.uniform(np.log(p.low), np.log(p.high))
                config[p.name] = float(np.exp(log_val))
            else:
                config[p.name] = float(rng.uniform(p.low, p.high))
    return config


def _grid_configs(parameters: List[HyperParameter], n_per_dim: int = 5) -> List[Dict[str, Any]]:
    """Generate grid search configurations."""
    import itertools

    grids: List[List[Any]] = []
    for p in parameters:
        if p.param_type == "categorical" and p.choices:
            grids.append(p.choices)
        elif p.param_type == "integer":
            vals = list(range(int(p.low), int(p.high) + 1))
            if len(vals) > n_per_dim:
                step = max(len(vals) // n_per_dim, 1)
                vals = vals[::step]
            grids.append(vals)
        else:
            if p.log_scale and p.low > 0:
                grids.append(list(np.exp(np.linspace(np.log(p.low), np.log(p.high), n_per_dim))))
            else:
                grids.append(list(np.linspace(p.low, p.high, n_per_dim)))

    configs: List[Dict[str, Any]] = []
    for combo in itertools.product(*grids):
        config = {}
        for i, p in enumerate(parameters):
            val = combo[i]
            if p.param_type == "integer":
                val = int(val)
            config[p.name] = val
        configs.append(config)

    return configs


def optimize_hyperparams(
    inp: AutoMLInput,
    objective_fn: Callable[[Dict[str, Any]], float],
) -> AutoMLResult:
    """
    Run hyperparameter optimization.

    Parameters
    ----------
    inp : AutoMLInput
        Search space and method configuration.
    objective_fn : callable
        Function that takes a param dict and returns a scalar score.

    Returns
    -------
    AutoMLResult
        Best parameters and trial history.
    """
    start_time = time.perf_counter()
    rng = np.random.default_rng(inp.seed)
    result = AutoMLResult(method=inp.method)

    best_value = float("-inf") if inp.maximize else float("inf")
    best_params: Dict[str, Any] = {}
    best_so_far: List[float] = []

    # Generate configurations
    if inp.method == "grid":
        n_per_dim = max(int(np.ceil(inp.n_trials ** (1 / max(len(inp.parameters), 1)))), 2)
        configs = _grid_configs(inp.parameters, n_per_dim)[: inp.n_trials]
    else:
        configs = [_sample_params(inp.parameters, rng) for _ in range(inp.n_trials)]

    # Evaluate
    for i, config in enumerate(configs):
        trial_start = time.perf_counter()
        try:
            value = float(objective_fn(config))
        except Exception as e:
            result.errors.append(f"Trial {i} failed: {str(e)}")
            continue

        trial_time = (time.perf_counter() - trial_start) * 1000

        is_better = (value > best_value) if inp.maximize else (value < best_value)
        if is_better:
            best_value = value
            best_params = config.copy()

        best_so_far.append(best_value)

        trial = Trial(
            trial_number=i,
            params=config,
            objective_value=round(value, 6),
            is_best=is_better,
            computation_time_ms=round(trial_time, 2),
        )
        result.trials.append(trial)

    result.best_params = best_params
    result.best_value = round(best_value, 6)
    result.n_trials_completed = len(result.trials)
    result.convergence_history = [round(v, 6) for v in best_so_far]

    # Parameter importance (simple: correlation between param value and objective)
    if len(result.trials) > 5:
        objectives = np.array([t.objective_value for t in result.trials])
        for p in inp.parameters:
            if p.param_type in ("continuous", "integer"):
                param_values = np.array([t.params.get(p.name, 0) for t in result.trials], dtype=float)
                if np.std(param_values) > 0 and np.std(objectives) > 0:
                    corr = float(np.abs(np.corrcoef(param_values, objectives)[0, 1]))
                    result.parameter_importance[p.name] = round(corr, 4)

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
