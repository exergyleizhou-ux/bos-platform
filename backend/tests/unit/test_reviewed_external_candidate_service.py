from datetime import UTC, datetime

import pytest

from app.engine.feedstock_db import FEEDSTOCK_DB
from app.engine.species_db import SPECIES_DB
from app.models import Batch, User
from app.models_bos import KnowledgeRelationRecord, ReleaseDecision
from app.schemas.external_source_review import ExternalSourceReviewCardResolveRequest
from app.services.external_knowledge_activation_service import (
    ACTIVATION_EXECUTED_PREDICATE,
    activation_scope_key,
    get_active_external_candidate_payload,
)
from app.services.reviewed_external_candidate_service import (
    create_literature_value_promotion_approval,
    create_literature_extraction_review_draft,
    create_literature_value_release_evidence_link,
    create_literature_value_runtime_activation,
    fill_phase4a_domain_reviewed_candidates,
    get_business_knowledge_review_packet_export,
    get_extraction_record,
    get_external_source_schema_readiness,
    get_literature_extraction_evidence_chain_readiness,
    get_literature_extraction_review_draft_comparison,
    get_literature_value_promotion_audit_export,
    get_literature_value_promotion_lifecycle,
    get_literature_value_runtime_activation_preview,
    get_literature_value_promotion_readiness,
    create_literature_value_promotion_request,
    get_reviewed_candidate_lane_summary,
    get_reviewed_candidate_activation_preview,
    get_reviewed_candidate_review_packet,
    get_reviewed_candidate_review_packet_export,
    get_reviewed_candidate_rollback_preview,
    get_reviewed_candidate_runtime_readiness,
    get_source_procurement_summary,
    list_feedstock_dataset_candidates,
    list_literature_extraction_candidates,
    list_literature_extraction_review_drafts,
    list_extraction_records,
    list_review_cards,
    list_reviewed_candidates,
    promote_literature_value_request_to_overlay,
    resolve_review_card,
    rollback_literature_value_runtime_activation,
    seed_literature_extraction_candidates,
    seed_phase4a_domain_metadata_sources,
    seed_p0_external_sources,
)
from app.schemas.external_source_review import LiteratureExtractionReviewDraftCreateRequest
from app.schemas.external_source_review import LiteratureValueOverlayCreateRequest
from app.schemas.external_source_review import LiteratureValuePromotionApprovalCreateRequest
from app.schemas.external_source_review import LiteratureValuePromotionRequestCreateRequest
from app.schemas.external_source_review import LiteratureValueReleaseEvidenceLinkCreateRequest
from app.schemas.external_source_review import LiteratureValueRollbackCreateRequest
from app.schemas.external_source_review import LiteratureValueRuntimeActivationCreateRequest


@pytest.mark.asyncio
async def test_literature_extraction_candidates_are_numeric_but_review_gated(db_session):
    response = await list_literature_extraction_candidates(db_session)

    assert response.schema_version == "literature_extraction_candidate_list_v1"
    assert response.count >= 5
    assert response.metric_counts["germination_index"] >= 1
    assert response.metric_counts["phytotoxicity"] >= 1
    assert response.side_effects == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "promotion": False,
        "final_action_execution": False,
    }
    assert {item.candidate_type for item in response.items} == {"literature_extraction_candidate"}
    assert {item.review_status for item in response.items} == {"pending_review"}
    assert {item.human_review_required for item in response.items} == {True}
    assert {item.numeric_values_included for item in response.items} == {True}
    assert {item.release_evidence_allowed for item in response.items} == {False}
    assert {item.runtime_activation_enabled for item in response.items} == {False}
    assert {item.validated_default_write_enabled for item in response.items} == {False}
    assert {item.promotion_enabled for item in response.items} == {False}

    filtered = await list_literature_extraction_candidates(db_session, metric_key="phytotoxicity")
    assert filtered.count == response.metric_counts["phytotoxicity"]
    assert {item.metric_key for item in filtered.items} == {"phytotoxicity"}


@pytest.mark.asyncio
async def test_seed_literature_extraction_candidates_persists_candidate_values_only(db_session, test_tenant):
    seed_response = await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)

    assert seed_response.schema_version == "literature_extraction_candidate_seed_v1"
    assert seed_response.source_count == 1
    assert seed_response.candidate_count >= 5
    assert seed_response.created_candidate_count >= 5
    assert seed_response.updated_candidate_count == 0
    assert seed_response.review_status == "pending_review"
    assert seed_response.numeric_values_included is True
    assert seed_response.release_evidence_allowed is False
    assert seed_response.runtime_activation_enabled is False
    assert seed_response.validated_default_write_enabled is False
    assert seed_response.promotion_enabled is False
    assert seed_response.side_effects == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "promotion": False,
        "final_action_execution": False,
    }

    response = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    assert response.count == seed_response.candidate_count
    assert all(item.candidate_type == "literature_extraction_candidate" for item in response.items)
    assert all(item.review_status == "pending_review" for item in response.items)
    assert all(item.human_review_required is True for item in response.items)
    assert all(item.numeric_values_included is True for item in response.items)
    assert all(item.release_evidence_allowed is False for item in response.items)
    assert all(item.runtime_activation_enabled is False for item in response.items)
    assert all(item.validated_default_write_enabled is False for item in response.items)
    assert all(item.promotion_enabled is False for item in response.items)

    second_seed_response = await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    assert second_seed_response.created_candidate_count == 0
    assert second_seed_response.updated_candidate_count == seed_response.candidate_count


@pytest.mark.asyncio
async def test_literature_extraction_review_draft_records_intent_without_candidate_mutation(
    db_session,
    test_tenant,
    operator_user,
):
    await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidates_before = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidate = candidates_before.items[0]

    draft = await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="approve_candidate_use_intent",
            reviewer_notes="Reviewer intent only; keep raw literature value pending review.",
            idempotency_key="idem-literature-review-draft-service",
        ),
    )

    assert draft is not None
    assert draft.review_draft_id.startswith("LERD-")
    assert draft.status == "draft_intent_recorded"
    assert draft.candidate_id == candidate.candidate_id
    assert draft.candidate_snapshot["review_status"] == "pending_review"
    assert draft.source_review_packet_hash
    assert draft.export_manifest["export_policy"] == "response_only_no_file_write"
    assert all(value is False for value in draft.side_effects.values())
    assert draft.release_evidence_allowed is False
    assert draft.runtime_activation_enabled is False
    assert draft.validated_default_write_enabled is False
    assert draft.promotion_enabled is False
    assert draft.final_action_execution is False

    repeated = await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="approve_candidate_use_intent",
            reviewer_notes="Repeated request should return the existing draft.",
            idempotency_key="idem-literature-review-draft-service",
        ),
    )
    assert repeated is not None
    assert repeated.review_draft_id == draft.review_draft_id

    listed = await list_literature_extraction_review_drafts(db_session, tenant_id=test_tenant.id)
    assert listed.count == 1
    assert listed.drafts[0].review_draft_id == draft.review_draft_id
    assert listed.side_effects["candidate_status_update"] is False

    candidates_after = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    after_by_id = {item.candidate_id: item for item in candidates_after.items}
    assert after_by_id[candidate.candidate_id].review_status == "pending_review"
    assert after_by_id[candidate.candidate_id].release_evidence_allowed is False
    assert after_by_id[candidate.candidate_id].runtime_activation_enabled is False
    assert after_by_id[candidate.candidate_id].validated_default_write_enabled is False
    assert after_by_id[candidate.candidate_id].promotion_enabled is False


