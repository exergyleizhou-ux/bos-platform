"""
BOS Supervisor Engine
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.engine.bos_mechanistic_engine import (
    analytic_handover_envelope,
    estimate_signal_state,
    fuse_proxy_measurement,
)


@dataclass
class SupervisorDecision:
    c_signal_hat: float
    dc_dt_hat: float | None
    confidence: float
    missing_channels: list[str]
    channels_used: list[str]
    trigger_reason: str | None
    expected_freshness_window_hours: float | None
    recommended_handover: bool
    information_loss: float
    observability_score: float
    negative_slope_streak: int
    computed_at: datetime


def evaluate_bos_supervisor_state(
    *,
    uv254: float | None,
    od280: float | None,
    do_value: float | None,
    ph: float | None,
    elapsed_hours: float,
    previous_c_signal_hat: float | None,
    previous_elapsed_hours: float | None,
    previous_dc_dt_hat: float | None = None,
    previous_negative_slope_streak: int = 0,
    confidence_threshold: float = 0.8,
    negative_slope_persistence: int = 3,
    observability_required: bool = True,
) -> SupervisorDecision:
    proxy_measurement = fuse_proxy_measurement(
        uv254=uv254,
        od280=od280,
        do_value=do_value,
        ph=ph,
    )
    observer = estimate_signal_state(
        current_measurement=proxy_measurement,
        elapsed_hours=elapsed_hours,
        previous_c_signal_hat=previous_c_signal_hat,
        previous_elapsed_hours=previous_elapsed_hours,
        previous_dc_dt_hat=previous_dc_dt_hat,
        previous_negative_slope_streak=previous_negative_slope_streak,
        confidence_threshold=confidence_threshold,
        negative_slope_persistence=negative_slope_persistence,
        observability_required=observability_required,
    )

    envelope = analytic_handover_envelope(
        c_max=max(1.0, observer.c_signal_estimate + proxy_measurement.observability_score),
        alpha_c=0.025 + (0.01 * proxy_measurement.observability_score),
        k_decay=0.004 + (0.006 * observer.information_loss),
        eta_comp=0.003,
        competition_pressure=1.0 + max(0.0, elapsed_hours) / 24.0,
    )
    expected_window = round(
        max(0.25, envelope.tau_star_minutes / 60.0) * max(observer.confidence, 0.35),
        2,
    )

    recommended_handover = (
        observer.confidence < confidence_threshold
        and bool(observer.missing_channels)
        and observability_required
    ) or (
        observer.negative_slope_streak >= negative_slope_persistence
        and observer.dc_dt_estimate is not None
        and observer.dc_dt_estimate < 0
    )

    trigger_reason = None
    if recommended_handover:
        trigger_reason = (
            "confidence_threshold"
            if observer.confidence < confidence_threshold
            else "negative_slope_persistence"
        )

    return SupervisorDecision(
        c_signal_hat=observer.c_signal_estimate,
        dc_dt_hat=observer.dc_dt_estimate,
        confidence=observer.confidence,
        missing_channels=observer.missing_channels,
        channels_used=observer.channels_used,
        trigger_reason=trigger_reason,
        expected_freshness_window_hours=expected_window,
        recommended_handover=recommended_handover,
        information_loss=observer.information_loss,
        observability_score=observer.observability_score,
        negative_slope_streak=observer.negative_slope_streak,
        computed_at=datetime.now(timezone.utc),
    )
