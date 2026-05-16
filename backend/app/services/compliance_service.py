"""Compliance and product quality gate service."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.external_knowledge_candidates import build_candidate_context
from app.models import Batch
from app.models_bos import BatchAssayRecord, ReleaseGateRecord
from app.schemas.compliance import (
    BatchAssayCreate,
    BatchAssayResponse,
    ComplianceEvaluateRequest,
    ComplianceRulesResponse,
    ReleaseGateResponse,
)
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate
from app.services.evidence_service import create_evidence_pack
from app.services.external_knowledge_activation_service import get_active_external_candidate_payload

REQUIRED_ASSAYS: dict[str, list[str]] = {
    "insect_dry_matter": ["moisture", "protein", "heavy_metals", "microbiology"],
    "insect_oil": ["moisture", "fatty_acid_profile", "heavy_metals", "microbiology"],
    "frass_organic_fertilizer": ["moisture", "nitrogen", "heavy_metals", "pathogens"],
    "residue_handling": ["moisture", "pathogens", "heavy_metals"],
}

THRESHOLD_RULES: dict[str, dict[str, dict[str, float]]] = {
    "insect_dry_matter": {
        "moisture": {"max": 12.0},
        "heavy_metals": {"max": 1.0},
        "microbiology": {"max": 0.0},
    },
    "insect_oil": {
        "moisture": {"max": 1.0},
        "heavy_metals": {"max": 1.0},
        "microbiology": {"max": 0.0},
    },
    "frass_organic_fertilizer": {
        "moisture": {"max": 35.0},
        "heavy_metals": {"max": 1.0},
        "pathogens": {"max": 0.0},
    },
    "residue_handling": {
        "moisture": {"max": 50.0},
        "pathogens": {"max": 0.0},
        "heavy_metals": {"max": 1.0},
    },
}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _assay_response(record: BatchAssayRecord) -> BatchAssayResponse:
    return BatchAssayResponse(
        assay_id=record.assay_id,
        batch_id=record.batch_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        assay_type=record.assay_type,
        value=record.value,
        unit=record.unit,
        payload=record.payload,
        created_at=record.created_at,
    )


def _gate_response(record: ReleaseGateRecord) -> ReleaseGateResponse:
    return ReleaseGateResponse(
        gate_id=record.gate_id,
        batch_id=record.batch_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        jurisdiction=record.jurisdiction,
        product_category=record.product_category,
        status=record.status,  # type: ignore[arg-type]
        missing_assays=record.missing_assays or [],
        blocked_reasons=record.blocked_reasons or [],
        human_review_required=record.human_review_required,
        evidence_pack_id=record.evidence_pack_id,
        payload=record.payload,
        created_at=record.created_at,
    )


def _list_payload_strings(payload: dict, key: str) -> list[str] | None:
    values = payload.get(key)
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        return None
    return list(values)


async def create_batch_assay(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    batch_id: int,
    payload: BatchAssayCreate,
) -> BatchAssayResponse | None:
    batch = await db.scalar(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id))
    if batch is None:
        return None
    record = BatchAssayRecord(
        assay_id=_new_id("ASY"),
        batch_id=batch_id,
        tenant_id=tenant_id,
        user_id=user_id,
        assay_type=payload.assay_type,
        value=payload.value,
        unit=payload.unit,
        payload=jsonable_encoder(payload.payload),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _assay_response(record)


async def evaluate_compliance(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: ComplianceEvaluateRequest,
) -> ReleaseGateResponse | None:
    batch = await db.scalar(select(Batch).where(Batch.id == payload.batch_id, Batch.tenant_id == tenant_id))
    if batch is None:
        return None
    assay_result = await db.execute(
        select(BatchAssayRecord).where(
            BatchAssayRecord.batch_id == payload.batch_id,
            BatchAssayRecord.tenant_id == tenant_id,
        )
    )
    assay_records = assay_result.scalars().all()
    available = {item.assay_type for item in assay_records}
    assay_by_type = {item.assay_type: item for item in assay_records}
    default_required = REQUIRED_ASSAYS[payload.product_category]
    default_threshold_rules = THRESHOLD_RULES.get(payload.product_category, {})
    compliance_candidate_key = f"{payload.product_category}.{payload.jurisdiction.lower()}"
    active_rule_candidate = await get_active_external_candidate_payload(
        db,
        tenant_id=tenant_id,
        candidate_type="compliance_rule_candidate",
        candidate_key=compliance_candidate_key,
    )
    active_rule_payload = active_rule_candidate.get("payload") if isinstance(active_rule_candidate, dict) else None
    if not isinstance(active_rule_payload, dict):
        active_rule_payload = {}
    active_required = _list_payload_strings(active_rule_payload, "required_assays")
    active_threshold_rules = active_rule_payload.get("threshold_rules")
    if not isinstance(active_threshold_rules, dict):
        active_threshold_rules = None
    required = active_required or default_required
    threshold_rules = active_threshold_rules or default_threshold_rules
    rule_source_kind = str(active_rule_candidate.get("source_kind")) if active_rule_candidate else "fallback_default"
    rule_source_ref = (
        str(active_rule_candidate.get("source_ref"))
        if active_rule_candidate
        else f"assumed_internal_rule:{payload.jurisdiction}:{payload.product_category}"
    )
    evidence_source_kind = (
        str(active_rule_candidate.get("candidate_source_kind") or "official_standard")
        if active_rule_candidate
        else "fallback_default"
    )
    rule_candidate_context = build_candidate_context(
        "compliance_rule_candidate",
        [payload.product_category, compliance_candidate_key],
    )
    release_gate_candidate_context = build_candidate_context(
        "release_gate_candidate",
        [payload.product_category, f"{payload.product_category}.{payload.jurisdiction.lower()}"],
    )
    missing = [item for item in required if item not in available]
    threshold_breaches: list[dict] = []
    for assay_type, rule in threshold_rules.items():
        assay = assay_by_type.get(assay_type)
        if assay is None or assay.value is None:
            continue
        max_value = rule.get("max")
        if max_value is not None and assay.value > max_value:
            threshold_breaches.append({"assay_type": assay_type, "value": assay.value, "max": max_value})
    blocked_reasons = [f"missing_assay:{item}" for item in missing]
    blocked_reasons.extend(f"threshold_breach:{item['assay_type']}" for item in threshold_breaches)
    ambiguous = payload.product_category in {"residue_handling"}
    status = "blocked" if missing or threshold_breaches else ("insufficient_evidence" if ambiguous else "ready_for_review")
    human_review_required = True
    review_gate = {
        "human_review_required": human_review_required,
        "rule_source": rule_source_kind,
        "rule_source_ref": rule_source_ref,
        "active_registry_rule": active_rule_candidate,
        "external_candidates_available": bool(rule_candidate_context["candidates"] or release_gate_candidate_context["candidates"]),
        "pending_candidates_not_used": active_rule_candidate is None,
        "rule_candidates": rule_candidate_context,
        "release_gate_candidates": release_gate_candidate_context,
    }
    pack = await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type="release_gate",
            subject_id=str(payload.batch_id),
            title=f"Compliance gate for batch {payload.batch_id}",
            summary=f"{payload.product_category} in {payload.jurisdiction}: {status}",
            verification_status=status,
            human_review_required=human_review_required,
            items=[
                EvidenceItemCreate(
                    kind="compliance_rules",
                    source_kind=evidence_source_kind,  # type: ignore[arg-type]
                    source_ref=rule_source_ref,
                    payload={
                        "required_assays": required,
                        "missing_assays": missing,
                        "threshold_breaches": threshold_breaches,
                        "review_gate": review_gate,
                    },
                    uncertainty_level="high" if missing or threshold_breaches else "medium",
                )
            ],
        ),
    )
    record = ReleaseGateRecord(
        gate_id=_new_id("GATE"),
        batch_id=payload.batch_id,
        tenant_id=tenant_id,
        user_id=user_id,
        jurisdiction=payload.jurisdiction,
        product_category=payload.product_category,
        status=status,
        missing_assays=missing,
        blocked_reasons=blocked_reasons,
        human_review_required=human_review_required,
        evidence_pack_id=pack.evidence_pack_id,
        payload={
            "required_assays": required,
            "available_assays": sorted(available),
            "threshold_breaches": threshold_breaches,
            "threshold_rules": threshold_rules,
            "review_gate": review_gate,
        },
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _gate_response(record)


async def list_release_gates(
    db: AsyncSession,
    *,
    tenant_id: int,
    batch_id: int,
) -> list[ReleaseGateResponse] | None:
    batch = await db.scalar(select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id))
    if batch is None:
        return None
    result = await db.execute(
        select(ReleaseGateRecord)
        .where(ReleaseGateRecord.batch_id == batch_id, ReleaseGateRecord.tenant_id == tenant_id)
        .order_by(ReleaseGateRecord.id)
    )
    return [_gate_response(record) for record in result.scalars().all()]


def get_compliance_rules() -> ComplianceRulesResponse:
    return ComplianceRulesResponse(rules=REQUIRED_ASSAYS)