@pytest.mark.asyncio
async def test_literature_extraction_review_draft_comparison_is_response_only_audit_trail(
    db_session,
    test_tenant,
    operator_user,
):
    await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidates = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidate = candidates.items[0]

    first = await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="needs_review",
            reviewer_notes="Initial reviewer intent only.",
            idempotency_key="idem-literature-review-draft-comparison-1",
        ),
    )
    second = await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="needs_license_clearance",
            reviewer_notes="Second reviewer intent only; still no candidate mutation.",
            idempotency_key="idem-literature-review-draft-comparison-2",
        ),
    )

    assert first is not None
    assert second is not None
    comparison = await get_literature_extraction_review_draft_comparison(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )

    assert comparison is not None
    assert comparison.schema_version == "literature_extraction_review_draft_comparison_v1"
    assert comparison.current_review_draft_id == second.review_draft_id
    assert comparison.previous_review_draft_id == first.review_draft_id
    assert comparison.comparison_manifest["comparison_policy"] == "response_only_no_file_write"
    assert comparison.report_manifest["report_policy"] == "response_only_no_file_write"
    assert comparison.report_manifest["file_written"] is False
    assert comparison.report_payload["summary"]["packet_hash_matches"] is True
    assert comparison.comparison_manifest["candidate_status"] == "pending_review"
    assert comparison.comparison_summary["review_intent_changed_since_previous"] is True
    assert comparison.comparison_summary["current_response_packet_hash_matches_draft"] is True
    assert "review_intent" in comparison.changed_fields
    assert len(comparison.audit_trail) == 2
    assert comparison.audit_trail[1].changed_fields == ["review_intent"]
    assert all(value is False for value in comparison.side_effects.values())

    after = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    after_by_id = {item.candidate_id: item for item in after.items}
    assert after_by_id[candidate.candidate_id].review_status == "pending_review"
    assert after_by_id[candidate.candidate_id].release_evidence_allowed is False
    assert after_by_id[candidate.candidate_id].runtime_activation_enabled is False
    assert after_by_id[candidate.candidate_id].validated_default_write_enabled is False

    filtered = await get_literature_extraction_review_draft_comparison(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        changed_field="source_review_packet_hash",
    )
    assert filtered is not None
    assert filtered.changed_field_filter == "source_review_packet_hash"
    assert filtered.changed_fields == []
    assert filtered.report_manifest["changed_field_filter"] == "source_review_packet_hash"
    assert filtered.report_payload["summary"]["changed_fields"] == []


@pytest.mark.asyncio
async def test_literature_extraction_evidence_chain_readiness_is_final_read_only_summary(
    db_session,
    test_tenant,
    operator_user,
):
    before = await get_literature_extraction_evidence_chain_readiness(db_session, tenant_id=test_tenant.id)
    assert before.schema_version == "literature_extraction_evidence_chain_readiness_v1"
    assert before.chain_complete is False
    assert before.candidate_count == 0
    assert before.auto_use_allowed is False
    assert before.final_action_execution is False
    assert all(value is False for value in before.side_effects.values())

    await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidates = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidate = candidates.items[0]
    await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="approve_candidate_use_intent",
            reviewer_notes="Final readiness summary smoke keeps candidate pending review.",
            idempotency_key="idem-literature-readiness-summary",
        ),
    )

    readiness = await get_literature_extraction_evidence_chain_readiness(db_session, tenant_id=test_tenant.id)
    assert readiness.chain_complete is True
    assert readiness.promotion_ready is True
    assert readiness.candidate_count == candidates.count
    assert readiness.packet_export_ready is True
    assert readiness.bulk_export_ready is True
    assert readiness.review_draft_count == 1
    assert readiness.comparison_ready is True
    assert readiness.report_ready is True
    assert readiness.blocking_reason is None
    assert readiness.auto_use_allowed is False
    assert readiness.release_evidence_allowed is False
    assert readiness.runtime_activation_enabled is False
    assert readiness.validated_default_write_enabled is False
    assert readiness.promotion_enabled is False
    assert readiness.final_action_execution is False
    assert "literature_evidence_chain_readiness_is_read_only" in readiness.guardrails
    assert all(value is False for value in readiness.side_effects.values())

    after = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    assert {item.review_status for item in after.items} == {"pending_review"}
    assert {item.release_evidence_allowed for item in after.items} == {False}
    assert {item.runtime_activation_enabled for item in after.items} == {False}
    assert {item.validated_default_write_enabled for item in after.items} == {False}
    assert {item.promotion_enabled for item in after.items} == {False}


