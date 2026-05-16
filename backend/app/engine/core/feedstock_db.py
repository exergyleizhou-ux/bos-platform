"""
BOS Pipeline v9.0 - Feedstock Reference Database

Curated feedstock profiles used by BOS for substrate screening,
stoichiometry defaults, and contamination-aware planning.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


CandidateReviewStatus = Literal["pending_review", "reviewed", "rejected"]


@dataclass(frozen=True)
class FeedstockProfile:
    key: str
    display_name: str
    category: str
    typical_cn_min: float | None
    typical_cn_max: float | None
    moisture_risk: str
    contamination_risk: str
    lignocellulose_severity: str
    suitability_notes: str
    evidence_basis: str
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedstockCandidate:
    """Review-gated external feedstock seed.

    These records are deliberately separate from FEEDSTOCK_DB. They let BOS read
    external matrix candidates without converting unreviewed values into
    validated substrate defaults.
    """

    key: str
    display_name: str
    category: str
    risk_tier: str
    source_kind: str
    source_ref: str
    license_note: str
    ingestion_mode: str
    human_review_required: bool
    review_status: CandidateReviewStatus
    candidate_scope: str
    suitability_notes: str
    references: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


FEEDSTOCK_DB: Dict[str, FeedstockProfile] = {
    "distillers_grains": FeedstockProfile(
        key="distillers_grains",
        display_name="Distillers grains",
        category="agro-industrial residue",
        typical_cn_min=10.0,
        typical_cn_max=20.0,
        moisture_risk="medium",
        contamination_risk="low",
        lignocellulose_severity="medium",
        suitability_notes=(
            "Core BOS manuscript feedstock. Strong candidate for mealworm-led upstream "
            "conditioning and relay-style staged conversion."
        ),
        evidence_basis="manuscript+public benchmark literature",
        references=(
            "Supplied BOS manuscript: core TM->PB relay on distillers grains.",
            "Historical Perspective on Distillers Grains. DOI:10.1201/b11047-9",
            "Supplied BOS manuscript introduction and BSF benchmark positioning on brewery/distillery side streams.",
        ),
    ),
    "brewery_spent_grains": FeedstockProfile(
        key="brewery_spent_grains",
        display_name="Brewery spent grains / beer lees",
        category="agro-industrial residue",
        typical_cn_min=11.0,
        typical_cn_max=18.0,
        moisture_risk="high",
        contamination_risk="low",
        lignocellulose_severity="medium",
        suitability_notes=(
            "Useful as a wet, nutrient-rich co-substrate, but storage spoilage and "
            "mycotoxin drift need attention."
        ),
        evidence_basis="manuscript+public benchmark literature",
        references=(
            "Supplied BOS manuscript: beer-lees moisture-gradient campaign (Supplementary Table S4).",
            "BOS treats brewery and distillery side streams as moisture-sensitive wet residues requiring spoilage-aware handling.",
        ),
    ),
    "straw": FeedstockProfile(
        key="straw",
        display_name="Straw / crop residue",
        category="lignocellulosic residue",
        typical_cn_min=50.0,
        typical_cn_max=100.0,
        moisture_risk="low",
        contamination_risk="low",
        lignocellulose_severity="high",
        suitability_notes=(
            "High-fiber material. Usually needs blending, conditioning, or relay architecture "
            "to avoid conversion-recovery trade-off."
        ),
        evidence_basis="public benchmark literature",
        references=(
            "Review of the pretreatment and bioconversion of lignocellulosic biomass from wheat straw materials. DOI:10.1016/j.rser.2018.03.113",
            "Supplied BOS manuscript: lignocellulosic straw positioned as a high-severity fibrous residue requiring staged handling.",
        ),
    ),
    "straw_sludge_blend": FeedstockProfile(
        key="straw_sludge_blend",
        display_name="Straw-sludge blend",
        category="blended industrial residue",
        typical_cn_min=9.25,
        typical_cn_max=15.51,
        moisture_risk="medium",
        contamination_risk="high",
        lignocellulose_severity="high",
        suitability_notes=(
            "Manuscript-backed mixed substrate. Useful for envelope mapping, but requires "
            "strict contamination and stabilization review."
        ),
        evidence_basis="manuscript campaign",
        references=(
            "Supplied BOS manuscript: straw-sludge co-conversion series with initial C/N 9.25-15.51 (Supplementary Table S2).",
        ),
    ),
    "washed_kitchen_waste": FeedstockProfile(
        key="washed_kitchen_waste",
        display_name="Washed kitchen waste",
        category="municipal organic waste",
        typical_cn_min=12.0,
        typical_cn_max=25.0,
        moisture_risk="high",
        contamination_risk="medium",
        lignocellulose_severity="low",
        suitability_notes=(
            "Good for high-conversion scenarios after preprocessing. Washing ratio and dewatering "
            "control strongly affect stability and handling."
        ),
        evidence_basis="manuscript campaign",
        references=(
            "Supplied BOS manuscript: washed kitchen-waste campaign and preprocessing workflow (Supplementary Tables S3/S3a/S3b).",
        ),
    ),
    "sewage_sludge": FeedstockProfile(
        key="sewage_sludge",
        display_name="Sewage sludge",
        category="sludge",
        typical_cn_min=5.0,
        typical_cn_max=10.0,
        moisture_risk="high",
        contamination_risk="critical",
        lignocellulose_severity="low",
        suitability_notes=(
            "High contamination and pathogen risk. BOS should treat it as a controlled "
            "screening substrate, not a default deployment feedstock."
        ),
        evidence_basis="manuscript campaign+public risk literature",
        references=(
            "Supplied BOS manuscript: sludge-focused trial and heavy-metal context (Supplementary Tables S9 and S29).",
            "Heavy Metal Contamination of Soil with Domestic Sewage Sludge. DOI:10.1201/9781482280173-5",
            "Resource Utilization of Residual Organic Sludge Generated from Bioenergy Facilities Using Hermetia illucens Larvae. Insects (2024). DOI:10.3390/insects15070541",
        ),
    ),
    "tcm_residue": FeedstockProfile(
        key="tcm_residue",
        display_name="Traditional Chinese medicine residue",
        category="botanical residue",
        typical_cn_min=None,
        typical_cn_max=None,
        moisture_risk="medium",
        contamination_risk="medium",
        lignocellulose_severity="medium",
        suitability_notes=(
            "Useful as a compatibility or booster-token screen on a DG base. "
            "Requires phytochemical provenance rather than only bulk nutrient accounting."
        ),
        evidence_basis="manuscript campaign+public botanical residue literature",
        references=(
            "Supplied BOS manuscript: TCM residue compatibility screen (Supplementary Table S30 / Figure S3).",
        ),
    ),
}


FEEDSTOCK_CANDIDATE_DB: Dict[str, FeedstockCandidate] = {
    "distillers_grains": FeedstockCandidate(
        key="distillers_grains",
        display_name="Distillers grains",
        category="agro-industrial residue",
        risk_tier="standard_review",
        source_kind="industry_reference",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-feedstock-candidate-matrix",
        license_note=(
            "External source seed only. Review license, supplier region, units, and "
            "customer-facing evidence use before promotion."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="feedstock_seed",
        suitability_notes=(
            "P0 feedstock candidate for mealworm and grub-class executor screening; "
            "candidate values must not overwrite FEEDSTOCK_DB."
        ),
        references=("BOS external knowledge matrix: distillers grains P0 feedstock row.",),
        aliases=("ddgs", "distillery_grains"),
    ),
    "brewery_spent_grains": FeedstockCandidate(
        key="brewery_spent_grains",
        display_name="Brewery spent grains",
        category="agro-industrial residue",
        risk_tier="standard_review",
        source_kind="industry_reference",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-feedstock-candidate-matrix",
        license_note=(
            "External source seed only. Review license, supplier region, units, and "
            "customer-facing evidence use before promotion."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="feedstock_seed",
        suitability_notes=(
            "Wet brewery residue candidate; spoilage, storage duration, and dewatering "
            "must remain review-gated."
        ),
        references=("BOS external knowledge matrix: brewery spent grains P0 feedstock row.",),
        aliases=("beer_lees", "bsg"),
    ),
    "washed_kitchen_waste": FeedstockCandidate(
        key="washed_kitchen_waste",
        display_name="Washed kitchen waste",
        category="municipal organic waste",
        risk_tier="standard_review",
        source_kind="industry_reference",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-feedstock-candidate-matrix",
        license_note=(
            "External source seed only. Review license, supplier region, units, and "
            "customer-facing evidence use before promotion."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="feedstock_seed",
        suitability_notes=(
            "Preprocessed municipal organic candidate; washing ratio, salt removal, and "
            "local contamination controls require review before use as evidence."
        ),
        references=("BOS external knowledge matrix: washed kitchen waste P0 feedstock row.",),
        aliases=("kitchen_waste_washed",),
    ),
    "mixed_food_waste": FeedstockCandidate(
        key="mixed_food_waste",
        display_name="Food waste / mixed food waste",
        category="municipal organic waste",
        risk_tier="standard_review",
        source_kind="public_dataset",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-feedstock-candidate-matrix",
        license_note=(
            "External source seed only. Review dataset license, region, units, collection "
            "protocol, and customer-facing evidence use before promotion."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="feedstock_seed",
        suitability_notes=(
            "Broad food-waste candidate for BSF and mixed-organics screening; not a "
            "validated substitute for washed kitchen waste."
        ),
        references=("BOS external knowledge matrix: food waste / mixed food waste P0 feedstock row.",),
        aliases=("food_waste", "mixed_organic_waste"),
    ),
    "manure_sludge_high_risk": FeedstockCandidate(
        key="manure_sludge_high_risk",
        display_name="Manure / sludge high-risk candidate",
        category="high-risk organic waste",
        risk_tier="high_risk_review_only",
        source_kind="official_standard",
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#p0-feedstock-candidate-matrix",
        license_note=(
            "High-risk external source seed only. Official standards, pathogen controls, "
            "heavy-metal limits, region, and product-use constraints must be reviewed "
            "before any release, compliance, or customer evidence use."
        ),
        ingestion_mode="manual_review_first",
        human_review_required=True,
        review_status="pending_review",
        candidate_scope="high_risk_feedstock_seed",
        suitability_notes=(
            "Review-only manure/sludge candidate. It must not be treated as a normal "
            "deployment feedstock or validated default."
        ),
        references=("BOS external knowledge matrix: manure/sludge high-risk candidate row.",),
        aliases=("manure", "sludge", "sewage_sludge_candidate"),
    ),
}


FEEDSTOCK_CANDIDATE_ALIASES: Dict[str, str] = {}
for key, candidate in FEEDSTOCK_CANDIDATE_DB.items():
    FEEDSTOCK_CANDIDATE_ALIASES[key] = key
    for alias in candidate.aliases:
        FEEDSTOCK_CANDIDATE_ALIASES[alias] = key


def get_feedstock(key: str) -> Optional[FeedstockProfile]:
    return FEEDSTOCK_DB.get(key)


def get_feedstock_candidate(key: str) -> Optional[FeedstockCandidate]:
    canonical_key = FEEDSTOCK_CANDIDATE_ALIASES.get(key.lower())
    if canonical_key is None:
        return None
    return FEEDSTOCK_CANDIDATE_DB.get(canonical_key)


def get_all_feedstock_candidates(
    review_status: CandidateReviewStatus | None = None,
) -> List[FeedstockCandidate]:
    items = list(FEEDSTOCK_CANDIDATE_DB.values())
    if review_status is None:
        return items
    return [item for item in items if item.review_status == review_status]


def get_feedstock_candidate_keys() -> List[str]:
    return list(FEEDSTOCK_CANDIDATE_DB.keys())


def get_all_feedstocks() -> List[FeedstockProfile]:
    return list(FEEDSTOCK_DB.values())


def get_feedstock_keys() -> List[str]:
    return list(FEEDSTOCK_DB.keys())
