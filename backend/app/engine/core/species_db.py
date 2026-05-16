"""
BOS Pipeline v9.0 - Species Database Engine

Reference database for insect species parameters used across BOS engines.
The values below are intended as auditable screening defaults for planning,
simulation, and compatibility checks.

Expansion notes
---------------
- The original BOS implementation centered on BSF and mealworm-like defaults.
- This revision explicitly supports the manuscript relay species pair:
  Tenebrio molitor (mealworm) and Protaetia brevitarsis (grub / chafer larva).
- Public literature and the supplied manuscript were used to anchor the
  temperature, moisture, development, and composition defaults.
- These are not universal biological constants; they are BOS defaults that can
  be localized later through site-specific calibration.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


CandidateReviewStatus = Literal["pending_review", "reviewed", "rejected"]


@dataclass(frozen=True)
class SpeciesParameters:
    """Immutable reference parameters for a single species."""

    code: str
    scientific_name: str
    common_name: str

    # Temperature (degC)
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
    max_growth_rate: float
    development_days: float
    survival_rate: float

    # Composition (% DM)
    protein_content: float
    fat_content: float
    chitin_content: float
    ash_content: float

    # SER benchmarks
    ser_typical: float
    ser_excellent: float

    # Energy density (MJ/kg DM)
    energy_density: float

    # Nitrogen conversion factor
    nitrogen_to_protein: float

    # BOS metadata
    aliases: tuple[str, ...] = ()
    source_basis: str = "screening_default"
    notes: str = ""
    references: tuple[str, ...] = ()
    best_fit_feedstocks: tuple[str, ...] = ()
    caution_feedstocks: tuple[str, ...] = ()


@dataclass(frozen=True)
class BioexecutorCandidate:
    """Review-gated external bioexecutor seed.

    These records are deliberately separate from SPECIES_DB. They make external
    matrix candidates readable by BOS without turning them into validated
    planning, release, compliance, or customer-evidence defaults.
    """

    code: str
    scientific_name: str
    common_name: str
    source_kind: str
    source_ref: str
    license_note: str
    ingestion_mode: str
    human_review_required: bool
    review_status: CandidateReviewStatus
    candidate_scope: str
    notes: str
    references: tuple[str, ...] = ()
    related_feedstocks: tuple[str, ...] = ()


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
        aliases=("BSFL", "BLACK_SOLDIER_FLY", "HERMETIA"),
        source_basis="literature+bos_default",
        notes=(
            "Reference executor for wet mixed organics, food waste, manure, and "
            "portability micro-audits. BOS manuscript uses BSF as an external "
            "compatibility executor in the HAL portability assay."
        ),
        references=(
            "Growth Performance, Waste Reduction Efficiency and Nutritional Composition of Black Soldier Fly (Hermetia illucens) Larvae and Prepupae Reared on Coconut Endosperm and Soybean Curd Residue with or without Supplementation. Insects (2021). DOI:10.3390/insects12080682",
            "Comparison of Growth and Composition of Black Soldier Fly (Hermetia illucens L.) Larvae Reared on Sugarcane By-Products and Other Substrates. Insects (2024). DOI:10.3390/insects15100771",
            "Hermetia illucens farming. CABI Compendium (2019). DOI:10.1079/cabicompendium.26920",
        ),
        best_fit_feedstocks=("washed_kitchen_waste", "brewery_spent_grains", "distillers_grains"),
        caution_feedstocks=("sewage_sludge", "tcm_residue"),
    ),
    "MW": SpeciesParameters(
        code="MW",
        scientific_name="Tenebrio molitor",
        common_name="Yellow Mealworm",
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
        aliases=("YMW", "MEALWORM", "YELLOW_MEALWORM", "TENEBRIO"),
        source_basis="literature+manuscript",
        notes=(
            "Primary upstream compiler species in the supplied BOS relay on "
            "distillers grains; also applicable to bran-rich, dry, and fibrous "
            "co-fed residues."
        ),
        references=(
            "Nutrient Composition of Mealworm (Tenebrio molitor). In Insect Physiology and Ecology (2020). DOI:10.1007/978-3-030-32952-5_20",
            "Influence of Dietary Protein Content on the Nutritional Composition of Mealworm Larvae (Tenebrio molitor L.). Insects (2023). DOI:10.3390/insects14030261",
            "Improving Product Safety for Edible Insects: Toxicokinetics of Hg in Tenebrio molitor and Hermetia illucens. ACS Food Science & Technology (2023). DOI:10.1021/acsfoodscitech.3c00051",
        ),
        best_fit_feedstocks=("distillers_grains", "straw", "tcm_residue"),
        caution_feedstocks=("sewage_sludge",),
    ),
    "PB": SpeciesParameters(
        code="PB",
        scientific_name="Protaetia brevitarsis",
        common_name="White-spotted Flower Chafer Grub",
        temp_optimal=25.0,
        temp_min=20.0,
        temp_max=30.0,
        temp_lethal_low=12.0,
        temp_lethal_high=38.0,
        moisture_optimal=65.0,
        moisture_min=50.0,
        moisture_max=80.0,
        feed_rate_optimal=0.12,
        feed_rate_min=0.05,
        feed_rate_max=0.22,
        density_optimal=2200.0,
        density_min=400.0,
        density_max=5000.0,
        max_growth_rate=0.020,
        development_days=28.0,
        survival_rate=0.82,
        protein_content=48.0,
        fat_content=30.0,
        chitin_content=7.0,
        ash_content=8.0,
        ser_typical=0.20,
        ser_excellent=0.27,
        energy_density=24.0,
        nitrogen_to_protein=4.76,
        aliases=("GRUB", "SCARAB_GRUB", "PROTAETIA", "PBR"),
        source_basis="manuscript+literature",
        notes=(
            "Primary downstream executor in the supplied BOS relay; used here as "
            "the canonical grub / chafer-class species for fibrous finishing."
        ),
        references=(
            "Development of feed material and its effect on the nutritional composition of Protaetia brevitarsis larvae. Entomological Research (2024). DOI:10.1111/1748-5967.12711",
            "Supplied BOS manuscript: core TM→PB relay and frass/product characterization anchors.",
            "Antioxidant and immunoactive effects of Protaetia brevitarsis seulensis larvae low temperature water extracts on RAW 264.7 cells. Korean Journal of Food Science and Technology (2024). DOI:10.9721/kjfst.2024.56.1.31",
        ),
        best_fit_feedstocks=("distillers_grains", "straw_sludge_blend", "washed_kitchen_waste"),
        caution_feedstocks=("sewage_sludge", "tcm_residue"),
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
        aliases=("CRICKET", "HOUSE_CRICKET"),
        references=(
            "BOS screening default carried forward for general orthopteran comparison; refine with site-specific literature before release-critical use.",
        ),
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
        aliases=("FRUIT_BEETLE_WORM", "PACHNODA"),
        references=(
            "BOS screening default for scarab-like beetle larvae; use alongside Protaetia brevitarsis manuscript-backed data when operating in grub-class scenarios.",
        ),
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
        aliases=("WAXWORM", "GALLERIA"),
        references=(
            "BOS screening default for wax worm comparative scenarios; not a manuscript-primary executor.",
        ),
        best_fit_feedstocks=("brewery_spent_grains",),
        caution_feedstocks=("sewage_sludge",),
    ),
}


BIOEXECUTOR_CANDIDATE_DB: Dict[str, BioexecutorCandidate] = {
    "BSF": BioexecutorCandidate(
        code="BSF",
        scientific_name="Hermetia illucens",
        common_name="Black Soldier Fly",
        source_kind="peer_reviewed_literature",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-bioexecutor-candidate-matrix",
        license_note=(
            "External literature seed only. Verify source license, citation terms, regional fit, "
            "and intended use before compliance, release, or customer evidence."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="multi_bioexecutor_seed",
        notes=(
            "P0 wet-organics executor candidate. Keep as a review-gated candidate until "
            "operator review promotes specific values into a site-scoped reference."
        ),
        references=(
            "BOS external knowledge matrix: BSF / Hermetia illucens P0 candidate row.",
        ),
        related_feedstocks=("washed_kitchen_waste", "mixed_food_waste", "brewery_spent_grains"),
    ),
    "MW": BioexecutorCandidate(
        code="MW",
        scientific_name="Tenebrio molitor",
        common_name="Yellow Mealworm",
        source_kind="peer_reviewed_literature",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-bioexecutor-candidate-matrix",
        license_note=(
            "External literature seed only. Verify source license, citation terms, regional fit, "
            "and intended use before compliance, release, or customer evidence."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="multi_bioexecutor_seed",
        notes=(
            "P0 dry and agro-industrial residue executor candidate. Candidate data must "
            "not replace manuscript-backed or calibrated defaults without review."
        ),
        references=(
            "BOS external knowledge matrix: MW / Tenebrio molitor P0 candidate row.",
        ),
        related_feedstocks=("distillers_grains", "brewery_spent_grains"),
    ),
    "PB": BioexecutorCandidate(
        code="PB",
        scientific_name="Protaetia brevitarsis",
        common_name="White-spotted Flower Chafer Grub",
        source_kind="peer_reviewed_literature",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-bioexecutor-candidate-matrix",
        license_note=(
            "External literature seed only. Verify source license, citation terms, regional fit, "
            "and intended use before compliance, release, or customer evidence."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="multi_bioexecutor_seed",
        notes=(
            "P0 grub-class finishing executor candidate. Treat regional taxonomy, feed "
            "permission, and product-use claims as human-review gates."
        ),
        references=(
            "BOS external knowledge matrix: PB / Protaetia brevitarsis P0 candidate row.",
        ),
        related_feedstocks=("distillers_grains", "washed_kitchen_waste", "manure_sludge_high_risk"),
    ),
}


SPECIES_ALIASES: Dict[str, str] = {}
for code, species in SPECIES_DB.items():
    SPECIES_ALIASES[code] = code
    for alias in species.aliases:
        SPECIES_ALIASES[alias.upper()] = code


BIOEXECUTOR_CANDIDATE_ALIASES: Dict[str, str] = {
    "BSF": "BSF",
    "BSFL": "BSF",
    "BLACK_SOLDIER_FLY": "BSF",
    "HERMETIA": "BSF",
    "HERMETIA_ILLUCENS": "BSF",
    "MW": "MW",
    "YMW": "MW",
    "MEALWORM": "MW",
    "YELLOW_MEALWORM": "MW",
    "TENEBRIO": "MW",
    "TENEBRIO_MOLITOR": "MW",
    "PB": "PB",
    "GRUB": "PB",
    "PROTAETIA": "PB",
    "PROTAETIA_BREVITARSIS": "PB",
}


def get_species(code: str) -> Optional[SpeciesParameters]:
    """Get species parameters by code or alias (case-insensitive)."""
    canonical_code = SPECIES_ALIASES.get(code.upper())
    if canonical_code is None:
        return None
    return SPECIES_DB.get(canonical_code)


def get_bioexecutor_candidate(code: str) -> Optional[BioexecutorCandidate]:
    """Get a review-gated bioexecutor candidate by code or alias."""
    canonical_code = BIOEXECUTOR_CANDIDATE_ALIASES.get(code.upper())
    if canonical_code is None:
        return None
    return BIOEXECUTOR_CANDIDATE_DB.get(canonical_code)


def get_all_bioexecutor_candidates(
    review_status: CandidateReviewStatus | None = None,
) -> List[BioexecutorCandidate]:
    """Get review-gated bioexecutor candidates without reading SPECIES_DB."""
    items = list(BIOEXECUTOR_CANDIDATE_DB.values())
    if review_status is None:
        return items
    return [item for item in items if item.review_status == review_status]


def get_bioexecutor_candidate_codes() -> List[str]:
    """Get canonical bioexecutor candidate codes."""
    return list(BIOEXECUTOR_CANDIDATE_DB.keys())


def get_all_species() -> List[SpeciesParameters]:
    """Get all canonical species in the database."""
    return list(SPECIES_DB.values())


def get_species_codes() -> List[str]:
    """Get all canonical species codes."""
    return list(SPECIES_DB.keys())


def get_optimal_ranges(code: str) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Get optimal operating ranges for a species.

    Returns legacy-compatible range dictionaries with min/max and
    optimal_min/optimal_max keys.
    """
    sp = get_species(code)
    if not sp:
        return None

    return {
        "temperature": {
            "min": sp.temp_min,
            "max": sp.temp_max,
            "optimal_min": sp.temp_optimal - 2.0,
            "optimal_max": sp.temp_optimal + 2.0,
        },
        "moisture": {
            "min": sp.moisture_min,
            "max": sp.moisture_max,
            "optimal_min": sp.moisture_optimal - 5.0,
            "optimal_max": sp.moisture_optimal + 5.0,
        },
        "feed_rate": {
            "min": sp.feed_rate_min,
            "max": sp.feed_rate_max,
            "optimal_min": sp.feed_rate_optimal,
            "optimal_max": sp.feed_rate_optimal,
        },
        "density": {
            "min": sp.density_min,
            "max": sp.density_max,
            "optimal_min": sp.density_optimal,
            "optimal_max": sp.density_optimal,
        },
    }