@pytest.mark.asyncio
async def test_literature_value_promotion_request_is_request_only(
    db_session,
    test_tenant,
    operator_user,
    scientist_user,
):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidates = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    candidate = candidates.items[0]
    draft = await create_literature_extraction_review_draft(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        reviewer_user_id=operator_user.id,
        request=LiteratureExtractionReviewDraftCreateRequest(
            review_intent="approve_candidate_use_intent",
            reviewer_notes="Promotion request starts only after review-only chain is complete.",
            idempotency_key="idem-literature-promotion-draft",
        ),
    )
    assert draft is not None

    readiness = await get_literature_value_promotion_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert readiness is not None
    assert readiness.schema_version == "literature_value_promotion_readiness_v1"
    assert readiness.chain_complete is True
    assert readiness.promotion_ready is True
    assert readiness.request_status == "not_requested"
    assert readiness.raw_value == candidate.raw_value
    assert readiness.unit == candidate.unit
    assert readiness.source_review_packet_hash == draft.source_review_packet_hash
    assert readiness.release_evidence_allowed is False
    assert readiness.runtime_activation_enabled is False
    assert readiness.validated_default_write_enabled is False
    assert readiness.promotion_enabled is False
    assert readiness.final_action_execution is False
    assert all(value is False for value in readiness.side_effects.values())

    promotion_request = await create_literature_value_promotion_request(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        requested_by_user_id=operator_user.id,
        request=LiteratureValuePromotionRequestCreateRequest(
            target_use="candidate_overlay_review",
            target_scope={"campaign_key": "frass-agronomy-review"},
            idempotency_key="idem-literature-promotion-request",
        ),
    )
    assert promotion_request is not None
    assert promotion_request.schema_version == "literature_value_promotion_request_v1"
    assert promotion_request.promotion_request_id.startswith("LVPR-")
    assert promotion_request.candidate_id == candidate.candidate_id
    assert promotion_request.source_review_packet_hash == draft.source_review_packet_hash
    assert promotion_request.review_draft_id == draft.review_draft_id
    assert promotion_request.raw_value == candidate.raw_value
    assert promotion_request.unit == candidate.unit
    assert promotion_request.target_use == "candidate_overlay_review"
    assert promotion_request.target_scope == {"campaign_key": "frass-agronomy-review"}
    assert promotion_request.request_status == "requested"
    assert promotion_request.release_evidence_allowed is False
    assert promotion_request.runtime_activation_enabled is False
    assert promotion_request.validated_default_write_enabled is False
    assert promotion_request.promotion_enabled is False
    assert promotion_request.final_action_execution is False
    assert all(value is False for value in promotion_request.side_effects.values())
    assert "request_status_requested_not_active" in promotion_request.guardrails

    repeated = await create_literature_value_promotion_request(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
        requested_by_user_id=operator_user.id,
        request=LiteratureValuePromotionRequestCreateRequest(
            target_use="candidate_overlay_review",
            target_scope={"campaign_key": "frass-agronomy-review"},
            idempotency_key="idem-literature-promotion-request",
        ),
    )
    assert repeated is not None
    assert repeated.promotion_request_id == promotion_request.promotion_request_id

    after_readiness = await get_literature_value_promotion_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert after_readiness is not None
    assert after_readiness.request_status == "requested"
    assert after_readiness.existing_promotion_request_id == promotion_request.promotion_request_id

    with pytest.raises(ValueError, match="literature_value_promotion_requester_cannot_approve"):
        await create_literature_value_promotion_approval(
            db_session,
            tenant_id=test_tenant.id,
            promotion_request_id=promotion_request.promotion_request_id,
            approved_by_user_id=operator_user.id,
            approved_by_user_roles={"scientist"},
            request=LiteratureValuePromotionApprovalCreateRequest(
                approval_action="approve",
                approver_notes="Requester cannot approve their own promotion request.",
                idempotency_key="idem-literature-promotion-self-approval",
            ),
        )

    approval = await create_literature_value_promotion_approval(
        db_session,
        tenant_id=test_tenant.id,
        promotion_request_id=promotion_request.promotion_request_id,
        approved_by_user_id=scientist_user.id,
        approved_by_user_roles={"scientist"},
        request=LiteratureValuePromotionApprovalCreateRequest(
            approval_action="approve",
            approver_notes="Reviewed request packet and scope; approval is audit-only before overlay creation.",
            idempotency_key="idem-literature-promotion-approval",
        ),
    )
    assert approval is not None
    assert approval.schema_version == "literature_value_promotion_approval_v1"
    assert approval.approval_id.startswith("LVPA-")
    assert approval.promotion_request_id == promotion_request.promotion_request_id
    assert approval.candidate_id == candidate.candidate_id
    assert approval.approval_action == "approve"
    assert approval.request_status_before == "requested"
    assert approval.request_status_after == "requested"
    assert approval.approved_by_user_roles == ["scientist"]
    assert approval.approval_audit_only is True
    assert approval.overlay_write_enabled is False
    assert approval.release_evidence_allowed is False
    assert approval.runtime_activation_enabled is False
    assert approval.validated_default_write_enabled is False
    assert approval.promotion_enabled is False
    assert approval.final_action_execution is False
    assert all(value is False for value in approval.side_effects.values())
    assert "approval_does_not_create_overlay" in approval.guardrails

    repeated_approval = await create_literature_value_promotion_approval(
        db_session,
        tenant_id=test_tenant.id,
        promotion_request_id=promotion_request.promotion_request_id,
        approved_by_user_id=scientist_user.id,
        approved_by_user_roles={"scientist"},
        request=LiteratureValuePromotionApprovalCreateRequest(
            approval_action="approve",
            approver_notes="Reviewed request packet and scope; approval is audit-only before overlay creation.",
            idempotency_key="idem-literature-promotion-approval",
        ),
    )
    assert repeated_approval is not None
    assert repeated_approval.approval_id == approval.approval_id

    approved_readiness = await get_literature_value_promotion_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert approved_readiness is not None
    assert approved_readiness.request_status == "requested"
    assert approved_readiness.promotion_enabled is False

    with pytest.raises(ValueError, match="literature_value_promotion_request_not_approved"):
        await promote_literature_value_request_to_overlay(
            db_session,
            tenant_id=test_tenant.id,
            promotion_request_id=promotion_request.promotion_request_id,
            created_by_user_id=operator_user.id,
            request=LiteratureValueOverlayCreateRequest(
                overlay_notes="Single-person approval cannot create an overlay.",
                idempotency_key="idem-literature-overlay-before-dual-approval",
            ),
        )

    release_manager = User(
        username="test_release_manager_phase21",
        hashed_password="test",
        full_name="Test Release Manager",
        email="test_release_manager_phase21@bos.io",
        role="release_manager",
        tenant_id=test_tenant.id,
        is_active=True,
    )
    db_session.add(release_manager)
    await db_session.commit()
    await db_session.refresh(release_manager)

    second_approval = await create_literature_value_promotion_approval(
        db_session,
        tenant_id=test_tenant.id,
        promotion_request_id=promotion_request.promotion_request_id,
        approved_by_user_id=release_manager.id,
        approved_by_user_roles={"release_manager"},
        request=LiteratureValuePromotionApprovalCreateRequest(
            approval_action="approve",
            approver_notes="Release manager confirms the scientist approval and scope remain review-only.",
            idempotency_key="idem-literature-promotion-approval-release-manager",
        ),
    )
    assert second_approval is not None
    assert second_approval.request_status_before == "requested"
    assert second_approval.request_status_after == "approved_for_promotion"
    assert second_approval.approved_by_user_roles == ["release_manager"]

    approved_readiness = await get_literature_value_promotion_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert approved_readiness is not None
    assert approved_readiness.request_status == "approved_for_promotion"
    assert approved_readiness.promotion_enabled is False

    overlay = await promote_literature_value_request_to_overlay(
        db_session,
        tenant_id=test_tenant.id,
        promotion_request_id=promotion_request.promotion_request_id,
        created_by_user_id=operator_user.id,
        request=LiteratureValueOverlayCreateRequest(
            overlay_notes="Create inactive overlay only; runtime activation remains separate.",
            idempotency_key="idem-literature-overlay",
        ),
    )
    assert overlay is not None
    assert overlay.schema_version == "literature_value_overlay_v1"
    assert overlay.overlay_id.startswith("LVO-")
    assert overlay.promotion_request_id == promotion_request.promotion_request_id
    assert overlay.approval_id == second_approval.approval_id
    assert overlay.candidate_id == candidate.candidate_id
    assert overlay.overlay_status == "inactive"
    assert overlay.overlay_active is False
    assert overlay.normalized_value == f"{candidate.raw_value} {candidate.unit}"
    assert overlay.source_ref == candidate.source_ref
    assert len(overlay.approval_hash) == 64
    assert len(overlay.overlay_hash) == 64
    assert overlay.validity_scope["target_scope"] == {"campaign_key": "frass-agronomy-review"}
    assert overlay.validity_scope["conditions"]["source_ref"] == candidate.source_ref
    assert overlay.rollback_pointer["required"] is True
    assert overlay.rollback_pointer["rollback_status"] == "not_rolled_back"
    assert overlay.release_evidence_allowed is False
    assert overlay.runtime_activation_enabled is False
    assert overlay.validated_default_write_enabled is False
    assert overlay.final_action_execution is False
    assert all(value is False for value in overlay.side_effects.values())
    assert "overlay_requires_separate_scoped_runtime_activation" in overlay.guardrails

    repeated_overlay = await promote_literature_value_request_to_overlay(
        db_session,
        tenant_id=test_tenant.id,
        promotion_request_id=promotion_request.promotion_request_id,
        created_by_user_id=operator_user.id,
        request=LiteratureValueOverlayCreateRequest(
            overlay_notes="Create inactive overlay only; runtime activation remains separate.",
            idempotency_key="idem-literature-overlay",
        ),
    )
    assert repeated_overlay is not None
    assert repeated_overlay.overlay_id == overlay.overlay_id

    preview = await get_literature_value_runtime_activation_preview(
        db_session,
        tenant_id=test_tenant.id,
        overlay_id=overlay.overlay_id,
    )
    assert preview is not None
    assert preview.schema_version == "literature_value_runtime_activation_preview_v1"
    assert preview.can_activate_scoped_runtime is True
    assert preview.global_activation_allowed is False
    assert preview.release_evidence_allowed is False
    assert preview.validated_default_write_enabled is False

    activation = await create_literature_value_runtime_activation(
        db_session,
        tenant_id=test_tenant.id,
        overlay_id=overlay.overlay_id,
        activated_by_user_id=operator_user.id,
        request=LiteratureValueRuntimeActivationCreateRequest(
            activation_scope={"campaign_key": "frass-agronomy-review"},
            operator_attestation="Activate only for the named campaign scope.",
            idempotency_key="idem-literature-runtime-activation",
        ),
    )
    assert activation is not None
    assert activation.schema_version == "literature_value_runtime_activation_v1"
    assert activation.activation_id.startswith("LVRA-")
    assert activation.overlay_id == overlay.overlay_id
    assert activation.activation_status == "active"
    assert activation.activation_scope == {"campaign_key": "frass-agronomy-review"}
    assert activation.scope_key == "campaign_key:frass-agronomy-review"
    assert activation.scoped_runtime_activation_enabled is True
    assert activation.global_activation_allowed is False
    assert activation.release_evidence_allowed is False
    assert activation.validated_default_write_enabled is False
    assert activation.final_action_execution is False
    assert activation.side_effects["scoped_runtime_activation"] is True
    assert activation.side_effects["global_runtime_activation"] is False
    assert "external literature overlay active for this scope" in activation.runtime_display

    repeated_activation = await create_literature_value_runtime_activation(
        db_session,
        tenant_id=test_tenant.id,
        overlay_id=overlay.overlay_id,
        activated_by_user_id=operator_user.id,
        request=LiteratureValueRuntimeActivationCreateRequest(
            activation_scope={"campaign_key": "frass-agronomy-review"},
            operator_attestation="Activate only for the named campaign scope.",
            idempotency_key="idem-literature-runtime-activation",
        ),
    )
    assert repeated_activation is not None
    assert repeated_activation.activation_id == activation.activation_id

    release_batch = Batch(
        batch_id="PHASE24-UNIT-BATCH",
        species="BSF",
        dm_in=10.0,
        dm_out=7.5,
        user_id=operator_user.id,
        tenant_id=test_tenant.id,
    )
    db_session.add(release_batch)
    await db_session.flush()
    release_decision = ReleaseDecision(
        batch_id=release_batch.id,
        user_id=operator_user.id,
        tenant_id=test_tenant.id,
        decision="review_required",
        reason_codes=["literature_overlay_requires_human_review"],
        trigger_metrics={"literature_overlay": "linked"},
    )
    db_session.add(release_decision)
    await db_session.commit()
    await db_session.refresh(release_decision)

    release_link = await create_literature_value_release_evidence_link(
        db_session,
        tenant_id=test_tenant.id,
        release_decision_id=release_decision.id,
        linked_by_user_id=operator_user.id,
        request=LiteratureValueReleaseEvidenceLinkCreateRequest(
            activation_id=activation.activation_id,
            link_notes="Link active scoped literature overlay as release evidence only.",
            idempotency_key="idem-literature-release-evidence",
        ),
    )
    assert release_link is not None
    assert release_link.schema_version == "literature_value_release_evidence_link_v1"
    assert release_link.link_id.startswith("LVREL-")
    assert release_link.release_decision_id == release_decision.id
    assert release_link.activation_id == activation.activation_id
    assert release_link.overlay_id == overlay.overlay_id
    assert release_link.release_decision_before == "review_required"
    assert release_link.release_decision_after == "review_required"
    assert release_link.release_decision_unchanged is True
    assert release_link.human_review_required is True
    assert release_link.final_action_execution is False
    assert all(value is False for value in release_link.side_effects.values())
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    rollback = await rollback_literature_value_runtime_activation(
        db_session,
        tenant_id=test_tenant.id,
        activation_id=activation.activation_id,
        rolled_back_by_user_id=operator_user.id,
        request=LiteratureValueRollbackCreateRequest(
            rollback_reason="Rollback scoped campaign evidence after release review.",
            operator_attestation="Rollback only deactivates scoped runtime and marks evidence links; release remains review_required.",
            idempotency_key="idem-literature-runtime-rollback",
        ),
    )
    assert rollback is not None
    assert rollback.schema_version == "literature_value_rollback_v1"
    assert rollback.rollback_id.startswith("LVRB-")
    assert rollback.activation_id == activation.activation_id
    assert rollback.overlay_id == overlay.overlay_id
    assert rollback.activation_status_before == "active"
    assert rollback.activation_status_after == "deactivated"
    assert rollback.overlay_status_before == "inactive"
    assert rollback.overlay_status_after == "rolled_back"
    assert rollback.affected_release_evidence_link_ids == [release_link.link_id]
    assert rollback.release_evidence_link_status_updates[0]["link_status_after"] == "rolled_back"
    assert rollback.release_decision_states[0]["release_decision_before"] == "review_required"
    assert rollback.release_decision_states[0]["release_decision_after"] == "review_required"
    assert rollback.release_decision_unchanged is True
    assert rollback.human_review_required is True
    assert rollback.final_action_execution is False
    assert rollback.side_effects["runtime_deactivation"] is True
    assert rollback.side_effects["overlay_status_update"] is True
    assert rollback.side_effects["release_evidence_link_status_update"] is True
    assert rollback.side_effects["release_decision_update"] is False
    assert rollback.side_effects["species_db_write"] is False
    assert rollback.side_effects["feedstock_db_write"] is False
    await db_session.refresh(release_decision)
    assert release_decision.decision == "review_required"

    repeated_rollback = await rollback_literature_value_runtime_activation(
        db_session,
        tenant_id=test_tenant.id,
        activation_id=activation.activation_id,
        rolled_back_by_user_id=operator_user.id,
        request=LiteratureValueRollbackCreateRequest(
            rollback_reason="Rollback scoped campaign evidence after release review.",
            operator_attestation="Rollback only deactivates scoped runtime and marks evidence links; release remains review_required.",
            idempotency_key="idem-literature-runtime-rollback",
        ),
    )
    assert repeated_rollback is not None
    assert repeated_rollback.rollback_id == rollback.rollback_id

    lifecycle = await get_literature_value_promotion_lifecycle(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert lifecycle is not None
    assert lifecycle.schema_version == "literature_value_promotion_lifecycle_v1"
    assert lifecycle.promotion_request_ids == [promotion_request.promotion_request_id]
    assert lifecycle.approval_ids == [approval.approval_id, second_approval.approval_id]
    assert lifecycle.overlay_ids == [overlay.overlay_id]
    assert lifecycle.activation_ids == [activation.activation_id]
    assert lifecycle.release_evidence_link_ids == [release_link.link_id]
    assert lifecycle.rollback_ids == [rollback.rollback_id]
    assert lifecycle.request_statuses == ["approved_for_promotion"]
    assert lifecycle.overlay_statuses == ["rolled_back"]
    assert lifecycle.activation_statuses == ["deactivated"]
    assert lifecycle.release_evidence_link_statuses == ["rolled_back"]
    assert lifecycle.rollback_statuses == ["completed"]
    assert lifecycle.release_decision_unchanged is True
    assert lifecycle.human_review_required is True
    assert lifecycle.final_action_execution is False
    assert all(value is False for value in lifecycle.side_effects.values())
    assert all(
        state["release_decision_before"] == "review_required"
        and state["release_decision_after"] == "review_required"
        for state in lifecycle.release_decision_states
    )

    state_snapshot_before_export = {
        "promotion_request_ids": list(lifecycle.promotion_request_ids),
        "approval_ids": list(lifecycle.approval_ids),
        "overlay_ids": list(lifecycle.overlay_ids),
        "activation_ids": list(lifecycle.activation_ids),
        "release_evidence_link_ids": list(lifecycle.release_evidence_link_ids),
        "rollback_ids": list(lifecycle.rollback_ids),
    }
    audit_export = await get_literature_value_promotion_audit_export(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert audit_export is not None
    assert audit_export.schema_version == "literature_value_promotion_audit_export_v1"
    assert audit_export.export_policy == "response_only_no_file_write"
    assert audit_export.export_manifest["file_written"] is False
    assert audit_export.export_manifest["export_policy"] == "response_only_no_file_write"
    assert audit_export.export_manifest["content_hash"] == audit_export.content_hash
    assert len(audit_export.content_hash) == 64
    assert audit_export.request is not None
    assert audit_export.request["promotion_request_id"] == promotion_request.promotion_request_id
    assert [approval["approval_id"] for approval in audit_export.approvals] == [
        approval.approval_id,
        second_approval.approval_id,
    ]
    assert audit_export.overlay is not None
    assert audit_export.overlay["overlay_id"] == overlay.overlay_id
    assert audit_export.runtime_activation is not None
    assert audit_export.runtime_activation["activation_id"] == activation.activation_id
    assert audit_export.release_evidence_link is not None
    assert audit_export.release_evidence_link["link_id"] == release_link.link_id
    assert audit_export.rollback is not None
    assert audit_export.rollback["rollback_id"] == rollback.rollback_id
    assert audit_export.db_pollution_proof["species_db_write"] is False
    assert audit_export.db_pollution_proof["feedstock_db_write"] is False
    assert audit_export.db_pollution_proof["validated_default_write"] is False
    assert audit_export.db_pollution_proof["candidate_id_present_in_species_db"] is False
    assert audit_export.db_pollution_proof["candidate_id_present_in_feedstock_db"] is False
    assert audit_export.final_action_non_execution_proof["final_action_execution"] is False
    assert audit_export.final_action_non_execution_proof["release_auto_approval"] is False
    assert audit_export.final_action_non_execution_proof["release_decision_update"] is False
    assert audit_export.final_action_non_execution_proof["release_decisions_all_review_required"] is True
    assert all(
        state["release_decision_before"] == "review_required"
        and state["release_decision_after"] == "review_required"
        for state in audit_export.final_action_non_execution_proof["release_decision_states"]
    )
    assert all(value is False for value in audit_export.side_effects.values())
    assert "promotion_audit_export_is_response_only" in audit_export.guardrails

    lifecycle_after_export = await get_literature_value_promotion_lifecycle(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id=candidate.candidate_id,
    )
    assert lifecycle_after_export is not None
    assert {
        "promotion_request_ids": list(lifecycle_after_export.promotion_request_ids),
        "approval_ids": list(lifecycle_after_export.approval_ids),
        "overlay_ids": list(lifecycle_after_export.overlay_ids),
        "activation_ids": list(lifecycle_after_export.activation_ids),
        "release_evidence_link_ids": list(lifecycle_after_export.release_evidence_link_ids),
        "rollback_ids": list(lifecycle_after_export.rollback_ids),
    } == state_snapshot_before_export

    after = await list_literature_extraction_candidates(db_session, tenant_id=test_tenant.id)
    after_by_id = {item.candidate_id: item for item in after.items}
    assert after_by_id[candidate.candidate_id].review_status == "pending_review"
    assert after_by_id[candidate.candidate_id].release_evidence_allowed is False
    assert after_by_id[candidate.candidate_id].runtime_activation_enabled is False
    assert after_by_id[candidate.candidate_id].validated_default_write_enabled is False
    assert after_by_id[candidate.candidate_id].promotion_enabled is False
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before


@pytest.mark.asyncio
async def test_seed_phase4a_domain_metadata_sources_only_touches_source_records(db_session, test_tenant):
    readiness_before = await get_external_source_schema_readiness(db_session)
    assert readiness_before.phase4a_domain_metadata_ready is False
    assert readiness_before.phase4a_domain_missing_counts == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }

    response = await seed_phase4a_domain_metadata_sources(db_session, tenant_id=test_tenant.id)

    assert response.source_count == 24
    assert response.created_source_count == 24
    assert response.updated_source_count == 0
    assert response.phase4a_domain_metadata_ready is True
    assert response.phase4a_domain_candidate_counts == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }
    assert response.phase4a_domain_missing_counts == {
        "lca": 0,
        "tea": 0,
        "compliance": 0,
        "model_provider": 0,
        "github_reference": 0,
    }
    assert response.runtime_activated_count == 0
    assert response.validated_default_write_enabled_count == 0
    assert response.numeric_value_candidate_count == 0
    assert "source_records_only" in response.guardrails
    assert "no_species_db_writes" in response.guardrails
    assert "no_feedstock_db_writes" in response.guardrails

    readiness_after = await get_external_source_schema_readiness(db_session)
    assert readiness_after.phase4a_domain_metadata_ready is True
    assert readiness_after.phase4a_domain_missing_counts == response.phase4a_domain_missing_counts

    cards = await list_review_cards(db_session, tenant_id=test_tenant.id)
    extractions = await list_extraction_records(db_session, tenant_id=test_tenant.id)
    reviewed = await list_reviewed_candidates(db_session, tenant_id=test_tenant.id)
    assert cards.count == 0
    assert extractions.count == 0
    assert reviewed.count == 0


