import json
from pathlib import Path
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.external_source_review import (
    BsfReviewedMetadataCandidatePayload,
    ExternalSourceReviewCardResolveRequest,
    ExternalSourceSchemaReadinessResponse,
    ExternalSourceSchemaReadinessTable,
    ExternalSourceReviewCard,
    ExternalSourceStagedMetadataArtifact,
    ExternalSourceStagedMetadataRecord,
    FeedstockDatasetCandidateListResponse,
    FeedstockDatasetCandidateRead,
    LiteratureExtractionCandidateListResponse,
    LiteratureExtractionCandidateRead,
    LiteratureExtractionCandidateReviewPacketBulkExportResponse,
    LiteratureExtractionCandidateReviewPacketExportResponse,
    LiteratureExtractionCandidateReviewPacketResponse,
    LiteratureExtractionCandidateSeedResponse,
    LiteratureExtractionEvidenceChainReadinessResponse,
    LiteratureExtractionReviewDraftComparisonResponse,
    LiteratureExtractionReviewDraftListResponse,
    LiteratureExtractionReviewDraftResponse,
    LiteratureExtractionReviewDraftRevisionRead,
    LiteratureValueOverlayResponse,
    LiteratureValuePromotionAuditExportResponse,
    LiteratureValuePromotionApprovalResponse,
    LiteratureValuePromotionLifecycleResponse,
    LiteratureValuePromotionReadinessResponse,
    LiteratureValuePromotionRequestResponse,
    LiteratureValueReleaseEvidenceLinkResponse,
    LiteratureValueRollbackCreateRequest,
    LiteratureValueRollbackResponse,
    LiteratureValueRuntimeActivationCreateRequest,
    LiteratureValueRuntimeActivationPreviewResponse,
    LiteratureValueRuntimeActivationResponse,
    ReviewedExternalCandidateRead,
    ReviewedMetadataCandidatePayload,
)


TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_P0_BSF_STAGED_METADATA_TEMPLATE.json"


def _valid_card_payload():
    return {
        "card_id": "BSF-CARD-001",
        "shortlist_id": "BSF-LIT-001",
        "source_catalog_id": "A-BSF-002",
        "doi": "10.1016/j.wasman.2020.07.050",
        "review_status": "pending_review",
        "reviewer": "unassigned",
        "reviewed_at": "pending",
        "license_status": "pending_review",
        "evidence_source_kind": "peer_reviewed_literature",
        "ingestion_mode": "manual_review_first",
        "human_review_required": True,
        "extracted_numeric_values_allowed": False,
        "boundary_condition_required": True,
        "allowed_use": "citation metadata and review-boundary planning only",
        "blocked_use": "no validated defaults; no release evidence; no compliance threshold",
        "next_action": "Assign reviewer and fill extraction checklist.",
    }


def test_external_source_review_card_accepts_pending_metadata_card():
    card = ExternalSourceReviewCard(**_valid_card_payload())

    assert card.review_status == "pending_review"
    assert card.human_review_required is True
    assert card.extracted_numeric_values_allowed is False


def test_external_source_review_card_rejects_numeric_value_enablement():
    payload = _valid_card_payload()
    payload["extracted_numeric_values_allowed"] = True

    with pytest.raises(ValidationError):
        ExternalSourceReviewCard(**payload)


def test_external_source_review_card_rejects_closed_status_without_reviewer_and_license():
    payload = _valid_card_payload()
    payload["review_status"] = "approved_for_candidate_use"

    with pytest.raises(ValidationError):
        ExternalSourceReviewCard(**payload)


def test_staged_metadata_artifact_template_is_metadata_only():
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    artifact = ExternalSourceStagedMetadataArtifact(**payload)

    assert artifact.artifact_status == "template_only"
    assert artifact.promotion_enabled is False
    assert artifact.numeric_values_included is False
    assert artifact.validated_default_write_enabled is False
    assert len(artifact.records) == 8
    assert {record.numeric_values_included for record in artifact.records} == {False}
    assert {bool(record.extracted_numeric_values) for record in artifact.records} == {False}


def test_staged_metadata_record_rejects_numeric_values():
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))["records"][0]
    payload["numeric_values_included"] = True
    payload["extracted_numeric_values"] = {"conversion_rate": 0.5}

    with pytest.raises(ValidationError):
        ExternalSourceStagedMetadataRecord(**payload)


def test_staged_metadata_artifact_rejects_promotion_enablement():
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["promotion_enabled"] = True

    with pytest.raises(ValidationError):
        ExternalSourceStagedMetadataArtifact(**payload)


def test_resolve_request_rejects_numeric_values_before_approved_review():
    with pytest.raises(ValidationError):
        ExternalSourceReviewCardResolveRequest(
            review_action="approve_metadata",
            reviewer="Dr. Reviewer",
            reviewed_at=datetime.now(UTC),
            license_status="metadata_only",
            boundary_condition="Metadata boundary reviewed.",
            allowed_use="candidate metadata only",
            blocked_use="no validated defaults; no release evidence",
            numeric_values_included=True,
            extracted_numeric_values={"conversion_rate": 0.5},
        )


@pytest.mark.parametrize(
    "review_action,review_status,license_status",
    [
        ("approve_metadata", "extracted_metadata", "metadata_only"),
        ("request_license_clearance", "needs_license_clearance", "restricted"),
        ("reject", "rejected", "blocked"),
        ("approve_for_candidate_use", "approved_for_candidate_use", "metadata_only"),
    ],
)
def test_resolve_request_maps_explicit_review_actions(review_action, review_status, license_status):
    payload = ExternalSourceReviewCardResolveRequest(
        review_action=review_action,
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status=license_status,
        boundary_condition="Reviewed metadata boundary only.",
        allowed_use="review workflow metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
    )

    assert payload.review_action == review_action
    assert payload.review_status == review_status


def test_resolve_request_rejects_mismatched_action_and_status():
    with pytest.raises(ValidationError):
        ExternalSourceReviewCardResolveRequest(
            review_action="reject",
            review_status="approved_for_candidate_use",
            reviewer="Dr. Reviewer",
            reviewed_at=datetime.now(UTC),
            license_status="blocked",
            boundary_condition="Reviewed metadata boundary only.",
            allowed_use="review workflow metadata only",
            blocked_use="no validated defaults; no release evidence; no runtime activation",
        )


def test_resolve_request_rejects_runtime_activation_flags():
    with pytest.raises(ValidationError):
        ExternalSourceReviewCardResolveRequest(
            reviewer="Dr. Reviewer",
            reviewed_at=datetime.now(UTC),
            license_status="metadata_only",
            boundary_condition="Metadata boundary reviewed.",
            allowed_use="candidate metadata only",
            blocked_use="no validated defaults; no release evidence",
            runtime_activated=True,
        )


