"""
BOS Pipeline v9.0 - Stoichiometric Modeling Engine

Models insect bioconversion using simplified elemental balance
(C, H, O, N, S, P) and reaction-based accounting.

This revision expands substrate coverage to align with:
  - the supplied BOS manuscript campaigns, and
  - common public insect-bioconversion benchmark feedstocks.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


ENGINE_VERSION = "9.0.0"

# Typical elemental composition (mass fraction, dry basis)
# These are BOS screening defaults, not universal constants.
ELEMENT_COMPOSITIONS: Dict[str, Dict[str, float]] = {
    "substrate_generic": {"C": 0.45, "H": 0.065, "O": 0.40, "N": 0.025, "S": 0.003, "P": 0.005, "ash": 0.052},
    "substrate_food_waste": {"C": 0.48, "H": 0.070, "O": 0.35, "N": 0.030, "S": 0.002, "P": 0.004, "ash": 0.064},
    "substrate_manure": {"C": 0.35, "H": 0.050, "O": 0.30, "N": 0.035, "S": 0.005, "P": 0.010, "ash": 0.250},
    "substrate_distillers_grains": {"C": 0.47, "H": 0.068, "O": 0.30, "N": 0.045, "S": 0.004, "P": 0.008, "ash": 0.105},
    "substrate_brewery_spent_grains": {"C": 0.48, "H": 0.066, "O": 0.31, "N": 0.040, "S": 0.003, "P": 0.007, "ash": 0.094},
    "substrate_beer_lees": {"C": 0.45, "H": 0.067, "O": 0.32, "N": 0.038, "S": 0.003, "P": 0.007, "ash": 0.115},
    "substrate_straw": {"C": 0.49, "H": 0.060, "O": 0.41, "N": 0.008, "S": 0.001, "P": 0.001, "ash": 0.030},
    "substrate_tobacco_straw": {"C": 0.47, "H": 0.058, "O": 0.39, "N": 0.020, "S": 0.002, "P": 0.002, "ash": 0.058},
    "substrate_sewage_sludge": {"C": 0.32, "H": 0.050, "O": 0.22, "N": 0.050, "S": 0.010, "P": 0.020, "ash": 0.330},
    "substrate_straw_sludge": {"C": 0.40, "H": 0.055, "O": 0.31, "N": 0.030, "S": 0.006, "P": 0.011, "ash": 0.188},
    "bsf_larvae": {"C": 0.50, "H": 0.080, "O": 0.20, "N": 0.070, "S": 0.005, "P": 0.010, "ash": 0.085},
    "mealworm_larvae": {"C": 0.53, "H": 0.082, "O": 0.17, "N": 0.083, "S": 0.004, "P": 0.009, "ash": 0.042},
    "grub_larvae": {"C": 0.50, "H": 0.078, "O": 0.21, "N": 0.072, "S": 0.004, "P": 0.010, "ash": 0.082},
    "bsf_frass": {"C": 0.38, "H": 0.055, "O": 0.42, "N": 0.020, "S": 0.003, "P": 0.008, "ash": 0.114},
    "mealworm_frass": {"C": 0.40, "H": 0.057, "O": 0.39, "N": 0.025, "S": 0.003, "P": 0.007, "ash": 0.118},
    "grub_frass": {"C": 0.39, "H": 0.056, "O": 0.40, "N": 0.022, "S": 0.003, "P": 0.008, "ash": 0.121},
}

SPECIES_TO_BIOMASS_KEYS = {
    "BSF": ("bsf_larvae", "bsf_frass"),
    "BSFL": ("bsf_larvae", "bsf_frass"),
    "MW": ("mealworm_larvae", "mealworm_frass"),
    "YMW": ("mealworm_larvae", "mealworm_frass"),
    "PB": ("grub_larvae", "grub_frass"),
    "GRUB": ("grub_larvae", "grub_frass"),
}

# Atomic masses
M_C = 12.011
M_H = 1.008
M_O = 15.999
M_N = 14.007
M_S = 32.065
M_P = 30.974


@dataclass
class StoichiometryInput:
    """Input for stoichiometric analysis."""

    dm_in: float = 10.0
    dm_larvae: float = 2.5
    dm_frass: float = 6.0
    species: str = "BSF"

    substrate_composition: Optional[Dict[str, float]] = None
    larvae_composition: Optional[Dict[str, float]] = None
    frass_composition: Optional[Dict[str, float]] = None

    substrate_type: str = "substrate_generic"


@dataclass
class StoichiometryResult:
    """Stoichiometric analysis results."""

    carbon_balance: Dict[str, float] = field(default_factory=dict)
    nitrogen_balance: Dict[str, float] = field(default_factory=dict)
    phosphorus_balance: Dict[str, float] = field(default_factory=dict)

    carbon_closure: float = 0.0
    nitrogen_closure: float = 0.0
    phosphorus_closure: float = 0.0

    co2_produced_kg: float = 0.0
    h2o_produced_kg: float = 0.0
    nh3_emitted_kg: float = 0.0
    o2_consumed_kg: float = 0.0

    gamma_substrate: float = 0.0
    gamma_biomass: float = 0.0
    theoretical_yield: float = 0.0
    mass_balance_closure: float = 0.0
    engine_version: str = ENGINE_VERSION
    warnings: List[str] = field(default_factory=list)


def _resolve_species_biomass_keys(species: str) -> tuple[str, str]:
    return SPECIES_TO_BIOMASS_KEYS.get(species.upper(), ("bsf_larvae", "bsf_frass"))


def _degree_of_reduction(comp: Dict[str, float]) -> float:
    c = comp.get("C", 0) / M_C
    h = comp.get("H", 0) / M_H
    o = comp.get("O", 0) / M_O
    n = comp.get("N", 0) / M_N
    s = comp.get("S", 0) / M_S
    if c == 0:
        return 0.0
    return (4 * c + h - 2 * o - 3 * n + 6 * s) / c


def compute_stoichiometry(inp: StoichiometryInput) -> StoichiometryResult:
    """Compute elemental stoichiometric balance."""
    result = StoichiometryResult()

    larvae_key, frass_key = _resolve_species_biomass_keys(inp.species)
    sub_comp = inp.substrate_composition or ELEMENT_COMPOSITIONS.get(
        inp.substrate_type, ELEMENT_COMPOSITIONS["substrate_generic"]
    )
    lar_comp = inp.larvae_composition or ELEMENT_COMPOSITIONS[larvae_key]
    fra_comp = inp.frass_composition or ELEMENT_COMPOSITIONS[frass_key]

    for elem in ("C", "H", "O", "N", "S", "P"):
        elem_in = inp.dm_in * sub_comp.get(elem, 0)
        elem_larvae = inp.dm_larvae * lar_comp.get(elem, 0)
        elem_frass = inp.dm_frass * fra_comp.get(elem, 0)
        elem_gas = elem_in - elem_larvae - elem_frass

        if elem == "C":
            result.carbon_balance = {
                "input_substrate": round(elem_in, 6),
                "output_larvae": round(elem_larvae, 6),
                "output_frass": round(elem_frass, 6),
                "output_gas_co2": round(max(elem_gas, 0), 6),
            }
            result.carbon_closure = round((elem_larvae + elem_frass) / max(elem_in, 1e-10), 4)
            result.co2_produced_kg = round(max(elem_gas, 0) * (M_C + 2 * M_O) / M_C, 4)
        elif elem == "N":
            result.nitrogen_balance = {
                "input_substrate": round(elem_in, 6),
                "output_larvae": round(elem_larvae, 6),
                "output_frass": round(elem_frass, 6),
                "output_gas_nh3": round(max(elem_gas, 0), 6),
            }
            result.nitrogen_closure = round((elem_larvae + elem_frass) / max(elem_in, 1e-10), 4)
            result.nh3_emitted_kg = round(max(elem_gas, 0) * (M_N + 3 * M_H) / M_N, 4)
        elif elem == "P":
            result.phosphorus_balance = {
                "input_substrate": round(elem_in, 6),
                "output_larvae": round(elem_larvae, 6),
                "output_frass": round(elem_frass, 6),
            }
            result.phosphorus_closure = round((elem_larvae + elem_frass) / max(elem_in, 1e-10), 4)
        elif elem == "H":
            h_gas = max(elem_gas, 0)
            result.h2o_produced_kg = round(h_gas * (2 * M_H + M_O) / (2 * M_H), 4)

    o_in_co2 = result.co2_produced_kg * (2 * M_O) / (M_C + 2 * M_O) if result.co2_produced_kg > 0 else 0
    o_in_h2o = result.h2o_produced_kg * M_O / (2 * M_H + M_O) if result.h2o_produced_kg > 0 else 0
    o_from_sub = inp.dm_in * sub_comp.get("O", 0)
    o_in_larvae = inp.dm_larvae * lar_comp.get("O", 0)
    o_in_frass = inp.dm_frass * fra_comp.get("O", 0)
    result.o2_consumed_kg = round(max(o_in_co2 + o_in_h2o - o_from_sub + o_in_larvae + o_in_frass, 0), 4)

    result.gamma_substrate = round(_degree_of_reduction(sub_comp), 4)
    result.gamma_biomass = round(_degree_of_reduction(lar_comp), 4)

    c_sub = sub_comp.get("C", 0.45)
    c_lar = lar_comp.get("C", 0.50)
    if c_lar > 0:
        result.theoretical_yield = round(c_sub / c_lar, 4)

    total_out = inp.dm_larvae + inp.dm_frass + result.co2_produced_kg + result.h2o_produced_kg + result.nh3_emitted_kg
    if inp.dm_in > 0:
        total_in = inp.dm_in + result.o2_consumed_kg
        result.mass_balance_closure = round(total_out / max(total_in, 1e-10) * 100, 2)

    if result.carbon_closure < 0.80:
        result.warnings.append(f"Low carbon closure ({result.carbon_closure:.0%}). Unaccounted carbon losses.")
    if result.nitrogen_closure > 1.10:
        result.warnings.append(f"Nitrogen closure >110% ({result.nitrogen_closure:.0%}). Check measurements.")

    if inp.substrate_type in {"substrate_sewage_sludge", "substrate_straw_sludge"}:
        result.warnings.append(
            "Sludge-bearing substrate selected. Interpret stoichiometry together with contamination screening."
        )

    return result