@pytest.mark.asyncio
async def test_fill_phase4a_domain_reviewed_candidates_creates_metadata_only_candidates(
    db_session,
    test_tenant,
    scientist_user,
):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)

    response = await fill_phase4a_domain_reviewed_candidates(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        reviewer="Dr. Phase4A Reviewer",
    )

    assert response.source_count == 24
    assert response.created_reviewed_candidate_count == 24
    assert response.updated_reviewed_candidate_count == 0
    assert response.reviewed_candidate_count == 24
    assert response.candidate_domains == {
        "lca": 6,
        "tea": 6,
        "compliance": 5,
        "model_provider": 4,
        "github_reference": 3,
    }
    assert response.candidate_types == {
        "lca_factor_candidate": 6,
        "tea_factor_candidate": 6,
        "compliance_rule_candidate": 5,
        "model_provider_capability_candidate": 4,
        "github_reference_candidate": 3,
    }
    assert response.runtime_activated_count == 0
    assert response.validated_default_write_enabled_count == 0
    assert response.numeric_value_candidate_count == 0

    listed = await list_reviewed_candidates(db_session, tenant_id=test_tenant.id, limit=30)
    assert listed.count == 24
    assert listed.total_count == 24
    assert listed.candidate_domains == response.candidate_domains
    by_id = {candidate.candidate_id: candidate for candidate in listed.items}
    lca_candidate = by_id["REC-PHASE4A-C-LCA-010"]
    assert lca_candidate.candidate_type == "lca_factor_candidate"
    assert lca_candidate.card_id == "PHASE4A-C-LCA-010"
    assert lca_candidate.source_id == "C-LCA-010"
    assert lca_candidate.candidate_payload["metadata_only"] is True
    assert lca_candidate.candidate_payload["read_only"] is True
    assert lca_candidate.candidate_payload["numeric_values_included"] is False
    assert lca_candidate.candidate_payload["extracted_numeric_values"] == {}
    assert lca_candidate.runtime_activated is False
    assert lca_candidate.validated_default_write_enabled is False

    cards = await list_review_cards(db_session, tenant_id=test_tenant.id)
    extractions = await list_extraction_records(db_session, tenant_id=test_tenant.id)
    assert cards.count == 24
    assert extractions.count == 24
    assert {card.review_status for card in cards.items} == {"approved_for_candidate_use"}
    assert all(extraction.numeric_values_included is False for extraction in extractions.items)

    summary = await get_reviewed_candidate_lane_summary(db_session, tenant_id=test_tenant.id)
    assert summary.reviewed_candidate_count == 24
    assert summary.pending_runtime_activation_count == 24
    assert summary.runtime_activated_count == 0
    assert summary.validated_default_write_enabled_count == 0
    assert summary.numeric_value_candidate_count == 0

    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
    active = await get_active_external_candidate_payload(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="lca_factor_candidate",
        candidate_key="lca_factor_candidate:C-LCA-010",
    )
    assert active is None