@pytest.mark.parametrize(
    "candidate_type",
    [
        "lca_factor_candidate",
        "tea_factor_candidate",
        "compliance_rule_candidate",
        "model_provider_capability_candidate",
        "github_reference_candidate",
        "lca_boundary_metadata_candidate",
        "species_metadata_candidate",
        "feedstock_metadata_candidate",
    ],
)
def test_resolve_request_accepts_metadata_only_candidate_types(candidate_type):
    payload = ExternalSourceReviewCardResolveRequest(
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Reviewed metadata boundary only; no numeric extraction.",
        allowed_use="reviewed candidate metadata for future activation review",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        candidate_type=candidate_type,
        candidate_payload={"review_scope": "metadata_only_contract"},
    )

    assert payload.candidate_type == candidate_type
    assert payload.numeric_values_included is False
    assert payload.extracted_numeric_values == {}
    assert payload.promotion_enabled is False
    assert payload.runtime_activated is False
    assert payload.validated_default_write_enabled is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("numeric_values_included", True),
        ("extracted_numeric_values", {"factor": 1.23}),
        ("promotion_enabled", True),
        ("runtime_activated", True),
        ("validated_default_write_enabled", True),
    ],
)
def test_resolve_request_rejects_new_candidate_guardrail_bypass(field, value):
    payload = {
        "reviewer": "Dr. Reviewer",
        "reviewed_at": datetime.now(UTC),
        "license_status": "metadata_only",
        "boundary_condition": "Reviewed metadata boundary only.",
        "allowed_use": "reviewed candidate metadata for future activation review",
        "blocked_use": "no validated defaults; no release evidence; no runtime activation",
        "candidate_type": "lca_factor_candidate",
        field: value,
    }

    with pytest.raises(ValidationError):
        ExternalSourceReviewCardResolveRequest(**payload)


def test_resolve_request_rejects_guarded_values_inside_candidate_payload():
    with pytest.raises(ValidationError):
        ExternalSourceReviewCardResolveRequest(
            reviewer="Dr. Reviewer",
            reviewed_at=datetime.now(UTC),
            license_status="metadata_only",
            boundary_condition="Reviewed metadata boundary only.",
            allowed_use="reviewed candidate metadata for future activation review",
            blocked_use="no validated defaults; no release evidence; no runtime activation",
            candidate_type="model_provider_capability_candidate",
            candidate_payload={"runtime_activated": True},
        )


def test_bsf_reviewed_metadata_candidate_payload_is_metadata_only():
    payload = BsfReviewedMetadataCandidatePayload(
        card_id="BSF-CARD-001",
        shortlist_id="BSF-LIT-001",
        source_catalog_id="A-BSF-002",
        doi="10.1016/j.wasman.2020.07.050",
        source_url="https://example.test/source",
        title="Rethinking organic wastes bioconversion",
        article_type="review",
        target_boundary_fields="substrate classes; lifecycle stage",
        boundary_condition="Citation metadata only; no numeric table extraction.",
        allowed_use="reviewed candidate metadata for future activation review",
        blocked_use="no validated defaults; no release evidence; no compliance threshold",
        evidence_source_kind="peer_reviewed_literature",
        ingestion_mode="manual_review_first",
        license_status="metadata_only",
        source_kind="peer_reviewed_literature",
        source_ref="10.1016/j.wasman.2020.07.050",
    )

    assert payload.numeric_values_included is False
    assert payload.runtime_activated is False
    assert payload.runtime_activation_required_before_use is True


def test_bsf_reviewed_metadata_candidate_payload_rejects_numeric_values():
    with pytest.raises(ValidationError):
        BsfReviewedMetadataCandidatePayload(
            card_id="BSF-CARD-001",
            shortlist_id="BSF-LIT-001",
            source_catalog_id="A-BSF-002",
            doi="10.1016/j.wasman.2020.07.050",
            source_url="https://example.test/source",
            title="Rethinking organic wastes bioconversion",
            article_type="review",
            target_boundary_fields="substrate classes; lifecycle stage",
            boundary_condition="Citation metadata only.",
            allowed_use="reviewed candidate metadata",
            blocked_use="no validated defaults; no release evidence",
            evidence_source_kind="peer_reviewed_literature",
            ingestion_mode="manual_review_first",
            license_status="metadata_only",
            source_kind="peer_reviewed_literature",
            source_ref="10.1016/j.wasman.2020.07.050",
            numeric_values_included=True,
            extracted_numeric_values={"conversion_rate": 0.5},
        )


def test_reviewed_metadata_candidate_payload_is_read_only_for_new_types():
    payload = ReviewedMetadataCandidatePayload(
        candidate_type="github_reference_candidate",
        candidate_domain="github_reference",
        card_id="BSF-CARD-001",
        shortlist_id="BSF-LIT-001",
        source_catalog_id="G-OSS-001",
        doi="10.1016/j.wasman.2020.07.050",
        source_url="https://github.com/example/project",
        title="Reference implementation metadata",
        boundary_condition="Repository metadata only; no runtime import.",
        allowed_use="reviewed OSS metadata for future implementation review",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        evidence_source_kind="github_reference",
        ingestion_mode="metadata_only",
        license_status="metadata_only",
        source_kind="github_reference",
        source_ref="https://github.com/example/project",
        reviewer_annotations={"stars_checked": "metadata_only"},
    )

    assert payload.candidate_family == "reviewed_metadata_candidate"
    assert payload.candidate_domain == "github_reference"
    assert payload.metadata_only is True
    assert payload.read_only is True
    assert payload.numeric_values_included is False
    assert payload.runtime_activated is False
    assert payload.validated_default_write_enabled is False


def test_reviewed_metadata_candidate_payload_rejects_default_write():
    with pytest.raises(ValidationError):
        ReviewedMetadataCandidatePayload(
            candidate_type="compliance_rule_candidate",
            candidate_domain="compliance",
            card_id="BSF-CARD-001",
            shortlist_id="BSF-LIT-001",
            source_catalog_id="E-COMP-001",
            doi="10.1016/j.wasman.2020.07.050",
            source_url="https://example.test/standard",
            title="Compliance metadata",
            boundary_condition="Rule metadata only.",
            allowed_use="reviewed compliance metadata for future review",
            blocked_use="no validated defaults; no release evidence",
            evidence_source_kind="official_standard",
            ingestion_mode="manual_review_first",
            license_status="metadata_only",
            source_kind="official_standard",
            source_ref="https://example.test/standard",
            validated_default_write_enabled=True,
        )


