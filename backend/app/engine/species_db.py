"""
BOS Pipeline v9.0 �� Species Database Engine

Reference database for insect species parameters used across all engines.
Provides species-specific defaults for temperature, moisture, feed rates,
growth kinetics, and composition.

Supported species:
  - BSF  : Black Soldier Fly (Hermetia illucens)
  - MW   : Mealworm (Tenebrio molitor)
  - CC   : Common Cricket (Acheta domesticus)
  - FBW  : Fruit Beetle Worm (Pachnoda sinuata)
  - WW   : Wax Worm (Galleria mellonella)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SpeciesParameters:
    """Immutable reference parameters for a single species."""

    code: str
    scientific_name: str
    common_name: str

    # Temperature (��C)
    temp_optimal: float
    temp_min: float
    temp_max: float
    temp_lethal_low: float
    temp_lethal_high: float

    # Moisture (% substrate wet basis)
    moisture_optimal: float
    moisture_min: float
    moisture_max: float

    # Feed rate (g substrate DM / larva / day)
    feed_rate_optimal: float
    feed_rate_min: float
    feed_rate_max: float

    # Density (larvae / m2)
    density_optimal: float
    density_min: float
    density_max: float

    # Growth kinetics
    max_growth_rate: float  # g/day (under optimal conditions)
    development_days: float  # Typical days from egg to prepupa/harvest
    survival_rate: float  # Fraction surviving to harvest

    # Composition (% DM)
    protein_content: float
    fat_content: float
    chitin_content: float
    ash_content: float

    # SER benchmarks
    ser_typical: float  # Typical SER for this species
    ser_excellent: float  # Top-tier SER

    # Energy density (MJ/kg DM)
    energy_density: float

    # Nitrogen conversion factor
    nitrogen_to_protein: float  # Kp factor (typically 4.76 for insects, not 6.25)


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Species Database
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

SPECIES_DB: Dict[str, SpeciesParameters] = {
    "BSF": SpeciesParameters(
        code="BSF",
        scientific_name="Hermetia illucens",
        common_name="Black Soldier Fly",
        temp_optimal=28.0,
        temp_min=20.0,
        temp_max=36.0,
        temp_lethal_low=10.0,
        temp_lethal_high=45.0,
        moisture_optimal=70.0,
        moisture_min=50.0,
        moisture_max=85.0,
        feed_rate_optimal=0.15,
        feed_rate_min=0.05,
        feed_rate_max=0.30,
        density_optimal=5000.0,
        density_min=1000.0,
        density_max=15000.0,
        max_growth_rate=0.025,
        development_days=14.0,
        survival_rate=0.85,
        protein_content=42.0,
        fat_content=35.0,
        chitin_content=8.0,
        ash_content=10.0,
        ser_typical=0.22,
        ser_excellent=0.30,
        energy_density=25.0,
        nitrogen_to_protein=4.76,
    ),
    "MW": SpeciesParameters(
        code="MW",
        scientific_name="Tenebrio molitor",
        common_name="Mealworm",
        temp_optimal=25.0,
        temp_min=18.0,
        temp_max=32.0,
        temp_lethal_low=5.0,
        temp_lethal_high=40.0,
        moisture_optimal=65.0,
        moisture_min=40.0,
        moisture_max=75.0,
        feed_rate_optimal=0.08,
        feed_rate_min=0.03,
        feed_rate_max=0.15,
        density_optimal=3000.0,
        density_min=500.0,
        density_max=8000.0,
        max_growth_rate=0.012,
        development_days=60.0,
        survival_rate=0.90,
        protein_content=52.0,
        fat_content=28.0,
        chitin_content=6.0,
        ash_content=4.0,
        ser_typical=0.18,
        ser_excellent=0.25,
        energy_density=27.0,
        nitrogen_to_protein=4.76,
    ),
    "CC": SpeciesParameters(
        code="CC",
        scientific_name="Acheta domesticus",
        common_name="Common Cricket",
        temp_optimal=30.0,
        temp_min=22.0,
        temp_max=35.0,
        temp_lethal_low=15.0,
        temp_lethal_high=42.0,
        moisture_optimal=55.0,
        moisture_min=30.0,
        moisture_max=70.0,
        feed_rate_optimal=0.05,
        feed_rate_min=0.02,
        feed_rate_max=0.10,
        density_optimal=2000.0,
        density_min=500.0,
        density_max=5000.0,
        max_growth_rate=0.015,
        development_days=45.0,
        survival_rate=0.80,
        protein_content=65.0,
        fat_content=18.0,
        chitin_content=10.0,
        ash_content=5.0,
        ser_typical=0.15,
        ser_excellent=0.22,
        energy_density=22.0,
        nitrogen_to_protein=4.76,
    ),
    "FBW": SpeciesParameters(
        code="FBW",
        scientific_name="Pachnoda sinuata",
        common_name="Fruit Beetle Worm",
        temp_optimal=27.0,
        temp_min=20.0,
        temp_max=33.0,
        temp_lethal_low=12.0,
        temp_lethal_high=40.0,
        moisture_optimal=60.0,
        moisture_min=40.0,
        moisture_max=75.0,
        feed_rate_optimal=0.10,
        feed_rate_min=0.04,
        feed_rate_max=0.20,
        density_optimal=2500.0,
        density_min=500.0,
        density_max=6000.0,
        max_growth_rate=0.018,
        development_days=30.0,
        survival_rate=0.82,
        protein_content=48.0,
        fat_content=30.0,
        chitin_content=7.0,
        ash_content=8.0,
        ser_typical=0.20,
        ser_excellent=0.27,
        energy_density=24.0,
        nitrogen_to_protein=4.76,
    ),
    "WW": SpeciesParameters(
        code="WW",
        scientific_name="Galleria mellonella",
        common_name="Wax Worm",
        temp_optimal=30.0,
        temp_min=25.0,
        temp_max=35.0,
        temp_lethal_low=15.0,
        temp_lethal_high=42.0,
        moisture_optimal=60.0,
        moisture_min=40.0,
        moisture_max=75.0,
        feed_rate_optimal=0.06,
        feed_rate_min=0.02,
        feed_rate_max=0.12,
        density_optimal=1500.0,
        density_min=300.0,
        density_max=4000.0,
        max_growth_rate=0.020,
        development_days=28.0,
        survival_rate=0.78,
        protein_content=38.0,
        fat_content=45.0,
        chitin_content=5.0,
        ash_content=3.0,
        ser_typical=0.16,
        ser_excellent=0.23,
        energy_density=30.0,
        nitrogen_to_protein=4.76,
    ),
}


# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
# Query Functions
# �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T


def get_species(code: str) -> Optional[SpeciesParameters]:
    """Get species parameters by code (case-insensitive)."""
    return SPECIES_DB.get(code.upper())


def get_all_species() -> List[SpeciesParameters]:
    """Get all species in the database."""
    return list(SPECIES_DB.values())


def get_species_codes() -> List[str]:
    """Get all supported species codes."""
    return list(SPECIES_DB.keys())


def get_optimal_ranges(code: str) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Get optimal operating ranges for a species.

    Returns a dict of parameter name �� (min, max) tuples.
    """
    sp = get_species(code)
    if not sp:
        return None

    return {
        "temperature": {
            "optimal_min": round(sp.temp_optimal - 2.0, 2),
            "optimal_max": round(sp.temp_optimal + 2.0, 2),
            "safe_min": round(sp.temp_min, 2),
            "safe_max": round(sp.temp_max, 2),
        },
        "moisture": {
            "optimal_min": round(sp.moisture_optimal - 5.0, 2),
            "optimal_max": round(sp.moisture_optimal + 5.0, 2),
            "safe_min": round(sp.moisture_min, 2),
            "safe_max": round(sp.moisture_max, 2),
        },
        "feed_rate": {
            "optimal_min": round(sp.feed_rate_optimal * 0.8, 4),
            "optimal_max": round(sp.feed_rate_optimal * 1.2, 4),
            "safe_min": round(sp.feed_rate_min, 4),
            "safe_max": round(sp.feed_rate_max, 4),
        },
        "density": {
            "optimal_min": round(sp.density_optimal * 0.7, 2),
            "optimal_max": round(sp.density_optimal * 1.3, 2),
            "safe_min": round(sp.density_min, 2),
            "safe_max": round(sp.density_max, 2),
        },
    }