@pytest.mark.asyncio
async def test_fill_phase4a_domain_reviewed_candidates_is_idempotent(
    db_session,
    test_tenant,
    scientist_user,
):
    first = await fill_phase4a_domain_reviewed_candidates(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
    )
    second = await fill_phase4a_domain_reviewed_candidates(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
    )

    assert first.created_reviewed_candidate_count == 24
    assert second.created_reviewed_candidate_count == 0
    assert second.updated_reviewed_candidate_count == 24
    assert second.reviewed_candidate_count == 24
    listed = await list_reviewed_candidates(db_session, tenant_id=test_tenant.id)
    assert listed.count == 24


@pytest.mark.asyncio
async def test_seed_p0_creates_eight_db_backed_review_cards(db_session, test_tenant):
    response = await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)

    assert response.source_count == 94
    assert response.review_card_count == 8
    assert response.extraction_count == 8
    assert response.reviewed_candidate_count == 0
    assert response.seeded_card_ids == [f"BSF-CARD-{index:03d}" for index in range(1, 9)]

    cards = await list_review_cards(db_session, tenant_id=test_tenant.id)
    assert cards.count == 8
    assert {card.review_status for card in cards.items} == {"pending_review"}
    assert {card.human_review_required for card in cards.items} == {True}
    assert {card.runtime_activated for card in cards.items} == {False}
    assert {card.validated_default_write_enabled for card in cards.items} == {False}

    extractions = await list_extraction_records(db_session, tenant_id=test_tenant.id)
    assert extractions.count == 8
    assert {item.numeric_values_included for item in extractions.items} == {False}
    assert {bool(item.extracted_numeric_values) for item in extractions.items} == {False}

    first_extraction = await get_extraction_record(db_session, tenant_id=test_tenant.id, extraction_id="EXT-BSF-CARD-001")
    assert first_extraction is not None
    assert first_extraction.card_id == "BSF-CARD-001"

    source_summary = await get_source_procurement_summary(db_session)
    assert source_summary.schema_version == "external_source_procurement_summary_v1"
    assert source_summary.source_count == 94
    assert source_summary.source_kind_counts["peer_reviewed_literature"] >= 8
    assert (
        source_summary.metadata_only_count
        + source_summary.manual_review_first_count
        + source_summary.other_ingestion_mode_count
    ) == 94
    assert source_summary.review_required_count >= 8
    assert "source_procurement_summary_is_read_only" in source_summary.guardrails

    readiness = await get_external_source_schema_readiness(db_session)
    assert readiness.knowledge_coverage_ready is True
    assert readiness.knowledge_coverage_percent == 100
    assert readiness.source_metadata_coverage_percent == 100
    assert readiness.business_knowledge_coverage_percent < readiness.source_metadata_coverage_percent
    assert readiness.business_knowledge_coverage_percent == 84.17
    business_groups = {group.group_key: group for group in readiness.business_knowledge_coverage_groups}
    assert business_groups["bioexecutor_species"].coverage_percent == 100
    assert business_groups["feedstock_substrates"].coverage_percent == 93.75
    assert business_groups["product_agronomy_outputs"].status == "partial"
    product_items = {
        item.item_key: item
        for item in business_groups["product_agronomy_outputs"].items
    }
    assert business_groups["product_agronomy_outputs"].coverage_percent == 70
    assert product_items["germination_rate"].status == "candidate_read_model"
    assert product_items["germination_rate"].coverage_basis == "candidate_read_model"
    assert product_items["germination_rate"].numeric_values_included is False
    assert product_items["germination_rate"].review_workflow is not None
    assert product_items["germination_rate"].review_workflow.review_packet_id == "AGR-GERMINATION-RATE-REVIEW-PACKET"
    assert product_items["germination_rate"].review_workflow.review_state == "pending_review"
    assert product_items["germination_rate"].review_workflow.source_packet_persistence == "read_model_only"
    assert product_items["germination_rate"].review_workflow.reviewer_notes_required is True
    assert product_items["germination_rate"].review_workflow.release_evidence_allowed is False
    assert product_items["germination_rate"].review_workflow.runtime_activation_enabled is False
    assert product_items["germination_rate"].review_workflow.validated_default_write_enabled is False
    assert product_items["germination_rate"].review_workflow.numeric_values_allowed is False
    assert product_items["germination_index"].status == "candidate_read_model"
    assert product_items["germination_index"].coverage_basis == "candidate_read_model"
    assert product_items["germination_index"].runtime_activation_enabled is False
    assert product_items["germination_index"].review_workflow is not None
    assert product_items["germination_index"].review_workflow.review_packet_id == "AGR-GERMINATION-INDEX-REVIEW-PACKET"
    assert product_items["phytotoxicity"].status == "candidate_read_model"
    assert product_items["phytotoxicity"].validated_default_write_enabled is False
    assert product_items["phytotoxicity"].review_workflow is not None
    assert product_items["phytotoxicity"].review_workflow.review_packet_id == "AGR-PHYTOTOXICITY-REVIEW-PACKET"
    packet_export = await get_business_knowledge_review_packet_export(
        db_session,
        tenant_id=test_tenant.id,
        item_key="germination_index",
    )
    assert packet_export is not None
    assert packet_export.schema_version == "business_knowledge_review_packet_export_v1"
    assert packet_export.export_filename == "AGR-GERMINATION-INDEX-REVIEW-PACKET.json"
    assert len(packet_export.content_hash) == 64
    assert packet_export.export_manifest["item_key"] == "germination_index"
    assert packet_export.export_manifest["group_key"] == "product_agronomy_outputs"
    assert packet_export.export_manifest["export_policy"] == "response_only_no_file_write"
    assert packet_export.review_packet.item.item_key == "germination_index"
    assert packet_export.review_packet.review_workflow.review_state == "pending_review"
    assert packet_export.review_packet.source_trace["release_evidence_allowed"] is False
    assert packet_export.review_packet.source_trace["numeric_values_included"] is False
    assert packet_export.review_packet.candidate_payload["value"] is None
    assert packet_export.side_effects == {
        "file_written": False,
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "numeric_value_extraction": False,
        "final_action_execution": False,
    }
    assert "export_response_only_no_file_write" in packet_export.guardrails
    assert await get_business_knowledge_review_packet_export(
        db_session,
        tenant_id=test_tenant.id,
        item_key="organic_fertilizer_assay_metadata",
    ) is None
    assert {domain.domain_key for domain in readiness.knowledge_coverage_domains} == {
        "bsf_metadata",
        "feedstock_metadata",
        "lca",
        "tea",
        "compliance",
        "model_provider",
        "github_reference",
    }
    assert {domain.status for domain in readiness.knowledge_coverage_domains} == {"covered"}
    assert {domain.runtime_activation_enabled for domain in readiness.knowledge_coverage_domains} == {False}
    assert {domain.validated_default_write_enabled for domain in readiness.knowledge_coverage_domains} == {False}

    feedstock_datasets = await list_feedstock_dataset_candidates(db_session)
    assert feedstock_datasets.count >= 9
    assert all(item.candidate_type == "feedstock_dataset_candidate" for item in feedstock_datasets.items)
    assert all(item.review_status == "pending_review" for item in feedstock_datasets.items)
    assert {item.numeric_values_included for item in feedstock_datasets.items} == {False}
    assert {item.runtime_activated for item in feedstock_datasets.items} == {False}
    assert {item.validated_default_write_enabled for item in feedstock_datasets.items} == {False}
    assert any("USDA" in item.source_name for item in feedstock_datasets.items)
    assert "no_feedstock_db_writes" in feedstock_datasets.guardrails


