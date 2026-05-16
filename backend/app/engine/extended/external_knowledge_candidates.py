"""Review-gated external knowledge candidates for BOS kernels.

This module is intentionally read-only. Candidates here are metadata about
external factors, rules, benchmark baselines, and model providers; they do not
promote themselves into validated defaults.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

ReviewStatus = Literal["pending_review", "reviewed", "approved", "rejected"]
CandidateType = Literal["lca_factor_candidate", "tea_factor_candidate", "compliance_rule_candidate", "release_gate_candidate"]
ExternalKnowledgeCandidateType = Literal[
    "lca_factor_candidate",
    "tea_factor_candidate",
    "compliance_rule_candidate",
    "release_gate_candidate",
    "model_provider_capability_candidate",
]

APPROVED_REVIEW_STATUSES = {"reviewed", "approved"}


@dataclass(frozen=True, slots=True)
class ExternalFactorCandidate:
    key: str
    candidate_type: CandidateType
    source_kind: str
    source_ref: str
    license_note: str
    region: str | None
    jurisdiction: str | None
    unit: str
    value: float | None
    payload: dict[str, Any]
    ingestion_mode: str = "metadata_only"
    review_status: ReviewStatus = "pending_review"
    human_review_required: bool = True
    effective_date: str | None = None
    checked_date: str | None = None

    @property
    def approved_for_kernel_use(self) -> bool:
        return self.review_status in APPROVED_REVIEW_STATUSES and not self.human_review_required and self.value is not None

    def to_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["approved_for_kernel_use"] = self.approved_for_kernel_use
        return data


@dataclass(frozen=True, slots=True)
class ModelProviderCapabilityCandidate:
    model_id: str
    provider: str
    context_window: int | None
    tool_calling: bool | None
    json_schema_output: bool | None
    vision: bool | None
    embedding: bool | None
    pricing_input: float | None
    pricing_output: float | None
    rate_limit: str | None
    data_retention_policy: str | None
    deployment_region: str | None
    fallback_candidate: bool
    source_ref: str
    checked_date: str
    review_status: ReviewStatus = "pending_review"
    human_review_required: bool = True
    source_kind: str = "model_provider_docs"
    license_note: str = "Provider capability and pricing metadata must be rechecked before promotion."

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LiteratureExtractionCandidate:
    candidate_id: str
    source_id: str
    doi: str
    source_ref: str
    title: str
    species: str
    feedstock: str
    treatment: str
    metric_key: str
    metric_label: str
    raw_value: str
    unit: str
    condition_context: str
    experiment_context: str
    table_or_section_ref: str
    extraction_note: str
    license_note: str
    review_status: Literal["pending_review"] = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    source_kind: str = "peer_reviewed_literature"
    candidate_type: Literal["literature_extraction_candidate"] = "literature_extraction_candidate"

    def to_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data["candidate_uid"] = f"{self.candidate_type}:{self.candidate_id}"
        data["guardrails"] = [
            "literature_values_are_pending_review_candidates",
            "numeric_values_included_but_not_validated_defaults",
            "release_evidence_allowed_false",
            "runtime_activation_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
        ]
        return data


FACTOR_CANDIDATES: tuple[ExternalFactorCandidate, ...] = (
    ExternalFactorCandidate(
        key="electricity_kgco2e_per_kwh",
        candidate_type="lca_factor_candidate",
        source_kind="public_dataset",
        source_ref="candidate:IEA-grid-emissions-factor",
        license_note="Metadata-only placeholder; verify license and regional applicability before promotion.",
        region="global",
        jurisdiction=None,
        unit="kgCO2e/kWh",
        value=0.45,
        payload={"factor_family": "grid_electricity", "applies_to": ["lca.compare"]},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="landfill_kgco2e_per_tonne",
        candidate_type="lca_factor_candidate",
        source_kind="peer_reviewed_literature",
        source_ref="candidate:landfill-baseline-literature",
        license_note="External literature candidate; not validated for BOS release defaults.",
        region="global",
        jurisdiction=None,
        unit="kgCO2e/tonne_substrate",
        value=450.0,
        payload={"factor_family": "landfill_baseline", "applies_to": ["lca.compare"]},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="energy_usd_per_kwh",
        candidate_type="tea_factor_candidate",
        source_kind="commercial_database",
        source_ref="candidate:regional-electricity-price",
        license_note="Commercial/region-sensitive price candidate; requires human price-date review.",
        region="global",
        jurisdiction=None,
        unit="USD/kWh",
        value=0.18,
        payload={"factor_family": "energy_price", "applies_to": ["tea.estimate"]},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="labor_usd_per_hour",
        candidate_type="tea_factor_candidate",
        source_kind="industry_reference",
        source_ref="candidate:operator-labor-rate",
        license_note="Industry reference candidate; requires site and date review.",
        region="global",
        jurisdiction=None,
        unit="USD/hour",
        value=18.0,
        payload={"factor_family": "labor_rate", "applies_to": ["tea.estimate"]},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="insect_dry_matter.cn",
        candidate_type="compliance_rule_candidate",
        source_kind="official_standard",
        source_ref="candidate:CN-insect-feed-product-quality-rule",
        license_note="Official-standard candidate; legal applicability must be reviewed before release use.",
        region=None,
        jurisdiction="CN",
        unit="rule_payload",
        value=None,
        payload={"product_category": "insect_dry_matter", "required_assays": ["moisture", "protein", "heavy_metals", "microbiology"]},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="frass_organic_fertilizer.cn",
        candidate_type="release_gate_candidate",
        source_kind="official_standard",
        source_ref="candidate:CN-frass-fertilizer-release-gate",
        license_note="Release gate candidate; regulator/legal review required before promotion.",
        region=None,
        jurisdiction="CN",
        unit="rule_payload",
        value=None,
        payload={"product_category": "frass_organic_fertilizer", "release_gate": "human_review_required"},
        checked_date="2026-04-26",
    ),
    ExternalFactorCandidate(
        key="germination_rate",
        candidate_type="release_gate_candidate",
        source_kind="peer_reviewed_literature",
        source_ref="candidate:frass-germination-rate-agronomy-metadata",
        license_note="Agronomy output metadata candidate only; numeric germination rates require human review before use.",
        region="global",
        jurisdiction=None,
        unit="metadata_payload",
        value=None,
        payload={
            "product_category": "frass_organic_fertilizer",
            "agronomy_output": "germination_rate",
            "review_boundary": "source metadata only; no germination percentage values or thresholds extracted",
            "applies_to": ["reference_atlas.business_knowledge_coverage"],
            "blocked_use": ["validated_defaults", "release_evidence", "runtime_activation", "numeric_thresholds"],
            "review_packet_id": "AGR-GERMINATION-RATE-REVIEW-PACKET",
            "review_state": "pending_review",
            "reviewer_notes_required": True,
            "source_packet_persistence": "read_model_only",
            "allowed_review_actions": ["approve_metadata", "request_license_clearance", "reject"],
            "release_evidence_allowed": False,
        },
        checked_date="2026-04-27",
    ),
    ExternalFactorCandidate(
        key="germination_index",
        candidate_type="release_gate_candidate",
        source_kind="peer_reviewed_literature",
        source_ref="candidate:frass-germination-index-agronomy-metadata",
        license_note="GI metadata candidate only; thresholds and source numeric values remain blocked pending review.",
        region="global",
        jurisdiction=None,
        unit="metadata_payload",
        value=None,
        payload={
            "product_category": "frass_organic_fertilizer",
            "agronomy_output": "germination_index",
            "review_boundary": "source metadata only; no GI values or phytotoxicity thresholds extracted",
            "applies_to": ["reference_atlas.business_knowledge_coverage"],
            "blocked_use": ["validated_defaults", "release_evidence", "runtime_activation", "numeric_thresholds"],
            "review_packet_id": "AGR-GERMINATION-INDEX-REVIEW-PACKET",
            "review_state": "pending_review",
            "reviewer_notes_required": True,
            "source_packet_persistence": "read_model_only",
            "allowed_review_actions": ["approve_metadata", "request_license_clearance", "reject"],
            "release_evidence_allowed": False,
        },
        checked_date="2026-04-27",
    ),
    ExternalFactorCandidate(
        key="phytotoxicity",
        candidate_type="release_gate_candidate",
        source_kind="peer_reviewed_literature",
        source_ref="candidate:frass-phytotoxicity-agronomy-metadata",
        license_note="Phytotoxicity metadata candidate only; validated safety claims require separate review.",
        region="global",
        jurisdiction=None,
        unit="metadata_payload",
        value=None,
        payload={
            "product_category": "frass_organic_fertilizer",
            "agronomy_output": "phytotoxicity",
            "review_boundary": "source metadata only; no phytotoxicity values, limits, or release claims extracted",
            "applies_to": ["reference_atlas.business_knowledge_coverage"],
            "blocked_use": ["validated_defaults", "release_evidence", "runtime_activation", "numeric_thresholds"],
            "review_packet_id": "AGR-PHYTOTOXICITY-REVIEW-PACKET",
            "review_state": "pending_review",
            "reviewer_notes_required": True,
            "source_packet_persistence": "read_model_only",
            "allowed_review_actions": ["approve_metadata", "request_license_clearance", "reject"],
            "release_evidence_allowed": False,
        },
        checked_date="2026-04-27",
    ),
)


LITERATURE_EXTRACTION_CANDIDATES: tuple[LiteratureExtractionCandidate, ...] = (
    LiteratureExtractionCandidate(
        candidate_id="LIT-AGR-GI-001",
        source_id="A-BSF-007",
        doi="10.3390/su151511526",
        source_ref="https://doi.org/10.3390/su151511526",
        title="Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        species="Hermetia illucens; Lactuca sativa assay crop",
        feedstock="food waste",
        treatment="BSFL frass from bioconverted food waste",
        metric_key="germination_index",
        metric_label="Seed germination index for lettuce",
        raw_value="around 100",
        unit="% GI",
        condition_context="Aqueous frass extract prepared at 1:10 w/v; lettuce cultivar Great Lakes; one-week germination assay.",
        experiment_context="Frass generated after 20 days of BSFL incubation on food waste; compared with wheat bran and biosolids treatments.",
        table_or_section_ref="Results section 3.2, Figure 2B-C",
        extraction_note="Textual result extracted as an approximate value; reviewer must check the figure before any downstream use.",
        license_note="Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
    ),
    LiteratureExtractionCandidate(
        candidate_id="LIT-AGR-GI-002",
        source_id="A-BSF-007",
        doi="10.3390/su151511526",
        source_ref="https://doi.org/10.3390/su151511526",
        title="Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        species="Hermetia illucens; Raphanus sativus assay crop",
        feedstock="wheat bran or food waste",
        treatment="BSFL frass from bioconverted wheat bran and food waste",
        metric_key="germination_index",
        metric_label="Seed germination index for radish",
        raw_value="above 100",
        unit="% GI",
        condition_context="Aqueous frass extract prepared at 1:10 w/v; radish cultivar French Breakfast; one-week germination assay.",
        experiment_context="Radish assay compared frass from wheat bran, food waste, biosolids, and 50:50 biosolids blends.",
        table_or_section_ref="Results section 3.2, Figure 2E-F",
        extraction_note="Article text reports the average GI above 100 for wheat-bran and food-waste frass; exact plotted values remain reviewer-gated.",
        license_note="Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
    ),
    LiteratureExtractionCandidate(
        candidate_id="LIT-AGR-PHYTO-001",
        source_id="A-BSF-007",
        doi="10.3390/su151511526",
        source_ref="https://doi.org/10.3390/su151511526",
        title="Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        species="Hermetia illucens; Lactuca sativa assay crop",
        feedstock="biosolids and biosolids-wheat blend",
        treatment="Undiluted BSFL frass extract from biosolids-containing feedstocks",
        metric_key="phytotoxicity",
        metric_label="Lettuce GI inhibition signal",
        raw_value="below 50",
        unit="% GI",
        condition_context="Undiluted frass extract; lettuce germination and radicle growth assay.",
        experiment_context="Biosolids-containing feedstocks generated higher NH4+-N and EC, correlating with lower GI.",
        table_or_section_ref="Results section 3.2, Figure 2C",
        extraction_note="Candidate records the article's qualitative numeric threshold statement, not a validated safety limit.",
        license_note="Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
    ),
    LiteratureExtractionCandidate(
        candidate_id="LIT-AGR-PHYTO-002",
        source_id="A-BSF-007",
        doi="10.3390/su151511526",
        source_ref="https://doi.org/10.3390/su151511526",
        title="Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        species="Hermetia illucens; Raphanus sativus assay crop",
        feedstock="biosolids treatments",
        treatment="Undiluted BSFL frass extract from biosolids-derived treatments",
        metric_key="phytotoxicity",
        metric_label="Radish GI inhibition range",
        raw_value="35-79",
        unit="% GI",
        condition_context="Undiluted frass extract; radish germination and radicle growth assay.",
        experiment_context="Radish germination was inhibited by frass from biosolids treatments.",
        table_or_section_ref="Results section 3.2, Figure 2F",
        extraction_note="Range is a literature extraction candidate and cannot be used as a release threshold before review.",
        license_note="Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
    ),
    LiteratureExtractionCandidate(
        candidate_id="LIT-AGR-GI-003",
        source_id="A-BSF-007",
        doi="10.3390/su151511526",
        source_ref="https://doi.org/10.3390/su151511526",
        title="Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        species="Hermetia illucens; lettuce and radish assay crops",
        feedstock="biosolids and biosolids-wheat blend",
        treatment="Diluted BSFL frass extract at 25% original extract concentration",
        metric_key="germination_index",
        metric_label="GI response after fourfold dilution",
        raw_value="lettuce up to 120; radish up to 170",
        unit="% GI",
        condition_context="Dilution assay using 25% original frass extract concentration.",
        experiment_context="Dilution increased GI for biosolids and biosolids-wheat frass extracts relative to undiluted extracts.",
        table_or_section_ref="Results section 3.2, Figure 3A-B",
        extraction_note="Combined textual extraction preserves crop-specific values in raw form pending reviewer split/approval.",
        license_note="Open-access publisher page; reuse and extracted-value policy must be checked before release evidence.",
    ),
)


MODEL_PROVIDER_CAPABILITY_CANDIDATES: tuple[ModelProviderCapabilityCandidate, ...] = (
    ModelProviderCapabilityCandidate("gpt-5.4", "OpenAI", None, None, None, None, None, None, None, None, None, "global", True, "https://platform.openai.com/docs", "2026-04-26"),
    ModelProviderCapabilityCandidate("claude-family", "Anthropic", None, None, None, None, None, None, None, None, None, "global", True, "https://docs.anthropic.com/", "2026-04-26"),
    ModelProviderCapabilityCandidate("gemini-family", "Google Gemini", None, None, None, None, None, None, None, None, None, "global", True, "https://ai.google.dev/gemini-api/docs", "2026-04-26"),
    ModelProviderCapabilityCandidate("mistral-family", "Mistral", None, None, None, None, None, None, None, None, None, "eu/global", True, "https://docs.mistral.ai/", "2026-04-26"),
    ModelProviderCapabilityCandidate("llama-family", "Meta Llama", None, None, None, None, None, None, None, None, None, "self-hosted/cloud", True, "https://llama.meta.com/docs/", "2026-04-26"),
    ModelProviderCapabilityCandidate("command-family", "Cohere", None, None, None, None, None, None, None, None, None, "global", True, "https://docs.cohere.com/", "2026-04-26"),
    ModelProviderCapabilityCandidate("qwen-family", "Qwen/DashScope", None, None, None, None, None, None, None, None, None, "cn/global", True, "https://help.aliyun.com/zh/model-studio/", "2026-04-26"),
    ModelProviderCapabilityCandidate("deepseek-family", "DeepSeek", None, None, None, None, None, None, None, None, None, "cn/global", True, "https://api-docs.deepseek.com/", "2026-04-26"),
    ModelProviderCapabilityCandidate("glm-family", "GLM/BigModel", None, None, None, None, None, None, None, None, None, "cn/global", True, "https://bigmodel.cn/dev/api", "2026-04-26"),
    ModelProviderCapabilityCandidate("kimi-family", "Kimi/Moonshot", None, None, None, None, None, None, None, None, None, "cn", True, "https://platform.moonshot.cn/docs", "2026-04-26"),
    ModelProviderCapabilityCandidate("ernie-family", "ERNIE/Qianfan", None, None, None, None, None, None, None, None, None, "cn", True, "https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html", "2026-04-26"),
    ModelProviderCapabilityCandidate("minimax-family", "MiniMax", None, None, None, None, None, None, None, None, None, "cn/global", True, "https://www.minimaxi.com/document", "2026-04-26"),
    ModelProviderCapabilityCandidate("sensenova-family", "SenseNova", None, None, None, None, None, None, None, None, None, "cn", True, "https://platform.sensenova.cn/", "2026-04-26"),
)


def list_external_factor_candidates(
    *,
    candidate_type: CandidateType | None = None,
    review_status: ReviewStatus | None = None,
) -> list[ExternalFactorCandidate]:
    candidates = list(FACTOR_CANDIDATES)
    if candidate_type:
        candidates = [item for item in candidates if item.candidate_type == candidate_type]
    if review_status:
        candidates = [item for item in candidates if item.review_status == review_status]
    return candidates


def get_approved_factor(candidate_type: CandidateType, key: str) -> ExternalFactorCandidate | None:
    for candidate in list_external_factor_candidates(candidate_type=candidate_type):
        if candidate.key == key and candidate.approved_for_kernel_use:
            return candidate
    return None


def build_candidate_context(candidate_type: CandidateType, keys: list[str] | None = None) -> dict[str, Any]:
    candidates = list_external_factor_candidates(candidate_type=candidate_type)
    if keys is not None:
        wanted = set(keys)
        candidates = [item for item in candidates if item.key in wanted or item.payload.get("product_category") in wanted]
    return {
        "candidate_type": candidate_type,
        "review_gate": "candidate_not_validated_until_reviewed",
        "pending_review_count": sum(1 for item in candidates if item.review_status == "pending_review"),
        "approved_count": sum(1 for item in candidates if item.approved_for_kernel_use),
        "candidates": [item.to_payload() for item in candidates],
    }


def list_model_provider_capability_candidates() -> list[dict[str, Any]]:
    return [item.to_payload() for item in MODEL_PROVIDER_CAPABILITY_CANDIDATES]


def list_literature_extraction_candidate_payloads(
    *,
    metric_key: str | None = None,
) -> list[dict[str, Any]]:
    candidates = list(LITERATURE_EXTRACTION_CANDIDATES)
    if metric_key is not None:
        candidates = [item for item in candidates if item.metric_key == metric_key]
    return [item.to_payload() for item in candidates]


def list_external_knowledge_candidate_payloads(
    *,
    candidate_type: ExternalKnowledgeCandidateType | None = None,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if candidate_type in {None, "lca_factor_candidate", "tea_factor_candidate", "compliance_rule_candidate", "release_gate_candidate"}:
        for item in list_external_factor_candidates(candidate_type=candidate_type if candidate_type != "model_provider_capability_candidate" else None):  # type: ignore[arg-type]
            payload = item.to_payload()
            payload["candidate_uid"] = f"{item.candidate_type}:{item.key}"
            payloads.append(payload)
    if candidate_type in {None, "model_provider_capability_candidate"}:
        for item in MODEL_PROVIDER_CAPABILITY_CANDIDATES:
            payload = item.to_payload()
            payload["key"] = item.model_id
            payload["candidate_type"] = "model_provider_capability_candidate"
            payload["candidate_uid"] = f"model_provider_capability_candidate:{item.model_id}"
            payload["ingestion_mode"] = "metadata_only"
            payload["approved_for_kernel_use"] = False
            payloads.append(payload)
    return payloads


def get_external_knowledge_candidate_payload(
    *,
    candidate_type: ExternalKnowledgeCandidateType,
    key: str,
) -> dict[str, Any] | None:
    for candidate in list_external_knowledge_candidate_payloads(candidate_type=candidate_type):
        if candidate.get("key") == key:
            return candidate
    return None
