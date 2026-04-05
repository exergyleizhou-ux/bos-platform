"""
BOS Pipeline v9.0 �� Energy Balance Engine

Computes the full energy balance for insect bioconversion operations,
including:
  - Energy inputs  : heating, ventilation, lighting, pumps, drying
  - Energy outputs : chemical energy in larvae (protein + fat), frass
  - Energy Return on Investment (EROI)
  - Specific energy consumption (kWh / kg output)

All energy in MJ unless otherwise noted.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

ENGINE_VERSION = "9.0.0"

# Energy density factors (MJ / kg DM)
ED_SUBSTRATE = 18.0  # Typical mixed organic waste
ED_LARVAE = 25.0  # BSF larvae (high fat content)
ED_FRASS = 14.0  # Composted frass
ED_PROTEIN = 23.6  # Protein energy density
ED_FAT = 39.6  # Fat energy density
ED_CARBOHYDRATE = 17.2  # Carbohydrate energy density
ED_CHITIN = 17.0  # Chitin energy density

# Conversion factors
KWH_TO_MJ = 3.6
MJ_TO_KWH = 1 / 3.6
M3_GAS_TO_MJ = 38.0  # Natural gas (HHV)
L_DIESEL_TO_MJ = 38.6  # Diesel fuel


@dataclass
class EnergyInput:
    """Input parameters for energy balance calculation."""

    # Batch mass (kg DM)
    dm_in: float = 0.0
    dm_out_larvae: float = 0.0
    dm_out_frass: float = 0.0
    dm_out: Optional[float] = None  # Legacy alias for dm_out_larvae

    # Larval composition (% DM)
    protein_content: float = 42.0
    fat_content: float = 35.0
    chitin_content: float = 8.0

    # Energy consumption (kWh unless noted)
    electricity_heating: float = 0.0  # kWh
    electricity_ventilation: float = 0.0  # kWh
    electricity_lighting: float = 0.0  # kWh
    electricity_pumps: float = 0.0  # kWh
    electricity_drying: float = 0.0  # kWh
    electricity_other: float = 0.0  # kWh
    electricity_kwh: Optional[float] = None  # Legacy shared electricity bucket
    heating_kwh: Optional[float] = None  # Legacy alias for electricity_heating
    mechanical_kwh: float = 0.0  # Legacy mechanical demand

    # Non-electric energy
    natural_gas_m3: float = 0.0
    diesel_liters: float = 0.0
    biomass_fuel_kg: float = 0.0  # kg DM of biomass fuel
    biomass_energy_density: float = 16.0  # MJ/kg DM

    # Duration
    batch_days: float = 14.0

    # Override energy densities
    substrate_energy_density: Optional[float] = None
    larvae_energy_density: Optional[float] = None
    renewable_fraction: float = 0.0  # Legacy reporting field

    def __post_init__(self) -> None:
        """Map legacy fields to the new schema."""
        if self.dm_out is not None and self.dm_out_larvae == 0.0:
            self.dm_out_larvae = self.dm_out

        if self.heating_kwh is not None and self.natural_gas_m3 == 0.0:
            self.natural_gas_m3 = (self.heating_kwh * KWH_TO_MJ) / M3_GAS_TO_MJ

        if self.electricity_kwh is not None:
            configured = (
                self.electricity_heating
                + self.electricity_ventilation
                + self.electricity_lighting
                + self.electricity_pumps
                + self.electricity_drying
                + self.electricity_other
            )
            if configured == 0.0:
                self.electricity_ventilation = self.electricity_kwh


@dataclass
class EnergyResult:
    """Energy balance calculation results."""

    # Inputs (MJ)
    chemical_energy_in: float = 0.0  # Chemical energy in substrate
    electrical_energy_in: float = 0.0  # Total electricity
    thermal_energy_in: float = 0.0  # Gas + diesel + biomass
    total_energy_in: float = 0.0

    # Electrical breakdown (MJ)
    electricity_breakdown: Dict[str, float] = field(default_factory=dict)

    # Outputs (MJ)
    chemical_energy_larvae: float = 0.0
    chemical_energy_frass: float = 0.0
    total_chemical_energy_out: float = 0.0

    # Losses (MJ)
    metabolic_heat_loss: float = 0.0
    energy_loss: float = 0.0

    # Efficiency metrics
    eroi: float = 0.0  # Energy Return on Investment
    eroi_operational: float = 0.0  # EROI excluding chemical input
    energy_efficiency: float = 0.0  # Total output / total input
    specific_energy: float = 0.0  # kWh / kg larvae DM
    specific_energy_per_protein: float = 0.0  # kWh / kg protein

    # Breakdown for visualization
    breakdown_in: Dict[str, float] = field(default_factory=dict)
    breakdown_out: Dict[str, float] = field(default_factory=dict)

    # Legacy compatibility fields
    total_input_energy: float = 0.0
    total_output_energy: float = 0.0
    net_energy: float = 0.0
    fossil_energy: float = 0.0
    renewable_energy: float = 0.0
    electrical_energy: float = 0.0
    thermal_energy: float = 0.0
    mechanical_energy: float = 0.0
    per_kg_larvae: float = 0.0

    engine_version: str = ENGINE_VERSION


def compute_energy_balance(inp: EnergyInput) -> EnergyResult:
    """
    Compute full energy balance for an insect bioconversion batch.

    Parameters
    ----------
    inp : EnergyInput
        Batch parameters and energy consumption data.

    Returns
    -------
    EnergyResult
        Detailed energy balance with efficiency metrics.
    """
    result = EnergyResult()

    sub_ed = inp.substrate_energy_density or ED_SUBSTRATE

    # ���� Chemical Energy In ����
    result.chemical_energy_in = round(inp.dm_in * sub_ed, 4)

    # ���� Electrical Energy In ����
    elec_kwh = (
        inp.electricity_heating
        + inp.electricity_ventilation
        + inp.electricity_lighting
        + inp.electricity_pumps
        + inp.electricity_drying
        + inp.electricity_other
        + inp.mechanical_kwh
    )
    result.electrical_energy_in = round(elec_kwh * KWH_TO_MJ, 4)

    result.electricity_breakdown = {
        "Heating": round(inp.electricity_heating * KWH_TO_MJ, 4),
        "Ventilation": round(inp.electricity_ventilation * KWH_TO_MJ, 4),
        "Lighting": round(inp.electricity_lighting * KWH_TO_MJ, 4),
        "Pumps": round(inp.electricity_pumps * KWH_TO_MJ, 4),
        "Drying": round(inp.electricity_drying * KWH_TO_MJ, 4),
        "Other": round(inp.electricity_other * KWH_TO_MJ, 4),
        "Mechanical": round(inp.mechanical_kwh * KWH_TO_MJ, 4),
    }

    # ���� Thermal Energy In ����
    gas_mj = inp.natural_gas_m3 * M3_GAS_TO_MJ
    diesel_mj = inp.diesel_liters * L_DIESEL_TO_MJ
    biomass_mj = inp.biomass_fuel_kg * inp.biomass_energy_density
    result.thermal_energy_in = round(gas_mj + diesel_mj + biomass_mj, 4)

    # ���� Total Energy In ����
    result.total_energy_in = round(
        result.chemical_energy_in + result.electrical_energy_in + result.thermal_energy_in,
        4,
    )

    # ���� Chemical Energy Out ����
    # Detailed composition-based calculation
    protein_energy = inp.dm_out_larvae * (inp.protein_content / 100) * ED_PROTEIN
    fat_energy = inp.dm_out_larvae * (inp.fat_content / 100) * ED_FAT
    chitin_energy = inp.dm_out_larvae * (inp.chitin_content / 100) * ED_CHITIN
    # Remaining DM assumed to be carbohydrate
    remaining_pct = max(100 - inp.protein_content - inp.fat_content - inp.chitin_content, 0)
    carb_energy = inp.dm_out_larvae * (remaining_pct / 100) * ED_CARBOHYDRATE

    result.chemical_energy_larvae = round(protein_energy + fat_energy + chitin_energy + carb_energy, 4)
    result.chemical_energy_frass = round(inp.dm_out_frass * ED_FRASS, 4)
    result.total_chemical_energy_out = round(result.chemical_energy_larvae + result.chemical_energy_frass, 4)

    # ���� Losses ����
    result.metabolic_heat_loss = round(
        result.chemical_energy_in - result.total_chemical_energy_out,
        4,
    )
    result.energy_loss = round(
        result.total_energy_in - result.total_chemical_energy_out,
        4,
    )

    # ���� Efficiency Metrics ����
    # EROI: chemical energy out / operational energy in
    operational_in = result.electrical_energy_in + result.thermal_energy_in
    if operational_in > 0:
        result.eroi = round(result.total_chemical_energy_out / operational_in, 4)
        result.eroi_operational = result.eroi

    # Overall energy efficiency
    if result.total_energy_in > 0:
        result.energy_efficiency = round(result.total_chemical_energy_out / result.total_energy_in, 4)

    # Specific energy consumption
    if inp.dm_out_larvae > 0:
        result.specific_energy = round(elec_kwh / inp.dm_out_larvae, 4)
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100)
        if protein_kg > 0:
            result.specific_energy_per_protein = round(elec_kwh / protein_kg, 4)

    # ���� Breakdown for Visualization ����
    result.breakdown_in = {
        "Chemical (substrate)": result.chemical_energy_in,
        "Electrical": result.electrical_energy_in,
        "Thermal (gas)": round(gas_mj, 4),
        "Thermal (diesel)": round(diesel_mj, 4),
        "Thermal (biomass)": round(biomass_mj, 4),
    }
    result.breakdown_out = {
        "Chemical (larvae)": result.chemical_energy_larvae,
        "Chemical (frass)": result.chemical_energy_frass,
        "Metabolic heat loss": max(result.metabolic_heat_loss, 0),
    }

    # Legacy-compatible summary metrics used by older tests/callers.
    result.total_input_energy = round(operational_in, 4)
    result.total_output_energy = result.total_chemical_energy_out
    result.net_energy = round(result.total_output_energy - result.total_input_energy, 4)
    result.electrical_energy = result.electrical_energy_in
    result.thermal_energy = result.thermal_energy_in
    result.mechanical_energy = round(inp.mechanical_kwh * KWH_TO_MJ, 4)
    renewable_fraction = min(max(inp.renewable_fraction, 0.0), 1.0)
    result.renewable_energy = round(result.total_input_energy * renewable_fraction, 4)
    result.fossil_energy = round(result.total_input_energy - result.renewable_energy, 4)
    result.per_kg_larvae = result.specific_energy

    return result
