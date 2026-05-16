"""Schemas for review-gated external source extraction work items."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ReviewStatus = Literal[
    "pending_review",
    "extracted_metadata",
    "needs_license_clearance",
    "rejected",
    "approved_for_candidate_use",
]
ReviewAction = Literal[
    "approve_metadata",
    "request_license_clearance",
    "reject",
    "approve_for_candidate_use",
]
ReviewActionState = Literal[
    "pending_review",
    "approve_metadata",
    "request_license_clearance",
    "reject",
    "approve_for_candidate_use",
]
LicenseStatus = Literal["pending_review", "metadata_only", "cleared", "restricted", "blocked"]
EvidenceSourceKind = Literal[
    "official_standard",
    "peer_reviewed_literature",
    "public_dataset",
    "industry_reference",
    "commercial_database",
    "model_provider_docs",
    "github_reference",
]
ReferenceIngestionMode = Literal["manual_review_first", "metadata_only", "auto_ingest_allowed", "reference_only"]
StagedMetadataArtifactStatus = Literal["template_only", "staged_metadata_only"]
ReviewedCandidateType = Literal[
    "bsf_reviewed_metadata_candidate",
    "lca_boundary_metadata_candidate",
    "species_metadata_candidate",
    "feedstock_metadata_candidate",
    "lca_factor_candidate",
    "tea_factor_candidate",
    "compliance_rule_candidate",
    "model_provider_capability_candidate",
    "github_reference_candidate",
]

METADATA_ONLY_REVIEWED_CANDIDATE_TYPES = {
    "bsf_reviewed_metadata_candidate",
    "lca_boundary_metadata_candidate",
    "species_metadata_candidate",
    "feedstock_metadata_candidate",
    "lca_factor_candidate",
    "tea_factor_candidate",
    "compliance_rule_candidate",
    "model_provider_capability_candidate",
    "github_reference_candidate",
}

REVIEWED_CANDIDATE_DOMAINS = {
    "bsf_metadata",
    "lca",
    "tea",
    "compliance",
    "model_provider",
    "github_reference",
    "species_metadata",
    "feedstock_metadata",
}

REVIEW_ACTION_TO_STATUS: dict[str, str] = {
    "approve_metadata": "extracted_metadata",
    "request_license_clearance": "needs_license_clearance",
    "reject": "rejected",
    "approve_for_candidate_use": "approved_for_candidate_use",
}
REVIEW_STATUS_TO_ACTION: dict[str, str] = {
    "pending_review": "pending_review",
    "extracted_metadata": "approve_metadata",
    "needs_license_clearance": "request_license_clearance",
    "rejected": "reject",
    "approved_for_candidate_use": "approve_for_candidate_use",
}


def review_status_for_action(review_action: str) -> str:
    return REVIEW_ACTION_TO_STATUS[review_action]


def review_action_for_status(review_status: str) -> str:
    return REVIEW_STATUS_TO_ACTION.get(review_status, "pending_review")


def reviewed_candidate_type_group(candidate_type: str) -> str:
    if candidate_type in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES:
        return "reviewed_metadata_candidate"
    return "unknown_reviewed_candidate"


def reviewed_candidate_domain(candidate_type: str) -> str:
    return {
        "bsf_reviewed_metadata_candidate": "bsf_metadata",
        "lca_boundary_metadata_candidate": "lca",
        "lca_factor_candidate": "lca",
        "tea_factor_candidate": "tea",
        "compliance_rule_candidate": "compliance",
        "model_provider_capability_candidate": "model_provider",
        "github_reference_candidate": "github_reference",
        "species_metadata_candidate": "species_metadata",
        "feedstock_metadata_candidate": "feedstock_metadata",
    }.get(candidate_type, "unknown")


def reviewed_candidate_types_for_domain(candidate_domain: str) -> set[str]:
    return {
        candidate_type
        for candidate_type in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES
        if reviewed_candidate_domain(candidate_type) == candidate_domain
    }


class ExternalSourceReviewCard(BaseModel):
    """A staged review card; it cannot carry validated-default values."""

    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(..., pattern=r"^BSF-CARD-\d{3}$")
    shortlist_id: str = Field(..., pattern=r"^BSF-LIT-\d{3}$")
    source_catalog_id: str = Field(..., pattern=r"^(A-BSF|B-FEED|C-LCA|D-TEA|E-COMP|F-MODEL|G-OSS)-\d{3}$")
    doi: str = Field(..., pattern=r"^10\.\d{4,9}/\S+$")
    review_status: ReviewStatus = "pending_review"
    reviewer: str = "unassigned"
    reviewed_at: str = "pending"
    license_status: LicenseStatus = "pending_review"
    evidence_source_kind: EvidenceSourceKind
    ingestion_mode: ReferenceIngestionMode
    human_review_required: bool = True
    extracted_numeric_values_allowed: bool = False
    boundary_condition_required: bool = True
    allowed_use: str = Field(..., min_length=1)
    blocked_use: str = Field(..., min_length=1)
    next_action: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def enforce_review_gate(self) -> "ExternalSourceReviewCard":
        if not self.human_review_required:
            raise ValueError("external source review cards must require human review")
        if self.extracted_numeric_values_allowed:
            raise ValueError("review cards cannot allow numeric extraction values")
        if not self.boundary_condition_required:
            raise ValueError("boundary conditions are required for every review card")

        blocked = self.blocked_use.lower()
        if "default" not in blocked:
            raise ValueError("blocked_use must block validated defaults")
        if "release evidence" not in blocked:
            raise ValueError("blocked_use must block release evidence")

        if self.review_status != "pending_review":
            if self.reviewer == "unassigned" or self.reviewed_at == "pending":
                raise ValueError("closed review cards require reviewer and reviewed_at")
            if self.license_status == "pending_review":
                raise ValueError("closed review cards require resolved license_status")

        return self


class ExternalSourceStagedMetadataRecord(BaseModel):
    """Machine-readable metadata shell for a reviewed source card.

    This is deliberately metadata-only. Numeric values require a separate,
    reviewer-approved candidate artifact.
    """

    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(..., pattern=r"^BSF-CARD-\d{3}$")
    shortlist_id: str = Field(..., pattern=r"^BSF-LIT-\d{3}$")
    source_catalog_id: str = Field(..., pattern=r"^(A-BSF|B-FEED|C-LCA|D-TEA|E-COMP|F-MODEL|G-OSS)-\d{3}$")
    doi: str = Field(..., pattern=r"^10\.\d{4,9}/\S+$")
    source_url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    evidence_source_kind: EvidenceSourceKind
    ingestion_mode: ReferenceIngestionMode
    review_status: ReviewStatus = "pending_review"
    license_status: LicenseStatus = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = False
    promotion_enabled: bool = False
    validated_default_write_enabled: bool = False
    extracted_numeric_values: dict[str, Any] = Field(default_factory=dict)
    boundary_metadata: dict[str, Any] = Field(default_factory=dict)
    allowed_use: str = Field(..., min_length=1)
    blocked_use: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def enforce_metadata_only_record(self) -> "ExternalSourceStagedMetadataRecord":
        if not self.human_review_required:
            raise ValueError("staged metadata records must require human review")
        if self.numeric_values_included or self.extracted_numeric_values:
            raise ValueError("staged metadata records cannot include numeric values")
        if self.promotion_enabled:
            raise ValueError("staged metadata records cannot enable promotion")
        if self.validated_default_write_enabled:
            raise ValueError("staged metadata records cannot write validated defaults")

        blocked = self.blocked_use.lower()
        if "default" not in blocked:
            raise ValueError("blocked_use must block validated defaults")
        if "release evidence" not in blocked:
            raise ValueError("blocked_use must block release evidence")

        return self


class ExternalSourceStagedMetadataArtifact(BaseModel):
    """A machine-readable staged metadata artifact that cannot execute ingestion."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., min_length=1)
    checked_date: str = Field(..., min_length=1)
    artifact_status: StagedMetadataArtifactStatus = "template_only"
    source_catalog: str = Field(..., min_length=1)
    source_shortlist: str = Field(..., min_length=1)
    review_card_queue: str = Field(..., min_length=1)
    promotion_enabled: bool = False
    numeric_values_included: bool = False
    validated_default_write_enabled: bool = False
    records: list[ExternalSourceStagedMetadataRecord] = Field(..., min_length=1)

    @model_validator(mode="after")
    def enforce_artifact_gate(self) -> "ExternalSourceStagedMetadataArtifact":
        if self.promotion_enabled:
            raise ValueError("staged metadata artifact cannot enable promotion")
        if self.numeric_values_included:
            raise ValueError("staged metadata artifact cannot include numeric values")
        if self.validated_default_write_enabled:
            raise ValueError("staged metadata artifact cannot write validated defaults")

        card_ids = [record.card_id for record in self.records]
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("staged metadata artifact contains duplicate card IDs")

        return self


class ExternalSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    source_name: str
    source_owner: str | None = None
    source_category: str | None = None
    license_note: str | None = None
    bos_module: str | None = None
    evidence_source_kind: str
    ingestion_mode: str
    auto_ingestion_note: str | None = None
    human_review_note: str | None = None
    next_action: str | None = None
    raw_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExternalSourceCatalogResponse(BaseModel):
    items: list[ExternalSourceRead]
    count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "source_catalog_metadata_only",
            "no_runtime_activation",
            "no_validated_default_writes",
        ]
    )


