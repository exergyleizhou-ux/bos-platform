"""Minimal evidence kernel service."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import EvidenceItemRecord, EvidencePackRecord, InputSnapshotRecord
from app.schemas.evidence import (
    EvidenceItemCreate,
    EvidenceItemResponse,
    EvidencePackCreate,
    EvidencePackResponse,
    InputSnapshotResponse,
)


def stable_payload_hash(payload: Any) -> str:
    encoded = json.dumps(jsonable_encoder(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _item_response(record: EvidenceItemRecord) -> EvidenceItemResponse:
    return EvidenceItemResponse(
        evidence_item_id=record.evidence_item_id,
        evidence_pack_id=record.evidence_pack_id,
        tenant_id=record.tenant_id,
        kind=record.kind,
        source_kind=record.source_kind,
        source_ref=record.source_ref,
        payload=record.payload or {},
        confidence=record.confidence,
        uncertainty_level=record.uncertainty_level,
        created_at=record.created_at,
    )


async def create_input_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
) -> InputSnapshotResponse:
    encoded_payload = jsonable_encoder(payload)
    snapshot = InputSnapshotRecord(
        input_snapshot_id=_new_id("INP"),
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=encoded_payload,
        payload_hash=stable_payload_hash(encoded_payload),
    )
    db.add(snapshot)
    await db.flush()
    return InputSnapshotResponse(
        input_snapshot_id=snapshot.input_snapshot_id,
        tenant_id=snapshot.tenant_id,
        subject_type=snapshot.subject_type,
        subject_id=snapshot.subject_id,
        payload=snapshot.payload,
        payload_hash=snapshot.payload_hash,
        created_at=snapshot.created_at or datetime.now(UTC),
    )


async def get_input_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
    input_snapshot_id: str,
) -> InputSnapshotResponse | None:
    result = await db.execute(
        select(InputSnapshotRecord).where(
            InputSnapshotRecord.input_snapshot_id == input_snapshot_id,
            InputSnapshotRecord.tenant_id == tenant_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        return None
    return InputSnapshotResponse(
        input_snapshot_id=snapshot.input_snapshot_id,
        tenant_id=snapshot.tenant_id,
        subject_type=snapshot.subject_type,
        subject_id=snapshot.subject_id,
        payload=snapshot.payload,
        payload_hash=snapshot.payload_hash,
        created_at=snapshot.created_at,
    )


async def create_evidence_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: EvidencePackCreate,
) -> EvidencePackResponse:
    pack = EvidencePackRecord(
        evidence_pack_id=_new_id("EVP"),
        tenant_id=tenant_id,
        user_id=user_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        title=payload.title,
        summary=payload.summary,
        verification_status=payload.verification_status,
        human_review_required=payload.human_review_required,
    )
    db.add(pack)
    await db.flush()
    for item in payload.items:
        db.add(_new_item_record(pack.evidence_pack_id, tenant_id, item))
    await db.flush()
    return await get_evidence_pack(db, tenant_id=tenant_id, evidence_pack_id=pack.evidence_pack_id)  # type: ignore[return-value]


def _new_item_record(evidence_pack_id: str, tenant_id: int, item: EvidenceItemCreate) -> EvidenceItemRecord:
    return EvidenceItemRecord(
        evidence_item_id=_new_id("EVI"),
        evidence_pack_id=evidence_pack_id,
        tenant_id=tenant_id,
        kind=item.kind,
        source_kind=item.source_kind,
        source_ref=item.source_ref,
        payload=jsonable_encoder(item.payload),
        confidence=item.confidence,
        uncertainty_level=item.uncertainty_level,
    )


async def add_evidence_items(
    db: AsyncSession,
    *,
    tenant_id: int,
    evidence_pack_id: str,
    items: list[EvidenceItemCreate],
) -> list[EvidenceItemResponse]:
    records = [_new_item_record(evidence_pack_id, tenant_id, item) for item in items]
    for record in records:
        db.add(record)
    await db.flush()
    return [_item_response(record) for record in records]


async def get_evidence_pack(
    db: AsyncSession,
    *,
    tenant_id: int,
    evidence_pack_id: str,
) -> EvidencePackResponse | None:
    result = await db.execute(
        select(EvidencePackRecord).where(
            EvidencePackRecord.evidence_pack_id == evidence_pack_id,
            EvidencePackRecord.tenant_id == tenant_id,
        )
    )
    pack = result.scalar_one_or_none()
    if pack is None:
        return None
    return EvidencePackResponse(
        evidence_pack_id=pack.evidence_pack_id,
        tenant_id=pack.tenant_id,
        user_id=pack.user_id,
        subject_type=pack.subject_type,
        subject_id=pack.subject_id,
        title=pack.title,
        summary=pack.summary,
        verification_status=pack.verification_status,
        human_review_required=pack.human_review_required,
        created_at=pack.created_at,
        items=await list_evidence_items(db, tenant_id=tenant_id, evidence_pack_id=pack.evidence_pack_id),
    )


async def list_evidence_items(
    db: AsyncSession,
    *,
    tenant_id: int,
    evidence_pack_id: str,
) -> list[EvidenceItemResponse]:
    result = await db.execute(
        select(EvidenceItemRecord)
        .where(
            EvidenceItemRecord.evidence_pack_id == evidence_pack_id,
            EvidenceItemRecord.tenant_id == tenant_id,
        )
        .order_by(EvidenceItemRecord.id)
    )
    return [_item_response(record) for record in result.scalars().all()]
