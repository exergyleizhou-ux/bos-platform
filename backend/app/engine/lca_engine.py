"""
BOS Pipeline v9.0 �� LCA Engine (Life Cycle Assessment)

Simplified cradle-to-gate life cycle assessment following ISO 14040/14044.

Impact categories (CML 2001 / ReCiPe midpoint):
  - GWP   : Global Warming Potential (kg CO?e)
  - AP    : Acidification Potential (kg SO?e)
  - EP    : Eutrophication Potential (kg PO?3?e)
  - POCP  : Photochemical Ozone Creation Potential (kg C?H?e)
  - ADP   : Abiotic Depletion Potential (kg Sbe)
  - CED   : Cumulative Energy Demand (MJ)
  - WF    : Water Footprint (L)
  - LU    : Land Use (m2��year)

The engine uses characterization factors from CML 2001 baseline for
consistency with existing insect farming literature.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

ENGINE_VERSION = "9.0.0"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Characterization Factors (per unit of stressor)
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

# Electricity (per kWh, EU average grid)
CF_ELEC = {
    "gwp": 0.45,        # kg CO?e
    "ap": 1.2e-3,       # kg SO?e
    "ep": 3.0e-4,       # kg PO?3?e
    "pocp": 5.0e-5,     # kg C?H?e
    "adp": 1.0e-7,      # kg Sbe
    "ced": 3.6,          # MJ (=1 kWh)
    "wf": 25.0,          # L
    "lu": 0.01,          # m2��yr
}

# Natural gas (per m3)
CF_GAS = {
    "gwp": 2.02,
    "ap": 2.0e-4,
    "ep": 5.0e-5,
    "pocp": 1.0e-4,
    "adp": 5.0e-6,
    "ced": 38.0,
    "wf": 0.5,
    "lu": 0.001,
}

# Transport (per t��km, truck)
CF_TRANSPORT = {
    "gwp": 6.2e-2,
    "ap": 3.0e-4,
    "ep": 8.0e-5,
    "pocp": 2.0e-5,
    "adp": 1.0e-8,
    "ced": 0.85,
    "wf": 0.1,
    "lu": 0.005,
}

# Substrate production (per kg DM, mixed organic waste �� low impact)
CF_SUBSTRATE = {
    "gwp": 0.10,
    "ap": 5.0e-4,
    "ep": 2.0e-4,
    "pocp": 1.0e-5,
    "adp": 1.0e-8,
    "ced": 1.5,
    "wf": 50.0,
    "lu": 0.5,
}

# Direct process emissions (per kg substrate DM processed)
CF_PROCESS = {
    "gwp": 0.14,   # CH? + N?O
    "ap": 8.0e-4,  # NH?
    "ep": 3.0e-4,  # N leaching
    "pocp": 0.0,
    "adp": 0.0,
    "ced": 0.0,
    "wf": 5.0,
    "lu": 0.0,
}

IMPACT_CATEGORIES = ["gwp", "ap", "ep", "pocp", "adp", "ced", "wf", "lu"]

IMPACT_UNITS = {
    "gwp": "kg CO?e",
    "ap": "kg SO?e",
    "ep": "kg PO?3?e",
    "pocp": "kg C?H?e",
    "adp": "kg Sbe",
    "ced": "MJ",
    "wf": "L",
    "lu": "m2��yr",
}

IMPACT_NAMES = {
    "gwp": "Global Warming Potential",
    "ap": "Acidification Potential",
    "ep": "Eutrophication Potential",
    "pocp": "Photochemical Ozone Creation",
    "adp": "Abiotic Depletion",
    "ced": "Cumulative Energy Demand",
    "wf": "Water Footprint",
    "lu": "Land Use",
}


@dataclass
class LCAInput:
    """Input parameters for LCA calculation."""

    dm_in: float = 0.0        # kg substrate DM
    dm_out_larvae: float = 0.0
    dm_out_frass: float = 0.0

    electricity_kwh: float = 0.0
    natural_gas_m3: float = 0.0
    transport_tkm: float = 0.0  # tonne-kilometers

    protein_content: float = 42.0  # % DM
    functional_unit: str = "kg_protein"  # "kg_larvae", "kg_protein", "tonne_substrate"


@dataclass
class LCAResult:
    """LCA results across all impact categories."""

    # Absolute impacts
    impacts: Dict[str, float] = field(default_factory=dict)

    # Impacts per functional unit
    impacts_per_fu: Dict[str, float] = field(default_factory=dict)
    functional_unit: str = "kg_protein"
    functional_unit_value: float = 0.0

    # Contribution analysis (which life cycle stage dominates)
    contributions: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Normalization (optional, relative to EU person-year)
    normalized: Dict[str, float] = field(default_factory=dict)

    # Units
    units: Dict[str, str] = field(default_factory=lambda: dict(IMPACT_UNITS))
    names: Dict[str, str] = field(default_factory=lambda: dict(IMPACT_NAMES))

    engine_version: str = ENGINE_VERSION


def compute_lca(inp: LCAInput) -> LCAResult:
    """
    Compute simplified cradle-to-gate LCA.

    Parameters
    ----------
    inp : LCAInput
        Process inputs and functional unit choice.

    Returns
    -------
    LCAResult
        Multi-category impact assessment.
    """
    result = LCAResult(functional_unit=inp.functional_unit)

    # ���� Calculate impacts from each life cycle stage ����
    stages = {
        "Substrate production": {cat: inp.dm_in * CF_SUBSTRATE[cat] for cat in IMPACT_CATEGORIES},
        "Process emissions": {cat: inp.dm_in * CF_PROCESS[cat] for cat in IMPACT_CATEGORIES},
        "Electricity": {cat: inp.electricity_kwh * CF_ELEC[cat] for cat in IMPACT_CATEGORIES},
        "Natural gas": {cat: inp.natural_gas_m3 * CF_GAS[cat] for cat in IMPACT_CATEGORIES},
        "Transport": {cat: inp.transport_tkm * CF_TRANSPORT[cat] for cat in IMPACT_CATEGORIES},
    }

    # ���� Sum across stages ����
    total_impacts: Dict[str, float] = {}
    for cat in IMPACT_CATEGORIES:
        total_impacts[cat] = round(sum(stages[stage][cat] for stage in stages), 6)

    result.impacts = total_impacts

    # ���� Contribution analysis ����
    for cat in IMPACT_CATEGORIES:
        total = total_impacts[cat]
        if total > 0:
            result.contributions[cat] = {
                stage: round(stages[stage][cat] / total * 100, 2) for stage in stages
            }
        else:
            result.contributions[cat] = {stage: 0.0 for stage in stages}

    # ���� Functional unit ����
    if inp.functional_unit == "kg_protein":
        fu_value = inp.dm_out_larvae * (inp.protein_content / 100)
    elif inp.functional_unit == "kg_larvae":
        fu_value = inp.dm_out_larvae
    elif inp.functional_unit == "tonne_substrate":
        fu_value = inp.dm_in / 1000
    else:
        fu_value = inp.dm_out_larvae  # default

    result.functional_unit_value = round(fu_value, 4)

    if fu_value > 0:
        result.impacts_per_fu = {cat: round(v / fu_value, 6) for cat, v in total_impacts.items()}
    else:
        result.impacts_per_fu = {cat: 0.0 for cat in IMPACT_CATEGORIES}

    # ���� Normalization (EU person-year equivalents) ����
    # EU normalization factors (CML 2001, per person per year)
    norm_factors = {
        "gwp": 8100.0,
        "ap": 36.0,
        "ep": 13.0,
        "pocp": 7.6,
        "adp": 0.095,
        "ced": 150_000.0,
        "wf": 1_200_000.0,
        "lu": 5_500.0,
    }

    result.normalized = {}
    for cat in IMPACT_CATEGORIES:
        nf = norm_factors.get(cat, 1.0)
        result.normalized[cat] = round(total_impacts[cat] / nf * 1000, 4)  # milli-person-years

    return result
