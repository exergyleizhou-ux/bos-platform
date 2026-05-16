"""Non-mutating preflight contract for future final action requests."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.final_actions import FinalActionPreflightInput, FinalActionPreflightResult, FinalActionType
from app.services.final_action_review_packet_service import get_review_packet_snapshot_by_source_id


PREVIEW_ONLY_PREFLIGHT_GUARDRAILS = [
    "preflight_only_no_mutation",
    "final_actions_not_executed",
    "final_action_request_drafts_not_created",
    "final_action_audit_records_not_written",
    "no_assistant_confirmation_authority",
    "no_human_approval_disposition_authority",
    "tenant_scoped_read_model",
    "no_release_decision_mutation",
    "no_model_activation",
    "no_external_share_record",
    "no_hardware_execution",
]

_ACTION_REQUIRED_ROLES: dict[FinalActionType, list[str]] = {
    "final_release_approval": ["final_release_approver"],
    "model_activation": ["model_governance_approver"],
    "external_release_share": ["external_release_share_approver"],
}

_ACTION_ROUTE_BLOCKERS: dict[FinalActionType, str] = {
    "final_release_approval": "final_release_approval_route_not_executable",
    "model_activation": "model_activation_route_not_executable",
    "external_release_share": "external_release_share_route_not_executable",
}


async def preflight_final_action_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    request: FinalActionPreflightInput,
) -> FinalActionPreflightResult:
    """Evaluate final-action request shape without creating drafts or audit rows."""

    source_packet = await get_review_packet_snapshot_by_source_id(
        db,
        tenant_id=tenant_id,
        source_review_packet_id=request.source_review_packet_id,
    )
    source_review_packet_found = source_packet is not None
    evidence_pack_ids = [str(value) for value in source_packet.evidence_pack_ids] if source_packet is not None else []

    blockers = [
        "final_action_workflow_unavailable",
        _ACTION_ROUTE_BLOCKERS[request.action_type],
        "final_action_request_draft_writer_not_enabled",
        "final_action_audit_writer_not_enabled",
    ]
    if not source_review_packet_found:
        blockers.insert(0, "source_review_packet_not_found")

    return FinalActionPreflightResult(
        tenant_id=tenant_id,
        action_type=request.action_type,
        target_type=request.target_type,
        target_id=request.target_id,
        requested_by_user_id=request.requested_by_user_id,
        source_review_packet_id=request.source_review_packet_id,
        idempotency_key=request.idempotency_key,
        eligible=False,
        executable=False,
        blockers=blockers,
        required_roles=_ACTION_REQUIRED_ROLES[request.action_type],
        source_review_packet_found=source_review_packet_found,
        evidence_pack_ids=evidence_pack_ids,
        would_create_request_draft=False,
        would_write_audit_record=False,
        guardrails=PREVIEW_ONLY_PREFLIGHT_GUARDRAILS,
    )
