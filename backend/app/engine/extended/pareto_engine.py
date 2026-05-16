"""
BOS Pipeline v9.0 — Pareto Multi-Objective Optimization Engine

Finds Pareto-optimal solutions for multi-objective optimization problems:
  - Minimize cost AND maximize SER
  - Minimize GHG AND maximize profit
  - Any combination of 2–4 objectives

Uses NSGA-II-inspired non-dominated sorting with crowding distance.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


@dataclass
class ParetoInput:
    """Input for Pareto optimization."""

    # Pre-evaluated solutions: list of dicts with objective values
    solutions: List[Dict[str, float]]
    objectives: List[str]  # Which keys are objectives
    minimize: List[bool]  # True = minimize, False = maximize (per objective)
    max_pareto_size: int = 50  # Max Pareto front points to return


@dataclass
class ParetoSolution:
    """A single Pareto-optimal solution."""

    values: Dict[str, float]
    rank: int = 0
    crowding_distance: float = 0.0


@dataclass
class ParetoResult:
    """Pareto optimization results."""

    pareto_front: List[ParetoSolution] = field(default_factory=list)
    pareto_size: int = 0
    total_solutions: int = 0
    dominated_count: int = 0
    ideal_point: Dict[str, float] = field(default_factory=dict)
    nadir_point: Dict[str, float] = field(default_factory=dict)
    hypervolume: Optional[float] = None
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def _dominates(a: NDArray, b: NDArray, minimize: List[bool]) -> bool:
    """Check if solution a dominates solution b."""
    better_in_at_least_one = False
    for i, is_min in enumerate(minimize):
        if is_min:
            if a[i] > b[i]:
                return False
            if a[i] < b[i]:
                better_in_at_least_one = True
        else:
            if a[i] < b[i]:
                return False
            if a[i] > b[i]:
                better_in_at_least_one = True
    return better_in_at_least_one


def _non_dominated_sort(obj_matrix: NDArray, minimize: List[bool]) -> List[List[int]]:
    """Sort solutions into non-domination fronts (NSGA-II style)."""
    n = obj_matrix.shape[0]
    domination_count = np.zeros(n, dtype=int)
    dominated_by: List[List[int]] = [[] for _ in range(n)]
    fronts: List[List[int]] = [[]]

    for i in range(n):
        for j in range(i + 1, n):
            if _dominates(obj_matrix[i], obj_matrix[j], minimize):
                dominated_by[i].append(j)
                domination_count[j] += 1
            elif _dominates(obj_matrix[j], obj_matrix[i], minimize):
                dominated_by[j].append(i)
                domination_count[i] += 1

    # First front
    for i in range(n):
        if domination_count[i] == 0:
            fronts[0].append(i)

    # Subsequent fronts
    current_front = 0
    while fronts[current_front]:
        next_front: List[int] = []
        for i in fronts[current_front]:
            for j in dominated_by[i]:
                domination_count[j] -= 1
                if domination_count[j] == 0:
                    next_front.append(j)
        current_front += 1
        if next_front:
            fronts.append(next_front)
        else:
            break

    return fronts


def _crowding_distance(obj_matrix: NDArray, front_indices: List[int]) -> NDArray:
    """Compute crowding distance for solutions in a front."""
    n = len(front_indices)
    m = obj_matrix.shape[1]

    if n <= 2:
        return np.full(n, float("inf"))

    distances = np.zeros(n)
    front_objs = obj_matrix[front_indices]

    for j in range(m):
        sorted_idx = np.argsort(front_objs[:, j])
        distances[sorted_idx[0]] = float("inf")
        distances[sorted_idx[-1]] = float("inf")

        obj_range = front_objs[sorted_idx[-1], j] - front_objs[sorted_idx[0], j]
        if obj_range < 1e-10:
            continue

        for i in range(1, n - 1):
            distances[sorted_idx[i]] += (
                front_objs[sorted_idx[i + 1], j] - front_objs[sorted_idx[i - 1], j]
            ) / obj_range

    return distances


def find_pareto_front(inp: ParetoInput) -> ParetoResult:
    """
    Find Pareto-optimal solutions.

    Parameters
    ----------
    inp : ParetoInput
        Solutions with objective values.

    Returns
    -------
    ParetoResult
        Pareto front with rankings and crowding distances.
    """
    start_time = time.perf_counter()
    result = ParetoResult(total_solutions=len(inp.solutions))

    if not inp.solutions:
        result.errors.append("No solutions provided")
        return result

    if len(inp.objectives) != len(inp.minimize):
        result.errors.append("objectives and minimize lists must have same length")
        return result

    # Build objective matrix
    obj_matrix = np.array([[sol.get(obj, 0.0) for obj in inp.objectives] for sol in inp.solutions], dtype=np.float64)

    n, m = obj_matrix.shape

    # Non-dominated sorting
    fronts = _non_dominated_sort(obj_matrix, inp.minimize)

    # Extract Pareto front (rank 0)
    pareto_indices = fronts[0] if fronts else []
    result.pareto_size = len(pareto_indices)
    result.dominated_count = n - result.pareto_size

    # Crowding distance
    if pareto_indices:
        distances = _crowding_distance(obj_matrix, pareto_indices)

        # Sort by crowding distance and limit size
        sorted_by_crowd = sorted(
            zip(pareto_indices, distances),
            key=lambda x: -x[1],
        )

        for idx, cd in sorted_by_crowd[: inp.max_pareto_size]:
            result.pareto_front.append(
                ParetoSolution(
                    values=inp.solutions[idx],
                    rank=0,
                    crowding_distance=round(float(cd), 6) if not np.isinf(cd) else 1e6,
                )
            )

    # Ideal and nadir points
    if pareto_indices:
        pareto_objs = obj_matrix[pareto_indices]
        for j, obj_name in enumerate(inp.objectives):
            if inp.minimize[j]:
                result.ideal_point[obj_name] = round(float(pareto_objs[:, j].min()), 6)
                result.nadir_point[obj_name] = round(float(pareto_objs[:, j].max()), 6)
            else:
                result.ideal_point[obj_name] = round(float(pareto_objs[:, j].max()), 6)
                result.nadir_point[obj_name] = round(float(pareto_objs[:, j].min()), 6)

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
