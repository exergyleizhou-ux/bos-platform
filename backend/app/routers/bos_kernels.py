"""Lightweight BOS v3.2-v3.5 consolidation kernel endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import (
    EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
    require_any_role,
    require_minimum_role,
    resolve_user_roles,
)
from app.engine.external_knowledge_candidates import (
    get_external_knowledge_candidate_payload,
    list_external_knowledge_candidate_payloads,
    list_model_provider_capability_candidates,
)
from app.models import Batch, User
from app.models_bos import (
    BenchmarkCaseRecord,
    BenchmarkRunRecord,
    EvidencePackRecord,
    HistoricalReplayRunRecord,
    HumanApprovalRequestRecord,
    KnowledgeRelationRecord,
    ModelRegistryRecord,
    ModelVersionRecord,
)
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate
from app.schemas.simulation_lab import SimulationScenarioCreate, SimulationInitialState
from app.services.bos_benchmark_cases import ensure_default_benchmark_cases
from app.services.evidence_service import create_evidence_pack
from app.services.external_knowledge_activation_service import (
    ACTIVATION_EXECUTED_PREDICATE,
    ACTIVATION_ROLLED_BACK_PREDICATE,
    activation_scope_for_patch,
    default_activation_runtime_paths,
    get_active_external_candidate_payload,
    get_validated_external_registry_patch,
    list_runtime_activation_events,
    resolve_active_runtime_activation,
)
from app.services.simulation_lab_service import create_scenario, list_runs, run_scenario

router = APIRouter()

RUNTIME_ACTIVATION_APPROVER_ROLES = [EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE]


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


class HistoricalReplayCreate(BaseModel):
    counterfactual_actions: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkRunCreate(BaseModel):
    suite_name: str = "simulation_lab_regression"
    scorecard: dict[str, Any] = Field(default_factory=dict)
    threshold_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ModelRegistryCreate(BaseModel):
    name: str
    task_type: str
    version: str = "v1"
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    benchmark_run_id: str | None = None


class ModelGovernanceRequest(BaseModel):
    benchmark_run_id: str
    decision: str = Field(default="request_review", pattern="^(request_review|approve_for_review|reject)$")
    reason: str = Field(..., min_length=1)


class KnowledgeRelationCreate(BaseModel):
    subject_type: str
    subject_id: str
    predicate: str
    object_type: str
    object_id: str
    evidence_pack_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ExternalKnowledgePromotionRequest(BaseModel):
    candidate_type: str = Field(
        ...,
        pattern="^(lca_factor_candidate|tea_factor_candidate|compliance_rule_candidate|release_gate_candidate|model_provider_capability_candidate)$",
    )
    candidate_key: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ExternalKnowledgePromotionResolve(BaseModel):
    approved: bool
    reason: str = Field(..., min_length=1)


class ExternalKnowledgeManualRegistryPatch(BaseModel):
    approval_request_id: str = Field(..., min_length=1)
    registry_version: str | None = None
    reason: str = Field(..., min_length=1)


class ExternalKnowledgeRuntimeActivationDraftCreate(BaseModel):
    registry_patch_id: str = Field(..., min_length=1)
    activation_scope: dict[str, Any] = Field(default_factory=dict)
    operator_attestation: str = Field(..., min_length=1)
    review_evidence_ids: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None


class ExternalKnowledgeRuntimeActivationDraftResolve(BaseModel):
    approved: bool
    reason: str = Field(..., min_length=1)


class ExternalKnowledgeRuntimeActivationExecute(BaseModel):
    activation_request_id: str = Field(..., min_length=1)
    expected_previous_active_registry_patch_id: str | None = None
    operator_attestation: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)


class ExternalKnowledgeRuntimeActivationRollback(BaseModel):
    activation_id: str = Field(..., min_length=1)
    operator_attestation: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)


def _case_response(record: BenchmarkCaseRecord) -> dict[str, Any]:
    return {
        "case_id": record.case_id,
        "name": record.name,
        "scenario_payload": record.scenario_payload,
        "expected_metrics": record.expected_metrics or {},
        "review_status": (record.expected_metrics or {}).get("review_status", "pending_review"),
        "human_review_required": True,
    }


def _benchmark_run_response(record: BenchmarkRunRecord) -> dict[str, Any]:
    return {
        "benchmark_run_id": record.benchmark_run_id,
        "suite_name": record.suite_name,
        "scorecard": record.scorecard,
        "evidence_pack_id": record.evidence_pack_id,
        "created_at": record.created_at,
    }


def _knowledge_relation_response(record: KnowledgeRelationRecord) -> dict[str, Any]:
    return {
        "relation_id": record.relation_id,
        "subject_type": record.subject_type,
        "subject_id": record.subject_id,
        "predicate": record.predicate,
        "object_type": record.object_type,
        "object_id": record.object_id,
        "evidence_pack_id": record.evidence_pack_id,
        "payload": record.payload or {},
        "created_at": record.created_at,
    }


def _candidate_uid(candidate_type: str, candidate_key: str) -> str:
    return f"{candidate_type}:{candidate_key}"


def _promotion_side_effects() -> dict[str, Any]:
    return {
        "promoted_to_validated_defaults": False,
        "species_db_mutated": False,
        "feedstock_db_mutated": False,
        "kernel_defaults_mutated": False,
        "provider_defaults_mutated": False,
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": False,
        "manual_default_patch_required": True,
    }


def _manual_registry_patch_side_effects() -> dict[str, Any]:
    return {
        "validated_external_registry_updated": True,
        "runtime_defaults_mutated": False,
        "species_db_mutated": False,
        "feedstock_db_mutated": False,
        "kernel_defaults_mutated": False,
        "provider_defaults_mutated": False,
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": False,
        "requires_separate_runtime_activation": True,
    }


def _promotion_request_response(
    approval: HumanApprovalRequestRecord,
    *,
    evidence_pack_id: str | None = None,
    relation: KnowledgeRelationRecord | None = None,
) -> dict[str, Any]:
    payload = approval.payload if isinstance(approval.payload, dict) else {}
    side_effects = payload.get("promotion_side_effects") if isinstance(payload.get("promotion_side_effects"), dict) else _promotion_side_effects()
    return {
        "approval_request_id": approval.approval_request_id,
        "status": approval.status,
        "subject_type": approval.subject_type,
        "subject_id": approval.subject_id,
        "candidate_type": payload.get("candidate_type"),
        "candidate_key": payload.get("candidate_key"),
        "candidate_uid": payload.get("candidate_uid", approval.subject_id),
        "reason": approval.reason,
        "evidence_pack_id": evidence_pack_id or payload.get("evidence_pack_id"),
        "knowledge_relation_id": relation.relation_id if relation else payload.get("knowledge_relation_id"),
        "review_gate": "explicit_human_review_required",
        "human_review_required": approval.status == "pending",
        "promoted_to_validated_defaults": False,
        "manual_default_patch_required": bool(side_effects.get("manual_default_patch_required", True)),
        "side_effects": side_effects,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
    }


def _manual_registry_patch_response(relation: KnowledgeRelationRecord) -> dict[str, Any]:
    payload = relation.payload if isinstance(relation.payload, dict) else {}
    return {
        "registry_patch_id": relation.relation_id,
        "status": "applied_to_validated_external_registry",
        "candidate_uid": relation.subject_id,
        "registry_key": relation.object_id,
        "registry_version": payload.get("registry_version"),
        "approval_request_id": payload.get("approval_request_id"),
        "evidence_pack_id": relation.evidence_pack_id,
        "validated_external_registry_updated": True,
        "runtime_defaults_mutated": False,
        "side_effects": payload.get("manual_registry_patch_side_effects", _manual_registry_patch_side_effects()),
        "created_at": relation.created_at,
    }


def _runtime_activation_side_effects(*, executed: bool = False, rollback: bool = False) -> dict[str, Any]:
    return {
        "validated_external_registry_updated": False,
        "runtime_defaults_mutated": False,
        "species_db_mutated": False,
        "feedstock_db_mutated": False,
        "hardcoded_defaults_mutated": False,
        "candidate_store_mutated": False,
        "release_decision": "unchanged",
        "model_activation": False,
        "external_share": False,
        "final_action_audit_record": False,
        "scoped_runtime_read_path_changed": executed or rollback,
        "rollback_event_written": rollback,
    }


def _registry_patch_payload(relation: KnowledgeRelationRecord | None) -> dict[str, Any]:
    if relation is None or not isinstance(relation.payload, dict):
        return {}
    return relation.payload


async def _latest_active_state_for_patch(
    db: AsyncSession,
    *,
    tenant_id: int,
    patch: KnowledgeRelationRecord,
) -> dict[str, Any]:
    patch_payload = _registry_patch_payload(patch)
    scope = activation_scope_for_patch(tenant_id=tenant_id, patch_payload=patch_payload)
    return await resolve_active_runtime_activation(db, tenant_id=tenant_id, scope_key=str(scope["scope_key"]))


def _activation_draft_response(approval: HumanApprovalRequestRecord, patch: KnowledgeRelationRecord | None = None) -> dict[str, Any]:
    payload = approval.payload if isinstance(approval.payload, dict) else {}
    return {
        "activation_request_id": approval.approval_request_id,
        "status": approval.status,
        "registry_patch_id": approval.subject_id,
        "candidate_type": payload.get("candidate_type"),
        "candidate_key": payload.get("candidate_key"),
        "registry_version": payload.get("registry_version"),
        "activation_scope": payload.get("activation_scope", {}),
        "previous_active_registry_patch_id": payload.get("previous_active_registry_patch_id"),
        "previous_active_registry_version": payload.get("previous_active_registry_version"),
        "rollback_target_registry_patch_id": payload.get("rollback_target_registry_patch_id"),
        "rollback_target_activation_id": payload.get("rollback_target_activation_id"),
        "operator_attestation": payload.get("operator_attestation"),
        "review_evidence_ids": payload.get("review_evidence_ids", []),
        "evidence_pack_id": payload.get("evidence_pack_id") or (patch.evidence_pack_id if patch else None),
        "review_gate": "explicit_human_review_required_before_runtime_activation",
        "human_review_required": approval.status == "pending",
        "runtime_activation_executed": False,
        "side_effects": payload.get("runtime_activation_side_effects", _runtime_activation_side_effects()),
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
    }


async def _find_activation_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    activation_request_id: str,
) -> HumanApprovalRequestRecord | None:
    return await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == activation_request_id,
            HumanApprovalRequestRecord.tenant_id == tenant_id,
            HumanApprovalRequestRecord.subject_type == "validated_external_knowledge_runtime_activation",
        )
    )


async def _activation_execution_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
    activation_request_id: str,
) -> dict[str, Any]:
    approval = await _find_activation_draft(db, tenant_id=tenant_id, activation_request_id=activation_request_id)
    blockers: list[str] = []
    if approval is None:
        return {
            "activation_request_id": activation_request_id,
            "activation_ready": False,
            "executable_now": False,
            "blockers": ["activation_request_not_found"],
            "target_found": False,
            "source_evidence_pack_ids": [],
            "required_roles": RUNTIME_ACTIVATION_APPROVER_ROLES,
            "side_effects_if_executed": _runtime_activation_side_effects(executed=True),
            "guardrails": ["tenant_scoped_activation_gate", "manual_registry_patch_required", "rollback_metadata_required"],
        }
    payload = approval.payload if isinstance(approval.payload, dict) else {}
    patch = await get_validated_external_registry_patch(db, tenant_id=tenant_id, registry_patch_id=approval.subject_id)
    if patch is None:
        blockers.append("registry_patch_not_found")
    if approval.status != "approved":
        blockers.append(f"activation_draft_not_approved:{approval.status}")
    if not payload.get("operator_attestation"):
        blockers.append("operator_attestation_required")
    evidence_ids = [str(item) for item in payload.get("review_evidence_ids", []) if item]
    if patch and patch.evidence_pack_id and patch.evidence_pack_id not in evidence_ids:
        evidence_ids.append(patch.evidence_pack_id)
    if not evidence_ids:
        blockers.append("review_evidence_required")
    if "previous_active_registry_patch_id" not in payload:
        blockers.append("previous_active_registry_version_required")
    if "rollback_target_registry_patch_id" not in payload:
        blockers.append("rollback_target_required")
    activation_scope = payload.get("activation_scope") if isinstance(payload.get("activation_scope"), dict) else {}
    if not activation_scope.get("scope_key"):
        blockers.append("activation_scope_required")
    ready = not blockers
    return {
        "activation_request_id": activation_request_id,
        "registry_patch_id": approval.subject_id,
        "status": approval.status,
        "activation_ready": ready,
        "executable_now": ready,
        "blockers": blockers,
        "target_found": patch is not None,
        "activation_scope": activation_scope,
        "previous_active_registry_patch_id": payload.get("previous_active_registry_patch_id"),
        "previous_active_registry_version": payload.get("previous_active_registry_version"),
        "rollback_target_registry_patch_id": payload.get("rollback_target_registry_patch_id"),
        "rollback_target_activation_id": payload.get("rollback_target_activation_id"),
        "source_evidence_pack_ids": evidence_ids,
        "required_roles": RUNTIME_ACTIVATION_APPROVER_ROLES,
        "would_write_activation_record_now": ready,
        "side_effects_if_executed": _runtime_activation_side_effects(executed=True),
        "guardrails": [
            "tenant_scoped_activation_gate",
            "manual_registry_patch_required",
            "approved_activation_draft_required",
            "operator_attestation_required",
            "rollback_metadata_required",
            "no_release_decision_mutation",
            "no_model_activation",
            "no_external_share",
        ],
    }


def _activation_event_response(relation: KnowledgeRelationRecord) -> dict[str, Any]:
    payload = relation.payload if isinstance(relation.payload, dict) else {}
    return {
        "activation_id": relation.relation_id,
        "registry_patch_id": relation.subject_id,
        "predicate": relation.predicate,
        "activation_scope": payload.get("activation_scope", {}),
        "registry_version": payload.get("registry_version"),
        "previous_active_registry_patch_id": payload.get("previous_active_registry_patch_id"),
        "previous_active_registry_version": payload.get("previous_active_registry_version"),
        "rollback_target_registry_patch_id": payload.get("rollback_target_registry_patch_id"),
        "rollback_target_activation_id": payload.get("rollback_target_activation_id"),
        "idempotency_key": payload.get("idempotency_key"),
        "status": payload.get("status", "recorded"),
        "side_effects": payload.get("runtime_activation_side_effects", _runtime_activation_side_effects()),
        "evidence_pack_id": relation.evidence_pack_id,
        "created_at": relation.created_at,
    }


async def _create_kernel_evidence_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    subject_type: str,
    subject_id: str,
    title: str,
    payload: dict[str, Any],
    item_kind: str,
    source_kind: str,
    uncertainty_level: str = "medium",
):
    return await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type=subject_type,
            subject_id=subject_id,
            title=title,
            summary="BOS v3 kernel evidence generated from immutable API inputs.",
            verification_status="review_required",
            human_review_required=True,
            items=[
                EvidenceItemCreate(
                    kind=item_kind,
                    source_kind=source_kind,
                    source_ref="bos_kernels_v3",
                    payload=jsonable_encoder(payload),
                    uncertainty_level=uncertainty_level,
                )
            ],
        ),
    )


def _benchmark_scenario_payload(record: BenchmarkCaseRecord, *, index: int) -> SimulationScenarioCreate:
    payload = record.scenario_payload or {}
    initial_state_payload = payload.get("initial_state") if isinstance(payload.get("initial_state"), dict) else {}
    return SimulationScenarioCreate(
        species=str(payload.get("species", "BSF")),
        feedstock=str(payload.get("feedstock", "mixed_food_waste")),
        scenario=payload.get("scenario", "normal"),
        initial_state=SimulationInitialState(**initial_state_payload),
        cycles=int(payload.get("cycles", 8)),
        seed=int(payload.get("seed", 17 + index)),
        policy=payload.get("policy", "rule_based"),
    )


def _score_benchmark_case(
    *,
    record: BenchmarkCaseRecord,
    expected_metrics: dict[str, Any],
    simulation_id: str,
    run_id: str | None,
    ending_risk: float,
    audit_event_count: int,
    cycle_count: int,
    evidence_pack_id: str | None,
) -> dict[str, Any]:
    expected = expected_metrics
    assertions: list[dict[str, Any]] = []
    passed = True
    if "max_ending_risk" in expected:
        max_ending_risk = float(expected["max_ending_risk"])
        assertion_passed = ending_risk <= max_ending_risk
        assertions.append(
            {
                "metric": "ending_risk",
                "actual": ending_risk,
                "expected_max": max_ending_risk,
                "passed": assertion_passed,
            }
        )
        passed = passed and assertion_passed
    if expected.get("audit_required"):
        assertion_passed = audit_event_count >= cycle_count
        assertions.append(
            {
                "metric": "audit_event_count",
                "actual": audit_event_count,
                "expected_min": cycle_count,
                "passed": assertion_passed,
            }
        )
        passed = passed and assertion_passed
    return {
        "case_id": record.case_id,
        "name": record.name,
        "status": "passed" if passed else "failed",
        "simulation_id": simulation_id,
        "run_id": run_id,
        "evidence_pack_id": evidence_pack_id,
        "metrics": {
            "ending_risk": ending_risk,
            "audit_event_count": audit_event_count,
            "cycle_count": cycle_count,
        },
        "assertions": assertions,
        "expected_metrics": expected,
    }


async def _run_benchmark_cases(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    cases: list[BenchmarkCaseRecord],
    threshold_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scored_cases: list[dict[str, Any]] = []
    threshold_overrides = threshold_overrides or {}
    for index, case in enumerate(cases):
        expected_metrics = {
            **(case.expected_metrics or {}),
            **threshold_overrides.get(case.case_id, {}),
        }
        scenario = await create_scenario(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=_benchmark_scenario_payload(case, index=index),
        )
        run = await run_scenario(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            simulation_id=scenario.simulation_id,
        )
        if run is None:
            scored_cases.append(
                {
                    "case_id": case.case_id,
                    "name": case.name,
                    "status": "failed",
                    "metrics": {},
                    "assertions": [{"metric": "run_created", "passed": False}],
                    "expected_metrics": expected_metrics,
                }
            )
            continue
        run_history = await list_runs(db, tenant_id=tenant_id, simulation_id=scenario.simulation_id)
        latest_run = run_history[0] if run_history else None
        scored_cases.append(
            _score_benchmark_case(
                record=case,
                expected_metrics=expected_metrics,
                simulation_id=scenario.simulation_id,
                run_id=latest_run.run_id if latest_run else None,
                ending_risk=run.summary.ending_risk,
                audit_event_count=run.summary.audit_event_count,
                cycle_count=run.summary.cycle_count,
                evidence_pack_id=latest_run.evidence_pack_id if latest_run else None,
            )
        )
    passed_count = sum(1 for item in scored_cases if item["status"] == "passed")
    failed_count = len(scored_cases) - passed_count
    return {
        "status": "ready_for_review" if failed_count == 0 else "blocked",
        "suite_gate": "human_review_required",
        "passed_count": passed_count,
        "failed_count": failed_count,
        "case_count": len(scored_cases),
        "cases": scored_cases,
    }


@router.post("/replay/batches/{batch_id}", status_code=status.HTTP_201_CREATED)
async def create_historical_replay_run(
    batch_id: int,
    payload: HistoricalReplayCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    batch = await db.scalar(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == current_user.tenant_id))
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    record = HistoricalReplayRunRecord(
        replay_id=_new_id("HRP"),
        batch_id=batch_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        immutable_snapshot={
            "id": batch.id,
            "batch_id": batch.batch_id,
            "species": batch.species,
            "substrate": batch.substrate,
            "dm_in": batch.dm_in,
            "dm_out": batch.dm_out,
            "status": batch.status,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
        },
        counterfactual_actions=payload.counterfactual_actions,
        outcome={"status": "benchmark_case_candidate", "original_batch_mutated": False},
    )
    db.add(record)
    await db.flush()
    pack = await _create_kernel_evidence_pack(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="historical_replay",
        subject_id=record.replay_id,
        title=f"Historical replay evidence for batch {batch.batch_id}",
        payload={
            "immutable_snapshot": record.immutable_snapshot,
            "counterfactual_actions": record.counterfactual_actions,
            "outcome": record.outcome,
        },
        item_kind="historical_replay_snapshot",
        source_kind="operator_input",
    )
    record.evidence_pack_id = pack.evidence_pack_id
    await db.commit()
    await db.refresh(record)
    return {
        "replay_id": record.replay_id,
        "immutable_snapshot": record.immutable_snapshot,
        "counterfactual_actions": record.counterfactual_actions or [],
        "outcome": record.outcome,
        "evidence_pack_id": record.evidence_pack_id,
    }


@router.get("/replay/runs/{replay_id}")
async def get_historical_replay_run(
    replay_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    record = await db.scalar(
        select(HistoricalReplayRunRecord).where(
            HistoricalReplayRunRecord.replay_id == replay_id,
            HistoricalReplayRunRecord.tenant_id == current_user.tenant_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Replay run not found")
    return {
        "replay_id": record.replay_id,
        "immutable_snapshot": record.immutable_snapshot,
        "counterfactual_actions": record.counterfactual_actions or [],
        "outcome": record.outcome,
        "evidence_pack_id": record.evidence_pack_id,
    }


@router.get("/benchmarks/cases")
async def list_benchmark_cases(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await ensure_default_benchmark_cases(db)
    result = await db.execute(
        select(BenchmarkCaseRecord)
        .where((BenchmarkCaseRecord.tenant_id.is_(None)) | (BenchmarkCaseRecord.tenant_id == current_user.tenant_id))
        .order_by(BenchmarkCaseRecord.id)
    )
    return [_case_response(record) for record in result.scalars().all()]


@router.get("/model-providers/capabilities")
async def list_model_provider_capabilities(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    providers = []
    active_count = 0
    for provider in list_model_provider_capability_candidates():
        active_provider = await get_active_external_candidate_payload(
            db,
            tenant_id=current_user.tenant_id,
            candidate_type="model_provider_capability_candidate",
            candidate_key=str(provider["model_id"]),
        )
        if active_provider is not None:
            active_count += 1
            providers.append(
                {
                    **provider,
                    **{
                        key: value
                        for key, value in active_provider.items()
                        if key in provider or key in {"source_kind", "source_ref", "review_status", "human_review_required"}
                    },
                    "runtime_activation_status": "active",
                    "registry_patch_id": active_provider.get("registry_patch_id"),
                    "registry_version": active_provider.get("registry_version"),
                    "activation_id": active_provider.get("activation_id"),
                    "activation_scope": active_provider.get("activation_scope"),
                    "metadata_policy": "active_registry_overlay_recheck_before_runtime_change",
                }
            )
        else:
            providers.append(
                {
                    **provider,
                    "runtime_activation_status": "inactive",
                    "metadata_policy": "metadata_only_until_human_review_and_runtime_activation",
                }
            )
    return {
        "providers": providers,
        "count": len(providers),
        "active_provider_count": active_count,
        "review_gate": "metadata_only_until_human_review",
        "human_review_required": True,
        "checked_date_policy": "provider pricing, context, retention, and rate limits must be rechecked before promotion",
        "runtime_defaults_mutated": False,
        "requires_separate_runtime_activation": active_count == 0,
    }


@router.get("/external-knowledge/candidates")
async def list_external_knowledge_candidates_endpoint(
    candidate_type: str | None = None,
    current_user: User = Depends(require_minimum_role("operator")),
):
    del current_user
    allowed_types = {
        "lca_factor_candidate",
        "tea_factor_candidate",
        "compliance_rule_candidate",
        "release_gate_candidate",
        "model_provider_capability_candidate",
    }
    if candidate_type is not None and candidate_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported candidate type")
    candidates = list_external_knowledge_candidate_payloads(candidate_type=candidate_type)  # type: ignore[arg-type]
    return {
        "candidates": candidates,
        "count": len(candidates),
        "review_gate": "explicit_human_review_required_before_manual_promotion",
        "human_review_required": True,
        "promotion_policy": {
            "request_only": True,
            "auto_promote": False,
            "validated_defaults_mutated": False,
            "manual_default_patch_required_after_approval": True,
        },
    }


@router.post("/external-knowledge/promotion-requests", status_code=status.HTTP_201_CREATED)
async def request_external_knowledge_promotion(
    payload: ExternalKnowledgePromotionRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    candidate = get_external_knowledge_candidate_payload(
        candidate_type=payload.candidate_type,  # type: ignore[arg-type]
        key=payload.candidate_key,
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External knowledge candidate not found")
    candidate_uid = _candidate_uid(payload.candidate_type, payload.candidate_key)
    existing = await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.tenant_id == current_user.tenant_id,
            HumanApprovalRequestRecord.subject_type == "external_knowledge_candidate",
            HumanApprovalRequestRecord.subject_id == candidate_uid,
            HumanApprovalRequestRecord.status == "pending",
        )
    )
    if existing is not None:
        return _promotion_request_response(existing)
    pack = await _create_kernel_evidence_pack(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="external_knowledge_candidate",
        subject_id=candidate_uid,
        title=f"External knowledge promotion request for {payload.candidate_key}",
        payload={
            "candidate": candidate,
            "reason": payload.reason,
            "review_gate": "explicit_human_review_required_before_manual_promotion",
            "promotion_side_effects": _promotion_side_effects(),
        },
        item_kind="external_knowledge_promotion_request",
        source_kind=str(candidate.get("source_kind", "candidate_metadata")),
        uncertainty_level="high",
    )
    approval = HumanApprovalRequestRecord(
        approval_request_id=_new_id("HAR"),
        release_decision_id=None,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="external_knowledge_candidate",
        subject_id=candidate_uid,
        status="pending",
        reason=payload.reason,
        payload=jsonable_encoder(
            {
                "candidate_type": payload.candidate_type,
                "candidate_key": payload.candidate_key,
                "candidate_uid": candidate_uid,
                "candidate": candidate,
                "evidence_pack_id": pack.evidence_pack_id,
                "review_gate": "explicit_human_review_required_before_manual_promotion",
                "promotion_side_effects": _promotion_side_effects(),
            }
        ),
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return _promotion_request_response(approval, evidence_pack_id=pack.evidence_pack_id)


@router.post("/external-knowledge/promotion-requests/{approval_request_id}/resolve")
async def resolve_external_knowledge_promotion(
    approval_request_id: str,
    payload: ExternalKnowledgePromotionResolve,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    approval = await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == approval_request_id,
            HumanApprovalRequestRecord.tenant_id == current_user.tenant_id,
            HumanApprovalRequestRecord.subject_type == "external_knowledge_candidate",
        )
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External knowledge promotion request not found")
    prior_payload = approval.payload if isinstance(approval.payload, dict) else {}
    if approval.status != "pending":
        return _promotion_request_response(approval)
    side_effects = _promotion_side_effects()
    approval.status = "approved" if payload.approved else "rejected"
    approval.reason = payload.reason
    approval.resolved_at = datetime.now(UTC)
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("KREL"),
        tenant_id=current_user.tenant_id,
        subject_type="external_knowledge_candidate",
        subject_id=approval.subject_id,
        predicate="promotion_approved_for_manual_default_patch" if payload.approved else "promotion_rejected",
        object_type="validated_default_registry",
        object_id="manual_patch_required" if payload.approved else "not_promoted",
        evidence_pack_id=prior_payload.get("evidence_pack_id"),
        payload=jsonable_encoder(
            {
                "approval_request_id": approval.approval_request_id,
                "approved": payload.approved,
                "reason": payload.reason,
                "review_gate": "explicit_human_review_required",
                "candidate_type": prior_payload.get("candidate_type"),
                "candidate_key": prior_payload.get("candidate_key"),
                "candidate_uid": prior_payload.get("candidate_uid", approval.subject_id),
                "promotion_side_effects": side_effects,
            }
        ),
    )
    db.add(relation)
    approval.payload = jsonable_encoder(
        {
            **prior_payload,
            "knowledge_relation_id": relation.relation_id,
            "promotion_resolution": {
                "approved": payload.approved,
                "resolved_by_user_id": current_user.id,
                "reason": payload.reason,
                "scope": "promotion_review_record_only",
                "side_effects": side_effects,
            },
            "promotion_side_effects": side_effects,
        }
    )
    await db.commit()
    await db.refresh(approval)
    await db.refresh(relation)
    return _promotion_request_response(approval, relation=relation)


@router.post("/external-knowledge/manual-registry-patches", status_code=status.HTTP_201_CREATED)
async def apply_external_knowledge_manual_registry_patch(
    payload: ExternalKnowledgeManualRegistryPatch,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    approval = await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == payload.approval_request_id,
            HumanApprovalRequestRecord.tenant_id == current_user.tenant_id,
            HumanApprovalRequestRecord.subject_type == "external_knowledge_candidate",
        )
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External knowledge promotion request not found")
    if approval.status != "approved":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="External knowledge promotion request is not approved")
    approval_payload = approval.payload if isinstance(approval.payload, dict) else {}
    candidate_type = str(approval_payload.get("candidate_type", ""))
    candidate_key = str(approval_payload.get("candidate_key", ""))
    candidate = get_external_knowledge_candidate_payload(
        candidate_type=candidate_type,  # type: ignore[arg-type]
        key=candidate_key,
    )
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="External knowledge candidate not found")
    existing = await db.scalar(
        select(KnowledgeRelationRecord).where(
            KnowledgeRelationRecord.tenant_id == current_user.tenant_id,
            KnowledgeRelationRecord.subject_type == "external_knowledge_candidate",
            KnowledgeRelationRecord.subject_id == approval.subject_id,
            KnowledgeRelationRecord.predicate == "manual_registry_patch_applied",
            KnowledgeRelationRecord.object_type == "validated_external_knowledge_registry",
        )
    )
    if existing is not None:
        return _manual_registry_patch_response(existing)
    registry_version = payload.registry_version or datetime.now(UTC).strftime("external-knowledge-registry-%Y%m%d")
    registry_key = f"{candidate_type}:{candidate_key}:{registry_version}"
    pack = await _create_kernel_evidence_pack(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="validated_external_knowledge_registry_patch",
        subject_id=registry_key,
        title=f"Manual registry patch for {candidate_key}",
        payload={
            "candidate": candidate,
            "approval_request_id": approval.approval_request_id,
            "approval_relation_id": approval_payload.get("knowledge_relation_id"),
            "registry_version": registry_version,
            "reason": payload.reason,
            "manual_registry_patch_side_effects": _manual_registry_patch_side_effects(),
        },
        item_kind="manual_validated_external_registry_patch",
        source_kind=str(candidate.get("source_kind", "candidate_metadata")),
        uncertainty_level="medium",
    )
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("KREL"),
        tenant_id=current_user.tenant_id,
        subject_type="external_knowledge_candidate",
        subject_id=approval.subject_id,
        predicate="manual_registry_patch_applied",
        object_type="validated_external_knowledge_registry",
        object_id=registry_key,
        evidence_pack_id=pack.evidence_pack_id,
        payload=jsonable_encoder(
            {
                "approval_request_id": approval.approval_request_id,
                "approval_relation_id": approval_payload.get("knowledge_relation_id"),
                "candidate_type": candidate_type,
                "candidate_key": candidate_key,
                "candidate_uid": approval.subject_id,
                "candidate": candidate,
                "registry_version": registry_version,
                "reason": payload.reason,
                "review_gate": "approved_promotion_required_before_manual_patch",
                "manual_registry_patch_side_effects": _manual_registry_patch_side_effects(),
            }
        ),
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return _manual_registry_patch_response(relation)


@router.get("/external-knowledge/validated-defaults")
async def list_validated_external_knowledge_registry(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(KnowledgeRelationRecord)
        .where(
            KnowledgeRelationRecord.tenant_id == current_user.tenant_id,
            KnowledgeRelationRecord.subject_type == "external_knowledge_candidate",
            KnowledgeRelationRecord.predicate == "manual_registry_patch_applied",
            KnowledgeRelationRecord.object_type == "validated_external_knowledge_registry",
        )
        .order_by(KnowledgeRelationRecord.created_at.desc(), KnowledgeRelationRecord.id.desc())
    )
    patches = [_manual_registry_patch_response(record) for record in result.scalars().all()]
    return {
        "registry": patches,
        "count": len(patches),
        "registry_type": "validated_external_knowledge_registry",
        "runtime_defaults_mutated": False,
        "requires_separate_runtime_activation": True,
    }


@router.get("/external-knowledge/runtime-activation/readiness")
async def get_external_knowledge_runtime_activation_readiness(
    registry_patch_id: str | None = None,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    patch = None
    if registry_patch_id:
        patch = await get_validated_external_registry_patch(db, tenant_id=current_user.tenant_id, registry_patch_id=registry_patch_id)
        if patch is None:
            return {
                "schema_version": "external_knowledge_runtime_activation_readiness_v1",
                "tenant_id": current_user.tenant_id,
                "activation_ready": False,
                "executable": False,
                "target_found": False,
                "registry_patch_id": registry_patch_id,
                "blockers": ["registry_patch_not_found"],
                "required_roles": RUNTIME_ACTIVATION_APPROVER_ROLES,
                "guardrails": ["readiness_only", "manual_registry_patch_required", "no_runtime_default_mutation"],
            }
    patch_payload = _registry_patch_payload(patch)
    scope = activation_scope_for_patch(tenant_id=current_user.tenant_id, patch_payload=patch_payload) if patch else {}
    active_state = (
        await resolve_active_runtime_activation(db, tenant_id=current_user.tenant_id, scope_key=str(scope["scope_key"]))
        if scope
        else {}
    )
    blockers = ["approved_activation_draft_required", "operator_attestation_required", "rollback_metadata_required"]
    return {
        "schema_version": "external_knowledge_runtime_activation_readiness_v1",
        "tenant_id": current_user.tenant_id,
        "activation_ready": False,
        "executable": False,
        "target_found": patch is not None,
        "registry_patch_id": registry_patch_id,
        "activation_scope": scope,
        "current_active_state": active_state,
        "blockers": blockers,
        "required_roles": RUNTIME_ACTIVATION_APPROVER_ROLES,
        "side_effects_if_executed": _runtime_activation_side_effects(executed=True),
        "guardrails": [
            "readiness_only",
            "manual_registry_patch_required",
            "explicit_activation_draft_required",
            "runtime_kernels_read_only_active_registry_version",
            "rollback_required_before_scope_switch",
            "no_release_decision_mutation",
            "no_model_activation",
            "no_external_share",
        ],
    }


@router.get("/external-knowledge/runtime-activation/state")
async def list_external_knowledge_runtime_activation_state(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    events = await list_runtime_activation_events(db, tenant_id=current_user.tenant_id)
    scope_keys = sorted({event.object_id for event in events})
    states = [
        await resolve_active_runtime_activation(db, tenant_id=current_user.tenant_id, scope_key=scope_key)
        for scope_key in scope_keys
    ]
    return {
        "schema_version": "external_knowledge_runtime_activation_state_v1",
        "tenant_id": current_user.tenant_id,
        "runtime_defaults_mutated": False,
        "active_scopes": states,
        "activation_event_count": len(events),
        "guardrails": [
            "tenant_scoped_runtime_activation",
            "runtime_reads_active_registry_version_only",
            "fallback_defaults_when_no_active_version",
        ],
    }


@router.post("/external-knowledge/runtime-activation/drafts", status_code=status.HTTP_201_CREATED)
async def create_external_knowledge_runtime_activation_draft(
    payload: ExternalKnowledgeRuntimeActivationDraftCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    patch = await get_validated_external_registry_patch(db, tenant_id=current_user.tenant_id, registry_patch_id=payload.registry_patch_id)
    if patch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validated external registry patch not found")
    patch_payload = _registry_patch_payload(patch)
    candidate_type = str(patch_payload.get("candidate_type", ""))
    candidate_key = str(patch_payload.get("candidate_key", ""))
    base_scope = activation_scope_for_patch(tenant_id=current_user.tenant_id, patch_payload=patch_payload)
    requested_scope = payload.activation_scope if isinstance(payload.activation_scope, dict) else {}
    activation_scope = {
        **requested_scope,
        **base_scope,
        "runtime_paths": requested_scope.get("runtime_paths") or default_activation_runtime_paths(candidate_type),
    }
    active_state = await resolve_active_runtime_activation(
        db,
        tenant_id=current_user.tenant_id,
        scope_key=str(activation_scope["scope_key"]),
    )
    existing = await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.tenant_id == current_user.tenant_id,
            HumanApprovalRequestRecord.subject_type == "validated_external_knowledge_runtime_activation",
            HumanApprovalRequestRecord.subject_id == payload.registry_patch_id,
            HumanApprovalRequestRecord.status == "pending",
        )
    )
    if existing is not None:
        return _activation_draft_response(existing, patch)
    review_evidence_ids = [str(item) for item in payload.review_evidence_ids if item]
    if patch.evidence_pack_id and patch.evidence_pack_id not in review_evidence_ids:
        review_evidence_ids.append(patch.evidence_pack_id)
    pack = await _create_kernel_evidence_pack(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="validated_external_knowledge_runtime_activation",
        subject_id=payload.registry_patch_id,
        title=f"Runtime activation draft for {candidate_key}",
        payload={
            "registry_patch_id": payload.registry_patch_id,
            "registry_version": patch_payload.get("registry_version"),
            "activation_scope": activation_scope,
            "previous_active_state": active_state,
            "operator_attestation": payload.operator_attestation,
            "review_evidence_ids": review_evidence_ids,
            "runtime_activation_side_effects": _runtime_activation_side_effects(),
        },
        item_kind="external_knowledge_runtime_activation_draft",
        source_kind="operator_input",
        uncertainty_level="high",
    )
    if pack.evidence_pack_id not in review_evidence_ids:
        review_evidence_ids.append(pack.evidence_pack_id)
    approval = HumanApprovalRequestRecord(
        approval_request_id=_new_id("EKRA"),
        release_decision_id=None,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="validated_external_knowledge_runtime_activation",
        subject_id=payload.registry_patch_id,
        status="pending",
        reason=payload.operator_attestation,
        payload=jsonable_encoder(
            {
                "registry_patch_id": payload.registry_patch_id,
                "registry_key": patch.object_id,
                "registry_version": patch_payload.get("registry_version"),
                "candidate_type": candidate_type,
                "candidate_key": candidate_key,
                "candidate_uid": patch.subject_id,
                "activation_scope": activation_scope,
                "previous_active_registry_patch_id": active_state.get("active_registry_patch_id"),
                "previous_active_registry_version": active_state.get("active_registry_version"),
                "previous_active_activation_id": active_state.get("active_activation_id"),
                "rollback_target_registry_patch_id": active_state.get("active_registry_patch_id"),
                "rollback_target_registry_version": active_state.get("active_registry_version"),
                "rollback_target_activation_id": active_state.get("active_activation_id"),
                "operator_attestation": payload.operator_attestation,
                "review_evidence_ids": review_evidence_ids,
                "evidence_pack_id": pack.evidence_pack_id,
                "idempotency_key": payload.idempotency_key or f"runtime-activate:{payload.registry_patch_id}:{activation_scope['scope_key']}",
                "runtime_activation_side_effects": _runtime_activation_side_effects(),
                "review_gate": "explicit_human_review_required_before_runtime_activation",
            }
        ),
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return _activation_draft_response(approval, patch)


@router.post("/external-knowledge/runtime-activation/drafts/{activation_request_id}/resolve")
async def resolve_external_knowledge_runtime_activation_draft(
    activation_request_id: str,
    payload: ExternalKnowledgeRuntimeActivationDraftResolve,
    current_user: User = Depends(require_any_role(EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    approval = await _find_activation_draft(db, tenant_id=current_user.tenant_id, activation_request_id=activation_request_id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime activation draft not found")
    if approval.status != "pending":
        patch = await get_validated_external_registry_patch(db, tenant_id=current_user.tenant_id, registry_patch_id=approval.subject_id)
        return _activation_draft_response(approval, patch)
    prior_payload = approval.payload if isinstance(approval.payload, dict) else {}
    reviewer_roles = sorted(await resolve_user_roles(db, current_user))
    approval.status = "approved" if payload.approved else "rejected"
    approval.reason = payload.reason
    approval.resolved_at = datetime.now(UTC)
    approval.payload = jsonable_encoder(
        {
            **prior_payload,
            "review_resolution": {
                "approved": payload.approved,
                "reason": payload.reason,
                "reviewed_by_user_id": current_user.id,
                "reviewed_by_user_role": current_user.role,
                "reviewed_by_user_roles": reviewer_roles,
                "required_role": EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
                "scope": "runtime_activation_review_only",
                "side_effects": _runtime_activation_side_effects(),
            },
        }
    )
    await db.commit()
    await db.refresh(approval)
    patch = await get_validated_external_registry_patch(db, tenant_id=current_user.tenant_id, registry_patch_id=approval.subject_id)
    return _activation_draft_response(approval, patch)


@router.get("/external-knowledge/runtime-activation/drafts/{activation_request_id}/execution-readiness")
async def get_external_knowledge_runtime_activation_execution_readiness(
    activation_request_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    return await _activation_execution_readiness(db, tenant_id=current_user.tenant_id, activation_request_id=activation_request_id)


@router.post("/external-knowledge/runtime-activation/executions", status_code=status.HTTP_201_CREATED)
async def execute_external_knowledge_runtime_activation(
    payload: ExternalKnowledgeRuntimeActivationExecute,
    current_user: User = Depends(require_any_role(EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    readiness = await _activation_execution_readiness(
        db,
        tenant_id=current_user.tenant_id,
        activation_request_id=payload.activation_request_id,
    )
    if not readiness.get("activation_ready"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=readiness)
    approval = await _find_activation_draft(db, tenant_id=current_user.tenant_id, activation_request_id=payload.activation_request_id)
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime activation draft not found")
    approval_payload = approval.payload if isinstance(approval.payload, dict) else {}
    previous_patch_id = approval_payload.get("previous_active_registry_patch_id")
    if payload.expected_previous_active_registry_patch_id != previous_patch_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="previous_active_registry_patch_mismatch")
    activation_scope = approval_payload.get("activation_scope") if isinstance(approval_payload.get("activation_scope"), dict) else {}
    scope_key = str(activation_scope.get("scope_key", ""))
    executor_roles = sorted(await resolve_user_roles(db, current_user))
    for event in await list_runtime_activation_events(db, tenant_id=current_user.tenant_id, scope_key=scope_key):
        event_payload = event.payload if isinstance(event.payload, dict) else {}
        if event_payload.get("idempotency_key") == payload.idempotency_key and event.predicate == ACTIVATION_EXECUTED_PREDICATE:
            return _activation_event_response(event)
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("EKRACT"),
        tenant_id=current_user.tenant_id,
        subject_type="validated_external_knowledge_registry_patch",
        subject_id=approval.subject_id,
        predicate=ACTIVATION_EXECUTED_PREDICATE,
        object_type="active_external_knowledge_runtime_scope",
        object_id=scope_key,
        evidence_pack_id=approval_payload.get("evidence_pack_id"),
        payload=jsonable_encoder(
            {
                "activation_request_id": approval.approval_request_id,
                "registry_patch_id": approval.subject_id,
                "registry_version": approval_payload.get("registry_version"),
                "candidate_type": approval_payload.get("candidate_type"),
                "candidate_key": approval_payload.get("candidate_key"),
                "activation_scope": activation_scope,
                "previous_active_registry_patch_id": previous_patch_id,
                "previous_active_registry_version": approval_payload.get("previous_active_registry_version"),
                "rollback_target_registry_patch_id": approval_payload.get("rollback_target_registry_patch_id"),
                "rollback_target_registry_version": approval_payload.get("rollback_target_registry_version"),
                "rollback_target_activation_id": approval_payload.get("rollback_target_activation_id"),
                "operator_attestation": payload.operator_attestation,
                "executed_by_user_id": current_user.id,
                "executed_by_user_role": current_user.role,
                "executed_by_user_roles": executor_roles,
                "required_role": EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
                "review_evidence_ids": readiness.get("source_evidence_pack_ids", []),
                "idempotency_key": payload.idempotency_key,
                "status": "active",
                "runtime_activation_side_effects": _runtime_activation_side_effects(executed=True),
            }
        ),
    )
    approval.status = "executed"
    approval.payload = jsonable_encoder({**approval_payload, "runtime_activation_id": relation.relation_id, "execution": relation.payload})
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return _activation_event_response(relation)


@router.post("/external-knowledge/runtime-activation/rollbacks", status_code=status.HTTP_201_CREATED)
async def rollback_external_knowledge_runtime_activation(
    payload: ExternalKnowledgeRuntimeActivationRollback,
    current_user: User = Depends(require_any_role(EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE)),
    db: AsyncSession = Depends(get_async_session),
):
    activation = await db.scalar(
        select(KnowledgeRelationRecord).where(
            KnowledgeRelationRecord.tenant_id == current_user.tenant_id,
            KnowledgeRelationRecord.relation_id == payload.activation_id,
            KnowledgeRelationRecord.predicate == ACTIVATION_EXECUTED_PREDICATE,
            KnowledgeRelationRecord.object_type == "active_external_knowledge_runtime_scope",
        )
    )
    if activation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime activation record not found")
    activation_payload = activation.payload if isinstance(activation.payload, dict) else {}
    scope_key = activation.object_id
    rollback_actor_roles = sorted(await resolve_user_roles(db, current_user))
    for event in await list_runtime_activation_events(db, tenant_id=current_user.tenant_id, scope_key=scope_key):
        event_payload = event.payload if isinstance(event.payload, dict) else {}
        if event_payload.get("idempotency_key") == payload.idempotency_key and event.predicate == ACTIVATION_ROLLED_BACK_PREDICATE:
            return _activation_event_response(event)
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("EKRROLL"),
        tenant_id=current_user.tenant_id,
        subject_type="validated_external_knowledge_runtime_activation",
        subject_id=activation.relation_id,
        predicate=ACTIVATION_ROLLED_BACK_PREDICATE,
        object_type="active_external_knowledge_runtime_scope",
        object_id=scope_key,
        evidence_pack_id=activation.evidence_pack_id,
        payload=jsonable_encoder(
            {
                "rolled_back_activation_id": activation.relation_id,
                "rolled_back_registry_patch_id": activation.subject_id,
                "registry_version": activation_payload.get("registry_version"),
                "activation_scope": activation_payload.get("activation_scope", {}),
                "rollback_target_registry_patch_id": activation_payload.get("rollback_target_registry_patch_id"),
                "rollback_target_registry_version": activation_payload.get("rollback_target_registry_version"),
                "rollback_target_activation_id": activation_payload.get("rollback_target_activation_id"),
                "operator_attestation": payload.operator_attestation,
                "rolled_back_by_user_id": current_user.id,
                "rolled_back_by_user_role": current_user.role,
                "rolled_back_by_user_roles": rollback_actor_roles,
                "required_role": EXTERNAL_RUNTIME_ACTIVATION_APPROVER_ROLE,
                "idempotency_key": payload.idempotency_key,
                "status": "rolled_back",
                "runtime_activation_side_effects": _runtime_activation_side_effects(rollback=True),
            }
        ),
    )
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return _activation_event_response(relation)


@router.post("/benchmarks/runs", status_code=status.HTTP_201_CREATED)
async def create_benchmark_run(
    payload: BenchmarkRunCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    cases = await ensure_default_benchmark_cases(db)
    scorecard = payload.scorecard or await _run_benchmark_cases(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        cases=cases,
        threshold_overrides=payload.threshold_overrides,
    )
    record = BenchmarkRunRecord(
        benchmark_run_id=_new_id("BMR"),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        suite_name=payload.suite_name,
        scorecard=scorecard,
    )
    db.add(record)
    await db.flush()
    pack = await _create_kernel_evidence_pack(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        subject_type="benchmark_run",
        subject_id=record.benchmark_run_id,
        title=f"Benchmark evidence for {record.suite_name}",
        payload={"suite_name": record.suite_name, "scorecard": scorecard},
        item_kind="benchmark_scorecard",
        source_kind="deterministic_model",
    )
    record.evidence_pack_id = pack.evidence_pack_id
    await db.commit()
    await db.refresh(record)
    return _benchmark_run_response(record)


@router.get("/benchmarks/runs")
async def list_benchmark_runs(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(BenchmarkRunRecord)
        .where(BenchmarkRunRecord.tenant_id == current_user.tenant_id)
        .order_by(BenchmarkRunRecord.created_at.desc(), BenchmarkRunRecord.id.desc())
    )
    return [_benchmark_run_response(record) for record in result.scalars().all()]


@router.get("/benchmarks/runs/{benchmark_run_id}")
async def get_benchmark_run(
    benchmark_run_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    record = await db.scalar(
        select(BenchmarkRunRecord).where(
            BenchmarkRunRecord.benchmark_run_id == benchmark_run_id,
            BenchmarkRunRecord.tenant_id == current_user.tenant_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark run not found")
    return _benchmark_run_response(record)


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def register_model(
    payload: ModelRegistryCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    benchmark_run: BenchmarkRunRecord | None = None
    if payload.benchmark_run_id:
        benchmark_run = await db.scalar(
            select(BenchmarkRunRecord).where(
                BenchmarkRunRecord.benchmark_run_id == payload.benchmark_run_id,
                BenchmarkRunRecord.tenant_id == current_user.tenant_id,
            )
        )
        if benchmark_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark run not found")
    model = ModelRegistryRecord(
        model_id=_new_id("MOD"),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=payload.name,
        task_type=payload.task_type,
        status="candidate",
    )
    db.add(model)
    await db.flush()
    version = ModelVersionRecord(
        model_version_id=_new_id("MVN"),
        model_id=model.model_id,
        version=payload.version,
        metadata_payload={
            **payload.metadata_payload,
            "benchmark_run_id": payload.benchmark_run_id,
            "evidence_pack_id": benchmark_run.evidence_pack_id if benchmark_run else None,
            "governance_status": "candidate",
            "source_ref": payload.metadata_payload.get("source_ref", "operator_registered_candidate"),
            "checked_date": payload.metadata_payload.get("checked_date", datetime.now(UTC).date().isoformat()),
            "review_status": "pending_review",
            "human_review_required": True,
            "fallback_candidate": bool(payload.metadata_payload.get("fallback_candidate", False)),
        },
        status="candidate",
    )
    db.add(version)
    await db.commit()
    return {
        "model_id": model.model_id,
        "model_version_id": version.model_version_id,
        "status": model.status,
        "version_status": version.status,
        "metadata_payload": version.metadata_payload,
    }


@router.get("/models")
async def list_models(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(ModelRegistryRecord)
        .where(ModelRegistryRecord.tenant_id == current_user.tenant_id)
        .order_by(ModelRegistryRecord.id)
    )
    return [{"model_id": item.model_id, "name": item.name, "task_type": item.task_type, "status": item.status} for item in result.scalars().all()]


@router.get("/models/{model_id}/versions")
async def list_model_versions(
    model_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    if await db.scalar(
        select(ModelRegistryRecord).where(
            ModelRegistryRecord.model_id == model_id,
            ModelRegistryRecord.tenant_id == current_user.tenant_id,
        )
    ) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    result = await db.execute(select(ModelVersionRecord).where(ModelVersionRecord.model_id == model_id).order_by(ModelVersionRecord.id))
    return [
        {
            "model_version_id": item.model_version_id,
            "model_id": item.model_id,
            "version": item.version,
            "status": item.status,
            "metadata_payload": item.metadata_payload or {},
        }
        for item in result.scalars().all()
    ]


@router.post("/models/{model_id}/versions/{model_version_id}/governance", status_code=status.HTTP_201_CREATED)
async def create_model_governance_decision(
    model_id: str,
    model_version_id: str,
    payload: ModelGovernanceRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    model = await db.scalar(
        select(ModelRegistryRecord).where(
            ModelRegistryRecord.model_id == model_id,
            ModelRegistryRecord.tenant_id == current_user.tenant_id,
        )
    )
    version = await db.scalar(
        select(ModelVersionRecord).where(
            ModelVersionRecord.model_id == model_id,
            ModelVersionRecord.model_version_id == model_version_id,
        )
    )
    if model is None or version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found")
    benchmark_run = await db.scalar(
        select(BenchmarkRunRecord).where(
            BenchmarkRunRecord.benchmark_run_id == payload.benchmark_run_id,
            BenchmarkRunRecord.tenant_id == current_user.tenant_id,
        )
    )
    if benchmark_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benchmark run not found")
    requested_review = payload.decision in {"request_review", "approve_for_review"}
    governance_decision = "request_review" if requested_review else "reject"
    version.status = "ready_for_review" if requested_review else "rejected"
    metadata = dict(version.metadata_payload or {})
    metadata["governance_status"] = version.status
    metadata["governance_reason"] = payload.reason
    metadata["benchmark_run_id"] = benchmark_run.benchmark_run_id
    metadata["evidence_pack_id"] = benchmark_run.evidence_pack_id
    version.metadata_payload = metadata
    model.status = "review_required" if requested_review else "rejected"
    approval_request: HumanApprovalRequestRecord | None = None
    if requested_review:
        approval_request = HumanApprovalRequestRecord(
            approval_request_id=_new_id("HAR"),
            release_decision_id=None,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            subject_type="model_version",
            subject_id=model_version_id,
            status="pending",
            reason=payload.reason,
            payload={
                "model_id": model_id,
                "model_version_id": model_version_id,
                "benchmark_run_id": payload.benchmark_run_id,
                "evidence_pack_id": benchmark_run.evidence_pack_id,
                "governance_decision": governance_decision,
            },
        )
        db.add(approval_request)
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("KREL"),
        tenant_id=current_user.tenant_id,
        subject_type="model_version",
        subject_id=model_version_id,
        predicate="evaluated_by" if requested_review else "rejected_by",
        object_type="benchmark_run",
        object_id=benchmark_run.benchmark_run_id,
        evidence_pack_id=benchmark_run.evidence_pack_id,
        payload={"decision": governance_decision, "reason": payload.reason},
    )
    db.add(relation)
    await db.commit()
    return {
        "model_id": model.model_id,
        "model_version_id": version.model_version_id,
        "model_status": model.status,
        "version_status": version.status,
        "knowledge_relation_id": relation.relation_id,
        "evidence_pack_id": benchmark_run.evidence_pack_id,
        "approval_request_id": approval_request.approval_request_id if approval_request else None,
    }


@router.post("/knowledge/relations", status_code=status.HTTP_201_CREATED)
async def create_knowledge_relation(
    payload: KnowledgeRelationCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    if payload.evidence_pack_id:
        pack = await db.scalar(
            select(EvidencePackRecord).where(
                EvidencePackRecord.evidence_pack_id == payload.evidence_pack_id,
                EvidencePackRecord.tenant_id == current_user.tenant_id,
            )
        )
        if pack is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence pack not found")
    record = KnowledgeRelationRecord(
        relation_id=_new_id("KREL"),
        tenant_id=current_user.tenant_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        predicate=payload.predicate,
        object_type=payload.object_type,
        object_id=payload.object_id,
        evidence_pack_id=payload.evidence_pack_id,
        payload=payload.payload,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _knowledge_relation_response(record)


@router.get("/knowledge/relations")
async def list_knowledge_relations(
    subject_type: str | None = None,
    subject_id: str | None = None,
    predicate: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    evidence_pack_id: str | None = None,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(KnowledgeRelationRecord).where(
        (KnowledgeRelationRecord.tenant_id.is_(None)) | (KnowledgeRelationRecord.tenant_id == current_user.tenant_id)
    )
    if subject_type:
        query = query.where(KnowledgeRelationRecord.subject_type == subject_type)
    if subject_id:
        query = query.where(KnowledgeRelationRecord.subject_id == subject_id)
    if predicate:
        query = query.where(KnowledgeRelationRecord.predicate == predicate)
    if object_type:
        query = query.where(KnowledgeRelationRecord.object_type == object_type)
    if object_id:
        query = query.where(KnowledgeRelationRecord.object_id == object_id)
    if evidence_pack_id:
        query = query.where(KnowledgeRelationRecord.evidence_pack_id == evidence_pack_id)
    result = await db.execute(query.order_by(KnowledgeRelationRecord.id))
    return [_knowledge_relation_response(item) for item in result.scalars().all()]


@router.get("/knowledge/relations/{relation_id}")
async def get_knowledge_relation(
    relation_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    record = await db.scalar(
        select(KnowledgeRelationRecord).where(
            KnowledgeRelationRecord.relation_id == relation_id,
            KnowledgeRelationRecord.tenant_id == current_user.tenant_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge relation not found")
    return _knowledge_relation_response(record)
