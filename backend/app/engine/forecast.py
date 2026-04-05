"""Backward-compatible forecasting module used by legacy tests."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass
class ForecastInput:
    values: list[float]
    method: str = "sma"  # sma | ewma | holt_winters
    horizon: int = 3
    window: int = 3
    alpha: float = 0.3
    beta: float = 0.1


@dataclass
class ForecastResult:
    forecast: list[float]
    ci_lower: list[float]
    ci_upper: list[float]
    method: str
    horizon: int
    mape: float | None = None
    rmse: float | None = None


def _validate(inp: ForecastInput) -> np.ndarray:
    if inp.horizon <= 0:
        raise ValueError("horizon must be > 0")
    values = np.asarray(inp.values, dtype=float)
    if values.size < 2:
        raise ValueError("values must contain at least 2 points")
    if inp.method == "sma" and values.size < max(2, inp.window):
        raise ValueError("not enough values for sma/window")
    return values


def _sma(values: np.ndarray, horizon: int, window: int) -> np.ndarray:
    level = float(np.mean(values[-window:]))
    return np.full(horizon, level, dtype=float)


def _ewma(values: np.ndarray, horizon: int, alpha: float) -> np.ndarray:
    level = float(values[0])
    for v in values[1:]:
        level = alpha * float(v) + (1.0 - alpha) * level
    return np.full(horizon, level, dtype=float)


def _holt(values: np.ndarray, horizon: int, alpha: float, beta: float) -> np.ndarray:
    level = float(values[0])
    trend = float(values[1] - values[0])
    for v in values[1:]:
        prev_level = level
        level = alpha * float(v) + (1.0 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1.0 - beta) * trend
    return np.array([level + (i + 1) * trend for i in range(horizon)], dtype=float)


def run_forecast(inp: ForecastInput) -> ForecastResult:
    values = _validate(inp)

    if inp.method == "sma":
        preds = _sma(values, inp.horizon, max(1, inp.window))
    elif inp.method == "ewma":
        preds = _ewma(values, inp.horizon, inp.alpha)
    elif inp.method == "holt_winters":
        preds = _holt(values, inp.horizon, inp.alpha, inp.beta)
    else:
        raise ValueError("unsupported forecast method")

    residual_std = float(np.std(np.diff(values))) if values.size > 2 else 0.0
    margin = 1.96 * residual_std
    ci_lower = preds - margin
    ci_upper = preds + margin

    # Light-weight holdout metrics.
    mape: float | None = None
    rmse: float | None = None
    if values.size >= 4:
        holdout = values[-2:]
        hist = values[:-2]
        if inp.method == "sma":
            base = float(np.mean(hist[-max(1, min(inp.window, hist.size)) :]))
            val_preds = np.array([base, base], dtype=float)
        elif inp.method == "ewma":
            level = float(hist[0])
            for v in hist[1:]:
                level = inp.alpha * float(v) + (1.0 - inp.alpha) * level
            val_preds = np.array([level, level], dtype=float)
        else:
            val_preds = _holt(hist, 2, inp.alpha, inp.beta)
        err = holdout - val_preds
        rmse = float(math.sqrt(np.mean(err**2)))
        denom = np.where(np.abs(holdout) < 1e-9, 1e-9, np.abs(holdout))
        mape = float(np.mean(np.abs(err) / denom))

    return ForecastResult(
        forecast=[float(v) for v in preds.tolist()],
        ci_lower=[float(v) for v in ci_lower.tolist()],
        ci_upper=[float(v) for v in ci_upper.tolist()],
        method=inp.method,
        horizon=inp.horizon,
        mape=mape,
        rmse=rmse,
    )
