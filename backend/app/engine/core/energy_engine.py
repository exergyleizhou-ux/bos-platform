"""
BOS Pipeline v9.0 energy balance engine.

Computes the energy balance for insect bioconversion operations.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

ENGINE_VERSION = "9.0.0"

ED_SUBSTRATE = 18.0
ED_LARVAE = 25.0
ED_FRASS = 14.0
ED_PROTEIN = 23.6
ED_FAT = 39.6
ED_CARBOHYDRATE = 17.2
ED_CHITIN = 17.0

KWH_TO_MJ = 3.6
M3_GAS_TO_MJ = 38.0
L_DIESEL_TO_MJ = 38.6


@dataclass
class EnergyInput:
    """Input parameters for energy balance calculation."""

    dm_in: float = 0.0
    dm_out: float = 0.0  # Legacy alias
    dm_out_larvae: float = 0.0
    dm_out_frass: float = 0.0

    protein_content: float = 42.0
    fat_content: float = 35.0
    chitin_content: float = 8.0

    electricity_heating: float = 0.0
    heating_kwh: float = 0.0  # Legacy alias
    electricity_ventilation: float = 0.0
    electricity_lighting: float = 0.0
    electricity_pumps: float = 0.0
    electricity_drying: float = 0.0
    electricity_other: float = 0.0
    electricity_kwh: float = 0.0  # Legacy alias
    mechanical_kwh: float = 0.0  # Legacy alias

    natural_gas_m3: float = 0.0
    diesel_liters: float = 0.0
    biomass_fuel_kg: float = 0.0
    biomass_energy_density: float = 16.0
    renewable_fraction: float = 0.0

    batch_days: float = 14.0
    substrate_energy_density: Optional[float] = None
    larvae_energy_density: Optional[float] = None


@dataclass
class EnergyResult:
    """Energy balance calculation results."""

    chemical_energy_in: float = 0.0
    electrical_energy_in: float = 0.0
    thermal_energy_in: float = 0.0
    total_energy_in: float = 0.0
    total_input_energy: float = 0.0

    electricity_breakdown: Dict[str, float] = field(default_factory=dict)

    chemical_energy_larvae: float = 0.0
    chemical_energy_frass: float = 0.0
    total_chemical_energy_out: float = 0.0
    total_output_energy: float = 0.0

    metabolic_heat_loss: float = 0.0
    energy_loss: float = 0.0
    net_energy: float = 0.0

    eroi: float = 0.0
    eroi_operational: float = 0.0
    energy_efficiency: float = 0.0
    specific_energy: float = 0.0
    specific_energy_per_protein: float = 0.0

    breakdown_in: Dict[str, float] = field(default_factory=dict)
    breakdown_out: Dict[str, float] = field(default_factory=dict)

    per_kg_larvae: float = 0.0
    electrical_energy: float = 0.0
    thermal_energy: float = 0.0
    mechanical_energy: float = 0.0
    fossil_energy: float = 0.0
    renewable_energy: float = 0.0

    engine_version: str = ENGINE_VERSION


def compute_energy_balance(inp: EnergyInput) -> EnergyResult:
    """Compute the full energy balance for a batch."""
    result = EnergyResult()

    dm_out_larvae = inp.dm_out_larvae if inp.dm_out_larvae > 0 else inp.dm_out
    electricity_heating = inp.electricity_heating
    electricity_other = inp.electricity_other + inp.electricity_kwh
    electricity_pumps = inp.electricity_pumps + inp.mechanical_kwh
    thermal_from_heating = inp.heating_kwh * KWH_TO_MJ

    sub_ed = inp.substrate_energy_density or ED_SUBSTRATE
    lar_ed = inp.larvae_energy_density or ED_LARVAE

    result.chemical_energy_in = round(inp.dm_in * sub_ed, 4)

    elec_kwh = (
        electricity_heating
        + inp.electricity_ventilation
        + inp.electricity_lighting
        + electricity_pumps
        + inp.electricity_drying
        + electricity_other
    )
    result.electrical_energy_in = round(elec_kwh * KWH_TO_MJ, 4)
    result.electrical_energy = result.electrical_energy_in
    result.mechanical_energy = round(inp.mechanical_kwh * KWH_TO_MJ, 4)

    gas_mj = inp.natural_gas_m3 * M3_GAS_TO_MJ
    diesel_mj = inp.diesel_liters * L_DIESEL_TO_MJ
    biomass_mj = inp.biomass_fuel_kg * inp.biomass_energy_density
    result.thermal_energy_in = round(gas_mj + diesel_mj + biomass_mj + thermal_from_heating, 4)
    result.thermal_energy = result.thermal_energy_in

    result.total_energy_in = round(
        result.chemical_energy_in + result.electrical_energy_in + result.thermal_energy_in,
        4,
    )
    result.total_input_energy = result.total_energy_in

    protein_energy = dm_out_larvae * (inp.protein_content / 100) * ED_PROTEIN
    fat_energy = dm_out_larvae * (inp.fat_content / 100) * ED_FAT
    chitin_energy = dm_out_larvae * (inp.chitin_content / 100) * ED_CHITIN
    remaining_pct = max(100 - inp.protein_content - inp.fat_content - inp.chitin_content, 0)
    carb_energy = dm_out_larvae * (remaining_pct / 100) * ED_CARBOHYDRATE

    result.chemical_energy_larvae = round(
        protein_energy + fat_energy + chitin_energy + carb_energy,
        4,
    )
    result.chemical_energy_frass = round(inp.dm_out_frass * ED_FRASS, 4)
    result.total_chemical_energy_out = round(
        result.chemical_energy_larvae + result.chemical_energy_frass,
        4,
    )
    result.total_output_energy = result.total_chemical_energy_out

    result.metabolic_heat_loss = round(result.chemical_energy_in - result.total_chemical_energy_out, 4)
    result.energy_loss = round(result.total_energy_in - result.total_chemical_energy_out, 4)
    result.net_energy = round(result.total_chemical_energy_out - result.total_energy_in, 4)

    operational_in = result.electrical_energy_in + result.thermal_energy_in
    if operational_in > 0:
        result.eroi_operational = round(result.total_chemical_energy_out / operational_in, 4)
    if result.total_energy_in > 0:
        result.energy_efficiency = result.total_chemical_energy_out / result.total_energy_in
        result.eroi = result.energy_efficiency

    if dm_out_larvae > 0:
        result.specific_energy = round(elec_kwh / dm_out_larvae, 4)
        result.per_kg_larvae = result.specific_energy
        protein_kg = dm_out_larvae * (inp.protein_content / 100)
        if protein_kg > 0:
            result.specific_energy_per_protein = round(elec_kwh / protein_kg, 4)

    renewable_fraction = min(max(inp.renewable_fraction, 0.0), 1.0)
    result.renewable_energy = round(result.total_energy_in * renewable_fraction, 4)
    result.fossil_energy = round(result.total_energy_in - result.renewable_energy, 4)

    result.electricity_breakdown = {
        "Heating": round(electricity_heating * KWH_TO_MJ, 4),
        "Ventilation": round(inp.electricity_ventilation * KWH_TO_MJ, 4),
        "Lighting": round(inp.electricity_lighting * KWH_TO_MJ, 4),
        "Pumps": round(electricity_pumps * KWH_TO_MJ, 4),
        "Drying": round(inp.electricity_drying * KWH_TO_MJ, 4),
        "Other": round(electricity_other * KWH_TO_MJ, 4),
    }

    result.breakdown_in = {
        "Chemical (substrate)": result.chemical_energy_in,
        "Electrical": result.electrical_energy_in,
        "Thermal (heating)": round(thermal_from_heating, 4),
        "Thermal (gas)": round(gas_mj, 4),
        "Thermal (diesel)": round(diesel_mj, 4),
        "Thermal (biomass)": round(biomass_mj, 4),
    }
    result.breakdown_out = {
        "Chemical (larvae)": result.chemical_energy_larvae,
        "Chemical (frass)": result.chemical_energy_frass,
        "Metabolic heat loss": max(result.metabolic_heat_loss, 0),
    }

    return result
