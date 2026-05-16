"""Release packet attachment service."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import HumanApprovalRequestRecord, ReleaseDecision, ReleasePacketAttachmentRecord
from app.schemas.release_packets import (
    HumanApprovalRequestCreate,
    HumanApprovalRequestResponse,
    ReleasePacketAttachmentResponse,
)
from app.services.evidence_service import stable_payload_hash
from app.services.release_guardrail_service import build_release_governance_envelope
from app.services.simulation_lab_service import build_release_appendix


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _attachment_response(record: ReleasePacketAttachmentRecord) -> ReleasePacketAttachmentResponse:
    return ReleasePacketAttachmentResponse(
        attachment_id=record.attachment_id,
        release_decision_id=record.release_decision_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        attachment_type=record.attachment_type,
        simulation_id=record.simulation_id,
        run_id=record.run_id,
        evidence_pack_id=record.evidence_pack_id,
        appendix_hash=record.appendix_hash,
        payload=record.payload,
        created_at=record.created_at,
    )


def _approval_response(record: HumanApprovalRequestRecord) -> HumanApprovalRequestResponse:
    return HumanApprovalRequestResponse(
        approval_request_id=record.approval_request_id,
        release_decision_id=record.release_decision_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        status=record.status,
        reason=record.reason,
        payload=record.payload,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


async def _release_decision_exists(db: AsyncSession, *, tenant_id: int, release_decision_id: int) -> bool:
    result = await db.execute(
        select(ReleaseDecision.id).where(
            ReleaseDecision.id == release_decision_id,
            ReleaseDecision.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def attach_simulation_appendix(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    release_decision_id: int,
    simulation_id: str,
    run_id: str | None = None,
) -> ReleasePacketAttachmentResponse | None:
    if not await _release_decision_exists(db, tenant_id=tenant_id, release_decision_id=release_decision_id):
        return None
    appendix = await build_release_appendix(
        db,
        tenant_id=tenant_id,
        simulation_id=simulation_id,
        run_id=run_id,
    )
    if appendix is None:
        return None
    payload = jsonable_encoder(appendix)
    payload["governance_envelope"] = jsonable_encoder(
        build_release_governance_envelope(
            evidence_chain_id=appendix.evidence_pack_id,
            source_boundary="simulation_lab_release_appendix",
            review_required_reason="simulation_appendix_is_release_review_evidence_only",
        )
    )
    record = ReleasePacketAttachmentRecord(
        attachment_id=_new_id("RPA"),
        release_decision_id=release_decision_id,
        tenant_id=tenant_id,
        user_id=user_id,
        attachment_type="simulation_appendix",
        simulation_id=simulation_id,
        run_id=appendix.selected_run.run_id if appendix.selected_run else run_id,
        evidence_pack_id=appendix.evidence_pack_id,
        appendix_hash=stable_payload_hash(payload),
        payload=payload,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _attachment_response(record)


async def list_release_attachments(
    db: AsyncSession,
    *,
    tenant_id: int,
    release_decision_id: int,
) -> list[ReleasePacketAttachmentResponse] | None:
    if not await _release_decision_exists(db, tenant_id=tenant_id, release_decision_id=release_decision_id):
        return None
    result = await db.execute(
        select(ReleasePacketAttachmentRecord)
        .where(
            ReleasePacketAttachmentRecord.release_decision_id == release_decision_id,
            ReleasePacketAttachmentRecord.tenant_id == tenant_id,
        )
        .order_by(ReleasePacketAttachmentRecord.id)
    )
    return [_attachment_response(record) for record in result.scalars().all()]


async def create_human_approval_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    release_decision_id: int,
    payload: HumanApprovalRequestCreate,
) -> HumanApprovalRequestResponse | None:
    if not await _release_decision_exists(db, tenant_id=tenant_id, release_decision_id=release_decision_id):
        return None
    record = HumanApprovalRequestRecord(
        approval_request_id=_new_id("HAR"),
        release_decision_id=release_decision_id,
        tenant_id=tenant_id,
        user_id=user_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id or str(release_decision_id),
        status="pending",
        reason=payload.reason,
        payload=jsonable_encoder(payload.payload),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _approval_response(record)
