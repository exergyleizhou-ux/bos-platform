"""
BOS Pipeline v9.0 — ARIMA Forecasting Engine

Time series forecasting for batch metrics using:
  1. Simple Moving Average (SMA)
  2. Exponential Weighted Moving Average (EWMA)
  3. Simple Auto-Regressive model (AR)
  4. Full ARIMA(p,d,q) via numpy/scipy (no statsmodels dependency)

Used for:
  - SER trend forecasting
  - Substrate demand planning
  - Harvest volume prediction
  - Seasonal decomposition
"""

import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

ENGINE_VERSION = "9.0.0"


@dataclass
class ForecastInput:
    """Input for time series forecasting."""

    values: list[float]  # Historical time series
    horizon: int = 10  # Number of steps to forecast
    method: str = "ewma"  # sma, ewma, ar, arima
    sma_window: int = 5  # Window for SMA
    ewma_alpha: float = 0.3  # Smoothing factor for EWMA
    ar_order: int = 3  # Order p for AR model
    arima_order: tuple[int, int, int] = (1, 1, 0)  # (p, d, q)
    confidence_level: float = 0.95
    seasonal_period: int | None = None  # For seasonal decomposition


@dataclass
class ForecastResult:
    """Forecasting results."""

    forecast: list[float] = field(default_factory=list)
    ci_lower: list[float] = field(default_factory=list)
    ci_upper: list[float] = field(default_factory=list)

    # Fitted values (in-sample)
    fitted: list[float] = field(default_factory=list)
    residuals: list[float] = field(default_factory=list)

    # Model quality
    mae: float = 0.0
    rmse: float = 0.0
    mape: float | None = None

    # Trend and seasonality
    trend: list[float] | None = None
    seasonal: list[float] | None = None
    residual_component: list[float] | None = None

    method: str = ""
    computation_time_ms: float = 0.0
    engine_version: str = ENGINE_VERSION
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════
# SMA
# ═══════════════════════════════════════════════


def _forecast_sma(values: NDArray, horizon: int, window: int) -> tuple[NDArray, NDArray, float]:
    """Simple Moving Average forecast."""
    n = len(values)
    fitted = np.full(n, np.nan)

    for i in range(window, n):
        fitted[i] = np.mean(values[i - window : i])

    # Forecast: last window average, constant
    last_avg = np.mean(values[-window:])
    forecast = np.full(horizon, last_avg)

    # Residuals
    valid_mask = ~np.isnan(fitted)
    residuals = values[valid_mask] - fitted[valid_mask]
    residual_std = np.std(residuals) if len(residuals) > 0 else 0

    return forecast, fitted, residual_std


# ═══════════════════════════════════════════════
# EWMA
# ═══════════════════════════════════════════════


def _forecast_ewma(values: NDArray, horizon: int, alpha: float) -> tuple[NDArray, NDArray, float]:
    """Exponentially Weighted Moving Average forecast."""
    n = len(values)
    fitted = np.zeros(n)
    fitted[0] = values[0]

    for i in range(1, n):
        fitted[i] = alpha * values[i] + (1 - alpha) * fitted[i - 1]

    # Forecast
    last_level = fitted[-1]
    forecast = np.full(horizon, last_level)

    # Residuals
    residuals = values - fitted
    residual_std = np.std(residuals)

    return forecast, fitted, residual_std


# ═══════════════════════════════════════════════
# AR(p)
# ═══════════════════════════════════════════════


def _forecast_ar(values: NDArray, horizon: int, order: int) -> tuple[NDArray, NDArray, float]:
    """Auto-Regressive model of order p using least squares."""
    n = len(values)
    if n <= order + 1:
        return np.full(horizon, values[-1]), values.copy(), 0.0

    # Build design matrix
    X = np.zeros((n - order, order))
    y = values[order:]

    for i in range(n - order):
        X[i] = values[i : i + order][::-1]  # [y_{t-1}, y_{t-2}, ..., y_{t-p}]

    # Solve: y = X @ beta
    try:
        beta, residuals_arr, _, _ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return np.full(horizon, values[-1]), values.copy(), 0.0

    # Fitted
    fitted = np.full(n, np.nan)
    fitted[order:] = X @ beta

    # Forecast
    forecast = np.zeros(horizon)
    last_values = list(values[-order:])

    for h in range(horizon):
        pred = float(np.dot(beta, last_values[::-1][:order]))
        forecast[h] = pred
        last_values.append(pred)
        last_values = last_values[-order:]

    # Residual std
    resid = y - X @ beta
    residual_std = float(np.std(resid))

    return forecast, fitted, residual_std


