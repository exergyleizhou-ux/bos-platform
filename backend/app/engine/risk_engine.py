"""
BOS Pipeline v9.0 �� Risk Engine (Contaminant Risk Assessment)

Assesses food/feed safety risks for insect products based on
heavy metals, pesticides, mycotoxins, and microbial contaminants.

Follows EU Novel Food Regulation (EU 2015/2283) and
EFSA guidelines on insects as food/feed.

Risk levels:
  - NEGLIGIBLE : Well below regulatory limits
  - LOW        : Below limits with adequate margin
  - MEDIUM     : Approaching limits (��50% of limit)
  - HIGH       : Near or exceeding limits (��80% of limit)
  - CRITICAL   : Exceeds regulatory limits
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

ENGINE_VERSION = "9.0.0"


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Regulatory Limits (mg/kg DM unless noted)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

# Heavy metals �� EU feed materials regulation (EC 2002/32 + amendments)
HEAVY_METAL_LIMITS: Dict[str, float] = {
    "lead": 5.0,       # Pb
    "cadmium": 2.0,    # Cd
    "mercury": 0.1,    # Hg
    "arsenic": 2.0,    # As (inorganic)
    "chromium": 5.0,   # Cr
    "nickel": 10.0,    # Ni
    "zinc": 150.0,     # Zn (for complete feed)
    "copper": 25.0,    # Cu (for complete feed)
}

# Pesticide residues �� EU MRLs (EC 396/2005)
PESTICIDE_LIMITS: Dict[str, float] = {
    "chlorpyrifos": 0.01,
    "ddt_total": 0.05,
    "lindane": 0.01,
    "dieldrin": 0.01,
    "endosulfan": 0.05,
    "glyphosate": 0.10,
    "default_mrl": 0.01,  # Default MRL when specific limit unavailable
}

# Mycotoxins �� EU regulation (EC 2002/32)
MYCOTOXIN_LIMITS: Dict[str, float] = {
    "aflatoxin_b1": 0.02,   # mg/kg
    "aflatoxin_total": 0.04,
    "deoxynivalenol": 8.0,
    "zearalenone": 3.0,
    "ochratoxin_a": 0.25,
    "fumonisin": 60.0,
}

# Microbial limits �� EU feed hygiene (EC 183/2005)
MICROBIAL_LIMITS: Dict[str, float] = {
    "salmonella_25g": 0.0,        # Absent in 25g (0 = absent required)
    "enterobacteriaceae": 300.0,  # CFU/g
    "total_plate_count": 1e6,     # CFU/g
    "e_coli": 100.0,              # CFU/g
    "listeria_25g": 0.0,          # Absent in 25g
    "clostridium": 100.0,         # CFU/g
}


@dataclass
class ContaminantReading:
    """Single contaminant measurement."""

    name: str
    value: float
    unit: str = "mg/kg"
    category: str = "heavy_metal"  # heavy_metal, pesticide, mycotoxin, microbial


@dataclass
class RiskCheckResult:
    """Risk assessment for a single contaminant."""

    name: str
    value: float
    limit: float
    unit: str
    ratio: float  # value / limit
    risk_level: str  # NEGLIGIBLE, LOW, MEDIUM, HIGH, CRITICAL
    category: str
    message: str = ""
    recommendation: str = ""


@dataclass
class RiskInput:
    """Input parameters for risk assessment."""

    contaminants: List[ContaminantReading] = field(default_factory=list)
    species: str = "BSF"
    product_use: str = "feed"  # "feed", "food", "fertilizer"
    substrate_type: str = "mixed_organic_waste"


@dataclass
class RiskResult:
    """Complete risk assessment results."""

    overall_risk: str = "NEGLIGIBLE"  # Worst case across all checks
    overall_safe: bool = True
    checks: List[RiskCheckResult] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    regulatory_framework: str = "EU Novel Food + Feed Hygiene"
    engine_version: str = ENGINE_VERSION


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Risk Classification
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

RISK_LEVELS = ["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_PRIORITY = {level: i for i, level in enumerate(RISK_LEVELS)}


def classify_risk(ratio: float) -> str:
    """Classify risk based on value/limit ratio."""
    if ratio <= 0.0:
        return "NEGLIGIBLE"
    elif ratio < 0.25:
        return "NEGLIGIBLE"
    elif ratio < 0.50:
        return "LOW"
    elif ratio < 0.80:
        return "MEDIUM"
    elif ratio < 1.0:
        return "HIGH"
    else:
        return "CRITICAL"


def _get_limit(reading: ContaminantReading) -> Tuple[float, str]:
    """Get regulatory limit for a contaminant."""
    name_lower = reading.name.lower().replace(" ", "_")

    if reading.category == "heavy_metal":
        limit = HEAVY_METAL_LIMITS.get(name_lower)
        if limit is not None:
            return limit, "EU EC 2002/32"
    elif reading.category == "pesticide":
        limit = PESTICIDE_LIMITS.get(name_lower, PESTICIDE_LIMITS["default_mrl"])
        return limit, "EU EC 396/2005"
    elif reading.category == "mycotoxin":
        limit = MYCOTOXIN_LIMITS.get(name_lower)
        if limit is not None:
            return limit, "EU EC 2002/32"
    elif reading.category == "microbial":
        limit = MICROBIAL_LIMITS.get(name_lower)
        if limit is not None:
            return limit, "EU EC 183/2005"

    return 0.0, "No limit found"


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Main Assessment
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def assess_risk(inp: RiskInput) -> RiskResult:
    """
    Perform contaminant risk assessment.

    Parameters
    ----------
    inp : RiskInput
        List of contaminant readings and context.

    Returns
    -------
    RiskResult
        Per-contaminant risk levels and overall safety assessment.
    """
    result = RiskResult()
    worst_risk = "NEGLIGIBLE"

    for reading in inp.contaminants:
        limit, regulation = _get_limit(reading)
        if inp.product_use == "food" and limit > 0:
            # Legacy behavior: food-grade limits are stricter than feed.
            limit *= 0.8

        if limit <= 0:
            # Special case: absent requirement (e.g., Salmonella)
            if reading.value > 0:
                ratio = 2.0  # Auto-critical
            else:
                ratio = 0.0
        else:
            ratio = reading.value / limit

        risk_level = classify_risk(ratio)

        # Generate message
        msg = f"{reading.name}: {reading.value} {reading.unit}"
        if limit > 0:
            msg += f" (limit: {limit} {reading.unit}, ratio: {ratio:.2f})"
        elif reading.value > 0:
            msg += f" �� must be absent per {regulation}"

        # Generate recommendation
        rec = ""
        if risk_level == "CRITICAL":
            rec = f"REJECT: {reading.name} exceeds regulatory limit. Do not use product."
            result.critical_count += 1
        elif risk_level == "HIGH":
            rec = f"CAUTION: {reading.name} near limit ({ratio:.0%}). Increase testing frequency."
            result.high_count += 1
        elif risk_level == "MEDIUM":
            rec = f"MONITOR: {reading.name} at {ratio:.0%} of limit. Review substrate sourcing."
            result.medium_count += 1

        check = RiskCheckResult(
            name=reading.name,
            value=reading.value,
            limit=limit,
            unit=reading.unit,
            ratio=round(ratio, 4),
            risk_level=risk_level.lower(),
            category=reading.category,
            message=msg,
            recommendation=rec,
        )
        result.checks.append(check)

        # Track worst
        if RISK_PRIORITY.get(risk_level, 0) > RISK_PRIORITY.get(worst_risk, 0):
            worst_risk = risk_level

    result.overall_risk = worst_risk.lower()
    result.overall_safe = worst_risk not in ("HIGH", "CRITICAL")

    # Overall recommendations
    if result.critical_count > 0:
        result.recommendations.append(
            f"? {result.critical_count} contaminant(s) exceed regulatory limits. Product is NOT SAFE for use as {inp.product_use}."
        )
    elif result.high_count > 0:
        result.recommendations.append(
            f"?? {result.high_count} contaminant(s) near regulatory limits. Implement corrective actions."
        )
    elif result.medium_count > 0:
        result.recommendations.append(
            f"?? {result.medium_count} contaminant(s) at moderate levels. Continue routine monitoring."
        )
    else:
        result.recommendations.append("? All contaminants well within regulatory limits.")

    # Substrate-specific warnings
    if inp.substrate_type in ("sewage_sludge", "animal_waste"):
        result.warnings.append(
            f"Substrate type '{inp.substrate_type}' has elevated contamination risk. "
            "Increase heavy metal and pathogen testing frequency."
        )

    if inp.product_use == "food":
        result.warnings.append(
            "Product intended for human consumption �� stricter limits may apply under EU Novel Food Regulation (EU 2015/2283). "
            "Consult national competent authority."
        )

    return result

