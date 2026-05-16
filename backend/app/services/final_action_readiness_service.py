"""Read-only readiness model for future final actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import (
    ExternalReleaseShareRecord,
    FinalActionRequestDraftRecord,
    ModelRegistryRecord,
    ModelVersionRecord,
    ReleaseDecision,
)
from app.schemas.final_actions import (
    FinalActionReadinessItem,
    FinalActionReadinessResponse,
    FinalActionReadinessState,
)
from app.services.assistant_service import build_review_workbench_audit_packet
from app.services.final_action_review_packet_service import (
    compute_review_packet_hash,
    get_review_packet_snapshot_by_hash,
)
from app.services.release_guardrail_service import build_release_governance_envelope


def _audit_bucket_count(packet: dict[str, Any], status: str) -> int:
    statuses = packet.get("statuses") if isinstance(packet.get("statuses"), dict) else {}
    bucket = statuses.get(status) if isinstance(statuses.get(status), dict) else {}
    counts = bucket.get("counts") if isinstance(bucket.get("counts"), dict) else {}
    value = counts.get("total", 0)
    return value if isinstance(value, int) else 0


def _readiness_status(blockers: list[str]) -> str:
    if any(blocker.startswith("pending_review_items") for blocker in blockers):
        return "blocked"
    return "locked"


def _action_item(
    *,
    action: str,
    blockers: list[str],
    required_roles: list[str],
    required_evidence_ids: list[str],
    missing_evidence_ids: list[str],
    source_review_packet_id: str | None,
) -> FinalActionReadinessItem:
    return FinalActionReadinessItem(
        action=action,  # type: ignore[arg-type]
        status=_readiness_status(blockers),  # type: ignore[arg-type]
        executable=False,
        blockers=blockers,
        required_roles=required_roles,
        required_evidence_ids=required_evidence_ids,
        missing_evidence_ids=missing_evidence_ids,
        source_review_packet_required=True,
        source_review_packet_id=source_review_packet_id,
    )


async def _latest_release_decision(db: AsyncSession, *, tenant_id: int) -> ReleaseDecision | None:
    return await db.scalar(
        select(ReleaseDecision)
        .where(ReleaseDecision.tenant_id == tenant_id)
        .order_by(desc(ReleaseDecision.created_at), desc(ReleaseDecision.id))
        .limit(1)
    )


async def _latest_model_version_for_tenant(db: AsyncSession, *, tenant_id: int) -> ModelVersionRecord | None:
    return await db.scalar(
        select(ModelVersionRecord)
        .join(ModelRegistryRecord, ModelRegistryRecord.model_id == ModelVersionRecord.model_id)
        .where(ModelRegistryRecord.tenant_id == tenant_id)
        .order_by(desc(ModelVersionRecord.created_at), desc(ModelVersionRecord.id))
        .limit(1)
    )


async def build_final_action_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
    limit: int = 50,
) -> FinalActionReadinessResponse:
    audit_packet = await build_review_workbench_audit_packet(db, tenant_id=tenant_id, limit=limit)
    latest_release_decision = await _latest_release_decision(db, tenant_id=tenant_id)
    latest_model_version = await _latest_model_version_for_tenant(db, tenant_id=tenant_id)
    request_draft_count = int(
        await db.scalar(
            select(func.count())
            .select_from(FinalActionRequestDraftRecord)
            .where(FinalActionRequestDraftRecord.tenant_id == tenant_id)
        )
        or 0
    )
    external_share_count = int(
        await db.scalar(
            select(func.count())
            .select_from(ExternalReleaseShareRecord)
            .where(ExternalReleaseShareRecord.tenant_id == tenant_id)
        )
        or 0
    )

    evidence_pack_ids = [
        str(evidence_id)
        for evidence_id in audit_packet.get("evidence_pack_ids", [])
        if isinstance(evidence_id, str) and evidence_id
    ]
    pending_count = _audit_bucket_count(audit_packet, "pending")
    approved_count = _audit_bucket_count(audit_packet, "approved")
    rejected_count = _audit_bucket_count(audit_packet, "rejected")
    audit_packet_hash = compute_review_packet_hash(audit_packet)
    source_review_packet = await get_review_packet_snapshot_by_hash(
        db,
        tenant_id=tenant_id,
        packet_hash=audit_packet_hash,
    )
    source_review_packet_id = source_review_packet.source_review_packet_id if source_review_packet is not None else None

    shared_blockers = [
        "request_draft_required",
        "approved_request_draft_required",
        "specific_final_action_approver_role_required",
    ]
    if source_review_packet_id is None:
        shared_blockers.append("immutable_source_review_packet_not_persisted")
    if pending_count:
        shared_blockers.append(f"pending_review_items:{pending_count}")

    release_missing = []
    if latest_release_decision is None:
        release_missing.append("tenant_scoped_release_decision")
    if not evidence_pack_ids:
        release_missing.append("review_workbench_evidence_pack")
    release_blockers = [
        *shared_blockers,
    ]
    if latest_release_decision is None:
        release_blockers.append("release_decision_missing")
    elif latest_release_decision.decision != "review_required":
        release_blockers.append(f"release_decision_not_review_required:{latest_release_decision.decision}")

    model_missing = []
    if latest_model_version is None:
        model_missing.append("tenant_scoped_model_version")
    if not evidence_pack_ids:
        model_missing.append("benchmark_or_review_evidence_pack")
    model_blockers = [
        *shared_blockers,
    ]
    if latest_model_version is None:
        model_blockers.append("model_version_missing")
    elif latest_model_version.status != "ready_for_review":
        model_blockers.append(f"model_version_not_ready_for_review:{latest_model_version.status}")

    share_missing = []
    if latest_release_decision is None:
        share_missing.append("tenant_scoped_release_decision")
    if not evidence_pack_ids:
        share_missing.append("redacted_release_packet_evidence")
    share_blockers = [
        *shared_blockers,
        "release_packet_attachment_required",
        "allowlisted_recipient_scope_required",
        "redaction_policy_attestation_required",
    ]
    if latest_release_decision is None:
        share_blockers.append("release_decision_missing")
    elif latest_release_decision.decision != "approved":
        share_blockers.append(f"release_decision_not_approved:{latest_release_decision.decision}")

    evidence_chain_id = source_review_packet_id or (evidence_pack_ids[0] if evidence_pack_ids else None)
    governance_envelope = build_release_governance_envelope(
        evidence_chain_id=evidence_chain_id,
        source_boundary="final_action_readiness_read_model",
        review_required_reason="final_actions_require_immutable_source_packet_and_human_review",
    )

    return FinalActionReadinessResponse(
        schema_version="final_action_readiness_v1",
        generated_at=datetime.now(UTC).isoformat(),
        tenant_id=tenant_id,
        review_only=True,
        audit_schema_available=True,
        request_draft_schema_available=True,
        source_review_packet_required=True,
        source_review_packet_id=source_review_packet_id,
        current_state=FinalActionReadinessState(
            latest_release_decision_id=latest_release_decision.id if latest_release_decision else None,
            latest_release_decision=latest_release_decision.decision if latest_release_decision else None,
            latest_model_version_id=latest_model_version.model_version_id if latest_model_version else None,
            latest_model_version_status=latest_model_version.status if latest_model_version else None,
            pending_review_items=pending_count,
            resolved_review_items=approved_count + rejected_count,
            evidence_pack_ids=evidence_pack_ids,
            external_share_record_created=external_share_count > 0,
            final_action_request_drafts_created=request_draft_count > 0,
        ),
        governance_envelope=governance_envelope,
        actions=[
            _action_item(
                action="final_release_approval",
                blockers=release_blockers,
                required_roles=["final_release_approver"],
                required_evidence_ids=evidence_pack_ids,
                missing_evidence_ids=release_missing,
                source_review_packet_id=source_review_packet_id,
            ),
            _action_item(
                action="model_activation",
                blockers=model_blockers,
                required_roles=["model_governance_approver"],
                required_evidence_ids=evidence_pack_ids,
                missing_evidence_ids=model_missing,
                source_review_packet_id=source_review_packet_id,
            ),
            _action_item(
                action="external_release_share",
                blockers=share_blockers,
                required_roles=["external_release_share_approver"],
                required_evidence_ids=evidence_pack_ids,
                missing_evidence_ids=share_missing,
                source_review_packet_id=source_review_packet_id,
            ),
        ],
        guardrails=[
            "readiness_only",
            "readiness_query_does_not_execute_final_actions",
            "no_assistant_confirmation_authority",
            "no_human_approval_disposition_authority",
            "tenant_scoped_read_model",
            "final_action_routes_require_approved_request_draft",
            "external_network_send_requires_separate_gate",
            "no_hardware_execution",
        ],
    )
