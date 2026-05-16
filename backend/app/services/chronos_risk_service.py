"""Chronos-backed forecast adapter with honest heuristic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.forecast import ForecastInput, run_forecast
from app.services.bos_native_runtime import run_native_inference_contract


def _as_float_list(values: Any) -> list[float]:
    if not isinstance(values, list):
        return []
    result: list[float] = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return result


def _confidence_band(result: dict[str, Any], forecast: list[float]) -> tuple[float, float]:
    ci_lower = _as_float_list(result.get("ci_lower"))
    ci_upper = _as_float_list(result.get("ci_upper"))
    if ci_lower and ci_upper:
        return min(ci_lower), max(ci_upper)

    quantiles = result.get("quantiles")
    if isinstance(quantiles, list):
        flattened: list[float] = []
        for row in quantiles:
            if isinstance(row, list):
                flattened.extend(_as_float_list(row))
            else:
                try:
                    flattened.append(float(row))
                except (TypeError, ValueError):
                    continue
        if flattened:
            return min(flattened), max(flattened)

    if forecast:
        return min(forecast), max(forecast)
    return 0.0, 0.0


@dataclass(slots=True)
class ChronosRiskForecast:
    model_name: str
    execution_mode: str
    fallback_used: bool
    forecast: list[float]
    confidence_band: tuple[float, float]
    warnings: list[str]
    raw_result: dict[str, Any]


def forecast_with_chronos_or_fallback(
    *,
    sensor_history: list[float],
    horizon: int,
    metric_name: str,
    batch: Any | None = None,
) -> ChronosRiskForecast:
    """Run Chronos when available; otherwise preserve the existing heuristic path."""

    values = [float(value) for value in sensor_history if value is not None]
    if len(values) < 2:
        seed = values[0] if values else 0.0
        values = [seed, seed]

    payload = {
        "sensor_history": values,
        "horizon": max(1, int(horizon)),
        "metric_name": metric_name,
    }

    try:
        response = run_native_inference_contract(
            model_key="chronos_bolt",
            payload=payload,
            batch=batch,
            dry_run=False,
        )
        result = response.get("result") or {}
        forecast = _as_float_list(result.get("forecast"))
        if not forecast:
            forecast = _as_float_list(result.get("forecast_preview"))
        if not forecast:
            raise RuntimeError("chronos_response_missing_forecast")

        execution_mode = str(response.get("execution_mode") or result.get("execution_mode") or "unknown")
        return ChronosRiskForecast(
            model_name="chronos_bolt",
            execution_mode=execution_mode,
            fallback_used=execution_mode != "chronos_bolt_live",
            forecast=forecast,
            confidence_band=_confidence_band(result, forecast),
            warnings=[str(item) for item in response.get("warnings", [])],
            raw_result=result,
        )
    except Exception as exc:
        fallback = run_forecast(
            ForecastInput(
                values=values,
                method="ewma",
                horizon=max(1, int(horizon)),
                alpha=0.3,
            )
        )
        forecast = _as_float_list(fallback.forecast)
        return ChronosRiskForecast(
            model_name="chronos_bolt",
            execution_mode="heuristic_exception_fallback",
            fallback_used=True,
            forecast=forecast,
            confidence_band=_confidence_band(
                {"ci_lower": fallback.ci_lower, "ci_upper": fallback.ci_upper},
                forecast,
            ),
            warnings=[f"Chronos runtime failed; used heuristic fallback: {exc}"],
            raw_result={
                "forecast": forecast,
                "ci_lower": fallback.ci_lower,
                "ci_upper": fallback.ci_upper,
                "fallback_method": "ewma",
                "execution_mode": "heuristic_exception_fallback",
            },
        )

