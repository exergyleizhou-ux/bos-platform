"""
Mechanistic BOS signal primitives.

This module provides lightweight, auditable calculations that can be reused by
the BOS supervisor, signal compilation flow, and future protocol surfaces.
The implementation stays causal and analytic; it avoids opaque residual models
while still correcting a few failure modes in the previous heuristic-only logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


EPSILON = 1e-6
DEFAULT_PROXY_SCALES = {
    "uv254": 4.0,
    "od280": 4.0,
    "do": 6.0,
    "ph": 14.0,
}
DEFAULT_PROXY_WEIGHTS = {
    "uv254": 0.36,
    "od280": 0.26,
    "do": 0.2,
    "ph": 0.18,
}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


@dataclass(frozen=True)
class CDISERDiagnostics:
    c_di_ser: float
    alpha_s: float
    beta_s: float
    penalty: float
    information_loss: float
    evidence_balance: float


@dataclass(frozen=True)
class ProxyFusionDiagnostics:
    c_signal_measurement: float
    measurement_noise: float
    information_loss: float
    observability_score: float
    measurement_spread: float
    channels_used: list[str]
    missing_channels: list[str]


@dataclass(frozen=True)
class ObserverDiagnostics:
    c_signal_estimate: float
    dc_dt_estimate: float | None
    confidence: float
    information_loss: float
    observability_score: float
    negative_slope_streak: int
    channels_used: list[str]
    missing_channels: list[str]


@dataclass(frozen=True)
class HandoverEnvelope:
    tau_star_minutes: float
    c_peak: float
    clock_frequency_per_minute: float
    rise_rate: float
    decay_rate: float


def compute_c_di_ser(
    *,
    d_prime: float | None,
    g_prime: float | None,
    information_loss: float = 0.0,
) -> CDISERDiagnostics:
    """
    Compute a bounded C-DI-SER-style score.

    The previous implementation hard-coded alpha to 0.5 in practice. Here we
    retain a transparent analytic form but let the exponent respond to the
    balance between D' and G' while remaining inside a conservative interval.
    """
    d = max(float(d_prime or 0.0), 0.0)
    g = max(float(g_prime or 0.0), 0.0)
    info_loss = clamp(float(information_loss), 0.0, 1.0)

    total = d + g
    evidence_balance = d / (total + EPSILON)
    alpha_s = clamp(0.35 + 0.3 * evidence_balance, 0.35, 0.65)
    beta_s = 1.0 - alpha_s
    penalty = 1.0 / (1.0 + info_loss)
    c_di_ser = (max(d, EPSILON) ** alpha_s) * (max(g, EPSILON) ** beta_s) * penalty

    return CDISERDiagnostics(
        c_di_ser=round(c_di_ser, 4),
        alpha_s=round(alpha_s, 4),
        beta_s=round(beta_s, 4),
        penalty=round(penalty, 4),
        information_loss=round(info_loss, 4),
        evidence_balance=round(evidence_balance, 4),
    )


def fuse_proxy_measurement(
    *,
    uv254: float | None,
    od280: float | None,
    do_value: float | None,
    ph: float | None,
) -> ProxyFusionDiagnostics:
    """
    Normalize and fuse the available low-cost proxy channels.

    This remains intentionally simple, but it now accounts for channel
    disagreement and missingness instead of treating one scalar score as ground
    truth.
    """
    raw_inputs = {
        "uv254": uv254,
        "od280": od280,
        "do": do_value,
        "ph": ph,
    }

    normalized: dict[str, float] = {}
    missing_channels: list[str] = []
    for channel, value in raw_inputs.items():
        if value is None:
            missing_channels.append(channel)
            continue
        try:
            numeric = max(float(value), 0.0)
        except (TypeError, ValueError):
            missing_channels.append(channel)
            continue
        normalized[channel] = clamp(numeric / DEFAULT_PROXY_SCALES[channel])

    channels_used = list(normalized.keys())
    if not channels_used:
        info_loss = 1.0
        return ProxyFusionDiagnostics(
            c_signal_measurement=0.0,
            measurement_noise=1.0,
            information_loss=info_loss,
            observability_score=0.0,
            measurement_spread=0.0,
            channels_used=[],
            missing_channels=missing_channels,
        )

    weight_total = sum(DEFAULT_PROXY_WEIGHTS[channel] for channel in channels_used)
    c_signal = sum(
        normalized[channel] * DEFAULT_PROXY_WEIGHTS[channel]
        for channel in channels_used
    ) / max(weight_total, EPSILON)

    values = [normalized[channel] for channel in channels_used]
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    spread = math.sqrt(variance)

    observability_score = clamp(weight_total / sum(DEFAULT_PROXY_WEIGHTS.values()))
    missing_penalty = 1.0 - observability_score
    disagreement_penalty = clamp(spread / 0.35)
    info_loss = clamp(0.65 * missing_penalty + 0.35 * disagreement_penalty)
    measurement_noise = 0.05 + 0.45 * info_loss

    return ProxyFusionDiagnostics(
        c_signal_measurement=round(clamp(c_signal), 4),
        measurement_noise=round(measurement_noise, 4),
        information_loss=round(info_loss, 4),
        observability_score=round(observability_score, 4),
        measurement_spread=round(spread, 4),
        channels_used=channels_used,
        missing_channels=missing_channels,
    )


def estimate_signal_state(
    *,
    current_measurement: ProxyFusionDiagnostics,
    elapsed_hours: float,
    previous_c_signal_hat: float | None,
    previous_elapsed_hours: float | None,
    previous_dc_dt_hat: float | None = None,
    previous_negative_slope_streak: int = 0,
    confidence_threshold: float = 0.8,
    negative_slope_persistence: int = 3,
    observability_required: bool = True,
) -> ObserverDiagnostics:
    """
    Estimate the latent signal state with an analytic scalar observer.

    The observer uses a measurement-quality-dependent blending factor rather
    than a fixed heuristic penalty, which keeps the logic inspectable and cheap.
    """
    measurement = current_measurement.c_signal_measurement
    dt = None
    if previous_elapsed_hours is not None:
        delta = float(elapsed_hours) - float(previous_elapsed_hours)
        if delta > 0:
            dt = delta

    if previous_c_signal_hat is None:
        c_estimate = measurement
    else:
        gain = clamp(1.0 - current_measurement.measurement_noise, 0.15, 0.95)
        predicted = previous_c_signal_hat
        if previous_dc_dt_hat is not None and dt is not None:
            predicted = clamp(previous_c_signal_hat + (previous_dc_dt_hat * dt))
        c_estimate = clamp(predicted + gain * (measurement - predicted))

    dc_dt_estimate = None
    if previous_c_signal_hat is not None and dt is not None:
        dc_dt_estimate = (c_estimate - previous_c_signal_hat) / dt
        if previous_dc_dt_hat is not None:
            dc_dt_estimate = (0.65 * previous_dc_dt_hat) + (0.35 * dc_dt_estimate)

    negative_slope_streak = 0
    if dc_dt_estimate is not None and dc_dt_estimate < 0:
        negative_slope_streak = previous_negative_slope_streak + 1

    slope_penalty = 0.0
    if dc_dt_estimate is not None and dc_dt_estimate < 0:
        slope_penalty = min(0.2, abs(dc_dt_estimate) * 0.5)

    confidence = clamp(
        1.0
        - (0.6 * current_measurement.information_loss)
        - (0.25 * current_measurement.measurement_spread)
        - slope_penalty
        - (0.1 if observability_required and current_measurement.observability_score < 0.5 else 0.0)
    )

    if (
        observability_required
        and current_measurement.observability_score < 0.5
        and confidence >= confidence_threshold
    ):
        confidence = round(confidence_threshold - 0.01, 4)

    if negative_slope_streak >= negative_slope_persistence:
        confidence = max(confidence, 0.7)

    return ObserverDiagnostics(
        c_signal_estimate=round(c_estimate, 4),
        dc_dt_estimate=round(dc_dt_estimate, 4) if dc_dt_estimate is not None else None,
        confidence=round(confidence, 4),
        information_loss=current_measurement.information_loss,
        observability_score=current_measurement.observability_score,
        negative_slope_streak=negative_slope_streak,
        channels_used=current_measurement.channels_used,
        missing_channels=current_measurement.missing_channels,
    )


def analytic_handover_envelope(
    *,
    c_max: float = 1.0,
    alpha_c: float = 0.03,
    k_decay: float = 0.006,
    eta_comp: float = 0.003,
    competition_pressure: float = 1.0,
) -> HandoverEnvelope:
    """
    Analytic rise-decay envelope with a true interior peak.

    C(t) = C_max * (1 - exp(-alpha_c * t)) * exp(-delta * t)
    delta = k_decay + eta_comp * competition_pressure
    """
    rise = max(float(alpha_c), EPSILON)
    delta = max(float(k_decay) + (float(eta_comp) * max(float(competition_pressure), 0.0)), EPSILON)
    tau_star = math.log((rise + delta) / delta) / rise
    peak = c_max * (1.0 - math.exp(-rise * tau_star)) * math.exp(-delta * tau_star)

    return HandoverEnvelope(
        tau_star_minutes=round(tau_star, 2),
        c_peak=round(clamp(peak, 0.0, max(c_max, 1.0)), 4),
        clock_frequency_per_minute=round(1.0 / max(tau_star, EPSILON), 6),
        rise_rate=round(rise, 6),
        decay_rate=round(delta, 6),
    )


def build_compile_diagnostics(
    *,
    dm_in: float | None,
    dm_out: float | None,
    potency: float | None,
    stability_window_hours: float | None,
    metering_completeness: float,
    locality_shift_pct: float = 0.0,
) -> dict:
    """
    Build a compact, serializable mechanistic compile context for QC markers.
    """
    d_prime = max(float(potency or 0.0), 0.0)
    g_prime = max(float(stability_window_hours or 0.0), 0.0) / 24.0

    mass_balance_ratio = safe_ratio(dm_out, dm_in) or 0.0
    information_loss = clamp(
        0.55 * (1.0 - clamp(metering_completeness))
        + 0.3 * max(0.0, 1.0 - mass_balance_ratio)
        + 0.15 * min(abs(locality_shift_pct) / 100.0, 1.0)
    )
    c_di_ser = compute_c_di_ser(
        d_prime=d_prime,
        g_prime=g_prime,
        information_loss=information_loss,
    )
    handover = analytic_handover_envelope(
        c_max=max(1.0, d_prime + g_prime),
        alpha_c=0.025 + (0.015 * clamp(metering_completeness)),
        k_decay=0.004 + (0.006 * information_loss),
        eta_comp=0.002 + (0.004 * clamp(abs(locality_shift_pct) / 100.0)),
    )

    return {
        "c_di_ser": {
            "score": c_di_ser.c_di_ser,
            "alpha_s": c_di_ser.alpha_s,
            "beta_s": c_di_ser.beta_s,
            "penalty": c_di_ser.penalty,
            "information_loss": c_di_ser.information_loss,
            "evidence_balance": c_di_ser.evidence_balance,
        },
        "handover_envelope": {
            "tau_star_min": handover.tau_star_minutes,
            "c_peak": handover.c_peak,
            "f_clock": handover.clock_frequency_per_minute,
            "rise_rate": handover.rise_rate,
            "decay_rate": handover.decay_rate,
        },
        "inputs": {
            "mass_balance_ratio": round(mass_balance_ratio, 4),
            "metering_completeness": round(clamp(metering_completeness), 4),
            "locality_shift_pct": round(locality_shift_pct, 4),
        },
    }