def compare_species(codes: List[str]) -> List[Dict[str, float]]:
    """Compare key parameters across multiple species."""
    result: List[Dict[str, float]] = []
    for code in codes:
        sp = get_species(code)
        if not sp:
            continue
        result.append(
            {
                "code": sp.code,
                "common_name": sp.common_name,
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
            }
        )
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
        "aliases": list(sp.aliases),
        "source_basis": sp.source_basis,
        "notes": sp.notes,
        "references": list(sp.references),
        "best_fit_feedstocks": list(sp.best_fit_feedstocks),
        "caution_feedstocks": list(sp.caution_feedstocks),
        "development_days": sp.development_days,
        "parameters": {
            "temperature": {
                "optimal": sp.temp_optimal,
                "min": sp.temp_min,
                "max": sp.temp_max,
            },
            "moisture": {
                "optimal": sp.moisture_optimal,
                "min": sp.moisture_min,
                "max": sp.moisture_max,
            },
            "feed_rate_optimal": sp.feed_rate_optimal,
            "density_optimal": sp.density_optimal,
        },
        "conditions": {
            "temperature": f"{sp.temp_optimal} degC (range: {sp.temp_min}-{sp.temp_max} degC)",
            "moisture": f"{sp.moisture_optimal}% (range: {sp.moisture_min}-{sp.moisture_max}%)",
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
