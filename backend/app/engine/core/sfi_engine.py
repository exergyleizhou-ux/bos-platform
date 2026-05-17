"""BOS Pipeline — Phase A SFI (Signal/Flight Integrity) engine.

Composes the existing ``flight_envelope.check_flight_envelope`` per-axis
classification with:
- a [0, 1] composite score across axes,
- Eq.6 physical-horizon check (``tau_max = ln(s0/s_min) / k_decay``),
- a simple forecast-breach hint when a ``SetpointProfile`` is given,
- discrete remediation actions.

The engine is a thin composition layer; it does NOT re-implement zone
classification. Phase D may upgrade the composite-score formula and
the forecast model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.engine.core.flight_envelope import (
    FlightEnvelopeInput,
    check_flight_envelope,
)

ENGINE_VERSION = "9.0.0"


# ---- Mapping tables ----------------------------------------------------

# Translate flight_envelope's legacy zone vocabulary back to the
# V5 four-zone scheme. (flight_envelope normalises green→optimal,
# yellow→acceptable/warning, red→critical/danger.)
_LEGACY_TO_V5_ZONE = {
    "optimal": "safe",
    "acceptable": "caution",
    "warning": "caution",
    "critical": "danger",
    "danger": "danger",
    "red": "danger",
    "yellow": "caution",
    "green": "safe",
}

# V5 axis name → flight_envelope's input field name.
# NOTE: V5 `density_kg_m3` is the BULK SUBSTRATE density (kg/m³). Legacy
# flight_envelope `density` is LARVAE density (larvae/m²) — totally
# different concept and unit. We do NOT map V5 density to the legacy
# axis. Phase B/D will add a proper substrate-density envelope.
_AXIS_TO_LEGACY = {
    "temperature_c": "temperature",
    "moisture_pct": "moisture",
    "ph": "ph",
    "oxygen_pct": "o2_level",
    "co2_pct": "co2_level",
    "feed_rate_g_per_larva_day": "feed_rate",
}

# Per-axis weight for the composite score. Sums to 1.0 when every axis
# present. Missing axes drop out and weights are renormalised below.
_AXIS_WEIGHTS = {
    "temperature_c": 0.25,
    "moisture_pct": 0.20,
    "density_kg_m3": 0.10,
    "ph": 0.10,
    "ammonia_ppm": 0.10,
    "oxygen_pct": 0.10,
    "co2_pct": 0.05,
    "feed_rate_g_per_larva_day": 0.10,
}

# Per-axis hard envelope (lo, hi) for ammonia — flight_envelope doesn't
# carry an ammonia check today, so we inline a conservative one here.
# A future flight_envelope upgrade should absorb this.
_AMMONIA_OPTIMAL = (0.0, 100.0)     # ppm
_AMMONIA_SAFE = (0.0, 500.0)        # ppm

# Status mapping from V5 zone.
_ZONE_TO_STATUS = {"safe": "pass", "caution": "warn", "danger": "fail",
                   "out_of_envelope": "fail"}

# Evidence-level downgrade for the k_decay provenance (paper honesty rule).
_K_DECAY_EVIDENCE = {
    "measured": "validated",
    "fitted": "supported",
    "literature": "planned",
}


# ---- Per-axis evaluation helpers --------------------------------------


@dataclass
class _AxisEval:
    axis: str
    value: float
    unit: str
    zone: str  # V5 zone
    status: str
    margin_to_breach: Optional[float]
    score: float  # [0, 1]; 1.0 = optimal, 0.0 = breach


def _eval_envelope_axes(
    species: str,
    m: Dict[str, Any],
) -> List[_AxisEval]:
    """Run flight_envelope on the subset of axes it knows about."""
    legacy_kwargs: Dict[str, Any] = {"species": species}
    for v5_name, legacy_name in _AXIS_TO_LEGACY.items():
        val = m.get(v5_name)
        if val is None:
            continue
        legacy_kwargs[legacy_name] = float(val)

    inp = FlightEnvelopeInput(**legacy_kwargs)
    result = check_flight_envelope(inp)

    out: List[_AxisEval] = []
    for chk in result.checks:
        v5_axis = _legacy_to_v5_axis_name(chk.parameter)
        v5_zone = _LEGACY_TO_V5_ZONE.get(chk.zone, "caution")
        score = _zone_score(v5_zone, chk.deviation_pct)
        margin = _axis_margin(chk.value, chk.optimal_min, chk.optimal_max,
                              chk.safe_min, chk.safe_max)
        out.append(_AxisEval(
            axis=v5_axis,
            value=float(chk.value),
            unit=chk.unit,
            zone=v5_zone,
            status=_ZONE_TO_STATUS[v5_zone],
            margin_to_breach=margin,
            score=score,
        ))
    return out


def _legacy_to_v5_axis_name(legacy_name: str) -> str:
    rev = {v: k for k, v in _AXIS_TO_LEGACY.items()}
    return rev.get(legacy_name, legacy_name)


def _zone_score(zone: str, deviation_pct: float) -> float:
    """Map zone + deviation% into a [0,1] score."""
    if zone == "safe":
        # 0% deviation = 1.0; 100% deviation (edge of optimal) = 0.7.
        return max(0.7, 1.0 - 0.003 * deviation_pct)
    if zone == "caution":
        # In the safe-but-not-optimal band: linearly between 0.7 and 0.3.
        return max(0.3, 0.7 - 0.004 * deviation_pct)
    # danger / out_of_envelope
    return max(0.0, 0.3 - 0.003 * deviation_pct)


def _axis_margin(
    value: float, opt_min: float, opt_max: float, safe_min: float, safe_max: float
) -> float:
    """Distance to the nearest envelope breach in axis units (signed)."""
    if value < safe_min:
        return value - safe_min  # negative
    if value > safe_max:
        return safe_max - value  # negative
    return min(value - safe_min, safe_max - value)


def _eval_ammonia(ammonia_ppm: float) -> _AxisEval:
    """Standalone ammonia check (not in legacy flight_envelope)."""
    opt_lo, opt_hi = _AMMONIA_OPTIMAL
    safe_lo, safe_hi = _AMMONIA_SAFE
    if opt_lo <= ammonia_ppm <= opt_hi:
        zone = "safe"
        score = 1.0
    elif safe_lo <= ammonia_ppm <= safe_hi:
        zone = "caution"
        # Linear from 0.7 at opt_hi → 0.3 at safe_hi.
        if ammonia_ppm > opt_hi:
            frac = (ammonia_ppm - opt_hi) / max(safe_hi - opt_hi, 1e-9)
            score = max(0.3, 0.7 - 0.4 * frac)
        else:
            score = 0.7
    else:
        zone = "danger"
        score = max(0.0, 0.3 - 0.003 * abs(ammonia_ppm - safe_hi))

    margin = min(ammonia_ppm - safe_lo, safe_hi - ammonia_ppm)
    return _AxisEval(
        axis="ammonia_ppm",
        value=float(ammonia_ppm),
        unit="ppm",
        zone=zone,
        status=_ZONE_TO_STATUS[zone],
        margin_to_breach=margin,
        score=score,
    )


# ---- Composite score, Eq.6 horizon, forecast, actions -----------------


def _composite_score(axes: List[_AxisEval]) -> float:
    """Weighted mean of per-axis scores. Missing axes drop from the weight."""
    if not axes:
        return 0.0
    weights = [(_AXIS_WEIGHTS.get(a.axis, 0.05), a.score) for a in axes]
    total_w = sum(w for w, _ in weights)
    if total_w == 0:
        return 0.0
    return sum(w * s for w, s in weights) / total_w


def _worst_zone(axes: List[_AxisEval]) -> str:
    order = {"safe": 0, "caution": 1, "danger": 2, "out_of_envelope": 3}
    if not axes:
        return "safe"
    worst = max(axes, key=lambda a: order[a.zone])
    return worst.zone


def _eq6_tau_max(s0: float, s_min: float, k_decay_point: float) -> float:
    """Eq.6 physical horizon: tau_max = ln(s0 / s_min) / k_decay."""
    if k_decay_point <= 0 or s_min <= 0 or s0 <= s_min:
        return math.inf
    return math.log(s0 / s_min) / k_decay_point


def _forecast_breach(
    measurements: Dict[str, Any],
    setpoint: Optional[Dict[str, Any]],
    horizon_hours: int,
) -> Optional[Dict[str, Any]]:
    """Simple linear-extrapolation forecast — Phase A placeholder.

    For each axis present in ``setpoint.target_state``, treat current
    deviation as a velocity and project. If projected breach occurs
    within horizon, emit the earliest one.
    """
    if not setpoint:
        return None
    target_state: Dict[str, float] = setpoint.get("target_state", {})
    tolerance_pct: float = float(setpoint.get("tolerance_pct", 10.0))
    if not target_state:
        return None

    earliest: Optional[Dict[str, Any]] = None
    for axis, target in target_state.items():
        current = measurements.get(axis)
        if current is None:
            continue
        # Tolerance in axis units = target * tolerance_pct / 100.
        tol = abs(target) * (tolerance_pct / 100.0)
        if tol == 0:
            continue
        deviation = float(current) - float(target)
        # If we are already outside tolerance, breach is "now".
        if abs(deviation) >= tol:
            candidate = {
                "earliest_breach_hour": 0.0,
                "axis": axis,
                "confidence": 0.95,
            }
        else:
            # Assume |deviation| grows linearly at 5%/hour (Phase A
            # placeholder; Phase D will use kinetics_engine for real drift).
            drift_rate_per_h = max(abs(deviation), tol * 0.01) * 0.05
            hours_to_breach = max(0.0, (tol - abs(deviation)) / drift_rate_per_h)
            if hours_to_breach > horizon_hours:
                continue
            candidate = {
                "earliest_breach_hour": round(hours_to_breach, 2),
                "axis": axis,
                "confidence": 0.5,
            }
        if earliest is None or candidate["earliest_breach_hour"] < earliest["earliest_breach_hour"]:
            earliest = candidate
    return earliest


def _recommend_actions(
    axes: List[_AxisEval],
    eq6_breach: bool,
) -> List[Dict[str, Any]]:
    """Map per-axis failures + Eq.6 verdict to discrete actions."""
    actions: List[Dict[str, Any]] = []

    if eq6_breach:
        actions.append({
            "action_type": "horizon_exceeds_physical_limit",
            "urgency": "high",
            "description": (
                "Requested horizon exceeds Eq.6 physical limit "
                "tau_max = ln(s0/s_min)/k_decay. Reduce horizon or "
                "increase substrate buffer."
            ),
        })

    for ax in axes:
        if ax.zone in ("safe", "caution"):
            continue
        if ax.axis == "temperature_c":
            actions.append({
                "action_type": "cool_down" if ax.value > 30 else "heat_up",
                "urgency": "high",
                "description": f"Temperature {ax.value} {ax.unit} outside safe range.",
            })
        elif ax.axis == "moisture_pct":
            actions.append({
                "action_type": "irrigate" if ax.value < 50 else "ventilate",
                "urgency": "medium",
                "description": f"Moisture {ax.value} {ax.unit} outside safe range.",
            })
        elif ax.axis == "ph":
            actions.append({
                "action_type": "ph_adjust",
                "urgency": "medium",
                "description": f"pH {ax.value} outside safe range.",
            })
        elif ax.axis == "ammonia_ppm":
            actions.append({
                "action_type": "ventilate",
                "urgency": "high",
                "description": f"Ammonia {ax.value} ppm exceeds safe band.",
            })
        elif ax.axis == "co2_pct":
            actions.append({
                "action_type": "ventilate",
                "urgency": "high",
                "description": f"CO2 {ax.value} % exceeds safe band.",
            })
        elif ax.axis == "oxygen_pct":
            actions.append({
                "action_type": "ventilate",
                "urgency": "high",
                "description": f"O2 {ax.value} % below safe band.",
            })
        elif ax.axis == "feed_rate_g_per_larva_day":
            actions.append({
                "action_type": "feed_reduce" if ax.value > 0.3 else "feed_increase",
                "urgency": "low",
                "description": f"Feed rate {ax.value} {ax.unit} outside band.",
            })
        elif ax.axis == "density_kg_m3":
            actions.append({
                "action_type": "harvest_now",
                "urgency": "medium",
                "description": f"Density {ax.value} {ax.unit} outside safe band.",
            })
    return actions[:20]


# ---- Public entry -----------------------------------------------------


def check_sfi(
    species_code: str,
    measurements: Dict[str, Any],
    setpoint_profile: Optional[Dict[str, Any]],
    horizon_hours: int,
    k_decay_band: Optional[Dict[str, Any]],
    s0: Optional[float],
    s_min: Optional[float],
) -> Dict[str, Any]:
    """Run the full SFI check and return a dict shaped like SfiCheckResponse.

    All inputs are validated by the API schema before reaching this
    engine, so we trust the structure here. ``measurements`` and
    ``setpoint_profile`` are passed as plain dicts so the engine can be
    unit-tested without the Pydantic dependency boundary.
    """
    # TODO(Phase A2/A3): Replace this prefix heuristic with an explicit
    # SPECIES_CODE_MAP when the species set grows beyond BSF. The V5
    # contract uses long codes (e.g. "BSF_LARVA"); the legacy species_db
    # uses short codes (e.g. "BSF"). See PHASE_A_PLAN §2.2 on species
    # nomenclature. Tracked as A1 technical debt.
    species = species_code.replace("_LARVA", "").replace("_", "")
    if species_code.startswith("BSF"):
        species = "BSF"

    axes: List[_AxisEval] = _eval_envelope_axes(species, measurements)

    # Ammonia: not in legacy flight_envelope.
    ammonia = measurements.get("ammonia_ppm")
    if ammonia is not None:
        axes.append(_eval_ammonia(float(ammonia)))

    # Eq.6 physical-horizon check.
    eq6_breach = False
    if k_decay_band and s0 is not None and s_min is not None:
        tau_max = _eq6_tau_max(float(s0), float(s_min), float(k_decay_band["point"]))
        if horizon_hours > tau_max:
            eq6_breach = True

    composite = _composite_score(axes)
    worst = _worst_zone(axes)
    zone = "out_of_envelope" if eq6_breach else worst

    sfi_pass = zone == "safe"

    per_axis = {
        a.axis: {
            "axis": a.axis,
            "value": a.value,
            "unit": a.unit,
            "status": a.status,
            "margin_to_breach": a.margin_to_breach,
        }
        for a in axes
    }

    forecast = _forecast_breach(measurements, setpoint_profile, horizon_hours)
    actions = _recommend_actions(axes, eq6_breach)

    # Evidence level: downgrade per k_decay provenance (paper honesty rule).
    if k_decay_band is None:
        evidence_level = "supported"
    else:
        evidence_level = _K_DECAY_EVIDENCE.get(k_decay_band.get("source", "literature"),
                                               "planned")

    return {
        "sfi_pass": sfi_pass,
        "zone": zone,
        "composite_score": round(composite, 4),
        "per_axis": per_axis,
        "forecast_breach": forecast,
        "recommended_actions": actions,
        "evidence_level": evidence_level,
        "k_decay_used": k_decay_band,
        "engine_version": ENGINE_VERSION,
    }
