"""
BOS Pipeline v9.0 闁?Risk Engine (Contaminant Risk Assessment)

Assesses food/feed safety risks for insect products based on
heavy metals, pesticides, mycotoxins, and microbial contaminants.

Follows EU Novel Food Regulation (EU 2015/2283) and
EFSA guidelines on insects as food/feed.

Risk levels:
  - NEGLIGIBLE : Well below regulatory limits
  - LOW        : Below limits with adequate margin
  - MEDIUM     : Approaching limits (闁?0% of limit)
  - HIGH       : Near or exceeding limits (闁?0% of limit)
  - CRITICAL   : Exceeds regulatory limits
"""

from dataclasses import dataclass, field

ENGINE_VERSION = "9.0.0"


# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?
# Regulatory Limits (mg/kg DM unless noted)
# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?

# Heavy metals 闁?EU feed materials regulation (EC 2002/32 + amendments)
HEAVY_METAL_LIMITS: dict[str, float] = {
    "lead": 5.0,  # Pb
    "cadmium": 2.0,  # Cd
    "mercury": 0.1,  # Hg
    "arsenic": 2.0,  # As (inorganic)
    "chromium": 5.0,  # Cr
    "nickel": 10.0,  # Ni
    "zinc": 150.0,  # Zn (for complete feed)
    "copper": 25.0,  # Cu (for complete feed)
}

# Pesticide residues 闁?EU MRLs (EC 396/2005)
PESTICIDE_LIMITS: dict[str, float] = {
    "chlorpyrifos": 0.01,
    "ddt_total": 0.05,
    "lindane": 0.01,
    "dieldrin": 0.01,
    "endosulfan": 0.05,
    "glyphosate": 0.10,
    "default_mrl": 0.01,  # Default MRL when specific limit unavailable
}

# Mycotoxins 闁?EU regulation (EC 2002/32)
MYCOTOXIN_LIMITS: dict[str, float] = {
    "aflatoxin_b1": 0.02,  # mg/kg
    "aflatoxin_total": 0.04,
    "deoxynivalenol": 8.0,
    "zearalenone": 3.0,
    "ochratoxin_a": 0.25,
    "fumonisin": 60.0,
}

# Microbial limits 闁?EU feed hygiene (EC 183/2005)
MICROBIAL_LIMITS: dict[str, float] = {
    "salmonella_25g": 0.0,  # Absent in 25g (0 = absent required)
    "enterobacteriaceae": 300.0,  # CFU/g
    "total_plate_count": 1e6,  # CFU/g
    "e_coli": 100.0,  # CFU/g
    "listeria_25g": 0.0,  # Absent in 25g
    "clostridium": 100.0,  # CFU/g
}

