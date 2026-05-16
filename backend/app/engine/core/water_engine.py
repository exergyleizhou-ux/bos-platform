"""
BOS Pipeline v9.0 — Water Footprint Engine

Computes the water footprint of insect bioconversion following the
Water Footprint Network methodology (Hoekstra et al., 2011).

Components:
  - Blue water  : Irrigation / process water consumed
  - Green water : Rainwater stored in substrate (agriculture phase)
  - Grey water  : Water needed to dilute pollutants to acceptable levels

Result in liters (L) per kg output, comparable to other protein sources.
"""

from dataclasses import dataclass, field

ENGINE_VERSION = "9.0.0"

# Default water footprint factors (L / kg DM)
WF_SUBSTRATE_BLUE = 50.0  # Blue water for substrate production
WF_SUBSTRATE_GREEN = 200.0  # Green water for substrate (e.g., crop residues)
WF_SUBSTRATE_GREY = 30.0  # Grey water for substrate
WF_PROCESS_BLUE = 5.0  # Process water per kg substrate DM
WF_CLEANING = 2.0  # Cleaning water per kg output DM
WF_COOLING = 1.5  # Evaporative cooling water per kWh

# Comparison factors (L / kg protein)
WF_BEEF_PROTEIN = 112_000.0 / 200.0  # ~560 L/kg protein
WF_CHICKEN_PROTEIN = 4_325.0 / 200.0  # ~21.6 L/kg protein (per kg meat, ~20% protein)
WF_SOY_PROTEIN = 2_145.0 / 360.0  # ~5.96 L/kg protein

# Actually use more realistic per-kg-protein values
WF_COMPARE = {
    "beef": 112.0,  # L / kg protein (simplified)
    "chicken": 34.0,
    "pork": 57.0,
    "soy": 19.0,
    "fishmeal": 15.0,
}


@dataclass
class WaterInput:
    """Input parameters for water footprint calculation."""

    dm_in: float = 0.0  # kg substrate DM
    dm_out: float | None = None  # Legacy alias for larvae dry matter output
    dm_out_larvae: float = 0.0  # kg larvae DM
    dm_out_frass: float = 0.0  # kg frass DM

    # Direct water use (L)
    water_direct_litres: float | None = None  # Legacy alias for aggregate direct water
    water_recycled_litres: float = 0.0  # Legacy recycled-water credit
    water_scarcity_index: float = 0.0  # Legacy scarcity weighting factor
    process_water: float | None = None  # If measured directly
    cleaning_water: float | None = None
    cooling_water: float | None = None

    # Energy for cooling (kWh)
    cooling_energy_kwh: float = 0.0

    # Substrate origin
    substrate_wf_blue: float | None = None  # Override L/kg DM
    substrate_wf_green: float | None = None
    substrate_wf_grey: float | None = None

    # Larval composition
    protein_content: float = 42.0  # % DM

    # Wastewater
    wastewater_volume: float = 0.0  # L produced
    wastewater_nitrogen: float = 0.0  # g N in wastewater
    max_allowable_nitrogen: float = 10.0  # mg N/L (regulatory limit)

    def __post_init__(self) -> None:
        if self.dm_out_larvae <= 0 and self.dm_out is not None:
            self.dm_out_larvae = self.dm_out
        if self.process_water is None and self.water_direct_litres is not None:
            self.process_water = max(self.water_direct_litres - self.water_recycled_litres, 0.0)


@dataclass
class WaterResult:
    """Water footprint calculation results."""

    # Component footprints (L)
    blue_water: float = 0.0
    green_water: float = 0.0
    grey_water: float = 0.0
    total_water: float = 0.0
    total_footprint: float = 0.0  # Legacy alias

    # Sub-components of blue water
    blue_substrate: float = 0.0
    blue_process: float = 0.0
    blue_cleaning: float = 0.0
    blue_cooling: float = 0.0

    # Intensity metrics
    wf_per_kg_larvae: float = 0.0  # L / kg larvae DM
    wf_per_kg_protein: float = 0.0  # L / kg protein
    per_kg_larvae: float = 0.0  # Legacy alias
    per_kg_protein: float = 0.0  # Legacy alias

    # Water use efficiency
    water_productivity: float = 0.0  # kg larvae DM / m3 water
    scarcity_weighted_footprint: float = 0.0

    # Comparison
    comparison: dict[str, dict[str, float]] = field(default_factory=dict)

    # Breakdown
    breakdown: dict[str, float] = field(default_factory=dict)

    engine_version: str = ENGINE_VERSION


