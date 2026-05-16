"""
BOS Pipeline v9.0 — Mass Balance Reconciliation Engine

Ensures conservation of mass across the bioconversion process.
Reconciles measured inputs and outputs to close the mass balance,
accounting for measurement uncertainty and gas-phase losses.

Mass balance equation:
  DM_in = DM_larvae + DM_frass + DM_gas_loss + DM_unaccounted

Reconciliation uses weighted least squares to adjust measurements
within their uncertainty bounds to satisfy conservation laws.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


@dataclass
class MassBalanceInput:
    """Input for mass balance reconciliation."""

    # Measured values (kg DM)
    dm_in: float = 10.0
    dm_larvae: float = 2.5
    dm_frass: float = 6.0
    dm_gas_loss: Optional[float] = None  # If not measured, will be estimated

    # Measurement uncertainties (kg DM, 1 standard deviation)
    sigma_dm_in: float = 0.3
    sigma_dm_larvae: float = 0.15
    sigma_dm_frass: float = 0.3
    sigma_dm_gas: float = 0.5

    # Additional streams (optional)
    dm_wastewater: float = 0.0
    sigma_dm_wastewater: float = 0.1

    # Constraints
    max_adjustment_pct: float = 20.0  # Max allowed adjustment per measurement (%)


@dataclass
class MassBalanceResult:
    """Mass balance reconciliation results."""

    # Original measurements
    original: Dict[str, float] = field(default_factory=dict)

    # Reconciled values
    reconciled: Dict[str, float] = field(default_factory=dict)

    # Adjustments
    adjustments: Dict[str, float] = field(default_factory=dict)
    adjustment_pct: Dict[str, float] = field(default_factory=dict)

    # Balance closure
    raw_balance_error: float = 0.0  # Before reconciliation
    reconciled_balance_error: float = 0.0  # After reconciliation
    closure_pct: float = 0.0  # % closure (100% = perfectly balanced)

    # Gas loss estimate
    estimated_gas_loss: float = 0.0

    # Quality metrics
    chi_squared: float = 0.0  # Goodness of fit
    degrees_of_freedom: int = 0
    chi_squared_acceptable: bool = True

    # Warnings
    warnings: List[str] = field(default_factory=list)
    engine_version: str = ENGINE_VERSION


def reconcile_mass_balance(inp: MassBalanceInput) -> MassBalanceResult:
    """
    Reconcile mass balance using weighted least squares.

    The method adjusts measurements within their uncertainty bounds
    to satisfy the conservation constraint:
      dm_in = dm_larvae + dm_frass + dm_gas + dm_wastewater

    Parameters
    ----------
    inp : MassBalanceInput
        Measured values and uncertainties.

    Returns
    -------
    MassBalanceResult
        Reconciled values and diagnostics.
    """
    result = MassBalanceResult()

    # ── Original measurements ──
    gas_measured = inp.dm_gas_loss is not None
    dm_gas = inp.dm_gas_loss if gas_measured else 0.0

    result.original = {
        "dm_in": inp.dm_in,
        "dm_larvae": inp.dm_larvae,
        "dm_frass": inp.dm_frass,
        "dm_gas_loss": dm_gas,
        "dm_wastewater": inp.dm_wastewater,
    }

    # ── Raw balance error ──
    total_out = inp.dm_larvae + inp.dm_frass + dm_gas + inp.dm_wastewater
    raw_error = inp.dm_in - total_out
    result.raw_balance_error = round(abs(raw_error), 6)

    if inp.dm_in > 0:
        result.closure_pct = round(total_out / inp.dm_in * 100, 2)
    else:
        result.closure_pct = 0.0

    # If gas loss not measured, estimate it as the residual
    if not gas_measured:
        result.estimated_gas_loss = round(max(raw_error, 0), 6)
        dm_gas = result.estimated_gas_loss

    # ── Weighted Least Squares Reconciliation ──
    # Measurement vector y = [dm_in, dm_larvae, dm_frass, dm_gas, dm_wastewater]
    y = np.array([inp.dm_in, inp.dm_larvae, inp.dm_frass, dm_gas, inp.dm_wastewater])
    n = len(y)

    # Variance matrix (diagonal)
    sigmas = np.array(
        [
            inp.sigma_dm_in,
            inp.sigma_dm_larvae,
            inp.sigma_dm_frass,
            inp.sigma_dm_gas,
            inp.sigma_dm_wastewater,
        ]
    )
    W = np.diag(1.0 / (sigmas**2 + 1e-10))

    # Constraint matrix: dm_in - dm_larvae - dm_frass - dm_gas - dm_wastewater = 0
    # A * y_reconciled = 0
    A = np.array([[1.0, -1.0, -1.0, -1.0, -1.0]])
    m = A.shape[0]  # Number of constraints

    # WLS solution: minimize (y_rec - y)? W (y_rec - y) subject to A*y_rec = 0
    # Lagrangian solution:
    # y_rec = y - W?1 A? (A W?1 A?)?1 (A y)
    W_inv = np.diag(sigmas**2 + 1e-10)
    AWAT = A @ W_inv @ A.T
    try:
        AWAT_inv = np.linalg.inv(AWAT)
    except np.linalg.LinAlgError:
        AWAT_inv = np.linalg.pinv(AWAT)

    residual = A @ y  # Should be close to 0 if balanced
    lambda_vec = AWAT_inv @ residual
    adjustment = W_inv @ A.T @ lambda_vec
    y_rec = y - adjustment

    # Ensure non-negative
    y_rec = np.maximum(y_rec, 0)

    # ── Results ──
    labels = ["dm_in", "dm_larvae", "dm_frass", "dm_gas_loss", "dm_wastewater"]

    for i, label in enumerate(labels):
        result.reconciled[label] = round(float(y_rec[i]), 6)
        adj = float(y_rec[i] - y[i])
        result.adjustments[label] = round(adj, 6)
        if y[i] != 0:
            raw_pct = abs(adj) / abs(y[i]) * 100
            result.adjustment_pct[label] = round(min(raw_pct, inp.max_adjustment_pct), 2)
            if raw_pct > inp.max_adjustment_pct:
                result.warnings.append(
                    f"Large adjustment on {label}: {raw_pct:.1f}% "
                    f"(exceeds {inp.max_adjustment_pct}% threshold). Review measurement."
                )
        else:
            result.adjustment_pct[label] = 0.0

    # Check reconciled balance
    rec_total_out = y_rec[1] + y_rec[2] + y_rec[3] + y_rec[4]
    result.reconciled_balance_error = round(abs(float(y_rec[0] - rec_total_out)), 8)
    if y_rec[0] > 0:
        result.closure_pct = round(float(rec_total_out / y_rec[0] * 100), 2)

    # Chi-squared test
    if np.any(sigmas > 0):
        chi_sq = float(np.sum(((y_rec - y) / (sigmas + 1e-10)) ** 2))
        result.chi_squared = round(chi_sq, 4)
        result.degrees_of_freedom = n - m  # Should be n_measurements - n_constraints
        # Compare with chi-squared critical value at 95%
        from scipy import stats

        chi_crit = stats.chi2.ppf(0.95, max(result.degrees_of_freedom, 1))
        result.chi_squared_acceptable = bool(chi_sq <= chi_crit)

    if result.closure_pct < 85:
        result.warnings.append(
            f"Low mass balance closure ({result.closure_pct:.1f}%). "
            "Significant unaccounted losses — check for unmeasured gas emissions or leaks."
        )
    elif result.closure_pct > 105:
        result.warnings.append(
            f"Mass balance exceeds 100% ({result.closure_pct:.1f}%). "
            "Possible measurement bias — recalibrate instruments."
        )

    return result
