"""Read-only final action request draft queries."""

from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import FINAL_ACTION_APPROVER_ROLES, resolve_user_roles, user_has_any_resolved_role
from app.models import User
from app.models_bos import FinalActionRequestDraftRecord
from app.schemas.final_actions import (
    FinalActionPreflightInput,
    FinalActionRequestDraftListResponse,
    FinalActionRequestDraftResolveRequest,
    FinalActionRequestDraftResponse,
)
from app.services.final_action_preflight_service import preflight_final_action_request

READ_ONLY_REQUEST_DRAFT_GUARDRAILS = [
    "read_only_final_action_request_drafts",
    "final_action_drafts_not_created_by_assistant",
    "final_action_drafts_created_only_by_internal_service",
    "final_actions_not_executed",
    "tenant_scoped_read_model",
    "no_release_decision_mutation",
    "no_model_activation",
    "no_external_share_record",
    "no_hardware_execution",
]

DRAFT_REQUEST_ALLOWED_ROLES = {"operator", "scientist", "admin", *FINAL_ACTION_APPROVER_ROLES}


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


def serialize_final_action_request_draft(
    draft: FinalActionRequestDraftRecord,
) -> FinalActionRequestDraftResponse:
    return FinalActionRequestDraftResponse(
        final_action_request_id=draft.final_action_request_id,
        tenant_id=draft.tenant_id,
        action_type=draft.action_type,
        target_type=draft.target_type,
        target_id=draft.target_id,
        requested_by_user_id=draft.requested_by_user_id,
        source_review_packet_id=draft.source_review_packet_id,
        source_evidence_pack_ids=[str(value) for value in draft.source_evidence_pack_ids],
        request_payload=draft.request_payload,
        preflight_snapshot=draft.preflight_snapshot,
        role_snapshot=draft.role_snapshot,
        idempotency_key=draft.idempotency_key,
        status=draft.status,
        created_at=_iso(draft.created_at),
        updated_at=_iso(draft.updated_at),
    )


async def list_final_action_request_drafts(
    db: AsyncSession,
    *,
    tenant_id: int,
    limit: int = 50,
) -> FinalActionRequestDraftListResponse:
    result = await db.execute(
        select(FinalActionRequestDraftRecord)
        .where(FinalActionRequestDraftRecord.tenant_id == tenant_id)
        .order_by(desc(FinalActionRequestDraftRecord.created_at), desc(FinalActionRequestDraftRecord.id))
        .limit(limit)
    )
    drafts = [serialize_final_action_request_draft(draft) for draft in result.scalars().all()]
    return FinalActionRequestDraftListResponse(
        tenant_id=tenant_id,
        count=len(drafts),
        drafts=drafts,
        guardrails=READ_ONLY_REQUEST_DRAFT_GUARDRAILS,
    )


async def get_final_action_request_draft_by_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    final_action_request_id: str,
) -> FinalActionRequestDraftRecord | None:
    return await db.scalar(
        select(FinalActionRequestDraftRecord)
        .where(
            FinalActionRequestDraftRecord.tenant_id == tenant_id,
            FinalActionRequestDraftRecord.final_action_request_id == final_action_request_id,
        )
        .limit(1)
    )


async def _get_final_action_request_draft_by_idempotency(
    db: AsyncSession,
    *,
    tenant_id: int,
    action_type: str,
    idempotency_key: str,
) -> FinalActionRequestDraftRecord | None:
    return await db.scalar(
        select(FinalActionRequestDraftRecord)
        .where(
            FinalActionRequestDraftRecord.tenant_id == tenant_id,
            FinalActionRequestDraftRecord.action_type == action_type,
            FinalActionRequestDraftRecord.idempotency_key == idempotency_key,
        )
        .limit(1)
    )


def _new_final_action_request_id() -> str:
    return f"FARD-{uuid.uuid4().hex[:16].upper()}"


