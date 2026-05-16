"""Read-only final action audit record queries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import (
    EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE,
    EXTERNAL_RELEASE_SHARE_APPROVER_ROLE,
    FINAL_RELEASE_APPROVER_ROLE,
    MODEL_GOVERNANCE_APPROVER_ROLE,
    resolve_user_roles,
    user_has_resolved_role,
)
from app.models import User
from app.models_bos import (
    ExternalReleaseShareRecord,
    FinalActionAuditRecord,
    FinalActionRequestDraftRecord,
    ModelRegistryRecord,
    ModelVersionRecord,
    ReleaseDecision,
    ReleasePacketAttachmentRecord,
)
from app.schemas.final_actions import (
    FinalActionAuditRecordListResponse,
    FinalActionAuditRecordResponse,
    FinalExternalReleaseDeliveryRequest,
    FinalExternalReleaseShareRequest,
    FinalModelActivationRequest,
    FinalReleaseApprovalRequest,
)
from app.services.final_action_review_packet_service import get_review_packet_snapshot_by_source_id

READ_ONLY_AUDIT_RECORD_GUARDRAILS = [
    "read_only_final_action_audit_records",
    "final_actions_not_executed",
    "tenant_scoped_read_model",
    "no_release_decision_mutation",
    "no_model_activation",
    "no_external_share_record",
    "no_hardware_execution",
]

EXECUTED_AUDIT_RECORD_GUARDRAILS = [
    "read_only_final_action_audit_records",
    "query_does_not_execute_final_actions",
    "tenant_scoped_read_model",
    "audit_records_may_include_executed_final_actions",
    "no_model_activation",
    "no_external_share_record",
    "no_hardware_execution",
]

EXECUTED_EXTERNAL_SHARE_AUDIT_RECORD_GUARDRAILS = [
    "read_only_final_action_audit_records",
    "query_does_not_execute_final_actions",
    "tenant_scoped_read_model",
    "audit_records_may_include_executed_final_actions",
    "external_share_records_may_include_prepared_internal_shares",
    "external_network_send_requires_separate_delivery_gate",
    "no_hardware_execution",
]

EXECUTED_EXTERNAL_DELIVERY_AUDIT_RECORD_GUARDRAILS = [
    "read_only_final_action_audit_records",
    "query_does_not_execute_final_actions",
    "tenant_scoped_read_model",
    "audit_records_may_include_executed_final_actions",
    "external_share_records_may_include_delivered_external_shares",
    "external_network_send_executed_by_delivery_gate",
    "no_hardware_execution",
]


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def serialize_final_action_audit_record(record: FinalActionAuditRecord) -> FinalActionAuditRecordResponse:
    return FinalActionAuditRecordResponse(
        final_action_id=record.final_action_id,
        tenant_id=record.tenant_id,
        action_type=record.action_type,
        target_type=record.target_type,
        target_id=record.target_id,
        requested_by_user_id=record.requested_by_user_id,
        reviewed_by_user_id=record.reviewed_by_user_id,
        role_snapshot=record.role_snapshot,
        source_review_packet_id=record.source_review_packet_id,
        source_evidence_pack_ids=[str(value) for value in record.source_evidence_pack_ids],
        precondition_snapshot=record.precondition_snapshot,
        before_state=record.before_state,
        after_state=record.after_state,
        decision=record.decision,
        reason=record.reason,
        idempotency_key=record.idempotency_key,
        status=record.status,
        effect_summary=record.effect_summary,
        created_at=_iso(record.created_at) or "",
        resolved_at=_iso(record.resolved_at),
    )


def _release_decision_snapshot(release_decision: ReleaseDecision) -> dict:
    return {
        "release_decision_id": release_decision.id,
        "decision": release_decision.decision,
        "reason_codes": release_decision.reason_codes or [],
        "trigger_metrics": release_decision.trigger_metrics or {},
        "approver": release_decision.approver,
        "rationale": release_decision.rationale,
        "blocking_factors": release_decision.blocking_factors or [],
        "warning_factors": release_decision.warning_factors or [],
        "passed_checks": release_decision.passed_checks or [],
        "decision_time": release_decision.decision_time.isoformat() if release_decision.decision_time else None,
    }


def _model_activation_snapshot(model: ModelRegistryRecord, version: ModelVersionRecord, active_versions: list[ModelVersionRecord]) -> dict:
    return {
        "model_id": model.model_id,
        "model_status": model.status,
        "model_version_id": version.model_version_id,
        "version_status": version.status,
        "metadata_payload": version.metadata_payload or {},
        "previous_active_version_ids": [item.model_version_id for item in active_versions],
    }


def _external_share_snapshot(
    *,
    release_decision: ReleaseDecision,
    release_packet: ReleasePacketAttachmentRecord,
    share: ExternalReleaseShareRecord | None = None,
    recipient_scope: str | None = None,
    redaction_policy_id: str | None = None,
) -> dict:
    state = {
        "release_decision_id": release_decision.id,
        "release_decision": release_decision.decision,
        "release_packet_attachment_id": release_packet.attachment_id,
        "release_packet_appendix_hash": release_packet.appendix_hash,
        "recipient_scope": recipient_scope,
        "redaction_policy_id": redaction_policy_id,
        "external_network_send": False,
    }
    if share is not None:
        state.update(
            {
                "share_id": share.share_id,
                "status": share.status,
                "delivery_status": share.delivery_status,
                "final_action_id": share.final_action_id,
            }
        )
    return state


def _external_delivery_snapshot(*, share: ExternalReleaseShareRecord, delivery_endpoint: str | None = None) -> dict:
    payload = share.payload or {}
    return {
        "share_id": share.share_id,
        "release_decision_id": share.release_decision_id,
        "release_packet_attachment_id": share.release_packet_attachment_id,
        "recipient_scope": share.recipient_scope,
        "redaction_policy_id": share.redaction_policy_id,
        "source_review_packet_id": share.source_review_packet_id,
        "preparation_final_action_id": share.final_action_id,
        "status": share.status,
        "delivery_status": share.delivery_status,
        "delivery_channel": payload.get("delivery_channel"),
        "delivery_endpoint": delivery_endpoint or payload.get("delivery_endpoint"),
        "delivery_response_status_code": payload.get("delivery_response_status_code"),
        "external_network_send": bool(payload.get("external_network_send", False)),
    }


def _allowed_external_share_endpoint_or_raise(delivery_endpoint: str) -> None:
    settings = get_settings()
    allowed_prefixes = [
        value.strip()
        for value in settings.BOS_EXTERNAL_SHARE_ALLOWED_ENDPOINTS.split(",")
        if value.strip()
    ]
    if not allowed_prefixes or not any(delivery_endpoint.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError("delivery_endpoint_not_allowlisted")


def _new_final_action_id() -> str:
    return f"FA-{uuid.uuid4().hex[:16].upper()}"


def _new_share_id() -> str:
    return f"ERS-{uuid.uuid4().hex[:16].upper()}"


async def _final_action_role_snapshot(db: AsyncSession, *, reviewer: User, required_role: str) -> dict:
    reviewed_by_user_roles = await resolve_user_roles(db, reviewer)
    return {
        "reviewed_by_user_id": reviewer.id,
        "reviewed_by_user_role": reviewer.role,
        "reviewed_by_user_roles": sorted(reviewed_by_user_roles),
        "required_role": required_role,
        required_role: True,
        "admin_override": False,
    }


async def list_final_action_audit_records(
    db: AsyncSession,
    *,
    tenant_id: int,
    limit: int = 50,
) -> FinalActionAuditRecordListResponse:
    result = await db.execute(
        select(FinalActionAuditRecord)
        .where(FinalActionAuditRecord.tenant_id == tenant_id)
        .order_by(desc(FinalActionAuditRecord.created_at), desc(FinalActionAuditRecord.id))
        .limit(limit)
    )
    records = [serialize_final_action_audit_record(record) for record in result.scalars().all()]
    has_external_delivery = any(bool((record.effect_summary or {}).get("external_network_send")) for record in records)
    has_external_share = any(bool((record.effect_summary or {}).get("external_share")) for record in records)
    return FinalActionAuditRecordListResponse(
        tenant_id=tenant_id,
        count=len(records),
        records=records,
        guardrails=(
            EXECUTED_EXTERNAL_DELIVERY_AUDIT_RECORD_GUARDRAILS
            if has_external_delivery
            else EXECUTED_EXTERNAL_SHARE_AUDIT_RECORD_GUARDRAILS
            if has_external_share
            else (EXECUTED_AUDIT_RECORD_GUARDRAILS if records else READ_ONLY_AUDIT_RECORD_GUARDRAILS)
        ),
    )


async def get_final_action_audit_record_by_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    final_action_id: str,
) -> FinalActionAuditRecord | None:
    return await db.scalar(
        select(FinalActionAuditRecord)
        .where(
            FinalActionAuditRecord.tenant_id == tenant_id,
            FinalActionAuditRecord.final_action_id == final_action_id,
        )
        .limit(1)
    )


async def _get_final_action_audit_record_by_idempotency(
    db: AsyncSession,
    *,
    tenant_id: int,
    action_type: str,
    idempotency_key: str,
) -> FinalActionAuditRecord | None:
    return await db.scalar(
        select(FinalActionAuditRecord)
        .where(
            FinalActionAuditRecord.tenant_id == tenant_id,
            FinalActionAuditRecord.action_type == action_type,
            FinalActionAuditRecord.idempotency_key == idempotency_key,
        )
        .limit(1)
    )


async def _approved_draft_or_raise(
    db: AsyncSession,
    *,
    tenant_id: int,
    final_action_request_id: str,
    action_type: str,
) -> FinalActionRequestDraftRecord:
    draft = await db.scalar(
        select(FinalActionRequestDraftRecord).where(
            FinalActionRequestDraftRecord.tenant_id == tenant_id,
            FinalActionRequestDraftRecord.final_action_request_id == final_action_request_id,
        )
    )
    if draft is None:
        raise ValueError("final_action_request_draft_not_found")
    if draft.action_type != action_type:
        raise ValueError(f"final_action_request_draft_action_type_not_{action_type}")
    if draft.status != "review_approved_no_execution":
        raise ValueError("final_action_request_draft_not_approved_for_execution")
    source_packet = await get_review_packet_snapshot_by_source_id(
        db,
        tenant_id=tenant_id,
        source_review_packet_id=draft.source_review_packet_id,
    )
    if source_packet is None:
        raise ValueError("source_review_packet_not_found")
    return draft


async def execute_final_release_approval(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer: User,
    payload: FinalReleaseApprovalRequest,
) -> FinalActionAuditRecord:
    """Execute the audited final release approval workflow only."""

    if reviewer.tenant_id != tenant_id:
        raise ValueError("reviewed_by_user_tenant_mismatch")
    if not await user_has_resolved_role(db, reviewer, FINAL_RELEASE_APPROVER_ROLE):
        raise ValueError("final_release_approver_role_required")

    existing = await _get_final_action_audit_record_by_idempotency(
        db,
        tenant_id=tenant_id,
        action_type="final_release_approval",
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if existing.precondition_snapshot.get("final_action_request_id") != payload.final_action_request_id:
            raise ValueError("final_action_audit_record_idempotency_conflict")
        return existing

    draft = await _approved_draft_or_raise(
        db,
        tenant_id=tenant_id,
        final_action_request_id=payload.final_action_request_id,
        action_type="final_release_approval",
    )

    try:
        release_decision_id = int(draft.target_id)
    except ValueError as exc:
        raise ValueError("release_decision_target_id_invalid") from exc

    release_decision = await db.get(ReleaseDecision, release_decision_id)
    if release_decision is None or release_decision.tenant_id != tenant_id:
        raise ValueError("release_decision_not_found")
    if release_decision.decision != payload.expected_current_decision:
        raise ValueError(f"release_decision_state_mismatch:{release_decision.decision}")

    before_state = _release_decision_snapshot(release_decision)
    final_action_id = _new_final_action_id()
    now = datetime.now(UTC)
    reason_codes = list(release_decision.reason_codes or [])
    if "final_action_release_approved" not in reason_codes:
        reason_codes.append("final_action_release_approved")
    trigger_metrics = dict(release_decision.trigger_metrics or {})
    trigger_metrics["final_action_id"] = final_action_id
    trigger_metrics["final_action_request_id"] = draft.final_action_request_id
    trigger_metrics["source_review_packet_id"] = draft.source_review_packet_id

    release_decision.decision = "approved"
    release_decision.reason_codes = reason_codes
    release_decision.trigger_metrics = trigger_metrics
    release_decision.approver = reviewer.full_name or reviewer.username
    release_decision.rationale = payload.operator_attestation
    release_decision.decision_time = now

    after_state = _release_decision_snapshot(release_decision)
    record = FinalActionAuditRecord(
        final_action_id=final_action_id,
        tenant_id=tenant_id,
        action_type="final_release_approval",
        target_type=draft.target_type,
        target_id=draft.target_id,
        requested_by_user_id=draft.requested_by_user_id,
        reviewed_by_user_id=reviewer.id,
        role_snapshot=await _final_action_role_snapshot(
            db,
            reviewer=reviewer,
            required_role=FINAL_RELEASE_APPROVER_ROLE,
        ),
        source_review_packet_id=draft.source_review_packet_id,
        source_evidence_pack_ids=[str(value) for value in draft.source_evidence_pack_ids],
        precondition_snapshot={
            "final_action_request_id": draft.final_action_request_id,
            "draft_status": draft.status,
            "expected_current_decision": payload.expected_current_decision,
            "operator_attestation": payload.operator_attestation,
            "source_review_packet_id": draft.source_review_packet_id,
        },
        before_state=before_state,
        after_state=after_state,
        decision="approved",
        reason=payload.operator_attestation,
        idempotency_key=payload.idempotency_key,
        status="executed",
        effect_summary={
            "release_decision": "changed",
            "model_activation": False,
            "external_share": False,
            "hardware_execution": False,
        },
        resolved_at=now,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def execute_final_model_activation(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer: User,
    payload: FinalModelActivationRequest,
) -> FinalActionAuditRecord:
    """Execute the audited model activation workflow only."""

    if reviewer.tenant_id != tenant_id:
        raise ValueError("reviewed_by_user_tenant_mismatch")
    if not await user_has_resolved_role(db, reviewer, MODEL_GOVERNANCE_APPROVER_ROLE):
        raise ValueError("model_governance_approver_role_required")

    existing = await _get_final_action_audit_record_by_idempotency(
        db,
        tenant_id=tenant_id,
        action_type="model_activation",
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if existing.precondition_snapshot.get("final_action_request_id") != payload.final_action_request_id:
            raise ValueError("final_action_audit_record_idempotency_conflict")
        return existing

    draft = await _approved_draft_or_raise(
        db,
        tenant_id=tenant_id,
        final_action_request_id=payload.final_action_request_id,
        action_type="model_activation",
    )
    model_version = await db.scalar(
        select(ModelVersionRecord)
        .join(ModelRegistryRecord, ModelRegistryRecord.model_id == ModelVersionRecord.model_id)
        .where(
            ModelRegistryRecord.tenant_id == tenant_id,
            ModelVersionRecord.model_version_id == draft.target_id,
        )
        .limit(1)
    )
    if model_version is None:
        raise ValueError("model_version_not_found")
    model = await db.scalar(
        select(ModelRegistryRecord).where(
            ModelRegistryRecord.tenant_id == tenant_id,
            ModelRegistryRecord.model_id == model_version.model_id,
        )
    )
    if model is None:
        raise ValueError("model_not_found")
    if model_version.status != payload.expected_current_version_status:
        raise ValueError(f"model_version_state_mismatch:{model_version.status}")

    active_result = await db.execute(
        select(ModelVersionRecord).where(
            ModelVersionRecord.model_id == model.model_id,
            ModelVersionRecord.status == "active",
            ModelVersionRecord.model_version_id != model_version.model_version_id,
        )
    )
    previous_active_versions = list(active_result.scalars().all())
    before_state = _model_activation_snapshot(model, model_version, previous_active_versions)
    final_action_id = _new_final_action_id()
    now = datetime.now(UTC)

    for active_version in previous_active_versions:
        metadata = dict(active_version.metadata_payload or {})
        metadata["superseded_by_final_action_id"] = final_action_id
        metadata["superseded_by_model_version_id"] = model_version.model_version_id
        active_version.metadata_payload = metadata
        active_version.status = "superseded"

    metadata = dict(model_version.metadata_payload or {})
    metadata["governance_status"] = "active"
    metadata["activated_by_final_action_id"] = final_action_id
    metadata["activated_by_user_id"] = reviewer.id
    metadata["source_review_packet_id"] = draft.source_review_packet_id
    model_version.metadata_payload = metadata
    model_version.status = "active"
    model.status = "active"

    after_state = _model_activation_snapshot(model, model_version, previous_active_versions)
    record = FinalActionAuditRecord(
        final_action_id=final_action_id,
        tenant_id=tenant_id,
        action_type="model_activation",
        target_type=draft.target_type,
        target_id=draft.target_id,
        requested_by_user_id=draft.requested_by_user_id,
        reviewed_by_user_id=reviewer.id,
        role_snapshot=await _final_action_role_snapshot(
            db,
            reviewer=reviewer,
            required_role=MODEL_GOVERNANCE_APPROVER_ROLE,
        ),
        source_review_packet_id=draft.source_review_packet_id,
        source_evidence_pack_ids=[str(value) for value in draft.source_evidence_pack_ids],
        precondition_snapshot={
            "final_action_request_id": draft.final_action_request_id,
            "draft_status": draft.status,
            "expected_current_version_status": payload.expected_current_version_status,
            "operator_attestation": payload.operator_attestation,
            "source_review_packet_id": draft.source_review_packet_id,
        },
        before_state=before_state,
        after_state=after_state,
        decision="activated",
        reason=payload.operator_attestation,
        idempotency_key=payload.idempotency_key,
        status="executed",
        effect_summary={
            "release_decision": "unchanged",
            "model_activation": True,
            "external_share": False,
            "hardware_execution": False,
        },
        resolved_at=now,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def execute_final_external_release_share(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer: User,
    payload: FinalExternalReleaseShareRequest,
) -> FinalActionAuditRecord:
    """Create an audited internal external-share record without sending externally."""

    if reviewer.tenant_id != tenant_id:
        raise ValueError("reviewed_by_user_tenant_mismatch")
    if not await user_has_resolved_role(db, reviewer, EXTERNAL_RELEASE_SHARE_APPROVER_ROLE):
        raise ValueError("external_release_share_approver_role_required")
    if not payload.recipient_scope.startswith("allowlisted:"):
        raise ValueError("recipient_scope_not_allowlisted")
    if not payload.redaction_policy_id or payload.redaction_policy_id.lower() in {"none", "unredacted"}:
        raise ValueError("redaction_policy_not_attested")

    existing = await _get_final_action_audit_record_by_idempotency(
        db,
        tenant_id=tenant_id,
        action_type="external_release_share",
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if existing.precondition_snapshot.get("final_action_request_id") != payload.final_action_request_id:
            raise ValueError("final_action_audit_record_idempotency_conflict")
        return existing

    draft = await _approved_draft_or_raise(
        db,
        tenant_id=tenant_id,
        final_action_request_id=payload.final_action_request_id,
        action_type="external_release_share",
    )
    try:
        release_decision_id = int(draft.target_id)
    except ValueError as exc:
        raise ValueError("release_decision_target_id_invalid") from exc

    release_decision = await db.get(ReleaseDecision, release_decision_id)
    if release_decision is None or release_decision.tenant_id != tenant_id:
        raise ValueError("release_decision_not_found")
    if release_decision.decision != "approved":
        raise ValueError(f"release_decision_not_approved:{release_decision.decision}")

    release_packet = await db.scalar(
        select(ReleasePacketAttachmentRecord).where(
            ReleasePacketAttachmentRecord.tenant_id == tenant_id,
            ReleasePacketAttachmentRecord.release_decision_id == release_decision.id,
            ReleasePacketAttachmentRecord.attachment_id == payload.release_packet_attachment_id,
        )
    )
    if release_packet is None:
        raise ValueError("release_packet_attachment_not_found")

    before_state = _external_share_snapshot(
        release_decision=release_decision,
        release_packet=release_packet,
        recipient_scope=payload.recipient_scope,
        redaction_policy_id=payload.redaction_policy_id,
    )
    final_action_id = _new_final_action_id()
    now = datetime.now(UTC)
    share = ExternalReleaseShareRecord(
        share_id=_new_share_id(),
        tenant_id=tenant_id,
        release_decision_id=release_decision.id,
        release_packet_attachment_id=release_packet.attachment_id,
        requested_by_user_id=draft.requested_by_user_id,
        reviewed_by_user_id=reviewer.id,
        recipient_scope=payload.recipient_scope,
        redaction_policy_id=payload.redaction_policy_id,
        source_review_packet_id=draft.source_review_packet_id,
        final_action_id=final_action_id,
        idempotency_key=payload.idempotency_key,
        status="prepared_internal_share",
        delivery_status="not_sent",
        payload={
            "operator_attestation": payload.operator_attestation,
            "external_network_send": False,
            "outbound_delivery_gate": "separate_approval_required",
        },
    )
    db.add(share)
    await db.flush()
    after_state = _external_share_snapshot(
        release_decision=release_decision,
        release_packet=release_packet,
        share=share,
        recipient_scope=payload.recipient_scope,
        redaction_policy_id=payload.redaction_policy_id,
    )
    record = FinalActionAuditRecord(
        final_action_id=final_action_id,
        tenant_id=tenant_id,
        action_type="external_release_share",
        target_type=draft.target_type,
        target_id=draft.target_id,
        requested_by_user_id=draft.requested_by_user_id,
        reviewed_by_user_id=reviewer.id,
        role_snapshot=await _final_action_role_snapshot(
            db,
            reviewer=reviewer,
            required_role=EXTERNAL_RELEASE_SHARE_APPROVER_ROLE,
        ),
        source_review_packet_id=draft.source_review_packet_id,
        source_evidence_pack_ids=[str(value) for value in draft.source_evidence_pack_ids],
        precondition_snapshot={
            "final_action_request_id": draft.final_action_request_id,
            "draft_status": draft.status,
            "release_packet_attachment_id": payload.release_packet_attachment_id,
            "recipient_scope": payload.recipient_scope,
            "redaction_policy_id": payload.redaction_policy_id,
            "operator_attestation": payload.operator_attestation,
            "source_review_packet_id": draft.source_review_packet_id,
            "outbound_delivery_gate": "separate_approval_required",
        },
        before_state=before_state,
        after_state=after_state,
        decision="prepared_internal_share",
        reason=payload.operator_attestation,
        idempotency_key=payload.idempotency_key,
        status="executed",
        effect_summary={
            "release_decision": "unchanged",
            "model_activation": False,
            "external_share": True,
            "hardware_execution": False,
            "external_network_send": False,
        },
        resolved_at=now,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def execute_final_external_release_delivery(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer: User,
    payload: FinalExternalReleaseDeliveryRequest,
) -> FinalActionAuditRecord:
    """Execute the outbound external-share delivery gate with an audited HTTP send."""

    if reviewer.tenant_id != tenant_id:
        raise ValueError("reviewed_by_user_tenant_mismatch")
    if not await user_has_resolved_role(db, reviewer, EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE):
        raise ValueError("external_release_delivery_approver_role_required")
    if payload.delivery_channel != "webhook":
        raise ValueError("unsupported_delivery_channel")
    if payload.external_network_send is not True:
        raise ValueError("external_network_send_attestation_required")
    _allowed_external_share_endpoint_or_raise(payload.delivery_endpoint)

    existing = await _get_final_action_audit_record_by_idempotency(
        db,
        tenant_id=tenant_id,
        action_type="external_release_delivery",
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if existing.precondition_snapshot.get("share_id") != payload.share_id:
            raise ValueError("final_action_audit_record_idempotency_conflict")
        return existing

    share = await db.scalar(
        select(ExternalReleaseShareRecord).where(
            ExternalReleaseShareRecord.tenant_id == tenant_id,
            ExternalReleaseShareRecord.share_id == payload.share_id,
        )
    )
    if share is None:
        raise ValueError("external_release_share_record_not_found")
    preparation_record = await get_final_action_audit_record_by_id(
        db,
        tenant_id=tenant_id,
        final_action_id=share.final_action_id,
    )
    if share.delivery_status != payload.expected_delivery_status:
        raise ValueError(f"external_release_share_delivery_status_mismatch:{share.delivery_status}")
    if share.status != "prepared_internal_share":
        raise ValueError(f"external_release_share_status_not_prepared:{share.status}")
    if not share.recipient_scope.startswith("allowlisted:"):
        raise ValueError("recipient_scope_not_allowlisted")
    if not share.redaction_policy_id or share.redaction_policy_id.lower() in {"none", "unredacted"}:
        raise ValueError("redaction_policy_not_attested")

    release_decision = await db.get(ReleaseDecision, share.release_decision_id)
    if release_decision is None or release_decision.tenant_id != tenant_id:
        raise ValueError("release_decision_not_found")
    if release_decision.decision != "approved":
        raise ValueError(f"release_decision_not_approved:{release_decision.decision}")
    release_packet = await db.scalar(
        select(ReleasePacketAttachmentRecord).where(
            ReleasePacketAttachmentRecord.tenant_id == tenant_id,
            ReleasePacketAttachmentRecord.release_decision_id == release_decision.id,
            ReleasePacketAttachmentRecord.attachment_id == share.release_packet_attachment_id,
        )
    )
    if release_packet is None:
        raise ValueError("release_packet_attachment_not_found")

    before_state = _external_delivery_snapshot(share=share, delivery_endpoint=payload.delivery_endpoint)
    final_action_id = _new_final_action_id()
    now = datetime.now(UTC)
    delivery_body = {
        "schema_version": "bos_external_release_delivery_v1",
        "share_id": share.share_id,
        "release_decision_id": release_decision.id,
        "release_packet_attachment_id": release_packet.attachment_id,
        "release_packet_appendix_hash": release_packet.appendix_hash,
        "recipient_scope": share.recipient_scope,
        "redaction_policy_id": share.redaction_policy_id,
        "source_review_packet_id": share.source_review_packet_id,
        "preparation_final_action_id": share.final_action_id,
        "delivery_final_action_id": final_action_id,
        "release_packet_payload": release_packet.payload or {},
    }
    timeout = float(get_settings().BOS_EXTERNAL_SHARE_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(payload.delivery_endpoint, json=delivery_body)
    except httpx.HTTPError as exc:
        raise ValueError("external_delivery_endpoint_unreachable") from exc
    if response.status_code < 200 or response.status_code >= 300:
        raise ValueError(f"external_delivery_endpoint_failed:{response.status_code}")

    delivery_payload = dict(share.payload or {})
    delivery_payload.update(
        {
            "delivery_channel": payload.delivery_channel,
            "delivery_endpoint": payload.delivery_endpoint,
            "delivery_response_status_code": response.status_code,
            "delivery_response_body_preview": response.text[:500],
            "delivery_final_action_id": final_action_id,
            "delivered_by_user_id": reviewer.id,
            "delivered_at": now.isoformat(),
            "external_network_send": True,
            "outbound_delivery_gate": "executed",
        }
    )
    share.payload = delivery_payload
    share.delivery_status = "sent"
    share.status = "delivered_external_share"

    after_state = _external_delivery_snapshot(share=share, delivery_endpoint=payload.delivery_endpoint)
    record = FinalActionAuditRecord(
        final_action_id=final_action_id,
        tenant_id=tenant_id,
        action_type="external_release_delivery",
        target_type="external_release_share_record",
        target_id=share.share_id,
        requested_by_user_id=share.requested_by_user_id,
        reviewed_by_user_id=reviewer.id,
        role_snapshot=await _final_action_role_snapshot(
            db,
            reviewer=reviewer,
            required_role=EXTERNAL_RELEASE_DELIVERY_APPROVER_ROLE,
        ),
        source_review_packet_id=share.source_review_packet_id,
        source_evidence_pack_ids=(
            [str(value) for value in preparation_record.source_evidence_pack_ids]
            if preparation_record is not None
            else []
        ),
        precondition_snapshot={
            "share_id": share.share_id,
            "expected_delivery_status": payload.expected_delivery_status,
            "delivery_channel": payload.delivery_channel,
            "delivery_endpoint": payload.delivery_endpoint,
            "operator_attestation": payload.operator_attestation,
            "external_network_send": payload.external_network_send,
        },
        before_state=before_state,
        after_state=after_state,
        decision="sent",
        reason=payload.operator_attestation,
        idempotency_key=payload.idempotency_key,
        status="executed",
        effect_summary={
            "release_decision": "unchanged",
            "model_activation": False,
            "external_share": True,
            "hardware_execution": False,
            "external_network_send": True,
        },
        resolved_at=now,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