class ExternalSourceProcurementSummary(BaseModel):
    schema_version: Literal["external_source_procurement_summary_v1"] = "external_source_procurement_summary_v1"
    source_count: int
    source_kind_counts: dict[str, int]
    ingestion_mode_counts: dict[str, int]
    bos_module_counts: dict[str, int]
    review_required_count: int
    metadata_only_count: int
    manual_review_first_count: int
    other_ingestion_mode_count: int
    commercial_or_restricted_count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "source_procurement_summary_is_read_only",
            "metadata_catalog_is_not_reviewed_candidate",
            "catalog_rows_do_not_enable_runtime_activation",
            "catalog_rows_do_not_write_validated_defaults",
        ]
    )


class ExternalSourceSchemaReadinessTable(BaseModel):
    table_name: str
    present: bool
    row_count: int | None = None


class ExternalKnowledgeCoverageDomain(BaseModel):
    domain_key: str
    label: str
    coverage_basis: Literal["source_metadata"]
    expected_source_count: int
    covered_source_count: int
    coverage_percent: float
    status: Literal["covered", "partial", "missing"]
    review_gated: bool = True
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    numeric_values_included: bool = False


BusinessKnowledgeCoverageStatus = Literal[
    "validated_read_model",
    "candidate_read_model",
    "source_metadata_only",
    "partial",
    "candidate_needed",
    "missing",
]


class BusinessKnowledgeReviewWorkflow(BaseModel):
    """Read-only reviewer workflow metadata for candidate business coverage."""

    review_packet_id: str
    review_state: Literal["pending_review", "approved_for_candidate_use", "rejected", "needs_license_clearance"] = (
        "pending_review"
    )
    source_packet_persistence: Literal["read_model_only", "persisted_review_packet_required"] = "read_model_only"
    reviewer_notes_required: bool = True
    reviewer_notes: str = ""
    allowed_review_actions: list[str] = Field(
        default_factory=lambda: [
            "approve_metadata",
            "request_license_clearance",
            "reject",
            "approve_for_candidate_use",
        ]
    )
    approval_enabled: bool = False
    rejection_enabled: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    numeric_values_allowed: bool = False
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "review_workflow_is_read_only",
            "reviewer_notes_required_before_any_promotion",
            "approval_state_does_not_enable_runtime",
            "source_packet_persistence_required_before_release_use",
            "numeric_values_blocked",
            "validated_default_write_enabled_false",
            "release_evidence_allowed_false",
        ]
    )


class BusinessKnowledgeCoverageItem(BaseModel):
    item_key: str
    label: str
    status: BusinessKnowledgeCoverageStatus
    coverage_basis: Literal["validated_read_model", "candidate_read_model", "source_metadata", "partial", "missing"]
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str = ""
    review_gated: bool = True
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    numeric_values_included: bool = False
    review_workflow: BusinessKnowledgeReviewWorkflow | None = None


class BusinessKnowledgeCoverageGroup(BaseModel):
    group_key: str
    label: str
    expected_item_count: int
    covered_item_count: int
    coverage_percent: float
    status: Literal["covered", "partial", "missing"]
    items: list[BusinessKnowledgeCoverageItem]
    review_gated: bool = True
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    numeric_values_included: bool = False


class ExternalSourceSchemaReadinessResponse(BaseModel):
    schema_version: Literal["external_source_schema_readiness_v1"] = "external_source_schema_readiness_v1"
    status: Literal["ready", "blocked"]
    schema_ready: bool
    source_catalog_ready: bool
    knowledge_coverage_ready: bool = False
    knowledge_coverage_percent: float = 0.0
    source_metadata_coverage_percent: float = 0.0
    knowledge_coverage_domains: list[ExternalKnowledgeCoverageDomain] = Field(default_factory=list)
    business_knowledge_coverage_percent: float = 0.0
    business_knowledge_coverage_groups: list[BusinessKnowledgeCoverageGroup] = Field(default_factory=list)
    feedstock_dataset_candidate_count: int
    literature_extraction_candidate_count: int = 0
    phase4a_domain_metadata_ready: bool = False
    phase4a_domain_candidate_counts: dict[str, int] = Field(default_factory=dict)
    phase4a_domain_expected_counts: dict[str, int] = Field(default_factory=dict)
    phase4a_domain_missing_counts: dict[str, int] = Field(default_factory=dict)
    reviewed_metadata_lane_ready: bool
    required_tables: list[ExternalSourceSchemaReadinessTable]
    missing_required_tables: list[str]
    blockers: list[str]
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "schema_readiness_only",
            "no_table_creation",
            "no_seed_mutation",
            "no_candidate_promotion",
            "no_validated_default_writes",
            "source_metadata_coverage_is_not_business_knowledge_coverage",
            "business_knowledge_coverage_is_read_only",
            "phase4a_domain_coverage_is_read_only",
        ]
    )


class ExternalSourcePhase4ADomainSeedResponse(BaseModel):
    schema_version: Literal["external_source_phase4a_domain_seed_v1"] = "external_source_phase4a_domain_seed_v1"
    source_count: int
    created_source_count: int
    updated_source_count: int
    seeded_source_ids: list[str]
    phase4a_domain_metadata_ready: bool
    phase4a_domain_candidate_counts: dict[str, int]
    phase4a_domain_expected_counts: dict[str, int]
    phase4a_domain_missing_counts: dict[str, int]
    runtime_activated_count: int
    validated_default_write_enabled_count: int
    numeric_value_candidate_count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "phase4a_seed_metadata_only",
            "source_records_only",
            "human_review_required",
            "numeric_values_included_false",
            "promotion_enabled_false",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_candidate_promotion",
            "no_final_action_execution",
        ]
    )


class ExternalSourcePhase4AReviewedCandidateFillResponse(BaseModel):
    schema_version: Literal["external_source_phase4a_reviewed_candidate_fill_v1"] = (
        "external_source_phase4a_reviewed_candidate_fill_v1"
    )
    source_count: int
    reviewed_candidate_count: int
    created_reviewed_candidate_count: int
    updated_reviewed_candidate_count: int
    reviewed_candidate_ids: list[str]
    candidate_types: dict[str, int]
    candidate_domains: dict[str, int]
    runtime_activated_count: int
    validated_default_write_enabled_count: int
    numeric_value_candidate_count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "phase4a_reviewed_candidates_metadata_only",
            "human_review_recorded",
            "numeric_values_included_false",
            "promotion_enabled_false",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_runtime_activation",
            "no_final_action_execution",
        ]
    )


class FeedstockDatasetCandidateRead(BaseModel):
    candidate_uid: str
    candidate_type: Literal["feedstock_dataset_candidate"] = "feedstock_dataset_candidate"
    source_id: str
    source_name: str
    source_owner: str | None = None
    source_kind: str
    source_ref: str
    license_note: str | None = None
    ingestion_mode: str
    geography: str | None = None
    units: str | None = None
    source_version_required: bool = True
    checked_at_required: bool = True
    mapping_confidence: Literal["unmapped"] = "unmapped"
    waste_proxy_warning: str
    review_status: Literal["pending_review"] = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False
    next_action: str | None = None

    @model_validator(mode="after")
    def enforce_feedstock_dataset_guardrails(self) -> "FeedstockDatasetCandidateRead":
        if not self.human_review_required:
            raise ValueError("feedstock dataset candidates must require human review")
        if self.numeric_values_included or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("feedstock dataset candidates cannot include numeric values, runtime activation, or default writes")
        return self


class FeedstockDatasetCandidateListResponse(BaseModel):
    items: list[FeedstockDatasetCandidateRead]
    count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "feedstock_dataset_candidates_are_metadata_only",
            "food_or_feed_items_are_waste_proxy_candidates_not_defaults",
            "no_feedstock_db_writes",
            "runtime_activation_blocked",
        ]
    )


