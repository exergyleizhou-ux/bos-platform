"""Read-only final action readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import (
    EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE,
    EXTERNAL_RELEASE_SHARE_APPROVER_ROLE,
    FINAL_RELEASE_APPROVER_ROLE,
    MODEL_GOVERNANCE_APPROVER_ROLE,
    require_any_role,
    require_minimum_role,
)
from app.models import User
from app.schemas.final_actions import (
    FinalActionAuditRecordListResponse,
    FinalActionAuditRecordResponse,
    FinalActionExecutionReadinessResponse,
    FinalExternalReleaseDeliveryRequest,
    FinalExternalReleaseShareRequest,
    FinalModelActivationRequest,
    FinalActionPreflightInput,
    FinalActionReadinessResponse,
    FinalActionRequestDraftCreateRequest,
    FinalActionRequestDraftListResponse,
    FinalActionRequestDraftResolveRequest,
    FinalActionRequestDraftResponse,
    FinalActionReviewPacketSnapshotResponse,
    FinalReleaseApprovalRequest,
)
from app.services.final_action_audit_record_service import (
    execute_final_external_release_delivery,
    execute_final_external_release_share,
    execute_final_model_activation,
    execute_final_release_approval,
    get_final_action_audit_record_by_id,
    list_final_action_audit_records,
    serialize_final_action_audit_record,
)
from app.services.final_action_execution_readiness_service import build_final_action_execution_readiness
from app.services.final_action_readiness_service import build_final_action_readiness
from app.services.final_action_request_draft_service import (
    create_non_executing_final_action_request_draft,
    get_final_action_request_draft_by_id,
    list_final_action_request_drafts,
    resolve_non_executing_final_action_request_draft,
    serialize_final_action_request_draft,
)
from app.services.final_action_review_packet_service import (
    get_latest_review_packet_snapshot,
    get_review_packet_snapshot_by_source_id,
    serialize_review_packet_snapshot,
)

router = APIRouter()


@router.get("/final-actions/readiness", response_model=FinalActionReadinessResponse)
async def get_final_action_readiness_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await build_final_action_readiness(db, tenant_id=current_user.tenant_id, limit=limit)


@router.get("/final-actions/audit-records", response_model=FinalActionAuditRecordListResponse)
async def list_final_action_audit_records_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await list_final_action_audit_records(db, tenant_id=current_user.tenant_id, limit=limit)


@router.post(
    "/final-actions/release-approvals",
    response_model=FinalActionAuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_final_release_approval_endpoint(
    payload: FinalReleaseApprovalRequest,
    current_user: User = Depends(require_any_role(FINAL_RELEASE_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        record = await execute_final_release_approval(
            db,
            tenant_id=current_user.tenant_id,
            reviewer=current_user,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"final_action_request_draft_not_found", "release_decision_not_found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail in {
            "final_action_audit_record_idempotency_conflict",
            "final_action_request_draft_action_type_not_release_approval",
            "final_action_request_draft_action_type_not_final_release_approval",
            "final_action_request_draft_not_approved_for_execution",
            "release_decision_target_id_invalid",
            "final_release_approver_role_required",
            "source_review_packet_not_found",
        } or detail.startswith("release_decision_state_mismatch:"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail == "reviewed_by_user_tenant_mismatch":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_audit_record(record)


@router.post(
    "/final-actions/model-activations",
    response_model=FinalActionAuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_final_model_activation_endpoint(
    payload: FinalModelActivationRequest,
    current_user: User = Depends(require_any_role(MODEL_GOVERNANCE_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        record = await execute_final_model_activation(
            db,
            tenant_id=current_user.tenant_id,
            reviewer=current_user,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"final_action_request_draft_not_found", "model_version_not_found", "model_not_found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail in {
            "final_action_audit_record_idempotency_conflict",
            "final_action_request_draft_action_type_not_model_activation",
            "final_action_request_draft_not_approved_for_execution",
            "model_governance_approver_role_required",
            "source_review_packet_not_found",
        } or detail.startswith("model_version_state_mismatch:"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail == "reviewed_by_user_tenant_mismatch":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_audit_record(record)


@router.post(
    "/final-actions/external-release-shares",
    response_model=FinalActionAuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_final_external_release_share_endpoint(
    payload: FinalExternalReleaseShareRequest,
    current_user: User = Depends(require_any_role(EXTERNAL_RELEASE_SHARE_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        record = await execute_final_external_release_share(
            db,
            tenant_id=current_user.tenant_id,
            reviewer=current_user,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {
            "final_action_request_draft_not_found",
            "release_decision_not_found",
            "release_packet_attachment_not_found",
        }:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail in {
            "final_action_audit_record_idempotency_conflict",
            "final_action_request_draft_action_type_not_external_release_share",
            "final_action_request_draft_not_approved_for_execution",
            "external_release_share_approver_role_required",
            "recipient_scope_not_allowlisted",
            "redaction_policy_not_attested",
            "release_decision_target_id_invalid",
            "source_review_packet_not_found",
        } or detail.startswith("release_decision_not_approved:"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail == "reviewed_by_user_tenant_mismatch":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_audit_record(record)


@router.post(
    "/final-actions/external-release-deliveries",
    response_model=FinalActionAuditRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_final_external_release_delivery_endpoint(
    payload: FinalExternalReleaseDeliveryRequest,
    current_user: User = Depends(require_any_role(EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        record = await execute_final_external_release_delivery(
            db,
            tenant_id=current_user.tenant_id,
            reviewer=current_user,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {
            "external_release_share_record_not_found",
            "release_decision_not_found",
            "release_packet_attachment_not_found",
        }:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail in {
            "final_action_audit_record_idempotency_conflict",
            "external_release_delivery_approver_role_required",
            "unsupported_delivery_channel",
            "external_network_send_attestation_required",
            "delivery_endpoint_not_allowlisted",
            "recipient_scope_not_allowlisted",
            "redaction_policy_not_attested",
            "external_delivery_endpoint_unreachable",
        } or detail.startswith(
            (
                "external_release_share_delivery_status_mismatch:",
                "external_release_share_status_not_prepared:",
                "release_decision_not_approved:",
                "external_delivery_endpoint_failed:",
            )
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail == "reviewed_by_user_tenant_mismatch":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_audit_record(record)


@router.get("/final-actions/audit-records/{final_action_id}", response_model=FinalActionAuditRecordResponse)
async def get_final_action_audit_record_endpoint(
    final_action_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    record = await get_final_action_audit_record_by_id(
        db,
        tenant_id=current_user.tenant_id,
        final_action_id=final_action_id,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final action audit record not found")
    return serialize_final_action_audit_record(record)


@router.get("/final-actions/request-drafts", response_model=FinalActionRequestDraftListResponse)
async def list_final_action_request_drafts_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await list_final_action_request_drafts(db, tenant_id=current_user.tenant_id, limit=limit)


@router.post(
    "/final-actions/request-drafts",
    response_model=FinalActionRequestDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_final_action_request_draft_endpoint(
    payload: FinalActionRequestDraftCreateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        draft = await create_non_executing_final_action_request_draft(
            db,
            tenant_id=current_user.tenant_id,
            request=FinalActionPreflightInput(
                action_type=payload.action_type,
                target_type=payload.target_type,
                target_id=payload.target_id,
                source_review_packet_id=payload.source_review_packet_id,
                idempotency_key=payload.idempotency_key,
                requested_by_user_id=current_user.id,
            ),
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "source_review_packet_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail == "final_action_request_draft_idempotency_conflict":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        if detail in {
            "requested_by_user_not_found",
            "requested_by_user_tenant_mismatch",
            "requested_by_user_role_not_allowed_for_final_action_draft",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_request_draft(draft)


@router.post(
    "/final-actions/request-drafts/{final_action_request_id}/resolve",
    response_model=FinalActionRequestDraftResponse,
)
async def resolve_final_action_request_draft_endpoint(
    final_action_request_id: str,
    payload: FinalActionRequestDraftResolveRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        draft = await resolve_non_executing_final_action_request_draft(
            db,
            tenant_id=current_user.tenant_id,
            final_action_request_id=final_action_request_id,
            reviewed_by_user_id=current_user.id,
            resolution=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "final_action_request_draft_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        if detail in {
            "reviewed_by_user_not_found",
            "reviewed_by_user_tenant_mismatch",
            "reviewed_by_user_role_not_allowed_for_final_action_draft",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail) from exc
        if detail == "final_action_request_draft_status_not_resolvable":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    return serialize_final_action_request_draft(draft)


@router.get(
    "/final-actions/request-drafts/{final_action_request_id}/execution-readiness",
    response_model=FinalActionExecutionReadinessResponse,
)
async def get_final_action_request_draft_execution_readiness_endpoint(
    final_action_request_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    draft = await get_final_action_request_draft_by_id(
        db,
        tenant_id=current_user.tenant_id,
        final_action_request_id=final_action_request_id,
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final action request draft not found")
    return await build_final_action_execution_readiness(db, tenant_id=current_user.tenant_id, draft=draft)


@router.get("/final-actions/request-drafts/{final_action_request_id}", response_model=FinalActionRequestDraftResponse)
async def get_final_action_request_draft_endpoint(
    final_action_request_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    draft = await get_final_action_request_draft_by_id(
        db,
        tenant_id=current_user.tenant_id,
        final_action_request_id=final_action_request_id,
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Final action request draft not found")
    return serialize_final_action_request_draft(draft)


@router.get(
    "/final-actions/source-review-packets/latest",
    response_model=FinalActionReviewPacketSnapshotResponse,
)
async def get_latest_source_review_packet_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    snapshot = await get_latest_review_packet_snapshot(db, tenant_id=current_user.tenant_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source review packet not found")
    return serialize_review_packet_snapshot(snapshot)


@router.get(
    "/final-actions/source-review-packets/{source_review_packet_id}",
    response_model=FinalActionReviewPacketSnapshotResponse,
)
async def get_source_review_packet_endpoint(
    source_review_packet_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    snapshot = await get_review_packet_snapshot_by_source_id(
        db,
        tenant_id=current_user.tenant_id,
        source_review_packet_id=source_review_packet_id,
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source review packet not found")
    return serialize_review_packet_snapshot(snapshot)
