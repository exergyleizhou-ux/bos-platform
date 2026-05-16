"""
BOS Pipeline v9.0 - Manuscript Reference Data

Structured reference layer that converts experimentally described manuscript
campaigns into BOS-readable data assets.

This is not a raw lab notebook replacement. It is a compact, queryable
representation of campaign-level evidence that BOS can use for:
  - substrate screening,
  - executor compatibility framing,
  - risk-aware planning,
  - future UI evidence surfacing.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ManuscriptCampaign:
    key: str
    title: str
    species_chain: tuple[str, ...]
    feedstocks: tuple[str, ...]
    campaign_type: str
    evidence_level: str
    summary: str
    key_parameters: Dict[str, object]
    observed_outputs: Dict[str, object]
    source_anchor: str
    references: tuple[str, ...] = ()


MANUSCRIPT_CAMPAIGNS: Dict[str, ManuscriptCampaign] = {
    "core_tm_pb_distillers_grains": ManuscriptCampaign(
        key="core_tm_pb_distillers_grains",
        title="Core TM→PB relay on distillers grains",
        species_chain=("MW", "PB"),
        feedstocks=("distillers_grains",),
        campaign_type="core_validation",
        evidence_level="manuscript_core",
        summary=(
            "Primary relay validation on distillers grains, with Tenebrio molitor "
            "as upstream compiler and Protaetia brevitarsis as downstream executor."
        ),
        key_parameters={
            "ser": 0.68,
            "d_prime": 0.683,
            "g_prime": 0.672,
            "n_reactors": 4,
            "delta_delta_ser": 0.15,
            "welch_95ci": [0.10, 0.20],
            "kernel_tau_m2_minutes": 120,
            "kernel_target_moisture_pct": 65.0,
            "kernel_temperature_c": 25.0,
        },
        observed_outputs={
            "best_single_stage_ser": 0.53,
            "signal_api_cellulase_uplift_pct": 47.0,
        },
        source_anchor="Abstract + Methods 2.2 + Results core validation",
        references=(
            "Supplied BOS manuscript abstract and core validation sections.",
            "Hermetia illucens and Tenebrio molitor comparative production literature used for BOS default envelopes.",
        ),
    ),
    "bsf_hal_portability_audit": ManuscriptCampaign(
        key="bsf_hal_portability_audit",
        title="BSF HAL portability micro-assay",
        species_chain=("MW", "BSF"),
        feedstocks=("distillers_grains",),
        campaign_type="portability_audit",
        evidence_level="manuscript_mechanistic",
        summary=(
            "Cross-executor portability audit using a T. molitor-compiled Signal-API "
            "dosed into Hermetia illucens under an identical Control-API."
        ),
        key_parameters={
            "hydraulic_loading_ml_per_kg_dry": 4.0,
            "audit_window_h": 24,
            "early_checkpoint_h": 12,
            "dose_nominal_bu_per_kg": 100,
            "dose_gain_bu_per_kg": 200,
            "translation_gain_g": 2.0,
            "replicates": 5,
        },
        observed_outputs={
            "classification": "PASS_WITH_GAIN",
            "cea_12h_mean_u_mg_protein": {
                "vehicle": 69.6,
                "dose_100_bu": 78.2,
                "dose_200_bu": 106.1,
            },
        },
        source_anchor="Supplementary Note S_A4 / Tables S_A4-1R and S_A4-2",
        references=(
            "Supplied BOS manuscript Supplementary Note S_A4.",
            "Cross-executor portability into Hermetia illucens under identical hydraulic loading.",
        ),
    ),
    "straw_sludge_series": ManuscriptCampaign(
        key="straw_sludge_series",
        title="Straw-sludge co-conversion series",
        species_chain=("MW", "PB"),
        feedstocks=("straw_sludge_blend",),
        campaign_type="adaptability_screen",
        evidence_level="manuscript_campaign",
        summary=(
            "Blend-envelope screen spanning straw:sludge ratios and initial C/N "
            "conditions to stress-test mixed high-risk feedstocks."
        ),
        key_parameters={
            "straw_to_sludge_dry_ratio_range": ["1:1", "1:4"],
            "initial_cn_range": [9.25, 15.51],
            "containers_per_ratio": 2,
        },
        observed_outputs={},
        source_anchor="Section 2.3 / Supplementary Table S2",
        references=(
            "Supplied BOS manuscript Section 2.3 and Supplementary Table S2.",
        ),
    ),
    "washed_kitchen_waste_campaign": ManuscriptCampaign(
        key="washed_kitchen_waste_campaign",
        title="Washed kitchen-waste actuator campaign",
        species_chain=("PB",),
        feedstocks=("washed_kitchen_waste",),
        campaign_type="adaptability_screen",
        evidence_level="manuscript_campaign",
        summary=(
            "Washed kitchen-waste substrate preparation and downstream actuator "
            "handling campaign for high-variability municipal organics."
        ),
        key_parameters={
            "dry_mass_per_compartment_g": 25,
            "rehydration_water_ml": 15,
            "initial_moisture_pct_range": [40, 50],
            "larvae_per_compartment": 20,
            "washing_temperature_c": 25,
            "washing_rpm": 180,
        },
        observed_outputs={},
        source_anchor="Section 2.3.1 / Supplementary Tables S3, S3a, S3b",
        references=(
            "Supplied BOS manuscript washed kitchen-waste campaign.",
        ),
    ),
    "beer_lees_moisture_gradient": ManuscriptCampaign(
        key="beer_lees_moisture_gradient",
        title="Beer lees moisture-gradient series",
        species_chain=("MW", "PB"),
        feedstocks=("brewery_spent_grains",),
        campaign_type="adaptability_screen",
        evidence_level="manuscript_campaign",
        summary=(
            "Controlled moisture-gradient series for brewery side streams to "
            "test response under wet-storage and handling variation."
        ),
        key_parameters={
            "moisture_gradient_pct": [0, 2, 4, 6],
            "containers_per_level": 2,
        },
        observed_outputs={},
        source_anchor="Section 2.3 / Supplementary Table S4",
        references=(
            "Supplied BOS manuscript beer-lees moisture-gradient campaign.",
        ),
    ),
    "sludge_focused_trial": ManuscriptCampaign(
        key="sludge_focused_trial",
        title="Sludge-focused trial",
        species_chain=("MW", "PB"),
        feedstocks=("sewage_sludge",),
        campaign_type="risk_control_screen",
        evidence_level="manuscript_campaign",
        summary=(
            "High-sludge screening campaign focused on biomass loading versus "
            "stabilization outcomes for risk-aware deployment decisions."
        ),
        key_parameters={},
        observed_outputs={},
        source_anchor="Supplementary Table S29",
        references=(
            "Supplied BOS manuscript sludge-focused trial.",
        ),
    ),
    "tcm_residue_screen": ManuscriptCampaign(
        key="tcm_residue_screen",
        title="Traditional Chinese medicine residue compatibility screen",
        species_chain=("MW",),
        feedstocks=("distillers_grains", "tcm_residue"),
        campaign_type="compatibility_screen",
        evidence_level="manuscript_pilot",
        summary=(
            "Ancillary mealworm pilot screening of botanical residues blended into "
            "a distillers-grains base under no-additional-feed stress conditions."
        ),
        key_parameters={
            "initial_larvae_per_container": 15,
            "typical_dg_g": 8,
            "typical_herbal_solid_g": 2,
            "total_substrate_g": 10,
            "screen_window_days": 24,
        },
        observed_outputs={
            "higher_compatibility_candidates": ["licorice", "astragalus"],
            "lower_compatibility_candidates": ["hawthorn", "Sophora flavescens", "chrysanthemum"],
            "tracked_residues": [
                "hawthorn",
                "Sophora flavescens",
                "chrysanthemum",
                "Astragalus",
                "licorice",
                "silkworm frass",
                "Isatis root",
            ],
        },
        source_anchor="Section 2.3.2 / Supplementary Table S30 / Figure S3",
        references=(
            "Supplied BOS manuscript TCM residue screen.",
        ),
    ),
    "heavy_metal_screening": ManuscriptCampaign(
        key="heavy_metal_screening",
        title="Heavy-metal screening and RI context",
        species_chain=("PB",),
        feedstocks=("distillers_grains",),
        campaign_type="safety_context",
        evidence_level="manuscript_analytical",
        summary=(
            "Third-party heavy-metal screening of the frass product stream used to "
            "provide regulatory and ecological-risk context."
        ),
        key_parameters={
            "laboratory": "CTI",
            "report_id": "A2230563971101001C",
        },
        observed_outputs={},
        source_anchor="Section 2.7 / Supplementary Table S9",
        references=(
            "Supplied BOS manuscript heavy-metal screening and RI context.",
            "Third-party CTI report anchor A2230563971101001C as cited in manuscript.",
        ),
    ),
}


def get_campaign(key: str) -> Optional[dict]:
    campaign = MANUSCRIPT_CAMPAIGNS.get(key)
    return asdict(campaign) if campaign else None


def get_all_campaigns() -> List[dict]:
    return [asdict(campaign) for campaign in MANUSCRIPT_CAMPAIGNS.values()]


def get_campaign_keys() -> List[str]:
    return list(MANUSCRIPT_CAMPAIGNS.keys())