SUBSTRATE_RISK_PROFILES: dict[str, dict[str, object]] = {
    "mixed_organic_waste": {
        "label": "Mixed organic waste",
        "heavy_metal_risk": "medium",
        "pathogen_risk": "medium",
        "notes": "Default mixed stream. Use routine heavy-metal, pathogen, and mycotoxin monitoring.",
        "references": (
            "EU Novel Food Regulation (EU 2015/2283).",
            "EU feed hygiene framework (EC 183/2005).",
        ),
    },
    "distillers_grains": {
        "label": "Distillers grains / distillery side stream",
        "heavy_metal_risk": "low",
        "pathogen_risk": "low",
        "notes": "Generally lower contamination risk than sludge-bearing streams, but moisture and storage hygiene still matter.",
        "references": (
            "Supplied BOS manuscript: core relay on distillers grains and side-stream framing.",
            "Historical Perspective on Distillers Grains. DOI:10.1201/b11047-9",
        ),
    },
    "brewery_spent_grains": {
        "label": "Brewery spent grains / beer lees",
        "heavy_metal_risk": "low",
        "pathogen_risk": "low",
        "notes": "Spoilage and mycotoxin risks can rise quickly if storage is not controlled.",
        "references": (
            "Supplied BOS manuscript: beer-lees moisture-gradient campaign.",
        ),
    },
    "crop_residue": {
        "label": "Crop residue / straw",
        "heavy_metal_risk": "low",
        "pathogen_risk": "low",
        "notes": "Usually cleaner on heavy metals, but pesticide carry-over and lignocellulose severity should be reviewed.",
        "references": (
            "Review of the pretreatment and bioconversion of lignocellulosic biomass from wheat straw materials. DOI:10.1016/j.rser.2018.03.113",
        ),
    },
    "straw_sludge_blend": {
        "label": "Straw-sludge blend",
        "heavy_metal_risk": "high",
        "pathogen_risk": "high",
        "notes": "Blend inherits sludge-side contamination risk and needs tighter contaminant screening.",
        "references": (
            "Supplied BOS manuscript: straw-sludge co-conversion series with initial C/N 9.25-15.51.",
        ),
    },
    "sewage_sludge": {
        "label": "Sewage sludge",
        "heavy_metal_risk": "critical",
        "pathogen_risk": "critical",
        "notes": "Highest-priority contamination stream. Increase heavy-metal and pathogen testing frequency.",
        "references": (
            "Heavy Metal Contamination of Soil with Domestic Sewage Sludge. DOI:10.1201/9781482280173-5",
            "Supplied BOS manuscript: sludge-focused trial and heavy-metal screening context.",
        ),
    },
    "animal_waste": {
        "label": "Animal waste / manure",
        "heavy_metal_risk": "medium",
        "pathogen_risk": "high",
        "notes": "Pathogen burden is usually more important than metals; review residue and veterinary drug exposure.",
        "references": (
            "EU feed hygiene framework (EC 183/2005).",
        ),
    },
    "tcm_residue": {
        "label": "Traditional Chinese medicine residue",
        "heavy_metal_risk": "medium",
        "pathogen_risk": "low",
        "notes": "Track phytochemical carry-over, lot identity, and medicinal residue provenance explicitly.",
        "references": (
            "Supplied BOS manuscript: TCM residue compatibility screen and licorice-focused discussion.",
        ),
    },
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

    contaminants: list[ContaminantReading] = field(default_factory=list)
    species: str = "BSF"
    product_use: str = "feed"  # "feed", "food", "fertilizer"
    substrate_type: str = "mixed_organic_waste"


@dataclass
class RiskResult:
    """Complete risk assessment results."""

    overall_risk: str = "NEGLIGIBLE"  # Worst case across all checks
    overall_safe: bool = True
    checks: list[RiskCheckResult] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    substrate_profile: dict[str, object] = field(default_factory=dict)
    regulatory_framework: str = "EU Novel Food + Feed Hygiene"
    engine_version: str = ENGINE_VERSION


# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?
# Risk Classification
# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?

RISK_LEVELS = ["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_PRIORITY = {level: i for i, level in enumerate(RISK_LEVELS)}


def _public_risk_level(level: str) -> str:
    """Return the legacy-compatible lowercase risk label for API/test consumers."""
    return level.lower()


def classify_risk(ratio: float) -> str:
    """Classify risk based on value/limit ratio."""
    if ratio <= 0.0 or ratio < 0.25:
        return "NEGLIGIBLE"
    elif ratio < 0.50:
        return "LOW"
    elif ratio < 0.80:
        return "MEDIUM"
    elif ratio < 1.0:
        return "HIGH"
    else:
        return "CRITICAL"


def _get_limit(reading: ContaminantReading) -> tuple[float, str]:
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


# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?
# Main Assessment
# 闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩￠幇銊︽珳闁崇儤鍔忛弲鏌ュ煛閹般劍娅滈柍鐑樺姀閺呮煡鍩?


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

        ratio = (2.0 if reading.value > 0 else 0.0) if limit <= 0 else reading.value / limit

        risk_level = classify_risk(ratio)

        # Generate message
        msg = f"{reading.name}: {reading.value} {reading.unit}"
        if limit > 0:
            msg += f" (limit: {limit} {reading.unit}, ratio: {ratio:.2f})"
        elif reading.value > 0:
            msg += f" - must be absent per {regulation}"

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
            risk_level=_public_risk_level(risk_level),
            category=reading.category,
            message=msg,
            recommendation=rec,
        )
        result.checks.append(check)

        # Track worst
        if RISK_PRIORITY.get(risk_level, 0) > RISK_PRIORITY.get(worst_risk, 0):
            worst_risk = risk_level

    result.overall_risk = _public_risk_level(worst_risk)
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

    result.substrate_profile = {
        "key": inp.substrate_type,
        **SUBSTRATE_RISK_PROFILES.get(
            inp.substrate_type,
            SUBSTRATE_RISK_PROFILES["mixed_organic_waste"],
        ),
    }

    # Substrate-specific warnings
    if inp.substrate_type in ("sewage_sludge", "animal_waste", "straw_sludge_blend"):
        result.warnings.append(
            f"Substrate type '{inp.substrate_type}' has elevated contamination risk. "
            "Increase heavy metal and pathogen testing frequency."
        )

    if inp.substrate_type in ("distillers_grains", "brewery_spent_grains"):
        result.warnings.append(
            "Wet distillery and brewery side streams should be screened for spoilage and mycotoxins if storage is prolonged."
        )

    if inp.substrate_type == "tcm_residue":
        result.warnings.append(
            "Medicinal-plant residues should carry lot-level provenance and phytochemical marker tracking."
        )

    if inp.product_use == "food":
        result.warnings.append(
            "Product intended for human consumption - stricter limits may apply under EU Novel Food Regulation (EU 2015/2283). "
            "Consult national competent authority."
        )

    return result
