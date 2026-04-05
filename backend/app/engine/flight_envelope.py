"""
BOS Pipeline v9.0 锟斤拷 Flight Envelope Engine

Checks whether current batch operating parameters fall within the
acceptable operating envelope for a given species.

"Flight envelope" is borrowed from aerospace engineering:
  - Green zone : Within optimal range 锟斤拷 nominal operation
  - Yellow zone: Within acceptable range 锟斤拷 caution
  - Red zone   : Outside safe limits 锟斤拷 alarm / halt

Parameters checked:
  - Temperature
  - Moisture
  - Feed rate
  - Density
  - pH (if available)
  - O2 / CO2 levels (if available)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.engine.species_db import get_species

ENGINE_VERSION = "9.0.0"


@dataclass
class EnvelopeCheck:
    """Single parameter envelope check result."""

    parameter: str
    value: float
    unit: str
    zone: str  # "green", "yellow", "red"
    optimal_min: float
    optimal_max: float
    safe_min: float
    safe_max: float
    deviation_pct: float = 0.0  # Percentage deviation from optimal center
    message: str = ""


@dataclass
class FlightEnvelopeInput:
    """Input parameters for flight envelope check."""

    species: str = "BSF"
    temperature: Optional[float] = None
    moisture: Optional[float] = None
    feed_rate: Optional[float] = None
    density: Optional[float] = None
    ph: Optional[float] = None
    o2_level: Optional[float] = None
    co2_level: Optional[float] = None


@dataclass
class FlightEnvelopeResult:
    """Complete flight envelope assessment."""

    overall_zone: str = "green"  # Worst zone across all parameters
    checks: List[EnvelopeCheck] = field(default_factory=list)
    in_envelope: bool = True
    warnings: List[str] = field(default_factory=list)
    alarms: List[str] = field(default_factory=list)
    species: str = "BSF"
    engine_version: str = ENGINE_VERSION


# 锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋
# Zone Classification
# 锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋

ZONE_PRIORITY = {
    "red": 3,
    "yellow": 2,
    "green": 1,
    "danger": 3,
    "critical": 3,
    "warning": 2,
    "acceptable": 2,
    "optimal": 1,
}


def _to_legacy_zone(zone: str) -> str:
    """Map canonical zone names to legacy vocabulary expected by older callers."""
    return {"green": "optimal", "yellow": "warning", "red": "critical"}.get(zone, zone)


def classify_zone(
    value: float,
    optimal_min: float,
    optimal_max: float,
    safe_min: float,
    safe_max: float,
) -> str:
    """Classify a parameter value into green/yellow/red zone."""
    if optimal_min <= value <= optimal_max:
        return "green"
    elif safe_min <= value <= safe_max:
        return "yellow"
    else:
        return "red"


def deviation_from_optimal(value: float, optimal_min: float, optimal_max: float) -> float:
    """Calculate percentage deviation from optimal center."""
    center = (optimal_min + optimal_max) / 2
    half_range = (optimal_max - optimal_min) / 2
    if half_range == 0:
        return 0.0
    return round(abs(value - center) / half_range * 100, 1)


# 锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋
# Main Check
# 锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋锟絋


def check_flight_envelope(inp: FlightEnvelopeInput) -> FlightEnvelopeResult:
    """
    Perform flight envelope check for all provided parameters.

    Parameters
    ----------
    inp : FlightEnvelopeInput
        Operating parameters to check against species envelope.

    Returns
    -------
    FlightEnvelopeResult
        Per-parameter zone assessment and overall status.
    """
    sp = get_species(inp.species)
    if not sp:
        return FlightEnvelopeResult(
            overall_zone="red",
            in_envelope=False,
            alarms=[f"Unknown species: {inp.species}"],
            species=inp.species,
        )

    checks: List[EnvelopeCheck] = []
    warnings: List[str] = []
    alarms: List[str] = []
    worst_zone = "green"

    # 锟斤拷锟斤拷 Temperature 锟斤拷锟斤拷
    if inp.temperature is not None:
        opt_min = sp.temp_optimal - 2.0
        opt_max = sp.temp_optimal + 2.0
        safe_min = sp.temp_min
        safe_max = sp.temp_max

        zone = classify_zone(inp.temperature, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.temperature, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"Temperature {inp.temperature}锟斤拷C is outside optimal range ({opt_min}锟紺{opt_max}锟斤拷C)"
            warnings.append(msg)
        elif zone == "red":
            if inp.temperature <= sp.temp_lethal_low:
                msg = f"LETHAL: Temperature {inp.temperature}锟斤拷C is at or below lethal threshold ({sp.temp_lethal_low}锟斤拷C)"
            elif inp.temperature >= sp.temp_lethal_high:
                msg = f"LETHAL: Temperature {inp.temperature}锟斤拷C is at or above lethal threshold ({sp.temp_lethal_high}锟斤拷C)"
            else:
                msg = f"ALARM: Temperature {inp.temperature}锟斤拷C is outside safe range ({safe_min}锟紺{safe_max}锟斤拷C)"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="temperature",
            value=inp.temperature,
            unit="锟斤拷C",
            zone=_to_legacy_zone(zone),
            optimal_min=opt_min,
            optimal_max=opt_max,
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 Moisture 锟斤拷锟斤拷
    if inp.moisture is not None:
        opt_min = sp.moisture_optimal - 5.0
        opt_max = sp.moisture_optimal + 5.0
        safe_min = sp.moisture_min
        safe_max = sp.moisture_max

        zone = classify_zone(inp.moisture, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.moisture, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"Moisture {inp.moisture}% outside optimal ({opt_min}锟紺{opt_max}%)"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: Moisture {inp.moisture}% outside safe range ({safe_min}锟紺{safe_max}%)"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="moisture",
            value=inp.moisture,
            unit="%",
            zone=_to_legacy_zone(zone),
            optimal_min=opt_min,
            optimal_max=opt_max,
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 Feed Rate 锟斤拷锟斤拷
    if inp.feed_rate is not None:
        opt_min = sp.feed_rate_optimal * 0.8
        opt_max = sp.feed_rate_optimal * 1.2
        safe_min = sp.feed_rate_min
        safe_max = sp.feed_rate_max

        zone = classify_zone(inp.feed_rate, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.feed_rate, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"Feed rate {inp.feed_rate} g/larva/day outside optimal ({opt_min:.3f}锟紺{opt_max:.3f})"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: Feed rate {inp.feed_rate} g/larva/day outside safe range"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="feed_rate",
            value=inp.feed_rate,
            unit="g DM/larva/day",
            zone=_to_legacy_zone(zone),
            optimal_min=round(opt_min, 4),
            optimal_max=round(opt_max, 4),
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 Density 锟斤拷锟斤拷
    if inp.density is not None:
        opt_min = sp.density_optimal * 0.7
        opt_max = sp.density_optimal * 1.3
        safe_min = sp.density_min
        safe_max = sp.density_max

        zone = classify_zone(inp.density, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.density, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"Density {inp.density} larvae/m2 outside optimal ({opt_min:.0f}锟紺{opt_max:.0f})"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: Density {inp.density} larvae/m2 outside safe range"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="density",
            value=inp.density,
            unit="larvae/m2",
            zone=_to_legacy_zone(zone),
            optimal_min=round(opt_min, 0),
            optimal_max=round(opt_max, 0),
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 pH (if available) 锟斤拷锟斤拷
    if inp.ph is not None:
        # Generic acceptable range for organic substrates
        opt_min, opt_max = 6.0, 7.5
        safe_min, safe_max = 4.5, 9.0

        zone = classify_zone(inp.ph, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.ph, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"pH {inp.ph} outside optimal ({opt_min}锟紺{opt_max})"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: pH {inp.ph} outside safe range ({safe_min}锟紺{safe_max})"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="ph",
            value=inp.ph,
            unit="pH",
            zone=_to_legacy_zone(zone),
            optimal_min=opt_min,
            optimal_max=opt_max,
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 O2 Level (if available) 锟斤拷锟斤拷
    if inp.o2_level is not None:
        opt_min, opt_max = 18.0, 21.0
        safe_min, safe_max = 15.0, 21.0

        zone = classify_zone(inp.o2_level, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.o2_level, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"O? level {inp.o2_level}% below optimal"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: O? level {inp.o2_level}% critically low"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="o2_level",
            value=inp.o2_level,
            unit="%",
            zone=_to_legacy_zone(zone),
            optimal_min=opt_min,
            optimal_max=opt_max,
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 CO2 Level (if available) 锟斤拷锟斤拷
    if inp.co2_level is not None:
        opt_min, opt_max = 0.0, 2.0
        safe_min, safe_max = 0.0, 5.0

        zone = classify_zone(inp.co2_level, opt_min, opt_max, safe_min, safe_max)
        dev = deviation_from_optimal(inp.co2_level, opt_min, opt_max)

        msg = ""
        if zone == "yellow":
            msg = f"CO? level {inp.co2_level}% elevated"
            warnings.append(msg)
        elif zone == "red":
            msg = f"ALARM: CO? level {inp.co2_level}% dangerously high"
            alarms.append(msg)

        checks.append(EnvelopeCheck(
            parameter="co2_level",
            value=inp.co2_level,
            unit="%",
            zone=_to_legacy_zone(zone),
            optimal_min=opt_min,
            optimal_max=opt_max,
            safe_min=safe_min,
            safe_max=safe_max,
            deviation_pct=dev,
            message=msg,
        ))

    # 锟斤拷锟斤拷 Overall Assessment 锟斤拷锟斤拷
    if checks:
        zone_values = [ZONE_PRIORITY.get(c.zone, 1) for c in checks]
        max_zone_val = max(zone_values)
        worst_zone = {3: "red", 2: "yellow", 1: "green"}.get(max_zone_val, "green")
    else:
        worst_zone = "green"

    in_envelope = worst_zone != "red"
    overall_zone_legacy = {"green": "optimal", "yellow": "acceptable", "red": "critical"}.get(worst_zone, worst_zone)

    return FlightEnvelopeResult(
        overall_zone=overall_zone_legacy,
        checks=checks,
        in_envelope=in_envelope,
        warnings=warnings,
        alarms=alarms,
        species=inp.species,
    )