@pytest.mark.asyncio
async def test_resolve_without_license_boundary_fails(db_session, test_tenant, scientist_user):
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest.model_construct(
        review_status="approved_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="pending_review",
        boundary_condition="",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence",
        candidate_type="bsf_reviewed_metadata_candidate",
        candidate_key=None,
        candidate_payload={},
        extracted_metadata={},
        extracted_numeric_values={},
        numeric_values_included=False,
        human_review_required=True,
        promotion_enabled=False,
        runtime_activated=False,
        validated_default_write_enabled=False,
        next_action="Persist reviewed candidate.",
    )

    with pytest.raises(ValueError):
        await resolve_review_card(
            db_session,
            tenant_id=test_tenant.id,
            reviewer_user_id=scientist_user.id,
            card_id="BSF-CARD-001",
            payload=payload,
        )


@pytest.mark.parametrize(
    "review_action,expected_status,license_status,card_id",
    [
        ("approve_metadata", "extracted_metadata", "metadata_only", "BSF-CARD-001"),
        ("request_license_clearance", "needs_license_clearance", "restricted", "BSF-CARD-002"),
        ("reject", "rejected", "blocked", "BSF-CARD-003"),
    ],
)
@pytest.mark.asyncio
async def test_non_candidate_review_actions_do_not_create_reviewed_candidates(
    db_session,
    test_tenant,
    scientist_user,
    review_action,
    expected_status,
    license_status,
    card_id,
):
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        review_action=review_action,
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status=license_status,
        boundary_condition="Reviewed metadata boundary only.",
        allowed_use="review workflow metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        next_action="Review action persisted without candidate creation.",
    )

    resolved = await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id=card_id,
        payload=payload,
    )

    assert resolved is not None
    assert resolved.review_card.review_action == review_action
    assert resolved.review_card.review_status == expected_status
    assert resolved.reviewed_candidate is None
    assert resolved.created_reviewed_candidate is False

    listed = await list_reviewed_candidates(db_session, tenant_id=test_tenant.id)
    assert listed.count == 0