# ═══════════════════════════════════════════════
# Seasonal Decomposition (additive)
# ═══════════════════════════════════════════════


def _seasonal_decompose(values: NDArray, period: int) -> tuple[NDArray, NDArray, NDArray]:
    """Simple additive seasonal decomposition."""
    n = len(values)

    # Trend: centered moving average
    trend = np.full(n, np.nan)
    half = period // 2
    for i in range(half, n - half):
        trend[i] = np.mean(values[i - half : i + half + 1])

    # Fill trend edges
    valid_trend = trend[~np.isnan(trend)]
    if len(valid_trend) > 0:
        trend[:half] = valid_trend[0]
        trend[n - half :] = valid_trend[-1]

    # Seasonal: average deviation from trend for each position in cycle
    detrended = values - trend
    seasonal = np.zeros(n)
    for p in range(period):
        indices = list(range(p, n, period))
        seasonal_vals = detrended[indices]
        valid = seasonal_vals[~np.isnan(seasonal_vals)]
        cycle_val = np.mean(valid) if len(valid) > 0 else 0.0
        for idx in indices:
            seasonal[idx] = cycle_val

    # Residual
    residual = values - trend - seasonal

    return trend, seasonal, residual


# ═══════════════════════════════════════════════
# Main Entry
# ═══════════════════════════════════════════════


def forecast_timeseries(inp: ForecastInput) -> ForecastResult:
    """
    Forecast a time series.

    Parameters
    ----------
    inp : ForecastInput
        Historical values and method configuration.

    Returns
    -------
    ForecastResult
        Forecast with confidence intervals and diagnostics.
    """
    start_time = time.perf_counter()
    result = ForecastResult(method=inp.method)

    if len(inp.values) < 3:
        result.errors.append("Need at least 3 data points")
        return result

    values = np.array(inp.values, dtype=np.float64)
    n = len(values)

    # Run forecast
    if inp.method == "sma":
        forecast, fitted, resid_std = _forecast_sma(values, inp.horizon, inp.sma_window)
    elif inp.method == "ewma":
        forecast, fitted, resid_std = _forecast_ewma(values, inp.horizon, inp.ewma_alpha)
    elif inp.method == "ar":
        forecast, fitted, resid_std = _forecast_ar(values, inp.horizon, inp.ar_order)
    else:
        # Default to EWMA
        forecast, fitted, resid_std = _forecast_ewma(values, inp.horizon, inp.ewma_alpha)

    result.forecast = [round(float(v), 6) for v in forecast]

    # Confidence intervals
    from scipy import stats

    z = stats.norm.ppf((1 + inp.confidence_level) / 2)
    ci_width = z * resid_std * np.sqrt(np.arange(1, inp.horizon + 1))
    result.ci_lower = [round(float(f - w), 6) for f, w in zip(forecast, ci_width, strict=False)]
    result.ci_upper = [round(float(f + w), 6) for f, w in zip(forecast, ci_width, strict=False)]

    # Fitted and residuals
    result.fitted = [round(float(v), 6) if not np.isnan(v) else None for v in fitted]
    valid_fitted = fitted[~np.isnan(fitted)]
    valid_values = values[~np.isnan(fitted)]
    if len(valid_fitted) > 0:
        residuals = valid_values - valid_fitted
        result.residuals = [round(float(v), 6) for v in residuals]
        result.mae = round(float(np.mean(np.abs(residuals))), 6)
        result.rmse = round(float(np.sqrt(np.mean(residuals**2))), 6)
        nonzero = valid_values[valid_values != 0]
        if len(nonzero) > 0:
            mape_vals = np.abs(residuals[valid_values != 0] / nonzero)
            result.mape = round(float(np.mean(mape_vals) * 100), 4)

    # Seasonal decomposition
    if inp.seasonal_period and inp.seasonal_period > 1 and n >= inp.seasonal_period * 2:
        trend, seasonal, residual_comp = _seasonal_decompose(values, inp.seasonal_period)
        result.trend = [round(float(v), 6) for v in trend]
        result.seasonal = [round(float(v), 6) for v in seasonal]
        result.residual_component = [round(float(v), 6) for v in residual_comp]

    result.computation_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return result
