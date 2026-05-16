"""Review-gated external source candidate routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_any_role, require_minimum_role, resolve_user_roles
from app.models import User
from app.schemas.external_source_review import (
    BusinessKnowledgeReviewPacketExportResponse,
    ExternalSourceCatalogResponse,
    ExternalSourceRead,
    ExternalSourceExtractionListResponse,
    ExternalSourceExtractionRead,
    ExternalSourcePhase4ADomainSeedResponse,
    ExternalSourcePhase4AReviewedCandidateFillResponse,
    ExternalSourceP0SeedResponse,
    ExternalSourceProcurementSummary,
    ExternalSourceReviewCardListResponse,
    ExternalSourceReviewCardRead,
    ExternalSourceReviewCardResolveRequest,
    ExternalSourceReviewCardResolveResponse,
    ExternalSourceSchemaReadinessResponse,
    FeedstockDatasetCandidateListResponse,
    LiteratureExtractionCandidateListResponse,
    LiteratureExtractionCandidateReviewPacketBulkExportResponse,
    LiteratureExtractionCandidateReviewPacketExportResponse,
    LiteratureExtractionCandidateSeedResponse,
    LiteratureExtractionEvidenceChainReadinessResponse,
    LiteratureExtractionReviewDraftCreateRequest,
    LiteratureExtractionReviewDraftComparisonResponse,
    LiteratureExtractionReviewDraftListResponse,
    LiteratureExtractionReviewDraftResponse,
    LiteratureValueOverlayCreateRequest,
    LiteratureValueOverlayResponse,
    LiteratureValuePromotionAuditExportResponse,
    LiteratureValuePromotionApprovalCreateRequest,
    LiteratureValuePromotionApprovalResponse,
    LiteratureValuePromotionLifecycleResponse,
    LiteratureValuePromotionReadinessResponse,
    LiteratureValuePromotionRejectRequest,
    LiteratureValuePromotionRequestCreateRequest,
    LiteratureValuePromotionRequestResponse,
    LiteratureValueReleaseEvidenceLinkCreateRequest,
    LiteratureValueReleaseEvidenceLinkResponse,
    LiteratureValueRollbackCreateRequest,
    LiteratureValueRollbackResponse,
    LiteratureValueRuntimeActivationCreateRequest,
    LiteratureValueRuntimeActivationDeactivateRequest,
    LiteratureValueRuntimeActivationPreviewResponse,
    LiteratureValueRuntimeActivationResponse,
    ReviewedExternalCandidateActivationPreviewResponse,
    ReviewedExternalCandidateKnowledgeBaseResponse,
    ReviewedExternalCandidateLaneSummary,
    ReviewedExternalCandidateListResponse,
    ReviewedExternalCandidateRead,
    ReviewedExternalCandidateRollbackPreviewResponse,
    ReviewedExternalCandidateRuntimeReadinessResponse,
    ReviewedExternalCandidateReviewPacketExportResponse,
    ReviewedExternalCandidateReviewPacketResponse,
)
from app.services.reviewed_external_candidate_service import (
    fill_phase4a_domain_reviewed_candidates,
    get_business_knowledge_review_packet_export,
    create_literature_extraction_review_draft,
    get_extraction_record,
    get_literature_extraction_candidate_review_packet_bulk_export,
    get_literature_extraction_candidate_review_packet_export,
    get_literature_extraction_evidence_chain_readiness,
    get_literature_extraction_review_draft_comparison,
    get_literature_value_promotion_audit_export,
    get_literature_value_promotion_lifecycle,
    get_literature_value_promotion_readiness,
    create_literature_value_promotion_approval,
    create_literature_value_promotion_request,
    create_literature_value_release_evidence_link,
    reject_literature_value_promotion_request,
    create_literature_value_runtime_activation,
    deactivate_literature_value_runtime_activation,
    get_literature_value_runtime_activation_preview,
    rollback_literature_value_runtime_activation,
    get_review_card,
    get_reviewed_candidate_knowledge_base,
    get_reviewed_candidate_activation_preview,
    get_reviewed_candidate_lane_summary,
    get_reviewed_candidate,
    get_reviewed_candidate_rollback_preview,
    get_reviewed_candidate_runtime_readiness,
    get_reviewed_candidate_review_packet_export,
    get_reviewed_candidate_review_packet,
    get_external_source_schema_readiness,
    get_source_procurement_summary,
    get_source_record,
    list_feedstock_dataset_candidates,
    list_literature_extraction_candidates,
    list_literature_extraction_review_drafts,
    list_extraction_records,
    list_review_cards,
    list_reviewed_candidates,
    list_source_catalog,
    promote_literature_value_request_to_overlay,
    resolve_review_card,
    seed_literature_extraction_candidates,
    seed_phase4a_domain_metadata_sources,
    seed_p0_external_sources,
)

router = APIRouter()


@router.get("/catalog", response_model=ExternalSourceCatalogResponse)
async def get_external_source_catalog(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    del current_user
    return await list_source_catalog(db)


@router.get("/catalog/summary", response_model=ExternalSourceProcurementSummary)
async def get_external_source_catalog_summary(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    del current_user
    return await get_source_procurement_summary(db)


@router.get("/schema-readiness", response_model=ExternalSourceSchemaReadinessResponse)
async def get_external_source_schema_readiness_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    del current_user
    return await get_external_source_schema_readiness(db)


@router.get("/feedstock-dataset-candidates", response_model=FeedstockDatasetCandidateListResponse)
async def list_external_source_feedstock_dataset_candidates(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    del current_user
    return await list_feedstock_dataset_candidates(db)


@router.get("/literature-extraction-candidates", response_model=LiteratureExtractionCandidateListResponse)
async def list_external_source_literature_extraction_candidates(
    metric_key: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await list_literature_extraction_candidates(db, tenant_id=current_user.tenant_id, metric_key=metric_key)


@router.post(
    "/literature-extraction-candidates/seed",
    response_model=LiteratureExtractionCandidateSeedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def seed_external_source_literature_extraction_candidates(
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    return await seed_literature_extraction_candidates(db, tenant_id=current_user.tenant_id)


@router.get(
    "/literature-extraction-candidates/review-packets/export",
    response_model=LiteratureExtractionCandidateReviewPacketBulkExportResponse,
)
async def export_external_source_literature_extraction_candidate_review_packets(
    metric_key: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_literature_extraction_candidate_review_packet_bulk_export(
        db,
        tenant_id=current_user.tenant_id,
        metric_key=metric_key,
    )


@router.get(
    "/literature-extraction-candidates/evidence-chain/readiness",
    response_model=LiteratureExtractionEvidenceChainReadinessResponse,
)
async def get_external_source_literature_extraction_evidence_chain_readiness(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_literature_extraction_evidence_chain_readiness(
        db,
        tenant_id=current_user.tenant_id,
    )


@router.get(
    "/literature-extraction-candidates/review-drafts",
    response_model=LiteratureExtractionReviewDraftListResponse,
)
async def list_external_source_literature_extraction_candidate_review_drafts(
    candidate_id: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await list_literature_extraction_review_drafts(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
        limit=limit,
    )


@router.post(
    "/literature-extraction-candidates/{candidate_id}/review-drafts",
    response_model=LiteratureExtractionReviewDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_source_literature_extraction_candidate_review_draft(
    candidate_id: str,
    payload: LiteratureExtractionReviewDraftCreateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        draft = await create_literature_extraction_review_draft(
            db,
            tenant_id=current_user.tenant_id,
            candidate_id=candidate_id,
            reviewer_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_extraction_review_draft_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature extraction candidate review packet not found")
    return draft


@router.get(
    "/literature-extraction-candidates/{candidate_id}/review-drafts/comparison",
    response_model=LiteratureExtractionReviewDraftComparisonResponse,
)
async def compare_external_source_literature_extraction_candidate_review_drafts(
    candidate_id: str,
    review_draft_id: str | None = Query(default=None),
    changed_field: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    comparison = await get_literature_extraction_review_draft_comparison(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
        review_draft_id=review_draft_id,
        changed_field=changed_field,
    )
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature extraction review draft comparison not found")
    return comparison


@router.get(
    "/literature-extraction-candidates/{candidate_id}/promotion-readiness",
    response_model=LiteratureValuePromotionReadinessResponse,
)
async def get_external_source_literature_value_promotion_readiness(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    readiness = await get_literature_value_promotion_readiness(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if readiness is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion readiness not found")
    return readiness


@router.get(
    "/literature-extraction-candidates/{candidate_id}/promotion-lifecycle",
    response_model=LiteratureValuePromotionLifecycleResponse,
)
async def get_external_source_literature_value_promotion_lifecycle(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    lifecycle = await get_literature_value_promotion_lifecycle(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if lifecycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion lifecycle not found")
    return lifecycle


@router.get(
    "/literature-extraction-candidates/{candidate_id}/promotion-audit/export",
    response_model=LiteratureValuePromotionAuditExportResponse,
)
async def export_external_source_literature_value_promotion_audit(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    exported = await get_literature_value_promotion_audit_export(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion audit export not found")
    return exported


@router.post(
    "/literature-extraction-candidates/{candidate_id}/promotion-requests",
    response_model=LiteratureValuePromotionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_source_literature_value_promotion_request(
    candidate_id: str,
    payload: LiteratureValuePromotionRequestCreateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        promotion_request = await create_literature_value_promotion_request(
            db,
            tenant_id=current_user.tenant_id,
            candidate_id=candidate_id,
            requested_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_promotion_request_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if promotion_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion readiness not found")
    return promotion_request


@router.post(
    "/promotion-requests/{promotion_request_id}/approvals",
    response_model=LiteratureValuePromotionApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_source_literature_value_promotion_approval(
    promotion_request_id: str,
    payload: LiteratureValuePromotionApprovalCreateRequest,
    current_user: User = Depends(require_any_role("scientist", "release_manager", "compliance_admin")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        current_user_roles = await resolve_user_roles(db, current_user)
        approval = await create_literature_value_promotion_approval(
            db,
            tenant_id=current_user.tenant_id,
            promotion_request_id=promotion_request_id,
            approved_by_user_id=current_user.id,
            approved_by_user_roles=current_user_roles,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_promotion_approval_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion request not found")
    return approval


@router.post(
    "/promotion-requests/{promotion_request_id}/reject",
    response_model=LiteratureValuePromotionApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reject_external_source_literature_value_promotion_request(
    promotion_request_id: str,
    payload: LiteratureValuePromotionRejectRequest,
    current_user: User = Depends(require_any_role("scientist", "release_manager", "compliance_admin")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        current_user_roles = await resolve_user_roles(db, current_user)
        rejection = await reject_literature_value_promotion_request(
            db,
            tenant_id=current_user.tenant_id,
            promotion_request_id=promotion_request_id,
            rejected_by_user_id=current_user.id,
            rejected_by_user_roles=current_user_roles,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_promotion_approval_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail in {
            "literature_value_promotion_approver_role_required",
            "literature_value_promotion_requester_cannot_approve",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if rejection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion request not found")
    return rejection


@router.post(
    "/promotion-requests/{promotion_request_id}/promote-overlay",
    response_model=LiteratureValueOverlayResponse,
    status_code=status.HTTP_201_CREATED,
)
async def promote_external_source_literature_value_request_to_overlay(
    promotion_request_id: str,
    payload: LiteratureValueOverlayCreateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        overlay = await promote_literature_value_request_to_overlay(
            db,
            tenant_id=current_user.tenant_id,
            promotion_request_id=promotion_request_id,
            created_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_overlay_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if overlay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value promotion request not found")
    return overlay


@router.get(
    "/overlays/{overlay_id}/activation-preview",
    response_model=LiteratureValueRuntimeActivationPreviewResponse,
)
async def get_external_source_literature_value_runtime_activation_preview(
    overlay_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    preview = await get_literature_value_runtime_activation_preview(
        db,
        tenant_id=current_user.tenant_id,
        overlay_id=overlay_id,
    )
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value overlay not found")
    return preview


@router.post(
    "/overlays/{overlay_id}/runtime-activations",
    response_model=LiteratureValueRuntimeActivationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_source_literature_value_runtime_activation(
    overlay_id: str,
    payload: LiteratureValueRuntimeActivationCreateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        activation = await create_literature_value_runtime_activation(
            db,
            tenant_id=current_user.tenant_id,
            overlay_id=overlay_id,
            activated_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_runtime_activation_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if activation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value overlay not found")
    return activation


@router.post(
    "/runtime-activations/{activation_id}/deactivate",
    response_model=LiteratureValueRuntimeActivationResponse,
)
async def deactivate_external_source_literature_value_runtime_activation(
    activation_id: str,
    payload: LiteratureValueRuntimeActivationDeactivateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        activation = await deactivate_literature_value_runtime_activation(
            db,
            tenant_id=current_user.tenant_id,
            activation_id=activation_id,
            deactivated_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if activation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value runtime activation not found")
    return activation


@router.post(
    "/runtime-activations/{activation_id}/rollback",
    response_model=LiteratureValueRollbackResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rollback_external_source_literature_value_runtime_activation(
    activation_id: str,
    payload: LiteratureValueRollbackCreateRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        rollback = await rollback_literature_value_runtime_activation(
            db,
            tenant_id=current_user.tenant_id,
            activation_id=activation_id,
            rolled_back_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_rollback_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if rollback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature value runtime activation not found")
    return rollback


@router.post(
    "/release-decisions/{release_decision_id}/literature-value-release-evidence-links",
    response_model=LiteratureValueReleaseEvidenceLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_source_literature_value_release_evidence_link(
    release_decision_id: int,
    payload: LiteratureValueReleaseEvidenceLinkCreateRequest,
    current_user: User = Depends(require_any_role("release_manager", "compliance_admin")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        link = await create_literature_value_release_evidence_link(
            db,
            tenant_id=current_user.tenant_id,
            release_decision_id=release_decision_id,
            linked_by_user_id=current_user.id,
            request=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "literature_value_release_evidence_link_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail in {
            "literature_value_runtime_activation_not_found",
            "literature_value_overlay_not_found",
        }:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision not found")
    return link


@router.get(
    "/literature-extraction-candidates/{candidate_id}/review-packet/export",
    response_model=LiteratureExtractionCandidateReviewPacketExportResponse,
)
async def export_external_source_literature_extraction_candidate_review_packet(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    exported = await get_literature_extraction_candidate_review_packet_export(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Literature extraction candidate review packet not found")
    return exported


@router.get("/catalog/{source_id}", response_model=ExternalSourceRead)
async def get_external_source_catalog_item(
    source_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    del current_user
    source = await get_source_record(db, source_id=source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External source not found")
    return source


@router.post("/p0/seed", response_model=ExternalSourceP0SeedResponse, status_code=status.HTTP_201_CREATED)
async def seed_p0_external_source_review_cards(
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    return await seed_p0_external_sources(db, tenant_id=current_user.tenant_id)


@router.post(
    "/phase4a/domain-metadata/seed",
    response_model=ExternalSourcePhase4ADomainSeedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def seed_phase4a_external_source_domain_metadata(
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    return await seed_phase4a_domain_metadata_sources(db, tenant_id=current_user.tenant_id)


@router.post(
    "/phase4a/reviewed-candidates/fill",
    response_model=ExternalSourcePhase4AReviewedCandidateFillResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fill_phase4a_external_source_reviewed_candidates(
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    return await fill_phase4a_domain_reviewed_candidates(
        db,
        tenant_id=current_user.tenant_id,
        reviewer_user_id=current_user.id,
        reviewer=current_user.full_name or current_user.username,
    )


@router.get("/review-cards", response_model=ExternalSourceReviewCardListResponse)
async def list_external_source_review_cards(
    review_status: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await list_review_cards(db, tenant_id=current_user.tenant_id, review_status=review_status)


@router.get("/review-cards/{card_id}", response_model=ExternalSourceReviewCardRead)
async def get_external_source_review_card(
    card_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    card = await get_review_card(db, tenant_id=current_user.tenant_id, card_id=card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External source review card not found")
    return card


@router.get("/extractions", response_model=ExternalSourceExtractionListResponse)
async def list_external_source_extractions(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await list_extraction_records(db, tenant_id=current_user.tenant_id)


@router.get("/extractions/{extraction_id}", response_model=ExternalSourceExtractionRead)
async def get_external_source_extraction(
    extraction_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    extraction = await get_extraction_record(db, tenant_id=current_user.tenant_id, extraction_id=extraction_id)
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External source extraction not found")
    return extraction


@router.post("/review-cards/{card_id}/resolve", response_model=ExternalSourceReviewCardResolveResponse)
async def resolve_external_source_review_card(
    card_id: str,
    body: ExternalSourceReviewCardResolveRequest,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        resolved = await resolve_review_card(
            db,
            tenant_id=current_user.tenant_id,
            reviewer_user_id=current_user.id,
            card_id=card_id,
            payload=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External source review card not found")
    return resolved


@router.get("/reviewed-candidates", response_model=ReviewedExternalCandidateListResponse)
async def list_external_source_reviewed_candidates(
    candidate_type: str | None = Query(default=None),
    candidate_domain: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=250),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await list_reviewed_candidates(
            db,
            tenant_id=current_user.tenant_id,
            candidate_type=candidate_type,
            candidate_domain=candidate_domain,
            review_status=review_status,
            offset=offset,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/reviewed-candidates/summary", response_model=ReviewedExternalCandidateLaneSummary)
async def get_external_source_reviewed_candidate_summary(
    candidate_type: str | None = Query(default=None),
    candidate_domain: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        return await get_reviewed_candidate_lane_summary(
            db,
            tenant_id=current_user.tenant_id,
            candidate_type=candidate_type,
            candidate_domain=candidate_domain,
            review_status=review_status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/reviewed-candidates/knowledge-base", response_model=ReviewedExternalCandidateKnowledgeBaseResponse)
async def get_external_source_reviewed_candidate_knowledge_base(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await get_reviewed_candidate_knowledge_base(db, tenant_id=current_user.tenant_id)


@router.get(
    "/business-knowledge/{item_key}/review-packet/export",
    response_model=BusinessKnowledgeReviewPacketExportResponse,
)
async def export_external_source_business_knowledge_review_packet(
    item_key: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    exported = await get_business_knowledge_review_packet_export(
        db,
        tenant_id=current_user.tenant_id,
        item_key=item_key,
    )
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business knowledge review packet not found")
    return exported


@router.get("/reviewed-candidates/{candidate_id}/review-packet", response_model=ReviewedExternalCandidateReviewPacketResponse)
async def get_external_source_reviewed_candidate_review_packet(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    packet = await get_reviewed_candidate_review_packet(db, tenant_id=current_user.tenant_id, candidate_id=candidate_id)
    if packet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate review packet not found")
    return packet


@router.get(
    "/reviewed-candidates/{candidate_id}/review-packet/export",
    response_model=ReviewedExternalCandidateReviewPacketExportResponse,
)
async def export_external_source_reviewed_candidate_review_packet(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    exported = await get_reviewed_candidate_review_packet_export(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate review packet not found")
    return exported


@router.get(
    "/reviewed-candidates/{candidate_id}/activation-preview",
    response_model=ReviewedExternalCandidateActivationPreviewResponse,
)
async def get_external_source_reviewed_candidate_activation_preview(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    preview = await get_reviewed_candidate_activation_preview(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate activation preview not found")
    return preview


@router.get(
    "/reviewed-candidates/{candidate_id}/runtime-readiness",
    response_model=ReviewedExternalCandidateRuntimeReadinessResponse,
)
async def get_external_source_reviewed_candidate_runtime_readiness(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    readiness = await get_reviewed_candidate_runtime_readiness(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if readiness is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate runtime readiness not found")
    return readiness


@router.get(
    "/reviewed-candidates/{candidate_id}/rollback-preview",
    response_model=ReviewedExternalCandidateRollbackPreviewResponse,
)
async def get_external_source_reviewed_candidate_rollback_preview(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    preview = await get_reviewed_candidate_rollback_preview(
        db,
        tenant_id=current_user.tenant_id,
        candidate_id=candidate_id,
    )
    if preview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate rollback preview not found")
    return preview


@router.get("/reviewed-candidates/{candidate_id}", response_model=ReviewedExternalCandidateRead)
async def get_external_source_reviewed_candidate(
    candidate_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = await get_reviewed_candidate(db, tenant_id=current_user.tenant_id, candidate_id=candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reviewed external candidate not found")
    return candidate