def test_reviewed_metadata_candidate_payload_rejects_domain_mismatch():
    with pytest.raises(ValidationError):
        ReviewedMetadataCandidatePayload(
            candidate_type="lca_factor_candidate",
            candidate_domain="github_reference",
            card_id="BSF-CARD-001",
            shortlist_id="BSF-LIT-001",
            source_catalog_id="C-LCA-010",
            doi="10.1016/j.wasman.2020.07.050",
            source_url="https://example.test/lca",
            title="LCA metadata",
            boundary_condition="LCA metadata only.",
            allowed_use="reviewed LCA metadata for future review",
            blocked_use="no validated defaults; no release evidence",
            evidence_source_kind="public_dataset",
            ingestion_mode="metadata_only",
            license_status="metadata_only",
            source_kind="public_dataset",
            source_ref="https://example.test/lca",
        )


def test_reviewed_external_candidate_read_rejects_unknown_candidate_type():
    with pytest.raises(ValidationError):
        ReviewedExternalCandidateRead(
            tenant_id=1,
            candidate_id="REC-BSF-CARD-001",
            candidate_type="release_gate_candidate",
            candidate_key="release_gate_candidate:BSF-CARD-001",
            card_id="BSF-CARD-001",
            source_id="A-BSF-002",
            source_kind="peer_reviewed_literature",
            source_ref="10.1016/j.wasman.2020.07.050",
            license_status="metadata_only",
            ingestion_mode="metadata_only",
            review_status="approved_for_candidate_use",
            reviewer="Dr. Reviewer",
            reviewed_at=datetime.now(UTC),
            boundary_condition="Metadata only.",
            allowed_use="candidate metadata only",
            blocked_use="no validated defaults; no release evidence",
            candidate_payload={
                "numeric_values_included": False,
                "extracted_numeric_values": {},
                "promotion_enabled": False,
                "runtime_activated": False,
                "validated_default_write_enabled": False,
            },
            audit_payload={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def _valid_feedstock_dataset_candidate_payload():
    return {
        "candidate_uid": "feedstock_dataset_candidate:B-FEED-001",
        "source_id": "B-FEED-001",
        "source_name": "USDA FoodData Central",
        "source_owner": "USDA",
        "source_kind": "public_dataset",
        "source_ref": "https://fdc.nal.usda.gov/",
        "license_note": "public domain",
        "ingestion_mode": "metadata_only",
        "geography": "US",
        "units": "source-defined",
        "waste_proxy_warning": "Food/feed dataset is only a reviewed waste proxy candidate.",
        "next_action": "Human reviewer must map source rows before any extraction.",
    }


def test_feedstock_dataset_candidate_schema_is_metadata_only():
    candidate = FeedstockDatasetCandidateRead(**_valid_feedstock_dataset_candidate_payload())
    response = FeedstockDatasetCandidateListResponse(items=[candidate], count=1)

    assert candidate.candidate_type == "feedstock_dataset_candidate"
    assert candidate.review_status == "pending_review"
    assert candidate.human_review_required is True
    assert candidate.numeric_values_included is False
    assert candidate.runtime_activated is False
    assert candidate.validated_default_write_enabled is False
    assert "no_feedstock_db_writes" in response.guardrails


def test_external_source_schema_readiness_reports_missing_tables_without_mutation():
    response = ExternalSourceSchemaReadinessResponse(
        status="blocked",
        schema_ready=False,
        source_catalog_ready=False,
        feedstock_dataset_candidate_count=0,
        reviewed_metadata_lane_ready=False,
        required_tables=[
            ExternalSourceSchemaReadinessTable(table_name="external_source_records", present=True, row_count=70),
            ExternalSourceSchemaReadinessTable(table_name="external_source_review_cards", present=False),
        ],
        missing_required_tables=["external_source_review_cards"],
        blockers=["missing required tables: external_source_review_cards"],
    )

    assert response.status == "blocked"
    assert response.schema_ready is False
    assert "no_table_creation" in response.guardrails
    assert "no_seed_mutation" in response.guardrails
    assert "no_validated_default_writes" in response.guardrails
    assert "phase4a_domain_coverage_is_read_only" in response.guardrails


@pytest.mark.parametrize(
    "field,value",
    [
        ("human_review_required", False),
        ("numeric_values_included", True),
        ("runtime_activated", True),
        ("validated_default_write_enabled", True),
    ],
)
def test_feedstock_dataset_candidate_schema_rejects_guardrail_bypass(field, value):
    payload = _valid_feedstock_dataset_candidate_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        FeedstockDatasetCandidateRead(**payload)


def _valid_literature_extraction_candidate_payload():
    return {
        "candidate_uid": "literature_extraction_candidate:LIT-AGR-GI-001",
        "candidate_id": "LIT-AGR-GI-001",
        "candidate_type": "literature_extraction_candidate",
        "source_id": "A-BSF-007",
        "doi": "10.3390/su151511526",
        "source_ref": "https://doi.org/10.3390/su151511526",
        "title": "Analysis of Chemical and Phytotoxic Properties of Frass Derived from Black Soldier Fly-Based Bioconversion of Biosolids",
        "species": "Hermetia illucens; Lactuca sativa assay crop",
        "feedstock": "food waste",
        "treatment": "BSFL frass from bioconverted food waste",
        "metric_key": "germination_index",
        "metric_label": "Seed germination index for lettuce",
        "raw_value": "around 100",
        "unit": "% GI",
        "condition_context": "Aqueous frass extract prepared at 1:10 w/v.",
        "experiment_context": "Frass generated after 20 days of BSFL incubation.",
        "table_or_section_ref": "Results section 3.2, Figure 2B-C",
        "extraction_note": "Approximate textual extraction pending reviewer figure check.",
        "license_note": "Open-access publisher page; license review required.",
        "source_kind": "peer_reviewed_literature",
        "review_status": "pending_review",
        "human_review_required": True,
        "numeric_values_included": True,
        "release_evidence_allowed": False,
        "runtime_activation_enabled": False,
        "validated_default_write_enabled": False,
        "promotion_enabled": False,
        "guardrails": ["numeric_values_included_but_not_validated_defaults"],
    }


def test_literature_extraction_candidate_allows_raw_values_but_blocks_runtime_use():
    candidate = LiteratureExtractionCandidateRead(**_valid_literature_extraction_candidate_payload())
    response = LiteratureExtractionCandidateListResponse(
        items=[candidate],
        count=1,
        metric_counts={"germination_index": 1},
    )

    assert candidate.candidate_type == "literature_extraction_candidate"
    assert candidate.review_status == "pending_review"
    assert candidate.numeric_values_included is True
    assert candidate.release_evidence_allowed is False
    assert candidate.runtime_activation_enabled is False
    assert candidate.validated_default_write_enabled is False
    assert candidate.promotion_enabled is False
    assert response.side_effects == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "promotion": False,
        "final_action_execution": False,
    }


def test_literature_extraction_candidate_seed_response_is_candidate_table_only():
    response = LiteratureExtractionCandidateSeedResponse(
        tenant_id=1,
        source_count=1,
        candidate_count=5,
        created_candidate_count=5,
        updated_candidate_count=0,
        seeded_candidate_ids=["LIT-AGR-GI-001"],
    )

    assert response.review_status == "pending_review"
    assert response.numeric_values_included is True
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.promotion_enabled is False
    assert response.side_effects["release_evidence_use"] is False
    assert "literature_extraction_candidate_records_only" in response.guardrails


def test_literature_extraction_candidate_review_packet_export_is_response_only():
    candidate = LiteratureExtractionCandidateRead(**_valid_literature_extraction_candidate_payload())
    packet = LiteratureExtractionCandidateReviewPacketResponse(
        tenant_id=1,
        candidate=candidate,
        candidate_payload=candidate.model_dump(mode="json"),
        source_trace={
            "candidate_id": candidate.candidate_id,
            "source_id": candidate.source_id,
            "source_ref": candidate.source_ref,
            "release_evidence_allowed": False,
            "runtime_activation_enabled": False,
            "validated_default_write_enabled": False,
            "promotion_enabled": False,
            "final_action_execution": False,
        },
        raw_value=candidate.raw_value,
        unit=candidate.unit,
        conditions={
            "condition_context": candidate.condition_context,
            "experiment_context": candidate.experiment_context,
            "table_or_section_ref": candidate.table_or_section_ref,
            "treatment": candidate.treatment,
        },
        license_note=candidate.license_note,
    )
    response = LiteratureExtractionCandidateReviewPacketExportResponse(
        tenant_id=1,
        export_filename="LIT-AGR-GI-001-literature-extraction-review-packet.json",
        content_hash="a" * 64,
        export_manifest={
            "candidate_id": candidate.candidate_id,
            "content_hash": "a" * 64,
            "export_policy": "response_only_no_file_write",
            "release_evidence_allowed": False,
            "runtime_activation_enabled": False,
            "validated_default_write_enabled": False,
            "promotion_enabled": False,
            "final_action_execution": False,
        },
        review_packet=packet,
    )

    assert response.review_packet.raw_value == "around 100"
    assert response.review_packet.unit == "% GI"
    assert response.review_packet.release_evidence_allowed is False
    assert response.review_packet.runtime_activation_enabled is False
    assert response.review_packet.validated_default_write_enabled is False
    assert response.review_packet.promotion_enabled is False
    assert response.review_packet.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert "export_response_only_no_file_write" in response.guardrails


def test_literature_extraction_candidate_bulk_export_indexes_response_only_packets():
    candidate = LiteratureExtractionCandidateRead(**_valid_literature_extraction_candidate_payload())
    packet = LiteratureExtractionCandidateReviewPacketResponse(
        tenant_id=1,
        candidate=candidate,
        candidate_payload=candidate.model_dump(mode="json"),
        source_trace={"candidate_id": candidate.candidate_id, "source_ref": candidate.source_ref},
        raw_value=candidate.raw_value,
        unit=candidate.unit,
        conditions={"condition_context": candidate.condition_context},
        license_note=candidate.license_note,
    )
    packet_export = LiteratureExtractionCandidateReviewPacketExportResponse(
        tenant_id=1,
        export_filename="LIT-AGR-GI-001-literature-extraction-review-packet.json",
        content_hash="b" * 64,
        export_manifest={
            "candidate_id": candidate.candidate_id,
            "content_hash": "b" * 64,
            "export_policy": "response_only_no_file_write",
        },
        review_packet=packet,
    )
    response = LiteratureExtractionCandidateReviewPacketBulkExportResponse(
        tenant_id=1,
        export_filename="literature-extraction-review-packets.json",
        content_hash="c" * 64,
        export_manifest={
            "candidate_count": 1,
            "candidate_ids": [candidate.candidate_id],
            "content_hash": "c" * 64,
            "export_policy": "response_only_no_file_write",
        },
        packet_exports=[packet_export],
        count=1,
        metric_counts={"germination_index": 1},
    )

    assert response.count == 1
    assert response.packet_exports[0].review_packet.raw_value == "around 100"
    assert response.export_manifest["candidate_ids"] == ["LIT-AGR-GI-001"]
    assert response.side_effects["file_written"] is False
    assert response.side_effects["release_evidence_use"] is False
    assert response.side_effects["final_action_execution"] is False
    assert "tenant_scoped_persisted_candidates_only" in response.guardrails


def test_literature_extraction_review_draft_records_intent_only():
    candidate = LiteratureExtractionCandidateRead(**_valid_literature_extraction_candidate_payload())
    response = LiteratureExtractionReviewDraftResponse(
        review_draft_id="LERD-TEST-001",
        tenant_id=1,
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        reviewer_user_id=1,
        review_intent="approve_candidate_use_intent",
        reviewer_notes="Reviewer agrees to keep this as pending review raw value only.",
        source_review_packet_export_id="literature-extraction-review-packet-export:LIT-AGR-GI-001:aaaaaaaaaaaa",
        source_review_packet_hash="a" * 64,
        candidate_snapshot=candidate.model_dump(mode="json"),
        export_manifest={
            "candidate_id": candidate.candidate_id,
            "content_hash": "a" * 64,
            "export_policy": "response_only_no_file_write",
        },
        idempotency_key="idem-literature-draft-001",
        created_at="2026-04-28T07:45:00+00:00",
        updated_at="2026-04-28T07:45:00+00:00",
    )
    listed = LiteratureExtractionReviewDraftListResponse(tenant_id=1, count=1, drafts=[response])

    assert response.status == "draft_intent_recorded"
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.promotion_enabled is False
    assert response.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert listed.side_effects["candidate_status_update"] is False
    assert "candidate_status_remains_pending_review" in response.guardrails


def test_literature_extraction_review_draft_comparison_is_response_only():
    candidate = LiteratureExtractionCandidateRead(**_valid_literature_extraction_candidate_payload())
    revision = LiteratureExtractionReviewDraftRevisionRead(
        review_draft_id="LERD-TEST-001",
        revision_index=1,
        revision_hash="a" * 64,
        candidate_snapshot_hash="b" * 64,
        export_manifest_hash="c" * 64,
        source_review_packet_hash="d" * 64,
        review_intent="approve_candidate_use_intent",
        changed_fields=[],
        side_effects={
            "candidate_status_update": False,
            "file_written": False,
            "runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "promotion": False,
            "final_action_execution": False,
        },
        created_at="2026-04-28T08:20:00+00:00",
    )
    response = LiteratureExtractionReviewDraftComparisonResponse(
        tenant_id=1,
        candidate_id=candidate.candidate_id,
        current_review_draft_id=revision.review_draft_id,
        current_revision_hash=revision.revision_hash,
        current_candidate_snapshot_hash=revision.candidate_snapshot_hash,
        current_export_manifest_hash=revision.export_manifest_hash,
        source_review_packet_hash=revision.source_review_packet_hash,
        current_response_packet_hash=revision.source_review_packet_hash,
        changed_field_filter=None,
        comparison_manifest={
            "comparison_id": "literature-extraction-review-draft-comparison:LIT-AGR-GI-001:aaaaaaaaaaaa",
            "candidate_id": candidate.candidate_id,
            "current_review_draft_id": revision.review_draft_id,
            "revision_count": 1,
            "comparison_hash": "e" * 64,
            "comparison_policy": "response_only_no_file_write",
            "candidate_status": "pending_review",
            "release_evidence_allowed": False,
            "runtime_activation_enabled": False,
            "validated_default_write_enabled": False,
            "promotion_enabled": False,
            "final_action_execution": False,
        },
        report_manifest={
            "report_id": "literature-extraction-review-draft-comparison-report:LIT-AGR-GI-001:aaaaaaaaaaaa",
            "report_policy": "response_only_no_file_write",
            "report_format": "json_response",
            "candidate_id": candidate.candidate_id,
            "current_review_draft_id": revision.review_draft_id,
            "changed_field_count": 0,
            "audit_trail_count": 1,
            "file_written": False,
            "release_evidence_allowed": False,
            "runtime_activation_enabled": False,
            "validated_default_write_enabled": False,
            "promotion_enabled": False,
            "final_action_execution": False,
        },
        report_payload={
            "summary": {
                "candidate_id": candidate.candidate_id,
                "current_review_draft_id": revision.review_draft_id,
                "changed_fields": [],
            },
            "audit_trail": [revision.model_dump(mode="json")],
            "guardrails": ["report_is_response_only"],
        },
        comparison_summary={
            "candidate_snapshot_changed_since_previous": False,
            "packet_hash_changed_since_previous": False,
            "review_intent_changed_since_previous": False,
            "side_effect_flags_changed_since_previous": False,
            "export_manifest_changed_since_previous": False,
            "current_response_packet_hash_matches_draft": True,
            "current_candidate_snapshot_matches_draft": True,
        },
        audit_trail=[revision],
    )

    assert response.schema_version == "literature_extraction_review_draft_comparison_v1"
    assert response.comparison_manifest["comparison_policy"] == "response_only_no_file_write"
    assert response.report_manifest["report_policy"] == "response_only_no_file_write"
    assert response.report_payload["summary"]["changed_fields"] == []
    assert response.comparison_summary["current_response_packet_hash_matches_draft"] is True
    assert response.audit_trail[0].revision_hash == "a" * 64
    assert all(value is False for value in response.side_effects.values())
    assert "literature_extraction_review_draft_comparison_is_read_only" in response.guardrails


def test_literature_extraction_evidence_chain_readiness_closes_read_only_chain():
    response = LiteratureExtractionEvidenceChainReadinessResponse(
        tenant_id=1,
        chain_complete=True,
        candidate_count=5,
        packet_export_ready=True,
        bulk_export_ready=True,
        review_draft_count=1,
        comparison_ready=True,
        report_ready=True,
        promotion_ready=True,
        readiness_notes=[
            "literature raw values are persisted only as pending_review candidates",
            "chain completion does not permit release evidence, runtime activation, defaults, promotion, or final actions",
        ],
    )

    assert response.schema_version == "literature_extraction_evidence_chain_readiness_v1"
    assert response.chain_complete is True
    assert response.auto_use_allowed is False
    assert response.promotion_ready is True
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.promotion_enabled is False
    assert response.final_action_execution is False
    assert response.blocking_reason is None
    assert all(value is False for value in response.side_effects.values())
    assert "literature_evidence_chain_readiness_is_read_only" in response.guardrails


def test_literature_value_promotion_readiness_is_request_only():
    readiness = LiteratureValuePromotionReadinessResponse(
        tenant_id=1,
        candidate_id="LIT-AGR-GI-001",
        chain_complete=True,
        promotion_ready=True,
        review_draft_id="LERD-TEST-001",
        source_review_packet_hash="a" * 64,
        comparison_hash="b" * 64,
        raw_value="85-102",
        unit="%",
        conditions={"condition_context": "Radish germination assay"},
    )

    assert readiness.schema_version == "literature_value_promotion_readiness_v1"
    assert readiness.promotion_ready is True
    assert readiness.request_status == "not_requested"
    assert readiness.release_evidence_allowed is False
    assert readiness.runtime_activation_enabled is False
    assert readiness.validated_default_write_enabled is False
    assert readiness.promotion_enabled is False
    assert readiness.final_action_execution is False
    assert all(value is False for value in readiness.side_effects.values())
    assert "promotion_ready_does_not_enable_promotion" in readiness.guardrails


def test_literature_value_promotion_request_is_requested_not_active():
    response = LiteratureValuePromotionRequestResponse(
        promotion_request_id="LVPR-TEST-001",
        tenant_id=1,
        candidate_id="LIT-AGR-GI-001",
        source_review_packet_hash="a" * 64,
        review_draft_id="LERD-TEST-001",
        comparison_hash="b" * 64,
        raw_value="85-102",
        unit="%",
        conditions={"condition_context": "Radish germination assay"},
        target_use="candidate_overlay_review",
        target_scope={"campaign_key": "frass-agronomy-review"},
        requested_by_user_id=1,
        idempotency_key="idem-promotion-request",
        created_at="2026-04-28T09:30:00+00:00",
        updated_at="2026-04-28T09:30:00+00:00",
    )

    assert response.schema_version == "literature_value_promotion_request_v1"
    assert response.request_status == "requested"
    assert response.auto_use_allowed is False
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.promotion_enabled is False
    assert response.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert "request_status_requested_not_active" in response.guardrails


def test_literature_value_promotion_approval_is_audit_only():
    response = LiteratureValuePromotionApprovalResponse(
        approval_id="LVPA-TEST-001",
        tenant_id=1,
        promotion_request_id="LVPR-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        approval_action="approve",
        request_status_before="requested",
        request_status_after="approved_for_promotion",
        approved_by_user_id=1,
        approved_by_user_roles=["scientist", "release_manager"],
        approver_notes="Reviewed packet hash, comparison hash, and target scope for overlay review only.",
        idempotency_key="idem-promotion-approval",
        source_review_packet_hash="a" * 64,
        review_draft_id="LERD-TEST-001",
        comparison_hash="b" * 64,
        target_use="candidate_overlay_review",
        target_scope={"campaign_key": "frass-agronomy-review"},
        created_at="2026-04-28T10:30:00+00:00",
        updated_at="2026-04-28T10:30:00+00:00",
    )

    assert response.schema_version == "literature_value_promotion_approval_v1"
    assert response.approval_audit_only is True
    assert response.request_status_after == "approved_for_promotion"
    assert response.approved_by_user_roles == ["scientist", "release_manager"]
    assert response.overlay_write_enabled is False
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.promotion_enabled is False
    assert response.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert "approval_does_not_create_overlay" in response.guardrails


def test_literature_value_promotion_approval_rejects_overlay_enablement():
    with pytest.raises(ValidationError):
        LiteratureValuePromotionApprovalResponse(
            approval_id="LVPA-TEST-001",
            tenant_id=1,
            promotion_request_id="LVPR-TEST-001",
            candidate_id="LIT-AGR-GI-001",
            approval_action="approve",
            request_status_before="requested",
            request_status_after="approved_for_promotion",
            approved_by_user_id=1,
            approver_notes="Invalid overlay enablement.",
            idempotency_key="idem-promotion-approval",
            source_review_packet_hash="a" * 64,
            review_draft_id="LERD-TEST-001",
            comparison_hash="b" * 64,
            target_use="candidate_overlay_review",
            target_scope={"campaign_key": "frass-agronomy-review"},
            overlay_write_enabled=True,
            created_at="2026-04-28T10:30:00+00:00",
            updated_at="2026-04-28T10:30:00+00:00",
        )


def test_literature_value_overlay_is_created_inactive():
    response = LiteratureValueOverlayResponse(
        overlay_id="LVO-TEST-001",
        tenant_id=1,
        promotion_request_id="LVPR-TEST-001",
        approval_id="LVPA-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        source_review_packet_hash="a" * 64,
        review_draft_id="LERD-TEST-001",
        comparison_hash="b" * 64,
        raw_value="85-102",
        normalized_value="85-102 %",
        unit="%",
        source_ref="10.1000/example",
        approval_hash="c" * 64,
        overlay_hash="d" * 64,
        conditions={"condition_context": "Radish germination assay"},
        target_use="candidate_overlay_review",
        target_scope={"campaign_key": "frass-agronomy-review"},
        validity_scope={"target_scope": {"campaign_key": "frass-agronomy-review"}},
        rollback_pointer={"required": True, "rollback_status": "not_rolled_back"},
        created_by_user_id=1,
        overlay_notes="Create inactive overlay for later scoped activation review.",
        idempotency_key="idem-overlay",
        created_at="2026-04-28T11:00:00+00:00",
        updated_at="2026-04-28T11:00:00+00:00",
    )

    assert response.schema_version == "literature_value_overlay_v1"
    assert response.overlay_status == "inactive"
    assert response.overlay_active is False
    assert response.normalized_value == "85-102 %"
    assert response.source_ref == "10.1000/example"
    assert response.approval_hash == "c" * 64
    assert response.overlay_hash == "d" * 64
    assert response.validity_scope["target_scope"] == {"campaign_key": "frass-agronomy-review"}
    assert response.rollback_pointer["required"] is True
    assert response.release_evidence_allowed is False
    assert response.runtime_activation_enabled is False
    assert response.validated_default_write_enabled is False
    assert response.final_action_execution is False
    assert response.rollback_required_before_use_change is True
    assert all(value is False for value in response.side_effects.values())
    assert "overlay_created_inactive" in response.guardrails


def test_literature_value_overlay_accepts_promoted_inactive_alias():
    response = LiteratureValueOverlayResponse(
        overlay_id="LVO-TEST-002",
        tenant_id=1,
        promotion_request_id="LVPR-TEST-001",
        approval_id="LVPA-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        overlay_status="promoted_inactive",
        source_review_packet_hash="a" * 64,
        review_draft_id="LERD-TEST-001",
        comparison_hash="b" * 64,
        raw_value="85-102",
        unit="%",
        conditions={"source_ref": "10.1000/example"},
        target_use="candidate_overlay_review",
        target_scope={"campaign_key": "frass-agronomy-review"},
        created_by_user_id=1,
        overlay_notes="Create promoted inactive overlay alias for compatibility.",
        idempotency_key="idem-overlay-alias",
        created_at="2026-04-28T11:00:00+00:00",
        updated_at="2026-04-28T11:00:00+00:00",
    )

    assert response.overlay_status == "promoted_inactive"
    assert response.overlay_active is False
    assert response.normalized_value == "85-102 %"
    assert response.source_ref == "10.1000/example"
    assert response.validity_scope == {"campaign_key": "frass-agronomy-review"}
    assert response.rollback_pointer["required"] is True


def test_literature_value_overlay_rejects_active_status():
    with pytest.raises(ValidationError):
        LiteratureValueOverlayResponse(
            overlay_id="LVO-TEST-001",
            tenant_id=1,
            promotion_request_id="LVPR-TEST-001",
            approval_id="LVPA-TEST-001",
            candidate_id="LIT-AGR-GI-001",
            overlay_status="active",
            overlay_active=True,
            source_review_packet_hash="a" * 64,
            review_draft_id="LERD-TEST-001",
            comparison_hash="b" * 64,
            raw_value="85-102",
            unit="%",
            conditions={"condition_context": "Radish germination assay"},
            target_use="candidate_overlay_review",
            target_scope={"campaign_key": "frass-agronomy-review"},
            created_by_user_id=1,
            overlay_notes="Invalid active overlay.",
            idempotency_key="idem-overlay",
            created_at="2026-04-28T11:00:00+00:00",
            updated_at="2026-04-28T11:00:00+00:00",
        )


def test_literature_value_runtime_activation_requires_scope():
    with pytest.raises(ValidationError):
        LiteratureValueRuntimeActivationCreateRequest(
            activation_scope={},
            operator_attestation="Activate for a scoped runtime only.",
            idempotency_key="idem-runtime-activation",
        )

    with pytest.raises(ValidationError):
        LiteratureValueRuntimeActivationCreateRequest(
            activation_scope={"global": True},
            operator_attestation="Invalid global activation.",
            idempotency_key="idem-runtime-activation",
        )


def test_literature_value_runtime_activation_preview_is_read_only():
    preview = LiteratureValueRuntimeActivationPreviewResponse(
        tenant_id=1,
        overlay_id="LVO-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        can_activate_scoped_runtime=True,
    )

    assert preview.schema_version == "literature_value_runtime_activation_preview_v1"
    assert preview.global_activation_allowed is False
    assert preview.release_evidence_allowed is False
    assert preview.validated_default_write_enabled is False
    assert preview.final_action_execution is False
    assert "scope_required" in preview.guardrails


def test_literature_value_runtime_activation_is_scoped():
    response = LiteratureValueRuntimeActivationResponse(
        activation_id="LVRA-TEST-001",
        tenant_id=1,
        overlay_id="LVO-TEST-001",
        promotion_request_id="LVPR-TEST-001",
        approval_id="LVPA-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        activation_status="active",
        activation_scope={"campaign_key": "frass-agronomy-review"},
        scope_key="campaign_key:frass-agronomy-review",
        activated_by_user_id=1,
        operator_attestation="Activate only for the named campaign scope.",
        idempotency_key="idem-runtime-activation",
        runtime_display="external literature overlay active for this scope: campaign_key:frass-agronomy-review (active)",
        scoped_runtime_activation_enabled=True,
        created_at="2026-04-28T11:30:00+00:00",
        updated_at="2026-04-28T11:30:00+00:00",
    )

    assert response.schema_version == "literature_value_runtime_activation_v1"
    assert response.activation_status == "active"
    assert response.activation_scope == {"campaign_key": "frass-agronomy-review"}
    assert response.scoped_runtime_activation_enabled is True
    assert response.global_activation_allowed is False
    assert response.release_evidence_allowed is False
    assert response.validated_default_write_enabled is False
    assert response.final_action_execution is False
    assert response.side_effects["scoped_runtime_activation"] is True
    assert response.side_effects["global_runtime_activation"] is False
    assert "scoped_runtime_activation_only" in response.guardrails


def test_literature_value_release_evidence_link_keeps_review_required():
    response = LiteratureValueReleaseEvidenceLinkResponse(
        link_id="LVREL-TEST-001",
        tenant_id=1,
        release_decision_id=10,
        activation_id="LVRA-TEST-001",
        overlay_id="LVO-TEST-001",
        promotion_request_id="LVPR-TEST-001",
        approval_id="LVPA-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        activation_scope={"campaign_key": "frass-agronomy-review"},
        scope_key="campaign_key:frass-agronomy-review",
        source_review_packet_hash="a" * 64,
        comparison_hash="b" * 64,
        release_decision_before="review_required",
        release_decision_after="review_required",
        linked_by_user_id=1,
        link_notes="Link active scoped literature overlay as evidence only.",
        idempotency_key="idem-release-evidence-link",
        created_at="2026-04-28T12:00:00+00:00",
        updated_at="2026-04-28T12:00:00+00:00",
    )

    assert response.schema_version == "literature_value_release_evidence_link_v1"
    assert response.release_decision_unchanged is True
    assert response.human_review_required is True
    assert response.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert "release_decision_remains_review_required" in response.guardrails


def test_literature_value_rollback_marks_scoped_runtime_without_release_mutation():
    request = LiteratureValueRollbackCreateRequest(
        rollback_reason="Rollback campaign-scoped literature overlay after review.",
        operator_attestation="I confirm this rollback only deactivates scoped runtime and preserves review_required release decisions.",
        idempotency_key="idem-literature-rollback",
    )
    assert request.rollback_reason.startswith("Rollback")

    response = LiteratureValueRollbackResponse(
        rollback_id="LVRB-TEST-001",
        tenant_id=1,
        activation_id="LVRA-TEST-001",
        overlay_id="LVO-TEST-001",
        promotion_request_id="LVPR-TEST-001",
        approval_id="LVPA-TEST-001",
        candidate_id="LIT-AGR-GI-001",
        activation_status_before="active",
        activation_status_after="deactivated",
        overlay_status_before="inactive",
        overlay_status_after="rolled_back",
        affected_release_evidence_link_ids=["LVREL-TEST-001"],
        release_evidence_link_status_updates=[
            {
                "link_id": "LVREL-TEST-001",
                "link_status_before": "active",
                "link_status_after": "rolled_back",
                "rollback_status_before": "none",
                "rollback_status_after": "rolled_back",
            }
        ],
        release_decision_states=[
            {
                "release_decision_id": 10,
                "link_id": "LVREL-TEST-001",
                "release_decision_before": "review_required",
                "release_decision_after": "review_required",
            }
        ],
        rolled_back_by_user_id=1,
        rollback_reason=request.rollback_reason,
        operator_attestation=request.operator_attestation,
        idempotency_key=request.idempotency_key,
        created_at="2026-04-28T13:00:00+00:00",
        updated_at="2026-04-28T13:00:00+00:00",
    )

    assert response.schema_version == "literature_value_rollback_v1"
    assert response.activation_status_after == "deactivated"
    assert response.overlay_status_after == "rolled_back"
    assert response.release_decision_unchanged is True
    assert response.human_review_required is True
    assert response.final_action_execution is False
    assert response.side_effects["runtime_deactivation"] is True
    assert response.side_effects["overlay_status_update"] is True
    assert response.side_effects["release_decision_update"] is False
    assert response.side_effects["species_db_write"] is False
    assert response.side_effects["feedstock_db_write"] is False
    assert "rollback_is_append_only_audit_record" in response.guardrails


def test_literature_value_rollback_rejects_release_decision_mutation():
    with pytest.raises(ValidationError):
        LiteratureValueRollbackResponse(
            rollback_id="LVRB-TEST-001",
            tenant_id=1,
            activation_id="LVRA-TEST-001",
            overlay_id="LVO-TEST-001",
            promotion_request_id="LVPR-TEST-001",
            approval_id="LVPA-TEST-001",
            candidate_id="LIT-AGR-GI-001",
            activation_status_before="active",
            activation_status_after="deactivated",
            overlay_status_before="inactive",
            overlay_status_after="rolled_back",
            affected_release_evidence_link_ids=["LVREL-TEST-001"],
            release_evidence_link_status_updates=[],
            release_decision_states=[
                {
                    "release_decision_id": 10,
                    "link_id": "LVREL-TEST-001",
                    "release_decision_before": "review_required",
                    "release_decision_after": "approved",
                }
            ],
            rolled_back_by_user_id=1,
            rollback_reason="Invalid rollback.",
            operator_attestation="Invalid release decision mutation.",
            idempotency_key="idem-literature-rollback-invalid",
            created_at="2026-04-28T13:00:00+00:00",
            updated_at="2026-04-28T13:00:00+00:00",
        )


def test_literature_value_promotion_lifecycle_is_read_only():
    response = LiteratureValuePromotionLifecycleResponse(
        tenant_id=1,
        candidate_id="LIT-AGR-GI-001",
        promotion_request_count=1,
        approval_count=1,
        overlay_count=1,
        runtime_activation_count=1,
        release_evidence_link_count=1,
        rollback_count=1,
        promotion_request_ids=["LVPR-TEST-001"],
        approval_ids=["LVPA-TEST-001"],
        overlay_ids=["LVO-TEST-001"],
        activation_ids=["LVRA-TEST-001"],
        release_evidence_link_ids=["LVREL-TEST-001"],
        rollback_ids=["LVRB-TEST-001"],
        request_statuses=["approved_for_promotion"],
        approval_actions=["approve"],
        overlay_statuses=["rolled_back"],
        activation_statuses=["deactivated"],
        release_evidence_link_statuses=["rolled_back"],
        rollback_statuses=["completed"],
        release_decision_states=[
            {
                "release_decision_id": 10,
                "link_id": "LVREL-TEST-001",
                "release_decision_before": "review_required",
                "release_decision_after": "review_required",
            }
        ],
    )

    assert response.schema_version == "literature_value_promotion_lifecycle_v1"
    assert response.lifecycle_read_only is True
    assert response.release_decision_unchanged is True
    assert response.human_review_required is True
    assert response.final_action_execution is False
    assert all(value is False for value in response.side_effects.values())
    assert "promotion_lifecycle_is_read_only" in response.guardrails


def test_literature_value_promotion_lifecycle_rejects_mutation_side_effects():
    with pytest.raises(ValidationError):
        LiteratureValuePromotionLifecycleResponse(
            tenant_id=1,
            candidate_id="LIT-AGR-GI-001",
            promotion_request_count=1,
            approval_count=1,
            overlay_count=1,
            runtime_activation_count=1,
            release_evidence_link_count=1,
            rollback_count=0,
            promotion_request_ids=["LVPR-TEST-001"],
            approval_ids=["LVPA-TEST-001"],
            overlay_ids=["LVO-TEST-001"],
            activation_ids=["LVRA-TEST-001"],
            release_evidence_link_ids=["LVREL-TEST-001"],
            rollback_ids=[],
            request_statuses=["approved_for_promotion"],
            approval_actions=["approve"],
            overlay_statuses=["inactive"],
            activation_statuses=["active"],
            release_evidence_link_statuses=["active"],
            rollback_statuses=[],
            release_decision_states=[
                {
                    "release_decision_id": 10,
                    "link_id": "LVREL-TEST-001",
                    "release_decision_before": "review_required",
                    "release_decision_after": "review_required",
                }
            ],
            side_effects={"release_decision_update": True},
        )


def test_literature_value_promotion_audit_export_is_response_only():
    response = LiteratureValuePromotionAuditExportResponse(
        tenant_id=1,
        candidate_id="LIT-AGR-GI-001",
        content_hash="e" * 64,
        export_manifest={
            "export_id": "literature-value-promotion-audit-export:LIT-AGR-GI-001:eeeeeeeeeeee",
            "candidate_id": "LIT-AGR-GI-001",
            "content_hash_algorithm": "sha256",
            "content_hash": "e" * 64,
            "export_policy": "response_only_no_file_write",
            "file_written": False,
            "promotion_request_count": 1,
            "approval_count": 2,
            "overlay_count": 1,
            "runtime_activation_count": 1,
            "release_evidence_link_count": 1,
            "rollback_count": 1,
            "request_statuses": ["approved_for_promotion"],
            "release_decision_states": [
                {
                    "release_decision_id": 10,
                    "link_id": "LVREL-TEST-001",
                    "release_decision_before": "review_required",
                    "release_decision_after": "review_required",
                }
            ],
            "db_pollution_proof_included": True,
            "final_action_non_execution_proof_included": True,
        },
        request={"promotion_request_id": "LVPR-TEST-001", "request_status": "approved_for_promotion"},
        approvals=[{"approval_id": "LVPA-TEST-001"}, {"approval_id": "LVPA-TEST-002"}],
        overlay={"overlay_id": "LVO-TEST-001", "overlay_status": "rolled_back"},
        runtime_activation={"activation_id": "LVRA-TEST-001", "activation_status": "deactivated"},
        release_evidence_link={"link_id": "LVREL-TEST-001", "link_status": "rolled_back"},
        rollback={"rollback_id": "LVRB-TEST-001", "rollback_status": "completed"},
        db_pollution_proof={
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "candidate_id_present_in_species_db": False,
            "candidate_id_present_in_feedstock_db": False,
        },
        final_action_non_execution_proof={
            "final_action_execution": False,
            "release_auto_approval": False,
            "release_decision_update": False,
            "release_decision_states": [
                {
                    "release_decision_id": 10,
                    "link_id": "LVREL-TEST-001",
                    "release_decision_before": "review_required",
                    "release_decision_after": "review_required",
                }
            ],
            "release_decisions_all_review_required": True,
        },
    )

    assert response.schema_version == "literature_value_promotion_audit_export_v1"
    assert response.export_policy == "response_only_no_file_write"
    assert response.export_manifest["file_written"] is False
    assert len(response.content_hash) == 64
    assert response.db_pollution_proof["species_db_write"] is False
    assert response.db_pollution_proof["feedstock_db_write"] is False
    assert response.db_pollution_proof["validated_default_write"] is False
    assert response.final_action_non_execution_proof["final_action_execution"] is False
    assert response.final_action_non_execution_proof["release_decisions_all_review_required"] is True
    assert all(value is False for value in response.side_effects.values())
    assert "promotion_audit_export_is_response_only" in response.guardrails


def test_literature_value_promotion_audit_export_rejects_file_write():
    with pytest.raises(ValidationError):
        LiteratureValuePromotionAuditExportResponse(
            tenant_id=1,
            candidate_id="LIT-AGR-GI-001",
            content_hash="e" * 64,
            export_manifest={
                "export_policy": "response_only_no_file_write",
                "file_written": True,
            },
            db_pollution_proof={
                "validated_default_write": False,
                "species_db_write": False,
                "feedstock_db_write": False,
            },
            final_action_non_execution_proof={
                "final_action_execution": False,
                "release_decision_states": [],
            },
        )


def test_literature_extraction_evidence_chain_readiness_rejects_auto_use():
    with pytest.raises(ValidationError):
        LiteratureExtractionEvidenceChainReadinessResponse(
            tenant_id=1,
            chain_complete=True,
            candidate_count=5,
            packet_export_ready=True,
            bulk_export_ready=True,
            review_draft_count=1,
            comparison_ready=True,
            report_ready=True,
            auto_use_allowed=True,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("human_review_required", False),
        ("numeric_values_included", False),
        ("release_evidence_allowed", True),
        ("runtime_activation_enabled", True),
        ("validated_default_write_enabled", True),
        ("promotion_enabled", True),
    ],
)
def test_literature_extraction_candidate_rejects_guardrail_bypass(field, value):
    payload = _valid_literature_extraction_candidate_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        LiteratureExtractionCandidateRead(**payload)