@pytest.mark.asyncio
async def test_approved_review_creates_non_runtime_candidate(db_session, test_tenant, scientist_user):
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Use citation and source boundary metadata only; no copied paywalled numeric tables.",
        allowed_use="reviewed candidate metadata for later activation review",
        blocked_use="no validated defaults; no release evidence; no compliance threshold",
        candidate_payload={"review_scope": "metadata_only_bsf_foundation"},
    )

    resolved = await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-001",
        payload=payload,
    )

    assert resolved is not None
    assert resolved.review_card.review_status == "approved_for_candidate_use"
    assert resolved.reviewed_candidate is not None
    assert resolved.reviewed_candidate.runtime_activated is False
    assert resolved.reviewed_candidate.promotion_enabled is False
    assert resolved.reviewed_candidate.validated_default_write_enabled is False
    assert resolved.reviewed_candidate.candidate_payload["payload_version"] == "bsf-reviewed-metadata-v1"
    assert resolved.reviewed_candidate.candidate_payload["candidate_family"] == "bsf_reviewed_metadata"
    assert resolved.reviewed_candidate.candidate_payload["article_type"] == "review"
    assert resolved.reviewed_candidate.candidate_payload["numeric_values_included"] is False
    assert resolved.reviewed_candidate.candidate_payload["runtime_activation_required_before_use"] is True
    assert resolved.reviewed_candidate.candidate_payload["reviewer_annotations"]["review_scope"] == "metadata_only_bsf_foundation"

    listed = await list_reviewed_candidates(db_session, tenant_id=test_tenant.id)
    assert listed.count == 1
    assert listed.total_count == 1
    assert listed.offset == 0
    assert listed.limit is None
    assert listed.has_more is False
    assert listed.items[0].candidate_id == "REC-BSF-CARD-001"

    filtered = await list_reviewed_candidates(
        db_session,
        tenant_id=test_tenant.id,
        candidate_domain="bsf_metadata",
    )
    assert filtered.count == 1
    assert filtered.total_count == 1
    assert filtered.candidate_domains == {"bsf_metadata": 1}

    paged = await list_reviewed_candidates(
        db_session,
        tenant_id=test_tenant.id,
        limit=1,
        offset=0,
    )
    assert paged.count == 1
    assert paged.total_count == 1
    assert paged.limit == 1
    assert paged.has_more is False

    summary = await get_reviewed_candidate_lane_summary(db_session, tenant_id=test_tenant.id)
    assert summary.schema_version == "reviewed_external_candidate_lane_summary_v1"
    assert summary.reviewed_candidate_count == 1
    assert summary.reviewed_metadata_candidate_count == 1
    assert summary.pending_runtime_activation_count == 1
    assert summary.runtime_activated_count == 0
    assert summary.validated_default_write_enabled_count == 0
    assert summary.numeric_value_candidate_count == 0
    assert summary.release_evidence_blocked_count == 1
    assert summary.statuses == {"approved_for_candidate_use": 1}
    assert summary.candidate_types == {"bsf_reviewed_metadata_candidate": 1}
    assert summary.candidate_domains == {"bsf_metadata": 1}
    assert "summary_is_read_only" in summary.guardrails

    filtered_summary = await get_reviewed_candidate_lane_summary(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="bsf_reviewed_metadata_candidate",
        review_status="approved_for_candidate_use",
    )
    assert filtered_summary.reviewed_candidate_count == 1
    assert filtered_summary.candidate_types == {"bsf_reviewed_metadata_candidate": 1}


@pytest.mark.asyncio
async def test_bsf_reviewed_metadata_lane_rejects_numeric_values(db_session, test_tenant, scientist_user):
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest.model_construct(
        review_status="approved_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for candidate queue.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence",
        candidate_type="bsf_reviewed_metadata_candidate",
        candidate_key=None,
        candidate_payload={},
        extracted_metadata={},
        extracted_numeric_values={"conversion_rate": 0.5},
        numeric_values_included=True,
        human_review_required=True,
        promotion_enabled=False,
        runtime_activated=False,
        validated_default_write_enabled=False,
        next_action="Persist reviewed candidate.",
    )

    with pytest.raises(ValueError, match="reviewed candidate resolutions cannot include numeric values"):
        await resolve_review_card(
            db_session,
            tenant_id=test_tenant.id,
            reviewer_user_id=scientist_user.id,
            card_id="BSF-CARD-003",
            payload=payload,
        )


@pytest.mark.asyncio
async def test_reviewed_candidate_does_not_mutate_defaults_or_runtime(db_session, test_tenant, scientist_user):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for candidate queue.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
    )

    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-002",
        payload=payload,
    )

    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
    active = await get_active_external_candidate_payload(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="bsf_reviewed_metadata_candidate",
        candidate_key="bsf_reviewed_metadata_candidate:BSF-CARD-002",
    )
    assert active is None


@pytest.mark.asyncio
async def test_review_packet_is_read_only_and_does_not_activate_runtime(db_session, test_tenant, scientist_user):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for review packet.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
    )

    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-004",
        payload=payload,
    )

    packet = await get_reviewed_candidate_review_packet(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-004",
    )

    assert packet is not None
    assert packet.candidate.candidate_id == "REC-BSF-CARD-004"
    assert packet.review_card.card_id == "BSF-CARD-004"
    assert packet.extraction is not None
    assert packet.extraction.numeric_values_included is False
    assert packet.side_effects == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
    active = await get_active_external_candidate_payload(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="bsf_reviewed_metadata_candidate",
        candidate_key="bsf_reviewed_metadata_candidate:BSF-CARD-004",
    )
    assert active is None


