"""Runtime activation read helpers for validated external knowledge.

Activation is represented as tenant-scoped knowledge relation events. Candidate
promotion and manual registry patch records remain separate from runtime use.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.external_knowledge_candidates import get_external_knowledge_candidate_payload
from app.models_bos import KnowledgeRelationRecord

ACTIVATION_EXECUTED_PREDICATE = "runtime_activation_executed"
ACTIVATION_ROLLED_BACK_PREDICATE = "runtime_activation_rolled_back"


def activation_scope_key(*, tenant_id: int, candidate_type: str, candidate_key: str) -> str:
    return f"tenant:{tenant_id}:{candidate_type}:{candidate_key}"


def default_activation_runtime_paths(candidate_type: str) -> list[str]:
    return {
        "lca_factor_candidate": ["lca.factor_runtime"],
        "tea_factor_candidate": ["tea.factor_runtime"],
        "compliance_rule_candidate": ["compliance.rule_runtime"],
        "release_gate_candidate": ["release.gate_runtime"],
        "model_provider_capability_candidate": ["provider.capability_runtime"],
    }.get(candidate_type, ["external_knowledge.runtime"])


def activation_scope_for_patch(*, tenant_id: int, patch_payload: dict[str, Any]) -> dict[str, Any]:
    candidate_type = str(patch_payload.get("candidate_type", ""))
    candidate_key = str(patch_payload.get("candidate_key", ""))
    return {
        "tenant_id": tenant_id,
        "tenant_scoped": True,
        "candidate_type": candidate_type,
        "candidate_key": candidate_key,
        "scope_key": activation_scope_key(
            tenant_id=tenant_id,
            candidate_type=candidate_type,
            candidate_key=candidate_key,
        ),
        "runtime_paths": default_activation_runtime_paths(candidate_type),
    }


async def get_validated_external_registry_patch(
    db: AsyncSession,
    *,
    tenant_id: int,
    registry_patch_id: str,
) -> KnowledgeRelationRecord | None:
    return await db.scalar(
        select(KnowledgeRelationRecord)
        .where(
            KnowledgeRelationRecord.tenant_id == tenant_id,
            KnowledgeRelationRecord.relation_id == registry_patch_id,
            KnowledgeRelationRecord.predicate == "manual_registry_patch_applied",
            KnowledgeRelationRecord.object_type == "validated_external_knowledge_registry",
        )
        .limit(1)
    )


async def list_runtime_activation_events(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope_key: str | None = None,
) -> list[KnowledgeRelationRecord]:
    query = select(KnowledgeRelationRecord).where(
        KnowledgeRelationRecord.tenant_id == tenant_id,
        KnowledgeRelationRecord.predicate.in_([ACTIVATION_EXECUTED_PREDICATE, ACTIVATION_ROLLED_BACK_PREDICATE]),
        KnowledgeRelationRecord.object_type == "active_external_knowledge_runtime_scope",
    )
    if scope_key:
        query = query.where(KnowledgeRelationRecord.object_id == scope_key)
    result = await db.execute(query.order_by(KnowledgeRelationRecord.created_at.asc(), KnowledgeRelationRecord.id.asc()))
    return list(result.scalars().all())


async def resolve_active_runtime_activation(
    db: AsyncSession,
    *,
    tenant_id: int,
    scope_key: str,
) -> dict[str, Any]:
    events = await list_runtime_activation_events(db, tenant_id=tenant_id, scope_key=scope_key)
    active_registry_patch_id: str | None = None
    active_activation_id: str | None = None
    active_registry_version: str | None = None
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.predicate == ACTIVATION_EXECUTED_PREDICATE:
            active_registry_patch_id = event.subject_id
            active_activation_id = event.relation_id
            active_registry_version = payload.get("registry_version")
        elif event.predicate == ACTIVATION_ROLLED_BACK_PREDICATE:
            active_registry_patch_id = payload.get("rollback_target_registry_patch_id")
            active_activation_id = payload.get("rollback_target_activation_id")
            active_registry_version = payload.get("rollback_target_registry_version")
    return {
        "scope_key": scope_key,
        "active_registry_patch_id": active_registry_patch_id,
        "active_activation_id": active_activation_id,
        "active_registry_version": active_registry_version,
        "event_count": len(events),
        "activation_required_before_runtime_use": active_registry_patch_id is None,
    }


async def get_active_external_factor(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_type: str,
    candidate_key: str,
) -> dict[str, Any] | None:
    candidate = await get_active_external_candidate_payload(
        db,
        tenant_id=tenant_id,
        candidate_type=candidate_type,
        candidate_key=candidate_key,
    )
    if candidate is None or candidate.get("value") is None:
        return None
    return {
        **candidate,
        "value": float(candidate["value"]),
    }


async def get_active_external_candidate_payload(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_type: str,
    candidate_key: str,
) -> dict[str, Any] | None:
    scope_key = activation_scope_key(tenant_id=tenant_id, candidate_type=candidate_type, candidate_key=candidate_key)
    active_state = await resolve_active_runtime_activation(db, tenant_id=tenant_id, scope_key=scope_key)
    registry_patch_id = active_state.get("active_registry_patch_id")
    if not registry_patch_id:
        return None
    patch = await get_validated_external_registry_patch(db, tenant_id=tenant_id, registry_patch_id=str(registry_patch_id))
    if patch is None:
        return None
    payload = patch.payload if isinstance(patch.payload, dict) else {}
    if payload.get("candidate_type") != candidate_type or payload.get("candidate_key") != candidate_key:
        return None
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else None
    if candidate is None:
        candidate = get_external_knowledge_candidate_payload(candidate_type=candidate_type, key=candidate_key)  # type: ignore[arg-type]
    if not isinstance(candidate, dict):
        return None
    return {
        **candidate,
        "candidate_source_kind": candidate.get("source_kind"),
        "candidate_source_ref": candidate.get("source_ref"),
        "review_status": "runtime_activated",
        "human_review_required": False,
        "used_in_kernel": True,
        "source_kind": "validated_external_registry_activation",
        "source_ref": patch.object_id,
        "registry_patch_id": patch.relation_id,
        "registry_version": payload.get("registry_version"),
        "activation_id": active_state.get("active_activation_id"),
        "activation_scope": activation_scope_for_patch(tenant_id=tenant_id, patch_payload=payload),
    }