class LiteratureExtractionCandidateRead(BaseModel):
    """Review-gated extracted literature values.

    Numeric values are intentionally allowed here, but only as pending-review
    candidates. This model must not overlap with validated defaults, release
    evidence, promotion, or runtime activation.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_uid: str
    candidate_id: str
    candidate_type: Literal["literature_extraction_candidate"] = "literature_extraction_candidate"
    source_id: str
    doi: str | None = None
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
    source_kind: EvidenceSourceKind = "peer_reviewed_literature"
    review_status: Literal["pending_review"] = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    guardrails: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_literature_extraction_candidate_gate(self) -> "LiteratureExtractionCandidateRead":
        if not self.human_review_required:
            raise ValueError("literature extraction candidates must require human review")
        if not self.numeric_values_included:
            raise ValueError("literature extraction candidates must explicitly mark numeric values as included")
        if self.review_status != "pending_review":
            raise ValueError("literature extraction candidates must remain pending_review")
        if self.release_evidence_allowed or self.runtime_activation_enabled:
            raise ValueError("literature extraction candidates cannot enable release evidence or runtime activation")
        if self.validated_default_write_enabled or self.promotion_enabled:
            raise ValueError("literature extraction candidates cannot enable validated defaults or promotion")
        return self


class LiteratureExtractionCandidateListResponse(BaseModel):
    schema_version: Literal["literature_extraction_candidate_list_v1"] = "literature_extraction_candidate_list_v1"
    items: list[LiteratureExtractionCandidateRead]
    count: int
    metric_counts: dict[str, int]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_candidates_are_review_gated",
            "numeric_values_are_candidate_raw_values_only",
            "pending_review_required",
            "release_evidence_allowed_false",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_list_read_only_gate(self) -> "LiteratureExtractionCandidateListResponse":
        if any(self.side_effects.values()):
            raise ValueError("literature extraction candidate list cannot report mutation side effects")
        return self


class LiteratureExtractionCandidateSeedResponse(BaseModel):
    schema_version: Literal["literature_extraction_candidate_seed_v1"] = "literature_extraction_candidate_seed_v1"
    tenant_id: int
    source_count: int
    candidate_count: int
    created_candidate_count: int
    updated_candidate_count: int
    seeded_candidate_ids: list[str]
    review_status: Literal["pending_review"] = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_candidate_records_only",
            "pending_review_required",
            "numeric_values_are_candidate_raw_values_only",
            "release_evidence_allowed_false",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_seed_gate(self) -> "LiteratureExtractionCandidateSeedResponse":
        if not self.human_review_required or self.review_status != "pending_review":
            raise ValueError("literature extraction candidate seed must remain pending review")
        if not self.numeric_values_included:
            raise ValueError("literature extraction candidate seed must explicitly mark numeric values as included")
        if (
            self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
        ):
            raise ValueError("literature extraction candidate seed cannot enable release, runtime, defaults, or promotion")
        if any(self.side_effects.values()):
            raise ValueError("literature extraction candidate seed cannot report mutation side effects outside candidate table")
        return self


class LiteratureExtractionCandidateReviewPacketResponse(BaseModel):
    schema_version: Literal["literature_extraction_candidate_review_packet_v1"] = (
        "literature_extraction_candidate_review_packet_v1"
    )
    tenant_id: int
    candidate: LiteratureExtractionCandidateRead
    candidate_payload: dict[str, Any]
    source_trace: dict[str, Any]
    raw_value: str
    unit: str
    conditions: dict[str, str]
    license_note: str
    review_status: Literal["pending_review"] = "pending_review"
    human_review_required: bool = True
    numeric_values_included: bool = True
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_review_packet_is_read_only",
            "candidate_raw_values_are_pending_review_only",
            "release_evidence_allowed_false",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_literature_review_packet_gate(self) -> "LiteratureExtractionCandidateReviewPacketResponse":
        if self.review_status != "pending_review" or not self.human_review_required:
            raise ValueError("literature extraction review packet must remain pending review")
        if not self.numeric_values_included:
            raise ValueError("literature extraction review packet must explicitly include candidate raw values")
        if (
            self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature extraction review packet cannot enable release, runtime, defaults, promotion, or final actions")
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review packet cannot report mutation side effects")
        return self


class LiteratureExtractionCandidateReviewPacketExportResponse(BaseModel):
    schema_version: Literal["literature_extraction_candidate_review_packet_export_v1"] = (
        "literature_extraction_candidate_review_packet_export_v1"
    )
    tenant_id: int
    export_format: Literal["json"] = "json"
    export_filename: str
    content_hash: str
    export_manifest: dict[str, Any]
    review_packet: LiteratureExtractionCandidateReviewPacketResponse
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_review_packet_export_is_read_only",
            "export_response_only_no_file_write",
            "candidate_raw_values_are_pending_review_only",
            "pending_review_is_not_release_evidence",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_literature_response_only_export(self) -> "LiteratureExtractionCandidateReviewPacketExportResponse":
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review packet export cannot report mutation side effects")
        if self.export_manifest.get("export_policy") != "response_only_no_file_write":
            raise ValueError("literature extraction review packet export must be response-only")
        return self


class LiteratureExtractionCandidateReviewPacketBulkExportResponse(BaseModel):
    schema_version: Literal["literature_extraction_candidate_review_packet_bulk_export_v1"] = (
        "literature_extraction_candidate_review_packet_bulk_export_v1"
    )
    tenant_id: int
    export_format: Literal["json"] = "json"
    export_filename: str
    content_hash: str
    export_manifest: dict[str, Any]
    packet_exports: list[LiteratureExtractionCandidateReviewPacketExportResponse]
    count: int
    metric_counts: dict[str, int]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_bulk_export_is_read_only",
            "export_response_only_no_file_write",
            "tenant_scoped_persisted_candidates_only",
            "pending_review_is_not_release_evidence",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_bulk_response_only_export(self) -> "LiteratureExtractionCandidateReviewPacketBulkExportResponse":
        if self.count != len(self.packet_exports):
            raise ValueError("literature extraction bulk export count must match packet exports")
        if any(self.side_effects.values()):
            raise ValueError("literature extraction bulk export cannot report mutation side effects")
        if self.export_manifest.get("export_policy") != "response_only_no_file_write":
            raise ValueError("literature extraction bulk export must be response-only")
        if self.export_manifest.get("candidate_count") != self.count:
            raise ValueError("literature extraction bulk export manifest must include candidate_count")
        for packet_export in self.packet_exports:
            if any(packet_export.side_effects.values()):
                raise ValueError("literature extraction child export cannot report mutation side effects")
        return self


class LiteratureExtractionReviewDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_intent: Literal[
        "needs_review",
        "approve_candidate_use_intent",
        "reject_candidate_intent",
        "needs_license_clearance",
    ] = "needs_review"
    reviewer_notes: str = ""
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_review_draft_request_boundary(self) -> "LiteratureExtractionReviewDraftCreateRequest":
        if not self.idempotency_key.strip():
            raise ValueError("literature extraction review draft idempotency key is required")
        return self


class LiteratureExtractionReviewDraftResponse(BaseModel):
    schema_version: Literal["literature_extraction_review_draft_v1"] = "literature_extraction_review_draft_v1"
    review_draft_id: str
    tenant_id: int
    candidate_id: str
    source_id: str
    reviewer_user_id: int
    review_intent: Literal[
        "needs_review",
        "approve_candidate_use_intent",
        "reject_candidate_intent",
        "needs_license_clearance",
    ]
    reviewer_notes: str
    status: Literal["draft_intent_recorded"] = "draft_intent_recorded"
    source_review_packet_export_id: str
    source_review_packet_hash: str
    candidate_snapshot: dict[str, Any]
    export_manifest: dict[str, Any]
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "candidate_status_update": False,
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_review_draft_records_intent_only",
            "candidate_status_remains_pending_review",
            "draft_is_not_release_evidence",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    idempotency_key: str
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_review_draft_side_effect_gate(self) -> "LiteratureExtractionReviewDraftResponse":
        if self.status != "draft_intent_recorded":
            raise ValueError("literature extraction review draft must remain an intent record")
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review draft cannot report mutation side effects")
        if (
            self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature extraction review draft cannot enable release, runtime, defaults, promotion, or final actions")
        if self.candidate_snapshot.get("review_status") != "pending_review":
            raise ValueError("literature extraction review draft candidate snapshot must remain pending_review")
        if self.export_manifest.get("export_policy") != "response_only_no_file_write":
            raise ValueError("literature extraction review draft must reference a response-only packet export")
        return self


class LiteratureExtractionReviewDraftListResponse(BaseModel):
    schema_version: Literal["literature_extraction_review_draft_list_v1"] = "literature_extraction_review_draft_list_v1"
    tenant_id: int
    count: int
    drafts: list[LiteratureExtractionReviewDraftResponse] = Field(default_factory=list)
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "candidate_status_update": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_review_draft_list_is_read_only",
            "candidate_status_remains_pending_review",
            "drafts_are_not_release_evidence",
            "tenant_scoped_review_drafts",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_review_draft_list_gate(self) -> "LiteratureExtractionReviewDraftListResponse":
        if self.count != len(self.drafts):
            raise ValueError("literature extraction review draft count must match drafts")
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review draft list cannot report mutation side effects")
        return self


class LiteratureExtractionReviewDraftRevisionRead(BaseModel):
    review_draft_id: str
    revision_index: int
    revision_hash: str
    candidate_snapshot_hash: str
    export_manifest_hash: str
    source_review_packet_hash: str
    review_intent: Literal[
        "needs_review",
        "approve_candidate_use_intent",
        "reject_candidate_intent",
        "needs_license_clearance",
    ]
    changed_fields: list[str] = Field(default_factory=list)
    side_effects: dict[str, bool]
    created_at: str

    @model_validator(mode="after")
    def enforce_revision_read_only_gate(self) -> "LiteratureExtractionReviewDraftRevisionRead":
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review draft revision cannot report mutation side effects")
        return self


class LiteratureExtractionReviewDraftComparisonResponse(BaseModel):
    schema_version: Literal["literature_extraction_review_draft_comparison_v1"] = (
        "literature_extraction_review_draft_comparison_v1"
    )
    tenant_id: int
    candidate_id: str
    current_review_draft_id: str
    previous_review_draft_id: str | None = None
    current_revision_hash: str
    current_candidate_snapshot_hash: str
    current_export_manifest_hash: str
    source_review_packet_hash: str
    current_response_packet_hash: str | None = None
    changed_field_filter: str | None = None
    comparison_manifest: dict[str, Any]
    report_manifest: dict[str, Any]
    report_payload: dict[str, Any]
    comparison_summary: dict[str, bool]
    changed_fields: list[str] = Field(default_factory=list)
    audit_trail: list[LiteratureExtractionReviewDraftRevisionRead] = Field(default_factory=list)
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "candidate_status_update": False,
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_extraction_review_draft_comparison_is_read_only",
            "derived_from_review_draft_records",
            "candidate_status_remains_pending_review",
            "comparison_is_not_release_evidence",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_comparison_response_only_gate(self) -> "LiteratureExtractionReviewDraftComparisonResponse":
        if any(self.side_effects.values()):
            raise ValueError("literature extraction review draft comparison cannot report mutation side effects")
        if self.comparison_manifest.get("comparison_policy") != "response_only_no_file_write":
            raise ValueError("literature extraction review draft comparison must be response-only")
        if self.report_manifest.get("report_policy") != "response_only_no_file_write":
            raise ValueError("literature extraction review draft comparison report must be response-only")
        if self.comparison_manifest.get("candidate_status") != "pending_review":
            raise ValueError("literature extraction review draft comparison must keep candidate pending_review")
        if self.comparison_manifest.get("release_evidence_allowed") is not False:
            raise ValueError("literature extraction review draft comparison cannot allow release evidence")
        if self.comparison_manifest.get("runtime_activation_enabled") is not False:
            raise ValueError("literature extraction review draft comparison cannot enable runtime activation")
        if self.comparison_manifest.get("validated_default_write_enabled") is not False:
            raise ValueError("literature extraction review draft comparison cannot enable default writes")
        if self.comparison_manifest.get("promotion_enabled") is not False:
            raise ValueError("literature extraction review draft comparison cannot enable promotion")
        if self.comparison_manifest.get("final_action_execution") is not False:
            raise ValueError("literature extraction review draft comparison cannot enable final actions")
        return self


class LiteratureExtractionEvidenceChainReadinessResponse(BaseModel):
    schema_version: Literal["literature_extraction_evidence_chain_readiness_v1"] = (
        "literature_extraction_evidence_chain_readiness_v1"
    )
    tenant_id: int
    chain_complete: bool
    candidate_count: int
    packet_export_ready: bool
    bulk_export_ready: bool
    review_draft_count: int
    comparison_ready: bool
    report_ready: bool
    auto_use_allowed: bool = False
    promotion_ready: bool = False
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "candidate_status_update": False,
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "literature_evidence_chain_readiness_is_read_only",
            "chain_complete_does_not_allow_auto_use",
            "candidate_raw_values_remain_pending_review",
            "release_evidence_allowed_false",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "promotion_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    blocking_reason: str | None = None
    readiness_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_readiness_read_only_gate(self) -> "LiteratureExtractionEvidenceChainReadinessResponse":
        if any(self.side_effects.values()):
            raise ValueError("literature extraction evidence chain readiness cannot report mutation side effects")
        if (
            self.auto_use_allowed
            or self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature extraction evidence chain readiness cannot enable auto-use or execution")
        return self


class LiteratureValuePromotionReadinessResponse(BaseModel):
    schema_version: Literal["literature_value_promotion_readiness_v1"] = "literature_value_promotion_readiness_v1"
    tenant_id: int
    candidate_id: str
    chain_complete: bool
    promotion_ready: bool
    review_draft_id: str | None = None
    source_review_packet_hash: str | None = None
    comparison_hash: str | None = None
    raw_value: str | None = None
    unit: str | None = None
    conditions: dict[str, str] = Field(default_factory=dict)
    request_status: Literal["not_requested", "requested", "approved", "approved_for_promotion", "rejected"] = (
        "not_requested"
    )
    existing_promotion_request_id: str | None = None
    target_use_options: list[str] = Field(
        default_factory=lambda: [
            "candidate_overlay_review",
            "scoped_runtime_overlay_review",
            "release_evidence_review",
        ]
    )
    auto_use_allowed: bool = False
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "overlay_write": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "promotion_readiness_is_request_only",
            "promotion_ready_does_not_enable_promotion",
            "no_overlay_write",
            "no_runtime_activation",
            "no_release_evidence_use",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    blocking_reason: str | None = None

    @model_validator(mode="after")
    def enforce_promotion_readiness_boundary(self) -> "LiteratureValuePromotionReadinessResponse":
        if any(self.side_effects.values()):
            raise ValueError("literature value promotion readiness cannot report mutation side effects")
        if (
            self.auto_use_allowed
            or self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature value promotion readiness cannot enable use or execution")
        return self


class LiteratureValuePromotionRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_use: str = "candidate_overlay_review"
    target_scope: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_request_payload(self) -> "LiteratureValuePromotionRequestCreateRequest":
        if not self.target_use.strip():
            raise ValueError("literature value promotion request target_use is required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value promotion request idempotency_key is required")
        return self


class LiteratureValuePromotionRequestResponse(BaseModel):
    schema_version: Literal["literature_value_promotion_request_v1"] = "literature_value_promotion_request_v1"
    promotion_request_id: str
    tenant_id: int
    candidate_id: str
    source_review_packet_hash: str
    review_draft_id: str
    comparison_hash: str
    raw_value: str
    unit: str
    conditions: dict[str, str]
    target_use: str
    target_scope: dict[str, Any]
    request_status: Literal["requested", "approved", "approved_for_promotion", "rejected"] = "requested"
    requested_by_user_id: int
    idempotency_key: str
    auto_use_allowed: bool = False
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "overlay_write": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "promotion_request_is_request_only",
            "request_status_requested_not_active",
            "no_overlay_write",
            "no_runtime_activation",
            "no_release_evidence_use",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_promotion_request_boundary(self) -> "LiteratureValuePromotionRequestResponse":
        if self.request_status not in {"requested", "approved", "approved_for_promotion", "rejected"}:
            raise ValueError("literature value promotion request status is invalid")
        if any(self.side_effects.values()):
            raise ValueError("literature value promotion request cannot report mutation side effects")
        if (
            self.auto_use_allowed
            or self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature value promotion request cannot enable use or execution")
        return self


class LiteratureValuePromotionApprovalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_action: Literal["approve", "reject"] = "approve"
    approver_notes: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_approval_payload(self) -> "LiteratureValuePromotionApprovalCreateRequest":
        if not self.approver_notes.strip():
            raise ValueError("literature value promotion approval notes are required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value promotion approval idempotency_key is required")
        return self


class LiteratureValuePromotionRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rejector_notes: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_reject_payload(self) -> "LiteratureValuePromotionRejectRequest":
        if not self.rejector_notes.strip():
            raise ValueError("literature value promotion rejection notes are required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value promotion rejection idempotency_key is required")
        return self


class LiteratureValuePromotionApprovalResponse(BaseModel):
    schema_version: Literal["literature_value_promotion_approval_v1"] = "literature_value_promotion_approval_v1"
    approval_id: str
    tenant_id: int
    promotion_request_id: str
    candidate_id: str
    approval_action: Literal["approve", "reject"]
    request_status_before: Literal["requested", "approved", "approved_for_promotion", "rejected"]
    request_status_after: Literal["requested", "approved", "approved_for_promotion", "rejected"]
    approved_by_user_id: int
    approved_by_user_roles: list[str] = Field(default_factory=list)
    approver_notes: str
    idempotency_key: str
    source_review_packet_hash: str
    review_draft_id: str
    comparison_hash: str
    target_use: str
    target_scope: dict[str, Any]
    approval_audit_only: bool = True
    overlay_write_enabled: bool = False
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    promotion_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "overlay_write": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "promotion_approval_is_audit_only",
            "requester_self_approval_forbidden",
            "dual_role_approval_required",
            "scientist_and_release_or_compliance_required",
            "approval_does_not_create_overlay",
            "approval_does_not_activate_runtime",
            "approval_does_not_allow_release_evidence",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_promotion_approval_boundary(self) -> "LiteratureValuePromotionApprovalResponse":
        if self.request_status_after not in {"requested", "approved", "approved_for_promotion", "rejected"}:
            raise ValueError("literature value promotion approval status is invalid")
        if self.approval_action == "approve" and self.request_status_after not in {"requested", "approved_for_promotion"}:
            raise ValueError("approval action approve must keep request requested or set approved_for_promotion")
        if self.approval_action == "reject" and self.request_status_after != "rejected":
            raise ValueError("approval action reject must set request_status_after rejected")
        if any(self.side_effects.values()):
            raise ValueError("literature value promotion approval cannot report mutation side effects")
        if (
            not self.approval_audit_only
            or self.overlay_write_enabled
            or self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.promotion_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature value promotion approval cannot enable overlay, runtime, release, or execution")
        return self


class LiteratureValueOverlayCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overlay_notes: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_overlay_payload(self) -> "LiteratureValueOverlayCreateRequest":
        if not self.overlay_notes.strip():
            raise ValueError("literature value overlay notes are required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value overlay idempotency_key is required")
        return self


class LiteratureValueOverlayResponse(BaseModel):
    schema_version: Literal["literature_value_overlay_v1"] = "literature_value_overlay_v1"
    overlay_id: str
    tenant_id: int
    promotion_request_id: str
    approval_id: str
    candidate_id: str
    overlay_status: Literal["inactive", "promoted_inactive", "rolled_back"] = "inactive"
    overlay_active: bool = False
    source_review_packet_hash: str
    review_draft_id: str
    comparison_hash: str
    raw_value: str
    normalized_value: str = ""
    unit: str
    source_ref: str = ""
    approval_hash: str = ""
    overlay_hash: str = ""
    conditions: dict[str, str]
    target_use: str
    target_scope: dict[str, Any]
    validity_scope: dict[str, Any] = Field(default_factory=dict)
    rollback_pointer: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: int
    overlay_notes: str
    idempotency_key: str
    release_evidence_allowed: bool = False
    runtime_activation_enabled: bool = False
    validated_default_write_enabled: bool = False
    final_action_execution: bool = False
    rollback_required_before_use_change: bool = True
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "overlay_created_inactive",
            "promoted_overlay_record_alias_supported",
            "overlay_hash_is_response_derived",
            "overlay_requires_separate_scoped_runtime_activation",
            "no_runtime_activation",
            "no_release_evidence_use",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_overlay_boundary(self) -> "LiteratureValueOverlayResponse":
        if self.overlay_status not in {"inactive", "promoted_inactive", "rolled_back"} or self.overlay_active:
            raise ValueError("literature value overlay must remain inactive, promoted_inactive, or rolled_back")
        if not self.normalized_value:
            self.normalized_value = f"{self.raw_value} {self.unit}".strip()
        if not self.source_ref:
            self.source_ref = str(self.conditions.get("source_ref") or self.source_review_packet_hash)
        if not self.validity_scope:
            self.validity_scope = dict(self.target_scope)
        if not self.rollback_pointer:
            self.rollback_pointer = {
                "required": True,
                "status": "not_rolled_back" if self.overlay_status != "rolled_back" else "rolled_back",
            }
        if any(self.side_effects.values()):
            raise ValueError("literature value overlay creation cannot report runtime, release, default, or final-action side effects")
        if (
            self.release_evidence_allowed
            or self.runtime_activation_enabled
            or self.validated_default_write_enabled
            or self.final_action_execution
            or not self.rollback_required_before_use_change
        ):
            raise ValueError("literature value overlay cannot enable runtime, release, default writes, or final actions")
        return self


LITERATURE_VALUE_ALLOWED_RUNTIME_SCOPE_KEYS = {
    "batch_id",
    "feedstock_key",
    "species_code",
    "locality_profile_id",
    "campaign_key",
}

LITERATURE_VALUE_BLOCKED_RUNTIME_SCOPE_KEYS = {
    "global",
    "default",
    "all",
    "all_tenants",
    "all_batches",
    "global_default",
}


def validate_literature_value_runtime_scope(scope: dict[str, Any]) -> dict[str, Any]:
    if not scope:
        raise ValueError("literature value runtime activation requires a non-empty scope")
    normalized = {str(key): value for key, value in scope.items()}
    blocked = sorted(set(normalized) & LITERATURE_VALUE_BLOCKED_RUNTIME_SCOPE_KEYS)
    if blocked:
        raise ValueError("literature value runtime activation cannot use global/default scope keys")
    allowed = sorted(set(normalized) & LITERATURE_VALUE_ALLOWED_RUNTIME_SCOPE_KEYS)
    if not allowed:
        raise ValueError("literature value runtime activation scope must include a supported scoped key")
    empty = [key for key in allowed if normalized.get(key) in (None, "")]
    if empty:
        raise ValueError("literature value runtime activation scope values cannot be empty")
    return normalized


class LiteratureValueRuntimeActivationPreviewResponse(BaseModel):
    schema_version: Literal["literature_value_runtime_activation_preview_v1"] = (
        "literature_value_runtime_activation_preview_v1"
    )
    tenant_id: int
    overlay_id: str
    candidate_id: str
    overlay_status: Literal["inactive", "rolled_back"] = "inactive"
    approved_overlay: bool = True
    activation_scope_options: list[str] = Field(
        default_factory=lambda: sorted(LITERATURE_VALUE_ALLOWED_RUNTIME_SCOPE_KEYS)
    )
    can_activate_scoped_runtime: bool
    blocking_reason: str | None = None
    global_activation_allowed: bool = False
    release_evidence_allowed: bool = False
    validated_default_write_enabled: bool = False
    final_action_execution: bool = False
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "activation_preview_is_read_only",
            "approved_overlay_required",
            "scope_required",
            "global_activation_forbidden",
            "no_release_evidence_use",
            "no_validated_default_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_activation_preview_boundary(self) -> "LiteratureValueRuntimeActivationPreviewResponse":
        if self.overlay_status != "inactive" and self.can_activate_scoped_runtime:
            raise ValueError("activation preview cannot activate a rolled back overlay")
        if (
            self.global_activation_allowed
            or self.release_evidence_allowed
            or self.validated_default_write_enabled
            or self.final_action_execution
        ):
            raise ValueError("activation preview cannot enable global runtime, release, defaults, or final actions")
        return self


class LiteratureValueRuntimeActivationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_scope: dict[str, Any]
    operator_attestation: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_runtime_activation_payload(self) -> "LiteratureValueRuntimeActivationCreateRequest":
        self.activation_scope = validate_literature_value_runtime_scope(self.activation_scope)
        if not self.operator_attestation.strip():
            raise ValueError("literature value runtime activation operator_attestation is required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value runtime activation idempotency_key is required")
        return self


class LiteratureValueRuntimeActivationDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deactivation_reason: str = Field(..., min_length=1)
    operator_attestation: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_runtime_deactivation_payload(self) -> "LiteratureValueRuntimeActivationDeactivateRequest":
        if not self.deactivation_reason.strip():
            raise ValueError("literature value runtime activation deactivation_reason is required")
        if not self.operator_attestation.strip():
            raise ValueError("literature value runtime activation deactivation attestation is required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value runtime activation deactivation idempotency_key is required")
        return self


class LiteratureValueRuntimeActivationResponse(BaseModel):
    schema_version: Literal["literature_value_runtime_activation_v1"] = "literature_value_runtime_activation_v1"
    activation_id: str
    tenant_id: int
    overlay_id: str
    promotion_request_id: str
    approval_id: str
    candidate_id: str
    activation_status: Literal["active", "deactivated"]
    activation_scope: dict[str, Any]
    scope_key: str
    activated_by_user_id: int
    operator_attestation: str
    deactivated_by_user_id: int | None = None
    deactivation_reason: str | None = None
    deactivated_at: str | None = None
    idempotency_key: str
    runtime_display: str
    scoped_runtime_activation_enabled: bool
    global_activation_allowed: bool = False
    release_evidence_allowed: bool = False
    validated_default_write_enabled: bool = False
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "scoped_runtime_activation": True,
            "global_runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "scoped_runtime_activation_only",
            "scope_required",
            "global_activation_forbidden",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_release_evidence_use",
            "no_final_action_execution",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_runtime_activation_boundary(self) -> "LiteratureValueRuntimeActivationResponse":
        validate_literature_value_runtime_scope(self.activation_scope)
        if self.activation_status == "active" and not self.scoped_runtime_activation_enabled:
            raise ValueError("active literature runtime activation must be scoped-enabled")
        if self.activation_status == "deactivated" and self.scoped_runtime_activation_enabled:
            raise ValueError("deactivated literature runtime activation cannot remain scoped-enabled")
        if (
            self.side_effects.get("global_runtime_activation")
            or self.side_effects.get("validated_default_write")
            or self.side_effects.get("species_db_write")
            or self.side_effects.get("feedstock_db_write")
            or self.side_effects.get("release_evidence_use")
            or self.side_effects.get("final_action_execution")
        ):
            raise ValueError("literature runtime activation cannot enable global/default/release/final-action side effects")
        if (
            self.global_activation_allowed
            or self.release_evidence_allowed
            or self.validated_default_write_enabled
            or self.final_action_execution
        ):
            raise ValueError("literature runtime activation cannot enable global runtime, release, defaults, or final actions")
        if "external literature overlay active for this scope" not in self.runtime_display:
            raise ValueError("runtime display must identify external literature overlay scoped activation")
        return self


class LiteratureValueReleaseEvidenceLinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: str = Field(..., min_length=1)
    link_notes: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_release_evidence_link_payload(self) -> "LiteratureValueReleaseEvidenceLinkCreateRequest":
        if not self.activation_id.strip():
            raise ValueError("literature value release evidence link activation_id is required")
        if not self.link_notes.strip():
            raise ValueError("literature value release evidence link notes are required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value release evidence link idempotency_key is required")
        return self


class LiteratureValueReleaseEvidenceLinkResponse(BaseModel):
    schema_version: Literal["literature_value_release_evidence_link_v1"] = (
        "literature_value_release_evidence_link_v1"
    )
    link_id: str
    tenant_id: int
    release_decision_id: int
    activation_id: str
    overlay_id: str
    promotion_request_id: str
    approval_id: str
    candidate_id: str
    link_status: Literal["active", "superseded", "rolled_back"] = "active"
    rollback_status: Literal["none", "superseded", "rolled_back"] = "none"
    activation_scope: dict[str, Any]
    scope_key: str
    source_review_packet_hash: str
    comparison_hash: str
    release_decision_before: Literal["review_required"]
    release_decision_after: Literal["review_required"]
    linked_by_user_id: int
    link_notes: str
    idempotency_key: str
    release_decision_unchanged: bool = True
    human_review_required: bool = True
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "release_decision_update": False,
            "release_auto_approval": False,
            "final_action_execution": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "release_evidence_link_requires_active_scoped_overlay",
            "release_decision_remains_review_required",
            "human_review_required",
            "no_release_auto_approval",
            "no_final_action_execution",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_release_evidence_link_boundary(self) -> "LiteratureValueReleaseEvidenceLinkResponse":
        validate_literature_value_runtime_scope(self.activation_scope)
        if self.release_decision_before != "review_required" or self.release_decision_after != "review_required":
            raise ValueError("literature evidence link must preserve review_required release decision")
        if not self.release_decision_unchanged or not self.human_review_required or self.final_action_execution:
            raise ValueError("literature evidence link cannot auto-approve release or execute final actions")
        if any(self.side_effects.values()):
            raise ValueError("literature evidence link cannot report release/default/final-action mutation side effects")
        return self


class LiteratureValueRollbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollback_reason: str = Field(..., min_length=1)
    operator_attestation: str = Field(..., min_length=1)
    idempotency_key: str

    @model_validator(mode="after")
    def enforce_rollback_payload(self) -> "LiteratureValueRollbackCreateRequest":
        if not self.rollback_reason.strip():
            raise ValueError("literature value rollback reason is required")
        if not self.operator_attestation.strip():
            raise ValueError("literature value rollback attestation is required")
        if not self.idempotency_key.strip():
            raise ValueError("literature value rollback idempotency_key is required")
        return self


class LiteratureValueRollbackResponse(BaseModel):
    schema_version: Literal["literature_value_rollback_v1"] = "literature_value_rollback_v1"
    rollback_id: str
    tenant_id: int
    activation_id: str
    overlay_id: str
    promotion_request_id: str
    approval_id: str
    candidate_id: str
    rollback_status: Literal["completed"] = "completed"
    activation_status_before: Literal["active", "deactivated"]
    activation_status_after: Literal["deactivated"]
    overlay_status_before: Literal["inactive", "rolled_back"]
    overlay_status_after: Literal["rolled_back"]
    affected_release_evidence_link_ids: list[str]
    release_evidence_link_status_updates: list[dict[str, Any]]
    release_decision_states: list[dict[str, Any]]
    rolled_back_by_user_id: int
    rollback_reason: str
    operator_attestation: str
    idempotency_key: str
    release_decision_unchanged: bool = True
    human_review_required: bool = True
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "runtime_deactivation": True,
            "overlay_status_update": True,
            "release_evidence_link_status_update": True,
            "release_decision_update": False,
            "release_auto_approval": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "rollback_is_append_only_audit_record",
            "runtime_activation_deactivated",
            "overlay_marked_rolled_back",
            "release_evidence_links_retained_and_marked_rolled_back",
            "release_decision_remains_review_required",
            "human_review_required",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def enforce_rollback_boundary(self) -> "LiteratureValueRollbackResponse":
        if self.activation_status_after != "deactivated" or self.overlay_status_after != "rolled_back":
            raise ValueError("literature rollback must deactivate runtime and mark overlay rolled_back")
        if not self.release_decision_unchanged or not self.human_review_required or self.final_action_execution:
            raise ValueError("literature rollback cannot approve release or execute final actions")
        forbidden = (
            "runtime_activation",
            "release_decision_update",
            "release_auto_approval",
            "validated_default_write",
            "species_db_write",
            "feedstock_db_write",
            "final_action_execution",
        )
        if any(self.side_effects.get(key) for key in forbidden):
            raise ValueError("literature rollback cannot report default/release/final-action mutation side effects")
        for state in self.release_decision_states:
            if state.get("release_decision_before") != "review_required" or state.get("release_decision_after") != "review_required":
                raise ValueError("literature rollback must preserve review_required release decisions")
        return self


class LiteratureValuePromotionLifecycleResponse(BaseModel):
    schema_version: Literal["literature_value_promotion_lifecycle_v1"] = (
        "literature_value_promotion_lifecycle_v1"
    )
    tenant_id: int
    candidate_id: str
    promotion_request_count: int
    approval_count: int
    overlay_count: int
    runtime_activation_count: int
    release_evidence_link_count: int
    rollback_count: int
    promotion_request_ids: list[str]
    approval_ids: list[str]
    overlay_ids: list[str]
    activation_ids: list[str]
    release_evidence_link_ids: list[str]
    rollback_ids: list[str]
    request_statuses: list[str]
    approval_actions: list[str]
    overlay_statuses: list[str]
    activation_statuses: list[str]
    release_evidence_link_statuses: list[str]
    rollback_statuses: list[str]
    release_decision_states: list[dict[str, Any]]
    lifecycle_read_only: bool = True
    release_decision_unchanged: bool = True
    human_review_required: bool = True
    final_action_execution: bool = False
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "lifecycle_read": False,
            "promotion_request_write": False,
            "approval_write": False,
            "overlay_write": False,
            "runtime_activation": False,
            "runtime_deactivation": False,
            "release_evidence_link_write": False,
            "rollback_write": False,
            "release_decision_update": False,
            "release_auto_approval": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "promotion_lifecycle_is_read_only",
            "release_decision_remains_review_required",
            "human_review_required",
            "no_runtime_activation",
            "no_runtime_deactivation",
            "no_release_auto_approval",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_lifecycle_boundary(self) -> "LiteratureValuePromotionLifecycleResponse":
        if not self.lifecycle_read_only or not self.release_decision_unchanged or not self.human_review_required:
            raise ValueError("literature promotion lifecycle must remain read-only and human-review gated")
        if self.final_action_execution or any(self.side_effects.values()):
            raise ValueError("literature promotion lifecycle cannot report mutation side effects")
        for state in self.release_decision_states:
            before = state.get("release_decision_before")
            after = state.get("release_decision_after")
            if before != "review_required" or after != "review_required":
                raise ValueError("literature promotion lifecycle must preserve review_required release decisions")
        return self


class LiteratureValuePromotionAuditExportResponse(BaseModel):
    schema_version: Literal["literature_value_promotion_audit_export_v1"] = (
        "literature_value_promotion_audit_export_v1"
    )
    tenant_id: int
    candidate_id: str
    export_format: Literal["json"] = "json"
    export_policy: Literal["response_only_no_file_write"] = "response_only_no_file_write"
    content_hash: str
    export_manifest: dict[str, Any]
    request: dict[str, Any] | None = None
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    overlay: dict[str, Any] | None = None
    runtime_activation: dict[str, Any] | None = None
    release_evidence_link: dict[str, Any] | None = None
    rollback: dict[str, Any] | None = None
    db_pollution_proof: dict[str, Any]
    final_action_non_execution_proof: dict[str, Any]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "file_written": False,
            "runtime_activation": False,
            "runtime_deactivation": False,
            "release_decision_update": False,
            "release_auto_approval": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "promotion_audit_export_is_response_only",
            "export_response_only_no_file_write",
            "request_approval_overlay_activation_release_rollback_manifest",
            "db_pollution_proof_included",
            "release_decision_remains_review_required",
            "final_action_non_execution_proof_included",
            "no_validated_default_writes",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_audit_export_boundary(self) -> "LiteratureValuePromotionAuditExportResponse":
        if self.export_policy != "response_only_no_file_write":
            raise ValueError("literature promotion audit export must be response-only")
        if self.export_manifest.get("file_written") is not False:
            raise ValueError("literature promotion audit export cannot write files")
        if any(self.side_effects.values()):
            raise ValueError("literature promotion audit export cannot report mutation side effects")
        for key in ("validated_default_write", "species_db_write", "feedstock_db_write"):
            if self.db_pollution_proof.get(key) is not False:
                raise ValueError("literature promotion audit export must prove default DBs were not polluted")
        if self.final_action_non_execution_proof.get("final_action_execution") is not False:
            raise ValueError("literature promotion audit export must prove final actions did not execute")
        release_states = self.final_action_non_execution_proof.get("release_decision_states", [])
        for state in release_states:
            if state.get("release_decision_before") != "review_required" or state.get("release_decision_after") != "review_required":
                raise ValueError("literature promotion audit export must preserve review_required release decisions")
        return self


class ExternalSourceReviewCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    card_id: str
    shortlist_id: str
    source_id: str
    doi: str
    source_url: str
    title: str
    review_status: str = "pending_review"
    review_action: ReviewActionState = "pending_review"
    reviewer: str = "unassigned"
    reviewer_user_id: int | None = None
    reviewed_at: datetime | None = None
    license_status: str = "pending_review"
    evidence_source_kind: str
    ingestion_mode: str
    human_review_required: bool = True
    extracted_numeric_values_allowed: bool = False
    boundary_condition_required: bool = True
    allowed_use: str
    blocked_use: str
    next_action: str
    boundary_metadata: dict[str, Any]
    raw_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    promotion_enabled: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False

    @model_validator(mode="after")
    def enforce_read_guardrails(self) -> "ExternalSourceReviewCardRead":
        self.review_action = review_action_for_status(self.review_status)  # type: ignore[assignment]
        if not self.human_review_required:
            raise ValueError("review cards must require human review")
        if self.extracted_numeric_values_allowed:
            raise ValueError("review cards cannot allow numeric extraction before resolution")
        if self.promotion_enabled or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("review cards cannot enable promotion, runtime activation, or default writes")
        return self


class ExternalSourceReviewCardListResponse(BaseModel):
    items: list[ExternalSourceReviewCardRead]
    count: int


class ExternalSourceExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    extraction_id: str
    card_id: str
    source_id: str
    extraction_status: str
    extracted_metadata: dict[str, Any]
    extracted_numeric_values: dict[str, Any]
    numeric_values_included: bool = False
    boundary_metadata: dict[str, Any]
    human_review_required: bool = True
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def reject_unreviewed_numeric_values(self) -> "ExternalSourceExtractionRead":
        if self.numeric_values_included or self.extracted_numeric_values:
            raise ValueError("extraction records cannot include numeric values before reviewed candidate approval")
        return self


class ExternalSourceExtractionListResponse(BaseModel):
    items: list[ExternalSourceExtractionRead]
    count: int
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "extractions_are_review_inputs",
            "numeric_values_blocked_for_bsf_metadata_lane",
            "no_runtime_activation",
        ]
    )


class BsfReviewedMetadataCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_version: str = "bsf-reviewed-metadata-v1"
    candidate_family: Literal["bsf_reviewed_metadata"] = "bsf_reviewed_metadata"
    card_id: str = Field(..., pattern=r"^BSF-CARD-\d{3}$")
    shortlist_id: str = Field(..., pattern=r"^BSF-LIT-\d{3}$")
    source_catalog_id: str = Field(..., pattern=r"^(A-BSF|B-FEED|C-LCA|D-TEA|E-COMP|F-MODEL|G-OSS)-\d{3}$")
    doi: str = Field(..., pattern=r"^10\.\d{4,9}/\S+$")
    source_url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    article_type: str = Field(..., min_length=1)
    target_boundary_fields: str = Field(..., min_length=1)
    boundary_condition: str = Field(..., min_length=1)
    allowed_use: str = Field(..., min_length=1)
    blocked_use: str = Field(..., min_length=1)
    evidence_source_kind: EvidenceSourceKind
    ingestion_mode: ReferenceIngestionMode
    license_status: LicenseStatus
    review_status: Literal["approved_for_candidate_use"] = "approved_for_candidate_use"
    source_kind: EvidenceSourceKind
    source_ref: str = Field(..., min_length=1)
    numeric_values_included: bool = False
    extracted_numeric_values: dict[str, Any] = Field(default_factory=dict)
    promotion_enabled: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False
    runtime_activation_required_before_use: bool = True
    reviewer_annotations: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_metadata_lane(self) -> "BsfReviewedMetadataCandidatePayload":
        if self.numeric_values_included or self.extracted_numeric_values:
            raise ValueError("BSF reviewed metadata candidates cannot include numeric values in phase 2")
        if self.promotion_enabled or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("BSF reviewed metadata candidates cannot enable promotion, runtime activation, or default writes")
        if not self.runtime_activation_required_before_use:
            raise ValueError("runtime activation remains required before BOS runtime use")
        blocked = self.blocked_use.lower()
        if "default" not in blocked or "release evidence" not in blocked:
            raise ValueError("blocked_use must block validated defaults and release evidence")
        return self


class ReviewedMetadataCandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload_version: str = "reviewed-metadata-candidate-v1"
    candidate_type: ReviewedCandidateType
    candidate_family: Literal["reviewed_metadata_candidate"] = "reviewed_metadata_candidate"
    candidate_type_group: Literal["reviewed_metadata_candidate"] = "reviewed_metadata_candidate"
    candidate_domain: str
    card_id: str = Field(..., min_length=1)
    shortlist_id: str = Field(..., min_length=1)
    source_catalog_id: str = Field(..., pattern=r"^(A-BSF|B-FEED|C-LCA|D-TEA|E-COMP|F-MODEL|G-OSS)-\d{3}$")
    doi: str = Field(..., min_length=1)
    source_url: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    boundary_condition: str = Field(..., min_length=1)
    allowed_use: str = Field(..., min_length=1)
    blocked_use: str = Field(..., min_length=1)
    evidence_source_kind: EvidenceSourceKind
    ingestion_mode: ReferenceIngestionMode
    license_status: LicenseStatus
    source_kind: EvidenceSourceKind
    source_ref: str = Field(..., min_length=1)
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)
    boundary_metadata: dict[str, Any] = Field(default_factory=dict)
    numeric_values_included: bool = False
    extracted_numeric_values: dict[str, Any] = Field(default_factory=dict)
    promotion_enabled: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False
    runtime_activation_required_before_use: bool = True
    read_only: bool = True
    metadata_only: bool = True
    reviewer_annotations: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_metadata_only_candidate(self) -> "ReviewedMetadataCandidatePayload":
        expected_domain = reviewed_candidate_domain(self.candidate_type)
        if self.candidate_domain != expected_domain:
            raise ValueError(f"candidate_domain must be {expected_domain} for {self.candidate_type}")
        if self.numeric_values_included or self.extracted_numeric_values:
            raise ValueError("reviewed metadata candidates cannot include numeric values")
        if self.promotion_enabled or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("reviewed metadata candidates cannot enable promotion, runtime activation, or default writes")
        if not self.runtime_activation_required_before_use:
            raise ValueError("runtime activation remains required before BOS runtime use")
        if not self.read_only or not self.metadata_only:
            raise ValueError("reviewed metadata candidates must remain metadata-only and read-only")
        blocked = self.blocked_use.lower()
        if "default" not in blocked or "release evidence" not in blocked:
            raise ValueError("blocked_use must block validated defaults and release evidence")
        return self


class ReviewedExternalCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: int
    candidate_id: str
    candidate_type: str
    candidate_type_group: str = "reviewed_metadata_candidate"
    candidate_domain: str = "unknown"
    candidate_type_counts: dict[str, int] = Field(default_factory=dict)
    candidate_domain_counts: dict[str, int] = Field(default_factory=dict)
    candidate_key: str
    card_id: str
    source_id: str
    source_kind: str
    source_ref: str
    license_status: str
    license_note: str | None = None
    ingestion_mode: str
    review_status: str
    reviewer: str
    reviewed_at: datetime
    boundary_condition: str
    allowed_use: str
    blocked_use: str
    candidate_payload: dict[str, Any]
    human_review_required: bool = True
    promotion_enabled: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False
    activation_relation_id: str | None = None
    audit_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def enforce_candidate_guardrails(self) -> "ReviewedExternalCandidateRead":
        if self.candidate_type not in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES:
            raise ValueError(f"unsupported reviewed candidate type: {self.candidate_type}")
        if self.promotion_enabled or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("reviewed candidates cannot enable promotion, runtime activation, or default writes")
        payload = self.candidate_payload if isinstance(self.candidate_payload, dict) else {}
        if payload.get("numeric_values_included") is True or bool(payload.get("extracted_numeric_values")):
            raise ValueError("reviewed candidates cannot expose numeric values")
        if (
            payload.get("promotion_enabled") is True
            or payload.get("runtime_activated") is True
            or payload.get("validated_default_write_enabled") is True
        ):
            raise ValueError("reviewed candidate payload cannot enable promotion, runtime activation, or default writes")
        self.candidate_type_group = reviewed_candidate_type_group(self.candidate_type)
        self.candidate_domain = reviewed_candidate_domain(self.candidate_type)
        if not self.candidate_type_counts:
            self.candidate_type_counts = {self.candidate_type: 1}
        if not self.candidate_domain_counts:
            self.candidate_domain_counts = {self.candidate_domain: 1}
        return self


class ReviewedExternalCandidateListResponse(BaseModel):
    items: list[ReviewedExternalCandidateRead]
    count: int
    total_count: int | None = None
    offset: int = 0
    limit: int | None = None
    has_more: bool = False
    candidate_types: dict[str, int] = Field(default_factory=dict)
    candidate_domains: dict[str, int] = Field(default_factory=dict)
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "approved_for_candidate_use_is_not_runtime_activation",
            "runtime_activated_false_until_overlay_activation",
            "validated_default_write_enabled_false",
            "candidate_type_counts_are_read_only",
            "candidate_domain_counts_are_read_only",
            "pagination_is_read_only",
        ]
    )


class ReviewedExternalCandidateLaneSummary(BaseModel):
    schema_version: Literal["reviewed_external_candidate_lane_summary_v1"] = (
        "reviewed_external_candidate_lane_summary_v1"
    )
    tenant_id: int
    reviewed_candidate_count: int
    reviewed_metadata_candidate_count: int
    pending_runtime_activation_count: int
    runtime_activated_count: int
    validated_default_write_enabled_count: int
    numeric_value_candidate_count: int
    release_evidence_blocked_count: int
    statuses: dict[str, int]
    candidate_types: dict[str, int]
    candidate_domains: dict[str, int]
    latest_reviewed_at: datetime | None = None
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "summary_is_read_only",
            "approved_for_candidate_use_is_not_runtime_activation",
            "numeric_values_remain_blocked_for_bsf_metadata_lane",
            "validated_default_write_enabled_false",
        ]
    )


class ReviewedExternalCandidateKnowledgeBaseResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_knowledge_base_v1"] = (
        "reviewed_external_candidate_knowledge_base_v1"
    )
    tenant_id: int
    status: Literal["ready_for_review", "blocked"]
    schema_ready: bool
    source_catalog_ready: bool
    reviewed_metadata_lane_ready: bool
    knowledge_coverage_ready: bool
    knowledge_coverage_percent: float
    source_metadata_coverage_percent: float
    knowledge_coverage_domains: list[ExternalKnowledgeCoverageDomain]
    business_knowledge_coverage_percent: float
    business_knowledge_coverage_groups: list[BusinessKnowledgeCoverageGroup]
    supported_candidate_types: list[str]
    supported_candidate_domains: list[str]
    phase4a_domain_metadata_ready: bool
    phase4a_domain_candidate_counts: dict[str, int]
    phase4a_domain_expected_counts: dict[str, int]
    phase4a_domain_missing_counts: dict[str, int]
    reviewed_candidate_count: int
    reviewed_metadata_candidate_count: int
    pending_runtime_activation_count: int
    runtime_activated_count: int
    validated_default_write_enabled_count: int
    numeric_value_candidate_count: int
    candidate_types: dict[str, int]
    candidate_domains: dict[str, int]
    blockers: list[str]
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "knowledge_base_summary_is_read_only",
            "approved_for_candidate_use_is_not_runtime_activation",
            "runtime_activated_false_until_overlay_activation",
            "validated_default_write_enabled_false",
            "numeric_values_blocked",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )


class BusinessKnowledgeReviewPacketResponse(BaseModel):
    schema_version: Literal["business_knowledge_review_packet_v1"] = "business_knowledge_review_packet_v1"
    tenant_id: int
    group_key: str
    item: BusinessKnowledgeCoverageItem
    review_workflow: BusinessKnowledgeReviewWorkflow
    candidate_payload: dict[str, Any]
    source_trace: dict[str, Any]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "numeric_value_extraction": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "business_knowledge_review_packet_is_read_only",
            "review_workflow_is_pending_review",
            "numeric_values_blocked",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_read_only_business_packet(self) -> "BusinessKnowledgeReviewPacketResponse":
        if self.item.review_workflow is None:
            raise ValueError("business knowledge review packet requires item review workflow metadata")
        if self.item.numeric_values_included or self.review_workflow.numeric_values_allowed:
            raise ValueError("business knowledge review packet cannot include or allow numeric values")
        if (
            self.item.runtime_activation_enabled
            or self.item.validated_default_write_enabled
            or self.review_workflow.runtime_activation_enabled
            or self.review_workflow.validated_default_write_enabled
            or self.review_workflow.release_evidence_allowed
        ):
            raise ValueError("business knowledge review packet must keep runtime, defaults, and release evidence disabled")
        if any(self.side_effects.values()):
            raise ValueError("business knowledge review packet cannot report mutation side effects")
        return self


class BusinessKnowledgeReviewPacketExportResponse(BaseModel):
    schema_version: Literal["business_knowledge_review_packet_export_v1"] = (
        "business_knowledge_review_packet_export_v1"
    )
    tenant_id: int
    export_format: Literal["json"] = "json"
    export_filename: str
    content_hash: str
    export_manifest: dict[str, Any]
    review_packet: BusinessKnowledgeReviewPacketResponse
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "numeric_value_extraction": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "business_knowledge_review_packet_export_is_read_only",
            "export_response_only_no_file_write",
            "pending_review_is_not_release_evidence",
            "numeric_values_blocked",
            "runtime_activation_enabled_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_response_only_export(self) -> "BusinessKnowledgeReviewPacketExportResponse":
        if any(self.side_effects.values()):
            raise ValueError("business knowledge review packet export cannot report mutation side effects")
        if self.export_manifest.get("export_policy") != "response_only_no_file_write":
            raise ValueError("business knowledge review packet export must be response-only")
        return self


class ReviewedExternalCandidateReviewPacketResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_review_packet_v1"] = (
        "reviewed_external_candidate_review_packet_v1"
    )
    tenant_id: int
    candidate: ReviewedExternalCandidateRead
    review_card: ExternalSourceReviewCardRead
    extraction: ExternalSourceExtractionRead | None = None
    source_trace: dict[str, Any]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "review_packet_is_read_only",
            "approved_for_candidate_use_is_not_runtime_activation",
            "numeric_values_blocked",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )


class ReviewedExternalCandidateActivationPreviewResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_activation_preview_v1"] = (
        "reviewed_external_candidate_activation_preview_v1"
    )
    tenant_id: int
    candidate: ReviewedExternalCandidateRead
    activation_scope: dict[str, Any]
    active_overlay_state: dict[str, Any]
    activation_audit_contract: dict[str, Any]
    can_execute_activation: bool = False
    runtime_overlay_preview_only: bool = True
    rollback_required: bool = True
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "activation_preview_is_read_only",
            "activation_requires_separate_audit_execution",
            "tenant_scope_required",
            "rollback_required",
            "runtime_activated_false_until_execution",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_preview_only(self) -> "ReviewedExternalCandidateActivationPreviewResponse":
        if self.can_execute_activation:
            raise ValueError("activation preview cannot execute activation")
        if not self.runtime_overlay_preview_only or not self.rollback_required:
            raise ValueError("activation preview must remain preview-only and rollback-gated")
        if self.side_effects.get("runtime_activation") or self.side_effects.get("validated_default_write"):
            raise ValueError("activation preview cannot report mutation side effects")
        if self.candidate.runtime_activated or self.candidate.validated_default_write_enabled:
            raise ValueError("activation preview candidates must remain inactive and default-write disabled")
        return self


class ReviewedExternalCandidateRuntimeReadinessResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_runtime_readiness_v1"] = (
        "reviewed_external_candidate_runtime_readiness_v1"
    )
    tenant_id: int
    candidate: ReviewedExternalCandidateRead
    activation_scope: dict[str, Any]
    active_overlay_state: dict[str, Any]
    active_candidate_payload: dict[str, Any] | None = None
    can_read_runtime_payload: bool = False
    runtime_read_path_enabled: bool = True
    rollback_required: bool = True
    rollback_contract: dict[str, Any]
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "runtime_rollback": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "runtime_readiness_is_read_only",
            "tenant_scope_required",
            "approval_is_not_runtime_activation",
            "rollback_required",
            "rollback_execution_endpoint_not_enabled",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_read_only_runtime_path(self) -> "ReviewedExternalCandidateRuntimeReadinessResponse":
        if not self.runtime_read_path_enabled or not self.rollback_required:
            raise ValueError("runtime readiness must expose read path and remain rollback-gated")
        if self.side_effects.get("runtime_activation") or self.side_effects.get("runtime_rollback"):
            raise ValueError("runtime readiness cannot report activation or rollback side effects")
        if self.side_effects.get("validated_default_write") or self.side_effects.get("final_action_execution"):
            raise ValueError("runtime readiness cannot report default-write or final-action side effects")
        if self.candidate.runtime_activated or self.candidate.validated_default_write_enabled:
            raise ValueError("reviewed candidates remain inactive until separate audited runtime activation")
        self.can_read_runtime_payload = self.active_candidate_payload is not None
        return self


class ReviewedExternalCandidateRollbackPreviewResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_rollback_preview_v1"] = (
        "reviewed_external_candidate_rollback_preview_v1"
    )
    tenant_id: int
    candidate: ReviewedExternalCandidateRead
    activation_scope: dict[str, Any]
    active_overlay_state: dict[str, Any]
    rollback_contract: dict[str, Any]
    rollback_audit_packet: dict[str, Any]
    rollback_target_available: bool = False
    can_execute_rollback: bool = False
    rollback_preview_only: bool = True
    rollback_required: bool = True
    rollback_blockers: list[str] = Field(default_factory=list)
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "runtime_activation": False,
            "runtime_rollback": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "rollback_preview_is_read_only",
            "rollback_requires_separate_audit_execution",
            "tenant_scope_required",
            "approval_is_not_runtime_activation",
            "runtime_rollback_endpoint_not_enabled",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )

    @model_validator(mode="after")
    def enforce_rollback_preview_only(self) -> "ReviewedExternalCandidateRollbackPreviewResponse":
        if self.can_execute_rollback or not self.rollback_preview_only or not self.rollback_required:
            raise ValueError("rollback preview cannot execute rollback and must remain rollback-gated")
        if self.side_effects.get("runtime_activation") or self.side_effects.get("runtime_rollback"):
            raise ValueError("rollback preview cannot report activation or rollback side effects")
        if self.side_effects.get("validated_default_write") or self.side_effects.get("final_action_execution"):
            raise ValueError("rollback preview cannot report default-write or final-action side effects")
        if self.candidate.runtime_activated or self.candidate.validated_default_write_enabled:
            raise ValueError("reviewed candidates remain inactive until separate audited runtime activation")
        return self


class ReviewedExternalCandidateReviewPacketExportResponse(BaseModel):
    schema_version: Literal["reviewed_external_candidate_review_packet_export_v1"] = (
        "reviewed_external_candidate_review_packet_export_v1"
    )
    tenant_id: int
    export_format: Literal["json"] = "json"
    export_filename: str
    content_hash: str
    export_manifest: dict[str, Any]
    review_packet: ReviewedExternalCandidateReviewPacketResponse
    side_effects: dict[str, bool] = Field(
        default_factory=lambda: {
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "final_action_execution": False,
        }
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "review_packet_export_is_read_only",
            "export_response_only_no_file_write",
            "approved_for_candidate_use_is_not_runtime_activation",
            "numeric_values_blocked",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
            "no_species_db_writes",
            "no_feedstock_db_writes",
            "no_final_action_execution",
        ]
    )


class ExternalSourceP0SeedResponse(BaseModel):
    source_count: int
    review_card_count: int
    extraction_count: int
    reviewed_candidate_count: int
    seeded_card_ids: list[str]
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "p0_seed_metadata_only",
            "numeric_values_included_false",
            "promotion_enabled_false",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
        ]
    )


class ExternalSourceReviewCardResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_action: ReviewAction = "approve_for_candidate_use"
    review_status: ReviewStatus | None = None
    reviewer: str = Field(..., min_length=1)
    reviewed_at: datetime
    license_status: LicenseStatus
    boundary_condition: str = Field(..., min_length=1)
    allowed_use: str = Field(..., min_length=1)
    blocked_use: str = Field(..., min_length=1)
    candidate_type: ReviewedCandidateType = "bsf_reviewed_metadata_candidate"
    candidate_key: str | None = None
    candidate_payload: dict[str, Any] = Field(default_factory=dict)
    extracted_metadata: dict[str, Any] = Field(default_factory=dict)
    extracted_numeric_values: dict[str, Any] = Field(default_factory=dict)
    numeric_values_included: bool = False
    human_review_required: bool = True
    promotion_enabled: bool = False
    runtime_activated: bool = False
    validated_default_write_enabled: bool = False
    next_action: str = "Persist reviewed candidate for future activation review."

    @model_validator(mode="after")
    def enforce_resolution_gate(self) -> "ExternalSourceReviewCardResolveRequest":
        expected_status = review_status_for_action(self.review_action)
        if self.review_status is not None and self.review_status != expected_status:
            raise ValueError("review_status must match review_action")
        self.review_status = expected_status  # type: ignore[assignment]

        if self.review_action == "approve_for_candidate_use" and self.license_status in {"pending_review", "blocked"}:
            raise ValueError("approved candidate use requires a non-pending, non-blocked license status")
        if self.numeric_values_included or self.extracted_numeric_values:
            raise ValueError("reviewed candidate resolutions cannot include numeric values")
        if self.promotion_enabled or self.runtime_activated or self.validated_default_write_enabled:
            raise ValueError("resolution cannot enable promotion, runtime activation, or validated default writes")
        blocked_candidate_payload_keys = [
            key
            for key in (
                "numeric_values_included",
                "extracted_numeric_values",
                "promotion_enabled",
                "runtime_activated",
                "validated_default_write_enabled",
            )
            if key in self.candidate_payload
            and (
                self.candidate_payload[key] is True
                or (key == "extracted_numeric_values" and bool(self.candidate_payload[key]))
            )
        ]
        if blocked_candidate_payload_keys:
            raise ValueError(
                "candidate_payload cannot enable guarded fields: " + ", ".join(sorted(blocked_candidate_payload_keys))
            )

        blocked = self.blocked_use.lower()
        if "default" not in blocked:
            raise ValueError("blocked_use must block validated defaults")
        if "release evidence" not in blocked:
            raise ValueError("blocked_use must block release evidence")

        return self


class ExternalSourceReviewCardResolveResponse(BaseModel):
    review_card: ExternalSourceReviewCardRead
    reviewed_candidate: ReviewedExternalCandidateRead | None = None
    created_reviewed_candidate: bool = False
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "review_resolution_persisted",
            "approved_for_candidate_use_is_not_runtime_activation",
            "runtime_activated_false",
            "validated_default_write_enabled_false",
        ]
    )