def compute_water_footprint(inp: WaterInput) -> WaterResult:
    """
    Compute water footprint for an insect bioconversion batch.

    Parameters
    ----------
    inp : WaterInput
        Batch parameters and water use data.

    Returns
    -------
    WaterResult
        Detailed water footprint breakdown.
    """
    result = WaterResult()

    # ── Blue Water ──
    # Substrate production
    sub_blue = inp.substrate_wf_blue if inp.substrate_wf_blue is not None else WF_SUBSTRATE_BLUE
    result.blue_substrate = round(inp.dm_in * sub_blue, 2)

    # Process water
    if inp.process_water is not None:
        result.blue_process = round(inp.process_water, 2)
    else:
        result.blue_process = round(inp.dm_in * WF_PROCESS_BLUE, 2)

    # Cleaning water
    if inp.cleaning_water is not None:
        result.blue_cleaning = round(inp.cleaning_water, 2)
    else:
        result.blue_cleaning = round(inp.dm_out_larvae * WF_CLEANING, 2)

    # Cooling water (evaporative)
    if inp.cooling_water is not None:
        result.blue_cooling = round(inp.cooling_water, 2)
    else:
        result.blue_cooling = round(inp.cooling_energy_kwh * WF_COOLING, 2)

    result.blue_water = round(
        result.blue_substrate + result.blue_process + result.blue_cleaning + result.blue_cooling,
        2,
    )

    # ── Green Water ──
    sub_green = inp.substrate_wf_green if inp.substrate_wf_green is not None else WF_SUBSTRATE_GREEN
    result.green_water = round(inp.dm_in * sub_green, 2)

    # ── Grey Water ──
    # Grey water = dilution volume for wastewater pollutants
    sub_grey = inp.substrate_wf_grey if inp.substrate_wf_grey is not None else WF_SUBSTRATE_GREY
    grey_substrate = inp.dm_in * sub_grey

    # Additional grey from wastewater
    grey_wastewater = 0.0
    if inp.wastewater_nitrogen > 0 and inp.max_allowable_nitrogen > 0:
        # Volume needed to dilute N to acceptable level
        n_mg = inp.wastewater_nitrogen * 1000  # g → mg
        grey_wastewater = n_mg / inp.max_allowable_nitrogen  # L

    result.grey_water = round(grey_substrate + grey_wastewater, 2)

    # ── Total ──
    result.total_water = round(result.blue_water + result.green_water + result.grey_water, 2)
    result.total_footprint = result.total_water

    # ── Intensity Metrics ──
    if inp.dm_out_larvae > 0:
        result.wf_per_kg_larvae = round(result.total_water / inp.dm_out_larvae, 2)
        result.per_kg_larvae = result.wf_per_kg_larvae
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100.0)
        if protein_kg > 0:
            result.wf_per_kg_protein = round(result.total_water / protein_kg, 2)
            result.per_kg_protein = result.wf_per_kg_protein

    # Water productivity
    if result.total_water > 0:
        result.water_productivity = round(inp.dm_out_larvae / (result.total_water / 1000.0), 4)  # kg/m3
        result.scarcity_weighted_footprint = round(result.total_water * (1 + max(inp.water_scarcity_index, 0.0)), 2)

    # ── Comparison ──
    if inp.dm_out_larvae > 0:
        protein_kg = inp.dm_out_larvae * (inp.protein_content / 100.0)
        insect_wf_per_protein = result.wf_per_kg_protein

        for source, wf_ref in WF_COMPARE.items():
            equivalent_wf = round(protein_kg * wf_ref, 2)
            saving_pct = round((1 - insect_wf_per_protein / wf_ref) * 100, 1) if wf_ref > 0 else 0
            result.comparison[source] = {
                "reference_wf_per_kg_protein": wf_ref,
                "equivalent_total_wf": equivalent_wf,
                "saving_percent": saving_pct,
            }

    # ── Breakdown ──
    result.breakdown = {
        "Blue — substrate": result.blue_substrate,
        "Blue — process": result.blue_process,
        "Blue — cleaning": result.blue_cleaning,
        "Blue — cooling": result.blue_cooling,
        "Green — substrate": result.green_water,
        "Grey — dilution": result.grey_water,
    }

    return result