@pytest.mark.asyncio
async def test_review_packet_export_is_response_only(db_session, test_tenant, scientist_user):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for export packet.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
    )

    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-005",
        payload=payload,
    )

    exported = await get_reviewed_candidate_review_packet_export(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-005",
    )

    assert exported is not None
    assert exported.export_format == "json"
    assert exported.export_filename == "REC-BSF-CARD-005-review-packet.json"
    assert len(exported.content_hash) == 64
    assert exported.export_manifest["export_policy"] == "response_only_no_file_write"
    assert exported.review_packet.candidate.candidate_id == "REC-BSF-CARD-005"
    assert exported.side_effects == {
        "file_written": False,
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
    active = await get_active_external_candidate_payload(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="bsf_reviewed_metadata_candidate",
        candidate_key="bsf_reviewed_metadata_candidate:BSF-CARD-005",
    )
    assert active is None


@pytest.mark.asyncio
async def test_activation_preview_is_audit_gated_and_does_not_activate_runtime(db_session, test_tenant, scientist_user):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        review_action="approve_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for activation preview.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        candidate_type="lca_factor_candidate",
    )
    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-006",
        payload=payload,
    )

    preview = await get_reviewed_candidate_activation_preview(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-006",
    )

    assert preview is not None
    assert preview.schema_version == "reviewed_external_candidate_activation_preview_v1"
    assert preview.candidate.candidate_id == "REC-BSF-CARD-006"
    assert preview.candidate.candidate_domain == "lca"
    assert preview.activation_scope["tenant_scoped"] is True
    assert preview.activation_scope["candidate_type"] == "lca_factor_candidate"
    assert preview.activation_audit_contract["activation_audit_id_required"] is True
    assert preview.activation_audit_contract["activation_execution_endpoint_enabled"] is False
    assert preview.activation_audit_contract["release_evidence_allowed"] is False
    assert preview.can_execute_activation is False
    assert preview.runtime_overlay_preview_only is True
    assert preview.rollback_required is True
    assert preview.active_overlay_state["activation_required_before_runtime_use"] is True
    assert preview.side_effects == {
        "runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
    active = await get_active_external_candidate_payload(
        db_session,
        tenant_id=test_tenant.id,
        candidate_type="lca_factor_candidate",
        candidate_key="lca_factor_candidate:BSF-CARD-006",
    )
    assert active is None


@pytest.mark.asyncio
async def test_runtime_readiness_is_tenant_scoped_read_only_and_rollback_required(
    db_session,
    test_tenant,
    scientist_user,
):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        review_action="approve_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for runtime read path.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        candidate_type="lca_factor_candidate",
    )
    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-007",
        payload=payload,
    )

    readiness = await get_reviewed_candidate_runtime_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-007",
    )

    assert readiness is not None
    assert readiness.schema_version == "reviewed_external_candidate_runtime_readiness_v1"
    assert readiness.candidate.candidate_id == "REC-BSF-CARD-007"
    assert readiness.candidate.runtime_activated is False
    assert readiness.activation_scope["tenant_id"] == test_tenant.id
    assert readiness.activation_scope["tenant_scoped"] is True
    assert readiness.activation_scope["candidate_type"] == "lca_factor_candidate"
    assert readiness.activation_scope["runtime_paths"] == ["lca.factor_runtime"]
    assert readiness.active_overlay_state["activation_required_before_runtime_use"] is True
    assert readiness.active_candidate_payload is None
    assert readiness.can_read_runtime_payload is False
    assert readiness.runtime_read_path_enabled is True
    assert readiness.rollback_required is True
    assert readiness.rollback_contract["rollback_execution_endpoint_enabled"] is False
    assert readiness.rollback_contract["rollback_target_required"] is False
    assert readiness.side_effects == {
        "runtime_activation": False,
        "runtime_rollback": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "runtime_readiness_is_read_only" in readiness.guardrails
    assert "approval_is_not_runtime_activation" in readiness.guardrails
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before


@pytest.mark.asyncio
async def test_rollback_preview_is_read_only_and_requires_separate_audit_execution(
    db_session,
    test_tenant,
    scientist_user,
):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        review_action="approve_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for rollback preview.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        candidate_type="tea_factor_candidate",
    )
    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-008",
        payload=payload,
    )

    preview = await get_reviewed_candidate_rollback_preview(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-008",
    )

    assert preview is not None
    assert preview.schema_version == "reviewed_external_candidate_rollback_preview_v1"
    assert preview.candidate.candidate_id == "REC-BSF-CARD-008"
    assert preview.candidate.candidate_type == "tea_factor_candidate"
    assert preview.activation_scope["tenant_id"] == test_tenant.id
    assert preview.activation_scope["tenant_scoped"] is True
    assert preview.rollback_target_available is False
    assert preview.can_execute_rollback is False
    assert preview.rollback_preview_only is True
    assert preview.rollback_required is True
    assert preview.rollback_blockers == ["no_active_runtime_activation_to_rollback"]
    assert preview.rollback_contract["rollback_execution_endpoint_enabled"] is False
    assert preview.rollback_audit_packet["rollback_execution_endpoint_enabled"] is False
    assert preview.rollback_audit_packet["rollback_target_available"] is False
    assert preview.rollback_audit_packet["blocked_until"] == ["no_active_runtime_activation_to_rollback"]
    assert "operator_attestation" in preview.rollback_audit_packet["required_attestations"]
    assert preview.side_effects == {
        "runtime_activation": False,
        "runtime_rollback": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "final_action_execution": False,
    }
    assert "rollback_preview_is_read_only" in preview.guardrails
    assert "rollback_requires_separate_audit_execution" in preview.guardrails
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before


@pytest.mark.asyncio
async def test_runtime_readiness_reads_existing_audited_activation_without_mutating_defaults(
    db_session,
    test_tenant,
    scientist_user,
):
    species_keys_before = set(SPECIES_DB)
    feedstock_keys_before = set(FEEDSTOCK_DB)
    await seed_p0_external_sources(db_session, tenant_id=test_tenant.id)
    payload = ExternalSourceReviewCardResolveRequest(
        review_action="approve_for_candidate_use",
        reviewer="Dr. Reviewer",
        reviewed_at=datetime.now(UTC),
        license_status="metadata_only",
        boundary_condition="Metadata-only source boundary reviewed for existing activation read path.",
        allowed_use="candidate metadata only",
        blocked_use="no validated defaults; no release evidence; no runtime activation",
        candidate_type="model_provider_capability_candidate",
    )
    await resolve_review_card(
        db_session,
        tenant_id=test_tenant.id,
        reviewer_user_id=scientist_user.id,
        card_id="BSF-CARD-001",
        payload=payload,
    )

    candidate_key = "model_provider_capability_candidate:BSF-CARD-001"
    scope_key = activation_scope_key(
        tenant_id=test_tenant.id,
        candidate_type="model_provider_capability_candidate",
        candidate_key=candidate_key,
    )
    db_session.add_all(
        [
            KnowledgeRelationRecord(
                relation_id="REG-PATCH-READONLY-001",
                tenant_id=test_tenant.id,
                subject_type="reviewed_external_candidate",
                subject_id="REC-BSF-CARD-001",
                predicate="manual_registry_patch_applied",
                object_type="validated_external_knowledge_registry",
                object_id="registry:model-provider-capability:BSF-CARD-001",
                payload={
                    "candidate_type": "model_provider_capability_candidate",
                    "candidate_key": candidate_key,
                    "registry_version": "readonly-v1",
                    "candidate": {
                        "candidate_key": candidate_key,
                        "metadata_only": True,
                        "source_kind": "reviewed_external_candidate",
                        "source_ref": "REC-BSF-CARD-001",
                    },
                },
            ),
            KnowledgeRelationRecord(
                relation_id="RUNTIME-ACTIVATION-READONLY-001",
                tenant_id=test_tenant.id,
                subject_type="validated_external_knowledge_registry",
                subject_id="REG-PATCH-READONLY-001",
                predicate=ACTIVATION_EXECUTED_PREDICATE,
                object_type="active_external_knowledge_runtime_scope",
                object_id=scope_key,
                payload={
                    "registry_version": "readonly-v1",
                    "activation_audit_id": "AUDIT-READONLY-001",
                },
            ),
        ]
    )
    await db_session.commit()

    readiness = await get_reviewed_candidate_runtime_readiness(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-001",
    )
    rollback_preview = await get_reviewed_candidate_rollback_preview(
        db_session,
        tenant_id=test_tenant.id,
        candidate_id="REC-BSF-CARD-001",
    )

    assert readiness is not None
    assert readiness.can_read_runtime_payload is True
    assert readiness.active_candidate_payload is not None
    assert readiness.active_candidate_payload["registry_patch_id"] == "REG-PATCH-READONLY-001"
    assert readiness.active_candidate_payload["activation_id"] == "RUNTIME-ACTIVATION-READONLY-001"
    assert readiness.active_candidate_payload["source_kind"] == "validated_external_registry_activation"
    assert readiness.active_overlay_state["activation_required_before_runtime_use"] is False
    assert readiness.rollback_contract["rollback_target_required"] is True
    assert rollback_preview is not None
    assert rollback_preview.rollback_target_available is True
    assert rollback_preview.rollback_blockers == []
    assert rollback_preview.can_execute_rollback is False
    assert rollback_preview.rollback_audit_packet["active_activation_id"] == "RUNTIME-ACTIVATION-READONLY-001"
    assert rollback_preview.rollback_audit_packet["rollback_execution_endpoint_enabled"] is False
    assert set(SPECIES_DB) == species_keys_before
    assert set(FEEDSTOCK_DB) == feedstock_keys_before
