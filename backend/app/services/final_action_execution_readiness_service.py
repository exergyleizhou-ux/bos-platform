"""Read-only execution readiness gate for reviewed final-action drafts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import FinalActionRequestDraftRecord, ModelRegistryRecord, ModelVersionRecord, ReleaseDecision
from app.schemas.final_actions import FinalActionEffectSummary, FinalActionExecutionReadinessResponse
from app.services.final_action_review_packet_service import get_review_packet_snapshot_by_source_id

_ACTION_REQUIRED_ROLES: dict[str, list[str]] = {
    "final_release_approval": ["final_release_approver"],
    "model_activation": ["model_governance_approver"],
    "external_release_share": ["external_release_share_approver"],
}


async def _release_decision_state(
    db: AsyncSession,
    *,
    tenant_id: int,
    target_id: str,
) -> tuple[bool, dict, list[str]]:
    try:
        release_decision_id = int(target_id)
    except ValueError:
        return False, {}, ["release_decision_target_id_invalid"]

    release_decision = await db.get(ReleaseDecision, release_decision_id)
    if release_decision is None or release_decision.tenant_id != tenant_id:
        return False, {}, ["release_decision_not_found"]
    state = {
        "release_decision_id": release_decision.id,
        "decision": release_decision.decision,
        "reason_codes": release_decision.reason_codes or [],
    }
    blockers = []
    if release_decision.decision != "review_required":
        blockers.append(f"release_decision_not_review_required:{release_decision.decision}")
    return True, state, blockers


async def _model_version_state(
    db: AsyncSession,
    *,
    tenant_id: int,
    target_id: str,
) -> tuple[bool, dict, list[str]]:
    model_version = await db.scalar(
        select(ModelVersionRecord)
        .join(ModelRegistryRecord, ModelRegistryRecord.model_id == ModelVersionRecord.model_id)
        .where(
            ModelRegistryRecord.tenant_id == tenant_id,
            ModelVersionRecord.model_version_id == target_id,
        )
        .limit(1)
    )
    if model_version is None:
        return False, {}, ["model_version_not_found"]
    state = {
        "model_version_id": model_version.model_version_id,
        "model_id": model_version.model_id,
        "status": model_version.status,
    }
    blockers = []
    if model_version.status != "ready_for_review":
        blockers.append(f"model_version_not_ready_for_review:{model_version.status}")
    return True, state, blockers


async def _target_state(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft: FinalActionRequestDraftRecord,
) -> tuple[bool, dict, list[str]]:
    if draft.action_type == "final_release_approval":
        return await _release_decision_state(db, tenant_id=tenant_id, target_id=draft.target_id)
    if draft.action_type == "model_activation":
        return await _model_version_state(db, tenant_id=tenant_id, target_id=draft.target_id)
    if draft.action_type == "external_release_share":
        found, state, blockers = await _release_decision_state(db, tenant_id=tenant_id, target_id=draft.target_id)
        if not found:
            return found, state, blockers
        blockers = [
            blocker.replace("release_decision_not_review_required:", "release_decision_not_approved:")
            for blocker in blockers
        ]
        if state.get("decision") == "approved":
            blockers = []
        state["external_network_send"] = False
        state["outbound_delivery_gate"] = "separate_approval_required"
        return True, state, blockers
    return False, {}, [f"unsupported_final_action_type:{draft.action_type}"]


async def build_final_action_execution_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
    draft: FinalActionRequestDraftRecord,
) -> FinalActionExecutionReadinessResponse:
    source_packet = await get_review_packet_snapshot_by_source_id(
        db,
        tenant_id=tenant_id,
        source_review_packet_id=draft.source_review_packet_id,
    )
    source_found = source_packet is not None
    target_found, target_state, target_blockers = await _target_state(db, tenant_id=tenant_id, draft=draft)

    blockers: list[str] = []
    if draft.status != "review_approved_no_execution":
        blockers.append(f"draft_not_review_approved_no_execution:{draft.status}")
    if not source_found:
        blockers.append("source_review_packet_not_found")
    if not target_found:
        blockers.append("target_not_found")
    blockers.extend(target_blockers)
    ready = draft.status == "review_approved_no_execution" and source_found and target_found and not target_blockers
    effect_summary = FinalActionEffectSummary()
    if ready and draft.action_type == "final_release_approval":
        effect_summary.release_decision = "changed"
    elif ready and draft.action_type == "model_activation":
        effect_summary.release_decision = "unchanged"
        effect_summary.model_activation = True
    elif ready and draft.action_type == "external_release_share":
        effect_summary.release_decision = "unchanged"
        effect_summary.external_share = True

    return FinalActionExecutionReadinessResponse(
        tenant_id=tenant_id,
        final_action_request_id=draft.final_action_request_id,
        action_type=draft.action_type,
        target_type=draft.target_type,
        target_id=draft.target_id,
        draft_status=draft.status,
        ready_for_audited_execution=ready,
        executable_now=ready,
        blockers=blockers,
        target_found=target_found,
        target_state=target_state,
        source_review_packet_found=source_found,
        source_evidence_pack_ids=[str(value) for value in draft.source_evidence_pack_ids],
        required_roles=_ACTION_REQUIRED_ROLES.get(draft.action_type, []),
        would_write_audit_record_now=ready,
        side_effects_if_executed=effect_summary,
        guardrails=[
            "execution_readiness_only",
            "specific_final_action_approver_role_required",
            "no_assistant_confirmation_authority",
            "no_human_approval_disposition_authority",
            "tenant_scoped_read_model",
            "external_network_send_requires_separate_gate",
            "no_hardware_execution",
        ],
    )