def compare_species(codes: List[str]) -> List[Dict[str, float]]:
    """
    Compare key parameters across multiple species.

    Returns a list of species comparison rows.
    """
    result: List[Dict[str, float]] = []
    for code in codes:
        sp = get_species(code)
        if sp:
            result.append({
                "code": sp.code,
                "temp_optimal": sp.temp_optimal,
                "moisture_optimal": sp.moisture_optimal,
                "feed_rate_optimal": sp.feed_rate_optimal,
                "density_optimal": sp.density_optimal,
                "development_days": sp.development_days,
                "survival_rate": sp.survival_rate,
                "protein_content": sp.protein_content,
                "fat_content": sp.fat_content,
                "ser_typical": sp.ser_typical,
                "ser_excellent": sp.ser_excellent,
                "energy_density": sp.energy_density,
            })
    return result


def get_species_summary(code: str) -> Optional[Dict]:
    """Get a human-readable summary of species parameters."""
    sp = get_species(code)
    if not sp:
        return None

    return {
        "code": sp.code,
        "scientific_name": sp.scientific_name,
        "common_name": sp.common_name,
        "parameters": {
            "development_days": sp.development_days,
            "ser_typical": sp.ser_typical,
            "protein_content": sp.protein_content,
            "fat_content": sp.fat_content,
        },
        "conditions": {
            "temperature": f"{sp.temp_optimal}��C (range: {sp.temp_min}�C{sp.temp_max}��C)",
            "moisture": f"{sp.moisture_optimal}% (range: {sp.moisture_min}�C{sp.moisture_max}%)",
            "feed_rate": f"{sp.feed_rate_optimal} g DM/larva/day",
            "density": f"{sp.density_optimal} larvae/m2",
        },
        "biology": {
            "development": f"{sp.development_days} days",
            "survival_rate": f"{sp.survival_rate * 100:.0f}%",
            "max_growth_rate": f"{sp.max_growth_rate} g/day",
        },
        "composition": {
            "protein": f"{sp.protein_content}% DM",
            "fat": f"{sp.fat_content}% DM",
            "chitin": f"{sp.chitin_content}% DM",
            "ash": f"{sp.ash_content}% DM",
        },
        "performance": {
            "ser_typical": sp.ser_typical,
            "ser_excellent": sp.ser_excellent,
            "energy_density": f"{sp.energy_density} MJ/kg DM",
        },
    }
