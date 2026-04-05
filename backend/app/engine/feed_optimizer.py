"""
BOS Pipeline v9.0 �� Feed Optimizer Engine

Solves feed mix optimization using Linear Programming (LP):
  - Minimize cost of substrate blend
  - Subject to nutritional constraints (protein, fat, fiber, moisture, energy)
  - Support min/max bounds per ingredient

Also supports multi-objective mode:
  - Minimize cost AND maximize predicted SER
  - Pareto front generation (delegated to pareto_engine)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog

ENGINE_VERSION = "9.0.0"


@dataclass
class Ingredient:
    """A single feed ingredient with nutritional profile."""

    name: str
    cost_per_kg: float  # $/kg
    protein: float  # % DM
    fat: float  # % DM
    fiber: float  # % DM
    moisture: float  # %
    energy: float  # MJ/kg DM
    ash: float  # % DM
    availability_kg: Optional[float] = None  # Max available (kg)
    min_fraction: float = 0.0  # Minimum fraction in mix [0, 1]
    max_fraction: float = 1.0  # Maximum fraction in mix [0, 1]


@dataclass
class NutrientConstraint:
    """Min/max constraint for a nutrient."""

    nutrient: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class FeedOptimizerInput:
    """Input for feed mix optimization."""

    ingredients: List[Ingredient]
    constraints: List[NutrientConstraint] = field(default_factory=lambda: [
        NutrientConstraint("protein", min_value=15.0, max_value=35.0),
        NutrientConstraint("fat", min_value=3.0, max_value=20.0),
        NutrientConstraint("fiber", max_value=25.0),
        NutrientConstraint("moisture", min_value=55.0, max_value=80.0),
        NutrientConstraint("energy", min_value=14.0),
    ])
    total_mass_kg: float = 1000.0  # Total mix mass needed
    objective: str = "min_cost"  # "min_cost" or "max_energy"


@dataclass
class FeedOptimizerResult:
    """Feed optimization results."""

    # Solution
    fractions: Dict[str, float] = field(default_factory=dict)  # Ingredient �� fraction [0,1]
    amounts_kg: Dict[str, float] = field(default_factory=dict)  # Ingredient �� kg
    total_cost: float = 0.0  # $/total_mass
    cost_per_kg: float = 0.0

    # Resulting nutritional profile
    mix_profile: Dict[str, float] = field(default_factory=dict)

    # Status
    feasible: bool = False
    solver_status: str = ""
    message: str = ""

    # Sensitivity (shadow prices)
    shadow_prices: Dict[str, float] = field(default_factory=dict)

    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


def optimize_feed_mix(inp: FeedOptimizerInput) -> FeedOptimizerResult:
    """
    Solve the feed mix optimization problem.

    Parameters
    ----------
    inp : FeedOptimizerInput
        Ingredients, constraints, and objective.

    Returns
    -------
    FeedOptimizerResult
        Optimal mix fractions, cost, and nutritional profile.
    """
    start_time = time.perf_counter()
    result = FeedOptimizerResult()

    n = len(inp.ingredients)
    if n == 0:
        result.errors.append("No ingredients provided")
        return result

    # ���� Decision variables: x_i = fraction of ingredient i in mix ����

    # Objective: minimize cost (c^T x)
    c = np.array([ing.cost_per_kg for ing in inp.ingredients])
    if inp.objective == "max_energy":
        # Maximize energy �� minimize negative energy
        c = np.array([-ing.energy for ing in inp.ingredients])

    # ���� Inequality constraints: A_ub @ x <= b_ub ����
    A_ub_rows: List[List[float]] = []
    b_ub_values: List[float] = []

    nutrient_map = {
        "protein": [ing.protein for ing in inp.ingredients],
        "fat": [ing.fat for ing in inp.ingredients],
        "fiber": [ing.fiber for ing in inp.ingredients],
        "moisture": [ing.moisture for ing in inp.ingredients],
        "energy": [ing.energy for ing in inp.ingredients],
        "ash": [ing.ash for ing in inp.ingredients],
    }

    constraint_names: List[str] = []

    for con in inp.constraints:
        values = nutrient_map.get(con.nutrient)
        if values is None:
            continue

        if con.max_value is not None:
            # sum(value_i * x_i) <= max_value
            A_ub_rows.append(values)
            b_ub_values.append(con.max_value)
            constraint_names.append(f"{con.nutrient}_max")

        if con.min_value is not None:
            # -sum(value_i * x_i) <= -min_value  (i.e., sum >= min)
            A_ub_rows.append([-v for v in values])
            b_ub_values.append(-con.min_value)
            constraint_names.append(f"{con.nutrient}_min")

    A_ub = np.array(A_ub_rows) if A_ub_rows else None
    b_ub = np.array(b_ub_values) if b_ub_values else None

    # ���� Equality constraint: fractions sum to 1 ����
    A_eq = np.ones((1, n))
    b_eq = np.array([1.0])

    # ���� Bounds: per-ingredient min/max fraction ����
    bounds = [(ing.min_fraction, ing.max_fraction) for ing in inp.ingredients]

    # ���� Solve LP ����
    try:
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )

        if res.success:
            result.feasible = True
            result.solver_status = "optimal"
            result.message = "Optimal solution found"

            x = res.x

            for i, ing in enumerate(inp.ingredients):
                frac = round(float(x[i]), 6)
                result.fractions[ing.name] = frac
                result.amounts_kg[ing.name] = round(frac * inp.total_mass_kg, 2)

            # Total cost
            cost_vec = np.array([ing.cost_per_kg for ing in inp.ingredients])
            result.total_cost = round(float(cost_vec @ x * inp.total_mass_kg), 2)
            result.cost_per_kg = round(float(cost_vec @ x), 4)

            # Resulting nutritional profile
            for nutrient, values in nutrient_map.items():
                val_arr = np.array(values)
                result.mix_profile[nutrient] = round(float(val_arr @ x), 4)

            # Shadow prices (dual values for inequality constraints)
            if hasattr(res, "ineqlin") and res.ineqlin is not None:
                marginals = getattr(res.ineqlin, "marginals", None)
                if marginals is not None:
                    for i, name in enumerate(constraint_names):
                        if i < len(marginals):
                            result.shadow_prices[name] = round(float(marginals[i]), 6)

        else:
            result.feasible = False
            result.solver_status = str(res.status)
            result.message = res.message if hasattr(res, "message") else "Optimization failed"

    except Exception as e:
        result.errors.append(f"Solver error: {str(e)}")
        result.feasible = False

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Default Ingredient Library
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

DEFAULT_INGREDIENTS = [
    Ingredient("Wheat bran", 0.25, 16.0, 4.0, 12.0, 12.0, 17.5, 6.0),
    Ingredient("Soybean meal", 0.45, 48.0, 1.5, 6.0, 12.0, 19.5, 7.0),
    Ingredient("Corn meal", 0.20, 9.0, 4.0, 2.5, 14.0, 18.0, 1.5),
    Ingredient("Brewery grain", 0.10, 26.0, 7.0, 17.0, 75.0, 16.0, 4.0),
    Ingredient("Fruit/veg waste", 0.05, 8.0, 2.0, 10.0, 85.0, 14.0, 8.0),
    Ingredient("Fish offal", 0.35, 55.0, 15.0, 0.5, 65.0, 22.0, 12.0),
    Ingredient("Poultry manure", 0.02, 25.0, 2.5, 15.0, 70.0, 13.0, 20.0),
    Ingredient("Rice bran", 0.18, 13.0, 18.0, 8.0, 10.0, 20.0, 10.0),
]
