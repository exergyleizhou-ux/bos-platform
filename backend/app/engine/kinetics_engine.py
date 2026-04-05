"""
BOS Pipeline v9.0 �� Growth Kinetics Engine

Models insect larval growth using standard microbial kinetics:
  1. Monod model      �� substrate-limited growth
  2. Logistic model   �� density-dependent growth with carrying capacity
  3. Gompertz model   �� asymmetric sigmoid growth curve
  4. Baranyi-Roberts  �� with lag phase

Also computes growth performance indices:
  - SGR (Specific Growth Rate)
  - FCR (Feed Conversion Ratio)
  - DGC (Daily Growth Coefficient)
  - TGC (Thermal Growth Coefficient)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import curve_fit

ENGINE_VERSION = "9.0.0"


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Growth Models
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def monod_growth(t: np.ndarray, B0: float, S0: float, mu_max: float, Ks: float, Y: float) -> np.ndarray:
    """
    Monod growth model (numerical integration).

    dB/dt = mu_max * S/(Ks + S) * B
    dS/dt = -1/Y * mu_max * S/(Ks + S) * B
    """
    def odes(t_val, state):
        B, S = state
        mu = mu_max * max(S, 0) / (Ks + max(S, 0))
        dBdt = mu * B
        dSdt = -mu * B / Y
        return [dBdt, dSdt]

    sol = solve_ivp(odes, [t[0], t[-1]], [B0, S0], t_eval=t, method="RK45", max_step=0.5)
    return sol.y[0]  # Return biomass trajectory


def logistic_growth(t: np.ndarray, B0: float, K: float, r: float) -> np.ndarray:
    """Logistic growth model: dB/dt = r * B * (1 - B/K)."""
    return K / (1 + ((K - B0) / B0) * np.exp(-r * t))


def gompertz_growth(t: np.ndarray, A: float, mu_m: float, lam: float) -> np.ndarray:
    """
    Gompertz growth model (reparameterized).

    A   : asymptotic maximum (ln(B_max/B_0))
    mu_m: maximum specific growth rate
    lam : lag time
    """
    return np.exp(A * np.exp(-np.exp(mu_m * np.e / A * (lam - t) + 1)))


def baranyi_growth(t: np.ndarray, B0: float, B_max: float, mu_max: float, lam: float) -> np.ndarray:
    """
    Baranyi-Roberts model with explicit lag phase.

    Accurate for modeling actual lag �� exponential �� stationary transition.
    """
    q0 = 1.0 / (np.exp(mu_max * lam) - 1)  # Initial physiological state
    A_t = t + (1 / mu_max) * np.log(np.exp(-mu_max * t) + q0 * np.exp(-mu_max * t) * (np.exp(mu_max * t) - 1) / (1 + q0))

    # Simplified: use approximation
    alpha = mu_max * t + np.log((np.exp(-mu_max * t) + q0) / (1 + q0))
    B = B0 * np.exp(alpha) / (1 - (B0 / B_max) * (1 - np.exp(alpha)))
    return np.clip(B, B0, B_max * 1.01)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Data Classes
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


@dataclass
class KineticsInput:
    """Input for growth kinetics analysis."""

    time_points: List[float]  # Time (days or hours)
    biomass_data: List[float]  # Biomass measurements (g or kg)
    substrate_data: Optional[List[float]] = None  # Substrate measurements (g or kg)
    temperature_data: Optional[List[float]] = None  # Temperature (��C)
    model: str = "logistic"  # monod, logistic, gompertz, baranyi
    time_unit: str = "days"


@dataclass
class KineticsResult:
    """Growth kinetics analysis results."""

    # Fitted parameters
    parameters: Dict[str, float] = field(default_factory=dict)
    parameter_errors: Dict[str, float] = field(default_factory=dict)

    # Fitted curve
    fitted_time: List[float] = field(default_factory=list)
    fitted_biomass: List[float] = field(default_factory=list)

    # Performance indices
    sgr: float = 0.0  # Specific Growth Rate (% / day)
    fcr: float = 0.0  # Feed Conversion Ratio (kg feed / kg gain)
    dgc: float = 0.0  # Daily Growth Coefficient
    tgc: float = 0.0  # Thermal Growth Coefficient

    # Model fit quality
    r_squared: float = 0.0
    rmse: float = 0.0
    aic: float = 0.0  # Akaike Information Criterion

    # Growth phases
    lag_phase_end: Optional[float] = None  # Time when lag phase ends
    exponential_phase_end: Optional[float] = None  # Time when exponential phase ends
    max_growth_rate: float = 0.0  # Maximum observed growth rate

    model_name: str = ""
    engine_version: str = ENGINE_VERSION
    errors: List[str] = field(default_factory=list)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Fitting
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def fit_growth_kinetics(inp: KineticsInput) -> KineticsResult:
    """
    Fit a growth model to biomass time-series data.

    Parameters
    ----------
    inp : KineticsInput
        Time points and biomass measurements.

    Returns
    -------
    KineticsResult
        Fitted parameters, curve, and performance indices.
    """
    result = KineticsResult(model_name=inp.model)

    if len(inp.time_points) < 3:
        result.errors.append("Need at least 3 time points for curve fitting")
        return result

    t = np.array(inp.time_points, dtype=np.float64)
    B = np.array(inp.biomass_data, dtype=np.float64)

    if len(t) != len(B):
        result.errors.append("time_points and biomass_data must have same length")
        return result

    B0 = float(B[0])
    B_max = float(B.max()) * 1.1

    # Choose model and fit
    try:
        if inp.model == "logistic":
            popt, pcov = curve_fit(
                logistic_growth, t, B,
                p0=[B0, B_max, 0.2],
                bounds=([0, B0, 0], [B_max * 2, B_max * 5, 10]),
                maxfev=5000,
            )
            result.parameters = {"B0": round(popt[0], 6), "K": round(popt[1], 6), "r": round(popt[2], 6)}
            B_fitted = logistic_growth(t, *popt)
            n_params = 3

        elif inp.model == "gompertz":
            A_guess = np.log(B_max / max(B0, 0.01))
            popt, pcov = curve_fit(
                gompertz_growth, t, B / max(B0, 0.01),  # Normalize
                p0=[A_guess, 0.3, 1.0],
                bounds=([0, 0, 0], [10, 5, t.max()]),
                maxfev=5000,
            )
            result.parameters = {"A": round(popt[0], 6), "mu_m": round(popt[1], 6), "lambda": round(popt[2], 6)}
            B_fitted = gompertz_growth(t, *popt) * max(B0, 0.01)
            n_params = 3

        elif inp.model == "baranyi":
            popt, pcov = curve_fit(
                baranyi_growth, t, B,
                p0=[B0, B_max, 0.2, 1.0],
                bounds=([B0 * 0.5, B0, 0, 0], [B0 * 2, B_max * 5, 5, t.max() / 2]),
                maxfev=5000,
            )
            result.parameters = {
                "B0": round(popt[0], 6), "B_max": round(popt[1], 6),
                "mu_max": round(popt[2], 6), "lambda": round(popt[3], 6),
            }
            B_fitted = baranyi_growth(t, *popt)
            result.lag_phase_end = round(float(popt[3]), 2)
            n_params = 4

        else:  # monod (default to logistic if no substrate data)
            popt, pcov = curve_fit(
                logistic_growth, t, B,
                p0=[B0, B_max, 0.2],
                bounds=([0, B0, 0], [B_max * 2, B_max * 5, 10]),
                maxfev=5000,
            )
            result.parameters = {"B0": round(popt[0], 6), "K": round(popt[1], 6), "r": round(popt[2], 6)}
            B_fitted = logistic_growth(t, *popt)
            n_params = 3

        # Parameter standard errors
        perr = np.sqrt(np.diag(pcov))
        for i, key in enumerate(result.parameters.keys()):
            if i < len(perr):
                result.parameter_errors[key] = round(float(perr[i]), 6)

    except Exception as e:
        result.errors.append(f"Curve fitting failed: {str(e)}")
        return result

    # ���� Fitted curve (high-resolution) ����
    t_fine = np.linspace(t[0], t[-1], 200)
    if inp.model == "logistic" or inp.model == "monod":
        B_fine = logistic_growth(t_fine, *popt)
    elif inp.model == "gompertz":
        B_fine = gompertz_growth(t_fine, *popt) * max(B0, 0.01)
    elif inp.model == "baranyi":
        B_fine = baranyi_growth(t_fine, *popt)
    else:
        B_fine = logistic_growth(t_fine, *popt)

    result.fitted_time = [round(float(v), 4) for v in t_fine]
    result.fitted_biomass = [round(float(v), 6) for v in B_fine]

    # ���� Model quality ����
    residuals = B - B_fitted
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((B - np.mean(B)) ** 2)
    n = len(B)

    result.r_squared = round(float(1 - ss_res / max(ss_tot, 1e-10)), 6)
    result.rmse = round(float(np.sqrt(np.mean(residuals ** 2))), 6)

    # AIC
    if n > n_params + 1:
        result.aic = round(float(n * np.log(ss_res / n) + 2 * n_params), 4)

    # ���� Performance Indices ����
    B_final = float(B[-1])
    t_total = float(t[-1] - t[0])

    if B0 > 0 and t_total > 0:
        # SGR: Specific Growth Rate (% per time unit)
        result.sgr = round(float((np.log(B_final) - np.log(B0)) / t_total * 100), 4)

        # DGC: Daily Growth Coefficient
        if inp.time_unit == "days":
            result.dgc = round(float((B_final ** (1 / 3) - B0 ** (1 / 3)) / t_total * 100), 4)

    # FCR: Feed Conversion Ratio
    if inp.substrate_data and len(inp.substrate_data) >= 2:
        S0 = inp.substrate_data[0]
        S_final = inp.substrate_data[-1]
        feed_consumed = S0 - S_final
        biomass_gain = B_final - B0
        if biomass_gain > 0:
            result.fcr = round(float(feed_consumed / biomass_gain), 4)

    # TGC: Thermal Growth Coefficient
    if inp.temperature_data and len(inp.temperature_data) > 0:
        avg_temp = np.mean(inp.temperature_data)
        if avg_temp > 0 and t_total > 0:
            result.tgc = round(
                float((B_final ** (1 / 3) - B0 ** (1 / 3)) / (avg_temp * t_total) * 1000),
                6,
            )

    # Max growth rate (from numerical differentiation)
    if len(B) > 1:
        dt_arr = np.diff(t)
        dB_arr = np.diff(B)
        growth_rates = dB_arr / (dt_arr + 1e-10)
        result.max_growth_rate = round(float(np.max(growth_rates)), 6)

    return result
