"""
BOS Pipeline v9.0 �� GHG Engine (Greenhouse Gas Balance)

Computes the greenhouse gas balance of an insect bioconversion batch,
including:
  - Direct emissions (CH?, N?O from substrate decomposition)
  - Indirect emissions (energy consumption, transport)
  - Carbon sequestration credit (frass used as fertilizer)
  - Avoided emissions (replacing fishmeal/soy protein)

All values in kg CO?-equivalent (CO?e).

Reference: IPCC AR6, GWP100 values.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

ENGINE_VERSION = "9.0.0"

# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# IPCC GWP100 Factors
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

GWP_CH4 = 27.9  # IPCC AR6 (was 28 in AR5)
GWP_N2O = 273.0  # IPCC AR6 (was 265 in AR5)
GWP_CO2 = 1.0

# Emission factors
EF_ELECTRICITY = 0.45  # kg CO?e / kWh (global average grid mix)
EF_NATURAL_GAS = 2.02  # kg CO?e / m3
EF_DIESEL = 2.68  # kg CO?e / L
EF_TRANSPORT_TRUCK = 0.062  # kg CO?e / t��km (medium truck)

# Bioconversion-specific emission factors
EF_CH4_SUBSTRATE = 0.005  # kg CH? / kg substrate DM (aerobic, managed)
EF_N2O_SUBSTRATE = 0.0001  # kg N?O / kg N input
EF_CO2_RESPIRATION = 0.40  # kg CO? / kg substrate DM consumed

# Credit factors
CREDIT_FRASS_FERTILIZER = -0.20  # kg CO?e / kg frass DM (replaces synthetic fertilizer)
CREDIT_PROTEIN_REPLACEMENT = -2.50  # kg CO?e / kg protein DM (replaces fishmeal)
CREDIT_FAT_REPLACEMENT = -1.80  # kg CO?e / kg fat DM (replaces palm oil)


@dataclass
class GHGInput:
    """Input parameters for GHG balance calculation."""

    # Batch data
    dm_in: float = 0.0  # kg substrate DM
    dm_out_larvae: float = 0.0  # kg larvae DM
    dm_out_frass: float = 0.0  # kg frass DM
    n_in: float = 0.0  # g nitrogen input
    dm_out: Optional[float] = None  # Legacy alias for dm_out_larvae

    # Composition (% DM of larvae)
    protein_content: float = 42.0
    fat_content: float = 35.0

    # Energy use
    electricity_kwh: float = 0.0
    energy_kwh: Optional[float] = None  # Legacy alias for electricity_kwh
    natural_gas_m3: float = 0.0
    diesel_liters: float = 0.0

    # Transport
    transport_distance_km: float = 50.0  # one-way
    transport_load_tonnes: float = 1.0
    transport_km: Optional[float] = None  # Legacy alias for transport_distance_km

    # Grid emission factor override
    grid_ef: Optional[float] = None  # kg CO?e / kWh
    grid_emission_factor: Optional[float] = None  # Legacy alias for grid_ef

    # Legacy direct/avoided emission overrides
    ch4_emissions_kg: Optional[float] = None
    n2o_emissions_kg: Optional[float] = None
    avoided_soybean_meal_kg: float = 0.0
    avoided_landfill_kg: float = 0.0

    # Options
    include_credits: bool = True
    include_avoided: bool = True
    include_transport: bool = True

    def __post_init__(self) -> None:
        """Map legacy fields to the new schema."""
        if self.dm_out is not None and self.dm_out_larvae == 0.0:
            self.dm_out_larvae = self.dm_out
        if self.energy_kwh is not None and self.electricity_kwh == 0.0:
            self.electricity_kwh = self.energy_kwh
        if self.transport_km is not None:
            self.transport_distance_km = self.transport_km
        if self.grid_emission_factor is not None and self.grid_ef is None:
            self.grid_ef = self.grid_emission_factor


@dataclass
class GHGResult:
    """GHG balance calculation results."""

    # Direct emissions
    ch4_emissions: float = 0.0  # kg CO?e
    n2o_emissions: float = 0.0  # kg CO?e
    co2_respiration: float = 0.0  # kg CO?e (biogenic, often excluded)

    # Indirect emissions
    electricity_emissions: float = 0.0  # kg CO?e
    gas_emissions: float = 0.0  # kg CO?e
    diesel_emissions: float = 0.0  # kg CO?e
    transport_emissions: float = 0.0  # kg CO?e

    # Credits
    frass_credit: float = 0.0  # kg CO?e (negative)
    protein_credit: float = 0.0  # kg CO?e (negative)
    fat_credit: float = 0.0  # kg CO?e (negative)

    # Totals
    total_direct: float = 0.0
    total_indirect: float = 0.0
    total_credits: float = 0.0
    total_net: float = 0.0  # Net GHG balance

    # Intensity metrics
    carbon_intensity_per_kg_larvae: float = 0.0  # kg CO?e / kg larvae DM
    carbon_intensity_per_kg_protein: float = 0.0  # kg CO?e / kg protein

    # Breakdown for visualization
    breakdown: Dict[str, float] = field(default_factory=dict)

    # Comparison
    comparison_fishmeal: Optional[float] = None  # kg CO?e for equivalent fishmeal production
    comparison_soy: Optional[float] = None  # kg CO?e for equivalent soy production
    savings_vs_fishmeal: Optional[float] = None  # % reduction
    savings_vs_soy: Optional[float] = None  # % reduction

    # Legacy compatibility fields
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


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Main Computation
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def compute_ghg(inp: GHGInput) -> GHGResult:
    """
    Compute full GHG balance for an insect bioconversion batch.

    Parameters
    ----------
    inp : GHGInput
        Batch parameters and energy use data.

    Returns
    -------
    GHGResult
        Detailed emission breakdown and net balance.
    """
    result = GHGResult()
    grid_ef = inp.grid_ef if inp.grid_ef is not None else EF_ELECTRICITY

    # ���� 1. Direct Emissions ����
    # CH? from anaerobic pockets in substrate
    ch4_kg = inp.ch4_emissions_kg if inp.ch4_emissions_kg is not None else inp.dm_in * EF_CH4_SUBSTRATE
    result.ch4_emissions = round(ch4_kg * GWP_CH4, 4)

    # N?O from nitrification/denitrification
    n_in_kg = inp.n_in / 1000.0  # g �� kg
    n2o_kg = inp.n2o_emissions_kg if inp.n2o_emissions_kg is not None else n_in_kg * EF_N2O_SUBSTRATE
    result.n2o_emissions = round(n2o_kg * GWP_N2O, 4)

    # CO? from biological respiration (biogenic �� often excluded from net accounting)
    dm_consumed = max(inp.dm_in - inp.dm_out_larvae - inp.dm_out_frass, 0)
    result.co2_respiration = round(dm_consumed * EF_CO2_RESPIRATION * GWP_CO2, 4)

    result.total_direct = round(
        result.ch4_emissions + result.n2o_emissions,  # Exclude biogenic CO?
        4,
    )

    # ���� 2. Indirect Emissions ����
    result.electricity_emissions = round(inp.electricity_kwh * grid_ef, 4)
    result.gas_emissions = round(inp.natural_gas_m3 * EF_NATURAL_GAS, 4)
    result.diesel_emissions = round(inp.diesel_liters * EF_DIESEL, 4)

    if inp.include_transport:
        # Round-trip transport
        transport_tkm = inp.transport_load_tonnes * inp.transport_distance_km * 2
        result.transport_emissions = round(transport_tkm * EF_TRANSPORT_TRUCK, 4)

    result.total_indirect = round(
        result.electricity_emissions
        + result.gas_emissions
        + result.diesel_emissions
        + result.transport_emissions,
        4,
    )

    # ���� 3. Credits ����
    if inp.include_credits:
        result.frass_credit = round(inp.dm_out_frass * CREDIT_FRASS_FERTILIZER, 4)

    if inp.include_avoided:
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100.0)
        fat_kg = inp.dm_out_larvae * (inp.fat_content / 100.0)
        result.protein_credit = round(protein_kg * CREDIT_PROTEIN_REPLACEMENT, 4)
        result.fat_credit = round(fat_kg * CREDIT_FAT_REPLACEMENT, 4)
        # Legacy avoided-emission knobs.
        result.protein_credit = round(result.protein_credit + inp.avoided_soybean_meal_kg * -2.0, 4)
        result.frass_credit = round(result.frass_credit + inp.avoided_landfill_kg * -0.5, 4)

    result.total_credits = round(
        result.frass_credit + result.protein_credit + result.fat_credit,
        4,
    )

    # ���� 4. Net Balance ����
    result.total_net = round(
        result.total_direct + result.total_indirect + result.total_credits,
        4,
    )

    # ���� 5. Intensity Metrics ����
    if inp.dm_out_larvae > 0:
        result.carbon_intensity_per_kg_larvae = round(result.total_net / inp.dm_out_larvae, 4)
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100.0)
        if protein_kg > 0:
            result.carbon_intensity_per_kg_protein = round(result.total_net / protein_kg, 4)

    # ���� 6. Comparison with Conventional ����
    if inp.dm_out_larvae > 0:
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100.0)
        # Fishmeal: ~3.5 kg CO?e / kg protein (global average)
        result.comparison_fishmeal = round(protein_kg * 3.5, 4)
        # Soy protein: ~2.0 kg CO?e / kg protein
        result.comparison_soy = round(protein_kg * 2.0, 4)

        # Savings
        if result.comparison_fishmeal > 0:
            net_per_protein = result.carbon_intensity_per_kg_protein
            result.savings_vs_fishmeal = round((1 - net_per_protein / 3.5) * 100, 1)
        if result.comparison_soy > 0:
            net_per_protein = result.carbon_intensity_per_kg_protein
            result.savings_vs_soy = round((1 - net_per_protein / 2.0) * 100, 1)

    # ���� 7. Breakdown for Visualization ����
    result.breakdown = {
        "CH? emissions": result.ch4_emissions,
        "N?O emissions": result.n2o_emissions,
        "Electricity": result.electricity_emissions,
        "Natural gas": result.gas_emissions,
        "Diesel": result.diesel_emissions,
        "Transport": result.transport_emissions,
        "Frass credit": result.frass_credit,
        "Protein replacement credit": result.protein_credit,
        "Fat replacement credit": result.fat_credit,
    }

    # Legacy-compatible summary metrics used by older tests/callers.
    result.total_emissions = round(result.total_direct + result.total_indirect, 4)
    result.avoided_emissions = round(abs(min(result.total_credits, 0.0)), 4)
    result.net_balance = result.total_net
    result.process_emissions = result.total_direct
    result.energy_emissions = round(
        result.electricity_emissions + result.gas_emissions + result.diesel_emissions,
        4,
    )
    result.biogenic_emissions = result.co2_respiration
    result.emission_intensity_per_kg = result.carbon_intensity_per_kg_larvae
    result.per_kg_larvae = result.carbon_intensity_per_kg_larvae
    result.per_kg_protein = result.carbon_intensity_per_kg_protein
    if inp.dm_in > 0:
        result.per_tonne_substrate = round(result.total_net / (inp.dm_in / 1000.0), 4)

    return result
