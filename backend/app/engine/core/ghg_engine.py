"""
BOS Pipeline v9.0 GHG engine.

Computes the greenhouse gas balance of an insect bioconversion batch.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

ENGINE_VERSION = "9.0.0"

GWP_CH4 = 27.9
GWP_N2O = 273.0
GWP_CO2 = 1.0

EF_ELECTRICITY = 0.45
EF_NATURAL_GAS = 2.02
EF_DIESEL = 2.68
EF_TRANSPORT_TRUCK = 0.062

EF_CH4_SUBSTRATE = 0.005
EF_N2O_SUBSTRATE = 0.0001
EF_CO2_RESPIRATION = 0.40

CREDIT_FRASS_FERTILIZER = -0.20
CREDIT_PROTEIN_REPLACEMENT = -2.50
CREDIT_FAT_REPLACEMENT = -1.80


@dataclass
class GHGInput:
    """Input parameters for GHG balance calculation."""

    dm_in: float = 0.0
    dm_out: float = 0.0  # Legacy alias
    dm_out_larvae: float = 0.0
    dm_out_frass: float = 0.0
    n_in: float = 0.0

    protein_content: float = 42.0
    fat_content: float = 35.0

    electricity_kwh: float = 0.0
    energy_kwh: float = 0.0  # Legacy alias
    natural_gas_m3: float = 0.0
    diesel_liters: float = 0.0

    transport_distance_km: float = 50.0
    transport_km: Optional[float] = None  # Legacy alias
    transport_load_tonnes: float = 1.0

    grid_ef: Optional[float] = None
    grid_emission_factor: Optional[float] = None  # Legacy alias

    include_credits: bool = True
    include_avoided: bool = True
    include_transport: bool = True

    ch4_emissions_kg: float = 0.0  # Legacy direct override
    n2o_emissions_kg: float = 0.0  # Legacy direct override
    avoided_soybean_meal_kg: float = 0.0
    avoided_landfill_kg: float = 0.0


@dataclass
class GHGResult:
    """GHG balance calculation results."""

    ch4_emissions: float = 0.0
    n2o_emissions: float = 0.0
    co2_respiration: float = 0.0

    electricity_emissions: float = 0.0
    gas_emissions: float = 0.0
    diesel_emissions: float = 0.0
    transport_emissions: float = 0.0

    frass_credit: float = 0.0
    protein_credit: float = 0.0
    fat_credit: float = 0.0

    total_direct: float = 0.0
    total_indirect: float = 0.0
    total_credits: float = 0.0
    total_net: float = 0.0

    carbon_intensity_per_kg_larvae: float = 0.0
    carbon_intensity_per_kg_protein: float = 0.0

    breakdown: Dict[str, float] = field(default_factory=dict)

    comparison_fishmeal: Optional[float] = None
    comparison_soy: Optional[float] = None
    savings_vs_fishmeal: Optional[float] = None
    savings_vs_soy: Optional[float] = None

    # Legacy aliases used by tests
    total_emissions: float = 0.0
    avoided_emissions: float = 0.0
    net_balance: float = 0.0
    process_emissions: float = 0.0
    energy_emissions: float = 0.0
    biogenic_emissions: float = 0.0
    emission_intensity_per_kg: float = 0.0
    per_kg_larvae: float = 0.0
    per_kg_protein: float = 0.0
    per_tonne_substrate: float = 0.0

    engine_version: str = ENGINE_VERSION


def compute_ghg(inp: GHGInput) -> GHGResult:
    """Compute full GHG balance for a bioconversion batch."""
    result = GHGResult()

    dm_out_larvae = inp.dm_out_larvae if inp.dm_out_larvae > 0 else inp.dm_out
    electricity_kwh = inp.electricity_kwh if inp.electricity_kwh > 0 else inp.energy_kwh
    transport_distance = inp.transport_distance_km if inp.transport_km is None else inp.transport_km
    grid_ef = inp.grid_ef if inp.grid_ef is not None else inp.grid_emission_factor
    if grid_ef is None:
        grid_ef = EF_ELECTRICITY

    # Direct emissions
    ch4_kg = inp.ch4_emissions_kg if inp.ch4_emissions_kg > 0 else inp.dm_in * EF_CH4_SUBSTRATE
    result.ch4_emissions = round(ch4_kg * GWP_CH4, 4)

    n_in_kg = inp.n_in / 1000.0
    n2o_kg = inp.n2o_emissions_kg if inp.n2o_emissions_kg > 0 else n_in_kg * EF_N2O_SUBSTRATE
    result.n2o_emissions = round(n2o_kg * GWP_N2O, 4)

    dm_consumed = max(inp.dm_in - dm_out_larvae - inp.dm_out_frass, 0)
    result.co2_respiration = round(dm_consumed * EF_CO2_RESPIRATION * GWP_CO2, 4)
    result.biogenic_emissions = result.co2_respiration

    result.total_direct = round(result.ch4_emissions + result.n2o_emissions, 4)
    result.process_emissions = result.total_direct

    # Indirect emissions
    result.electricity_emissions = round(electricity_kwh * grid_ef, 4)
    result.gas_emissions = round(inp.natural_gas_m3 * EF_NATURAL_GAS, 4)
    result.diesel_emissions = round(inp.diesel_liters * EF_DIESEL, 4)

    if inp.include_transport:
        transport_tkm = inp.transport_load_tonnes * transport_distance * 2
        result.transport_emissions = round(transport_tkm * EF_TRANSPORT_TRUCK, 4)

    result.total_indirect = round(
        result.electricity_emissions + result.gas_emissions + result.diesel_emissions + result.transport_emissions,
        4,
    )
    result.energy_emissions = round(
        result.electricity_emissions + result.gas_emissions + result.diesel_emissions,
        4,
    )

    # Credits
    if inp.include_credits:
        result.frass_credit = round(inp.dm_out_frass * CREDIT_FRASS_FERTILIZER, 4)

    if inp.include_avoided:
        protein_kg = dm_out_larvae * (inp.protein_content / 100.0)
        fat_kg = dm_out_larvae * (inp.fat_content / 100.0)
        result.protein_credit = round(protein_kg * CREDIT_PROTEIN_REPLACEMENT, 4)
        result.fat_credit = round(fat_kg * CREDIT_FAT_REPLACEMENT, 4)
        if inp.avoided_soybean_meal_kg > 0:
            result.protein_credit += round(inp.avoided_soybean_meal_kg * -2.0, 4)
        if inp.avoided_landfill_kg > 0:
            result.frass_credit += round(inp.avoided_landfill_kg * -0.5, 4)

    result.total_credits = round(result.frass_credit + result.protein_credit + result.fat_credit, 4)
    result.avoided_emissions = abs(result.total_credits)

    # Net balance
    result.total_net = round(result.total_direct + result.total_indirect + result.total_credits, 4)
    result.net_balance = result.total_net
    result.total_emissions = round(result.total_direct + result.total_indirect, 4)

    # Intensities
    if dm_out_larvae > 0:
        result.carbon_intensity_per_kg_larvae = round(result.total_net / dm_out_larvae, 4)
        result.emission_intensity_per_kg = result.carbon_intensity_per_kg_larvae
        result.per_kg_larvae = result.carbon_intensity_per_kg_larvae
        protein_kg = dm_out_larvae * (inp.protein_content / 100.0)
        if protein_kg > 0:
            result.carbon_intensity_per_kg_protein = round(result.total_net / protein_kg, 4)
            result.per_kg_protein = result.carbon_intensity_per_kg_protein
    if inp.dm_in > 0:
        result.per_tonne_substrate = round((result.total_net / inp.dm_in) * 1000, 4)

    protein_kg = dm_out_larvae * (inp.protein_content / 100.0)
    if protein_kg > 0:
        result.comparison_fishmeal = round(protein_kg * 3.5, 4)
        result.comparison_soy = round(protein_kg * 2.0, 4)
        if result.comparison_fishmeal > 0:
            result.savings_vs_fishmeal = round((1 - result.per_kg_protein / 3.5) * 100, 1)
        if result.comparison_soy > 0:
            result.savings_vs_soy = round((1 - result.per_kg_protein / 2.0) * 100, 1)

    result.breakdown = {
        "CH4 emissions": result.ch4_emissions,
        "N2O emissions": result.n2o_emissions,
        "Electricity": result.electricity_emissions,
        "Natural gas": result.gas_emissions,
        "Diesel": result.diesel_emissions,
        "Transport": result.transport_emissions,
        "Frass credit": result.frass_credit,
        "Protein replacement credit": result.protein_credit,
        "Fat replacement credit": result.fat_credit,
    }

    return result
