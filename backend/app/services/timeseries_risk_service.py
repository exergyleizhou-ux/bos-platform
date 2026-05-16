"""BOS time-series risk aggregation service."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Batch, ReleaseDecision, SignalBatch
from app.schemas.timeseries_risk import ConfidenceBand, RecentTimeseriesRiskResponse, TimeseriesRiskResponse
from app.services.chronos_risk_service import forecast_with_chronos_or_fallback


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def _batch_score(batch: Batch) -> float:
    return float(batch.score if batch.score is not None else (_safe_ratio(batch.dm_out, batch.dm_in) or 0.0))


def _metering_completeness(batch: Batch) -> float:
    observed = [
        batch.dm_in,
        batch.dm_out,
        batch.n_in,
        batch.n_larvae,
        batch.n_frass,
        batch.temperature,
        batch.moisture,
    ]
    return round(sum(value is not None for value in observed) / len(observed), 4)


async def _latest_signal(db: AsyncSession, *, batch_id: int, tenant_id: int) -> SignalBatch | None:
    result = await db.execute(
        select(SignalBatch)
        .where(SignalBatch.batch_id == batch_id, SignalBatch.tenant_id == tenant_id)
        .order_by(desc(SignalBatch.updated_at), desc(SignalBatch.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_release(db: AsyncSession, *, batch_id: int, tenant_id: int) -> ReleaseDecision | None:
    result = await db.execute(
        select(ReleaseDecision)
        .where(ReleaseDecision.batch_id == batch_id, ReleaseDecision.tenant_id == tenant_id)
        .order_by(desc(ReleaseDecision.created_at), desc(ReleaseDecision.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _score_history(db: AsyncSession, *, batch: Batch, tenant_id: int, limit: int = 24) -> list[float]:
    result = await db.execute(
        select(Batch)
        .where(Batch.tenant_id == tenant_id, Batch.score.isnot(None))
        .order_by(Batch.batch_date.asc(), Batch.created_at.asc(), Batch.id.asc())
        .limit(limit)
    )
    scores = [_batch_score(item) for item in result.scalars().all()]
    current_score = _batch_score(batch)
    if not scores or scores[-1] != current_score:
        scores.append(current_score)
    if len(scores) == 1:
        scores.insert(0, scores[0])
    return scores[-limit:]


def _signal_freshness_base(signal: SignalBatch | None) -> tuple[float, str]:
    if signal is None:
        return 0.55, "signal_missing"
    freshness = (signal.freshness_state or "unknown").lower()
    if "stale" in freshness:
        return 0.85, "signal_stale"
    if "stable" in freshness:
        return 0.5, "signal_stable"
    if "fresh" in freshness:
        return 0.2, "signal_fresh"
    return 0.6, "signal_unknown"


def _freshness_drift_score(signal: SignalBatch | None, forecast_delta_risk: float) -> tuple[float, str]:
    base, driver = _signal_freshness_base(signal)
    expiry_pressure = 0.0
    if signal and signal.expires_at:
        expires_at = signal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        hours_remaining = (expires_at - datetime.now(UTC)).total_seconds() / 3600
        if hours_remaining <= 0:
            expiry_pressure = 0.35
            driver = "signal_expired"
        elif hours_remaining <= 6:
            expiry_pressure = 0.2
            driver = "signal_near_expiry"
    return round(_clamp(base + expiry_pressure + forecast_delta_risk * 0.25), 4), driver


def _release_base(release: ReleaseDecision | None) -> tuple[float, str]:
    if release is None:
        return 0.45, "release_missing"
    decision = (release.decision or "unknown").upper()
    if decision == "FAIL":
        return 0.9, "release_fail"
    if decision == "PASS_WITH_RETUNING":
        return 0.65, "release_retuning"
    if decision == "PASS":
        return 0.2, "release_pass"
    return 0.55, "release_unknown"


def _release_warning_score(
    *,
    release: ReleaseDecision | None,
    future_risk_score: float,
    freshness_drift_score: float,
) -> tuple[float, str]:
    base, driver = _release_base(release)
    warning_count = len(release.warning_factors or []) if release else 0
    blocking_count = len(release.blocking_factors or []) if release else 0
    factor_pressure = min(0.25, warning_count * 0.06 + blocking_count * 0.12)
    score = base * 0.5 + future_risk_score * 0.3 + freshness_drift_score * 0.2 + factor_pressure
    return round(_clamp(score), 4), driver


def _future_risk_score(history: list[float], forecast: list[float], band: tuple[float, float]) -> tuple[float, str]:
    current = history[-1] if history else 0.0
    projected = mean(forecast) if forecast else current
    baseline = max(abs(current), 0.0001)
    downside_drift = max(0.0, (current - projected) / baseline)
    band_width = max(0.0, band[1] - band[0]) / max(abs(projected), 0.0001)
    recent_span = (max(history[-6:]) - min(history[-6:])) / max(abs(current), 0.0001) if len(history) >= 2 else 0.0
    score = 0.25 + downside_drift * 0.45 + band_width * 0.15 + recent_span * 0.15
    return round(_clamp(score), 4), f"ser_forecast_delta={round(projected - current, 4)}"


def _heuristic_baseline(
    *,
    history: list[float],
    future_risk_score: float,
    freshness_drift_score: float,
    release_warning_score: float,
) -> dict[str, Any]:
    return {
        "history_points": len(history),
        "latest_value": history[-1] if history else None,
        "future_risk_score": future_risk_score,
        "freshness_drift_score": freshness_drift_score,
        "release_warning_score": release_warning_score,
        "fallback_policy": "Chronos unavailable -> existing heuristic forecast",
    }


async def build_batch_timeseries_risk(
    *,
    db: AsyncSession,
    batch: Batch,
    tenant_id: int,
    horizon: int = 6,
) -> TimeseriesRiskResponse:
    history = await _score_history(db, batch=batch, tenant_id=tenant_id)
    signal = await _latest_signal(db, batch_id=batch.id, tenant_id=tenant_id)
    release = await _latest_release(db, batch_id=batch.id, tenant_id=tenant_id)
    forecast = forecast_with_chronos_or_fallback(
        sensor_history=history,
        horizon=horizon,
        metric_name="batch_ser_risk",
        batch=batch,
    )

    future_score, future_driver = _future_risk_score(
        history,
        forecast.forecast,
        forecast.confidence_band,
    )
    freshness_score, freshness_driver = _freshness_drift_score(signal, future_score)
    release_score, release_driver = _release_warning_score(
        release=release,
        future_risk_score=future_score,
        freshness_drift_score=freshness_score,
    )
    fallback_driver = (
        "fallback=existing_heuristic_forecast"
        if forecast.fallback_used
        else "fallback=not_used"
    )
    driver_features = [
        f"model_execution_mode={forecast.execution_mode}",
        future_driver,
        freshness_driver,
        release_driver,
        f"metering_completeness={_metering_completeness(batch)}",
        fallback_driver,
    ]
    if forecast.warnings:
        driver_features.append(f"model_warning={forecast.warnings[0]}")

    explanation = (
        "Chronos-backed risk forecast is available."
        if not forecast.fallback_used
        else "Chronos runtime was unavailable or incomplete; BOS preserved the phase-1 heuristic fallback."
    )

    return TimeseriesRiskResponse(
        batch_id=batch.id,
        batch_label=batch.batch_id,
        future_risk_score=future_score,
        freshness_drift_score=freshness_score,
        release_warning_score=release_score,
        driver_features=driver_features,
        forecast_window=f"{max(1, int(horizon))} steps from recent batch SER, signal, and release context",
        model_name=forecast.model_name,
        confidence_band=ConfidenceBand(
            lower=round(float(forecast.confidence_band[0]), 4),
            upper=round(float(forecast.confidence_band[1]), 4),
        ),
        execution_mode=forecast.execution_mode,
        fallback_used=forecast.fallback_used,
        forecast_preview=[round(float(value), 4) for value in forecast.forecast[:4]],
        heuristic_baseline=_heuristic_baseline(
            history=history,
            future_risk_score=future_score,
            freshness_drift_score=freshness_score,
            release_warning_score=release_score,
        ),
        explanation=explanation,
    )


async def build_recent_timeseries_risks(
    *,
    db: AsyncSession,
    tenant_id: int,
    limit: int = 5,
    horizon: int = 6,
) -> RecentTimeseriesRiskResponse:
    result = await db.execute(
        select(Batch)
        .where(Batch.tenant_id == tenant_id)
        .order_by(desc(Batch.updated_at), desc(Batch.id))
        .limit(max(1, min(limit, 20)))
    )
    items = [
        await build_batch_timeseries_risk(
            db=db,
            batch=batch,
            tenant_id=tenant_id,
            horizon=horizon,
        )
        for batch in result.scalars().all()
    ]
    return RecentTimeseriesRiskResponse(items=items, count=len(items))

