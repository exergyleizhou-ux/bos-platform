"""
BOS Pipeline v9.0 �� Stoichiometric Modeling Engine

Models the stoichiometry of insect bioconversion using elemental
balance (C, H, O, N, S, P) and reaction-based accounting.

Simplified overall reaction for BSF:
  Substrate(C_a H_b O_c N_d) + O? ��
    Biomass(C_e H_f O_g N_h) + CO? + H?O + NH? + Frass

Computes:
  - Elemental balance (C, N, P)
  - Theoretical yields
  - Oxygen demand
  - CO? production
  - Degree of reduction balance
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

ENGINE_VERSION = "9.0.0"

# Typical elemental composition (mass fraction)
# Based on published literature for BSF larvae and organic substrates

ELEMENT_COMPOSITIONS: Dict[str, Dict[str, float]] = {
    "substrate_generic": {"C": 0.45, "H": 0.065, "O": 0.40, "N": 0.025, "S": 0.003, "P": 0.005, "ash": 0.052},
    "substrate_food_waste": {"C": 0.48, "H": 0.070, "O": 0.35, "N": 0.030, "S": 0.002, "P": 0.004, "ash": 0.064},
    "substrate_manure": {"C": 0.35, "H": 0.050, "O": 0.30, "N": 0.035, "S": 0.005, "P": 0.010, "ash": 0.250},
    "bsf_larvae": {"C": 0.50, "H": 0.080, "O": 0.20, "N": 0.070, "S": 0.005, "P": 0.010, "ash": 0.085},
    "bsf_frass": {"C": 0.38, "H": 0.055, "O": 0.42, "N": 0.020, "S": 0.003, "P": 0.008, "ash": 0.114},
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

    dm_in: float = 10.0  # kg substrate DM
    dm_larvae: float = 2.5  # kg larvae DM
    dm_frass: float = 6.0  # kg frass DM

    # Custom compositions (override defaults)
    substrate_composition: Optional[Dict[str, float]] = None
    larvae_composition: Optional[Dict[str, float]] = None
    frass_composition: Optional[Dict[str, float]] = None

    substrate_type: str = "substrate_generic"


@dataclass
class StoichiometryResult:
    """Stoichiometric analysis results."""

    # Elemental balance (kg)
    carbon_balance: Dict[str, float] = field(default_factory=dict)
    nitrogen_balance: Dict[str, float] = field(default_factory=dict)
    phosphorus_balance: Dict[str, float] = field(default_factory=dict)

    # Closure fractions
    carbon_closure: float = 0.0  # Output/Input
    nitrogen_closure: float = 0.0
    phosphorus_closure: float = 0.0

    # Gas-phase estimates
    co2_produced_kg: float = 0.0  # kg CO?
    h2o_produced_kg: float = 0.0  # kg H?O
    nh3_emitted_kg: float = 0.0  # kg NH?

    # Oxygen demand
    o2_consumed_kg: float = 0.0  # kg O?

    # Degree of reduction
    gamma_substrate: float = 0.0  # Degree of reduction of substrate
    gamma_biomass: float = 0.0  # Degree of reduction of biomass

    # Theoretical maximum yield
    theoretical_yield: float = 0.0  # kg biomass / kg substrate (carbon-limited)

    # Summary
    mass_balance_closure: float = 0.0  # %
    engine_version: str = ENGINE_VERSION
    warnings: List[str] = field(default_factory=list)


def compute_stoichiometry(inp: StoichiometryInput) -> StoichiometryResult:
    """
    Compute elemental stoichiometric balance.

    Parameters
    ----------
    inp : StoichiometryInput
        Mass data and compositions.

    Returns
    -------
    StoichiometryResult
        Elemental balances and gas-phase estimates.
    """
    result = StoichiometryResult()

    # Get compositions
    sub_comp = inp.substrate_composition or ELEMENT_COMPOSITIONS.get(
        inp.substrate_type, ELEMENT_COMPOSITIONS["substrate_generic"]
    )
    lar_comp = inp.larvae_composition or ELEMENT_COMPOSITIONS["bsf_larvae"]
    fra_comp = inp.frass_composition or ELEMENT_COMPOSITIONS["bsf_frass"]

    # ���� Elemental flows (kg) ����
    elements = ["C", "H", "O", "N", "S", "P"]

    for elem in elements:
        elem_in = inp.dm_in * sub_comp.get(elem, 0)
        elem_larvae = inp.dm_larvae * lar_comp.get(elem, 0)
        elem_frass = inp.dm_frass * fra_comp.get(elem, 0)
        elem_gas = elem_in - elem_larvae - elem_frass  # Difference �� gas phase

        if elem == "C":
            result.carbon_balance = {
                "input_substrate": round(elem_in, 6),
                "output_larvae": round(elem_larvae, 6),
                "output_frass": round(elem_frass, 6),
                "output_gas_co2": round(max(elem_gas, 0), 6),
            }
            result.carbon_closure = round((elem_larvae + elem_frass) / max(elem_in, 1e-10), 4)
            # CO?: C + O? �� CO?
            result.co2_produced_kg = round(max(elem_gas, 0) * (M_C + 2 * M_O) / M_C, 4)

        elif elem == "N":
            result.nitrogen_balance = {
                "input_substrate": round(elem_in, 6),
                "output_larvae": round(elem_larvae, 6),
                "output_frass": round(elem_frass, 6),
                "output_gas_nh3": round(max(elem_gas, 0), 6),
            }
            result.nitrogen_closure = round((elem_larvae + elem_frass) / max(elem_in, 1e-10), 4)
            # NH?: N �� NH?
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

    # ���� Oxygen demand ����
    # O? consumed �� O in CO? + O in H?O - O from substrate
    o_in_co2 = result.co2_produced_kg * (2 * M_O) / (M_C + 2 * M_O) if result.co2_produced_kg > 0 else 0
    o_in_h2o = result.h2o_produced_kg * M_O / (2 * M_H + M_O) if result.h2o_produced_kg > 0 else 0
    o_from_sub = inp.dm_in * sub_comp.get("O", 0)
    o_in_larvae = inp.dm_larvae * lar_comp.get("O", 0)
    o_in_frass = inp.dm_frass * fra_comp.get("O", 0)
    result.o2_consumed_kg = round(max(o_in_co2 + o_in_h2o - o_from_sub + o_in_larvae + o_in_frass, 0), 4)

    # ���� Degree of reduction ����
    # �� = 4C + H - 2O - 3N + 6S + 5P (per C-mol basis, simplified)
    def _degree_of_reduction(comp: Dict[str, float]) -> float:
        c = comp.get("C", 0) / M_C
        h = comp.get("H", 0) / M_H
        o = comp.get("O", 0) / M_O
        n = comp.get("N", 0) / M_N
        s = comp.get("S", 0) / M_S
        if c == 0:
            return 0.0
        return (4 * c + h - 2 * o - 3 * n + 6 * s) / c

    result.gamma_substrate = round(_degree_of_reduction(sub_comp), 4)
    result.gamma_biomass = round(_degree_of_reduction(lar_comp), 4)

    # ���� Theoretical maximum yield (carbon-limited) ����
    c_sub = sub_comp.get("C", 0.45)
    c_lar = lar_comp.get("C", 0.50)
    if c_lar > 0:
        result.theoretical_yield = round(c_sub / c_lar, 4)

    # ���� Mass balance closure ����
    total_out = inp.dm_larvae + inp.dm_frass + result.co2_produced_kg + result.h2o_produced_kg + result.nh3_emitted_kg
    if inp.dm_in > 0:
        # Need to add O? consumed to inputs for full closure
        total_in = inp.dm_in + result.o2_consumed_kg
        result.mass_balance_closure = round(total_out / max(total_in, 1e-10) * 100, 2)

    # Warnings
    if result.carbon_closure < 0.80:
        result.warnings.append(f"Low carbon closure ({result.carbon_closure:.0%}). Unaccounted carbon losses.")
    if result.nitrogen_closure > 1.10:
        result.warnings.append(f"Nitrogen closure >110% ({result.nitrogen_closure:.0%}). Check measurements.")

    return result