async def create_non_executing_final_action_request_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    request: FinalActionPreflightInput,
) -> FinalActionRequestDraftRecord:
    """Create an internal blocked draft without writing audit rows or executing final actions."""

    requester = await db.get(User, request.requested_by_user_id)
    if requester is None:
        raise ValueError("requested_by_user_not_found")
    if requester.tenant_id != tenant_id:
        raise ValueError("requested_by_user_tenant_mismatch")
    requester_roles = await resolve_user_roles(db, requester)
    if not any(role in requester_roles for role in DRAFT_REQUEST_ALLOWED_ROLES):
        raise ValueError("requested_by_user_role_not_allowed_for_final_action_draft")

    existing = await _get_final_action_request_draft_by_idempotency(
        db,
        tenant_id=tenant_id,
        action_type=request.action_type,
        idempotency_key=request.idempotency_key,
    )
    if existing is not None:
        if existing.target_type != request.target_type or existing.target_id != request.target_id:
            raise ValueError("final_action_request_draft_idempotency_conflict")
        if existing.source_review_packet_id != request.source_review_packet_id:
            raise ValueError("final_action_request_draft_idempotency_conflict")
        return existing

    preflight = await preflight_final_action_request(db, tenant_id=tenant_id, request=request)
    if not preflight.source_review_packet_found:
        raise ValueError("source_review_packet_not_found")

    request_payload = {
        **request.model_dump(mode="json"),
        "execution": "not_executed",
        "review_only": True,
        "draft_writer": "internal_service_only",
    }
    preflight_snapshot = preflight.model_dump(mode="json")
    role_snapshot = {
        "requested_by_user_id": requester.id,
        "requested_by_user_role": requester.role,
        "requested_by_user_roles": sorted(requester_roles),
        "draft_request_allowed_roles": sorted(DRAFT_REQUEST_ALLOWED_ROLES),
        "required_final_action_roles": preflight.required_roles,
        "final_action_role_authority_implemented": True,
    }
    draft = FinalActionRequestDraftRecord(
        final_action_request_id=_new_final_action_request_id(),
        tenant_id=tenant_id,
        action_type=request.action_type,
        target_type=request.target_type,
        target_id=request.target_id,
        requested_by_user_id=request.requested_by_user_id,
        source_review_packet_id=request.source_review_packet_id,
        source_evidence_pack_ids=preflight.evidence_pack_ids,
        request_payload=request_payload,
        preflight_snapshot=preflight_snapshot,
        role_snapshot=role_snapshot,
        idempotency_key=request.idempotency_key,
        status="draft_blocked",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return draft


async def resolve_non_executing_final_action_request_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    final_action_request_id: str,
    reviewed_by_user_id: int,
    resolution: FinalActionRequestDraftResolveRequest,
) -> FinalActionRequestDraftRecord:
    """Resolve a draft review state without executing final actions or writing audit rows."""

    reviewer = await db.get(User, reviewed_by_user_id)
    if reviewer is None:
        raise ValueError("reviewed_by_user_not_found")
    if reviewer.tenant_id != tenant_id:
        raise ValueError("reviewed_by_user_tenant_mismatch")
    if not await user_has_any_resolved_role(db, reviewer, DRAFT_REQUEST_ALLOWED_ROLES):
        raise ValueError("reviewed_by_user_role_not_allowed_for_final_action_draft")

    draft = await get_final_action_request_draft_by_id(
        db,
        tenant_id=tenant_id,
        final_action_request_id=final_action_request_id,
    )
    if draft is None:
        raise ValueError("final_action_request_draft_not_found")

    if draft.status not in {"draft_blocked", "review_approved_no_execution", "review_rejected_no_execution"}:
        raise ValueError("final_action_request_draft_status_not_resolvable")

    next_status = "review_approved_no_execution" if resolution.approved else "review_rejected_no_execution"
    request_payload = dict(draft.request_payload or {})
    request_payload["review_resolution"] = {
        "approved": resolution.approved,
        "reason": resolution.reason,
        "reviewed_by_user_id": reviewed_by_user_id,
        "scope": "request_draft_review_only",
        "side_effects": {
            "release_decision": "unchanged",
            "model_activation": False,
            "external_share": False,
            "hardware_execution": False,
            "final_action_audit_record": False,
        },
    }
    request_payload["execution"] = "not_executed"
    request_payload["review_only"] = True

    draft.status = next_status
    draft.request_payload = request_payload
    await db.commit()
    await db.refresh(draft)
    return draft
