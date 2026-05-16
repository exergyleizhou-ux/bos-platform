"""Immutable source review packet snapshots for future final actions."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import FinalActionReviewPacketSnapshot
from app.schemas.final_actions import FinalActionReviewPacketSnapshotResponse

_NON_CANONICAL_TOP_LEVEL_KEYS = {"generated_at", "source_review_packet_id", "packet_hash"}


def _canonical_packet_payload(packet: dict[str, Any]) -> dict[str, Any]:
    encoded = jsonable_encoder(packet)
    if not isinstance(encoded, dict):
        return {}
    return {key: value for key, value in encoded.items() if key not in _NON_CANONICAL_TOP_LEVEL_KEYS}


def compute_review_packet_hash(packet: dict[str, Any]) -> str:
    canonical = _canonical_packet_payload(packet)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_review_packet_id_for_hash(packet_hash: str) -> str:
    return f"FARP-{packet_hash[:16].upper()}"


def _evidence_pack_ids(packet: dict[str, Any]) -> list[str]:
    values = packet.get("evidence_pack_ids")
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if isinstance(value, str) and value]


async def get_review_packet_snapshot_by_hash(
    db: AsyncSession,
    *,
    tenant_id: int,
    packet_hash: str,
) -> FinalActionReviewPacketSnapshot | None:
    return await db.scalar(
        select(FinalActionReviewPacketSnapshot)
        .where(
            FinalActionReviewPacketSnapshot.tenant_id == tenant_id,
            FinalActionReviewPacketSnapshot.packet_hash == packet_hash,
        )
        .order_by(desc(FinalActionReviewPacketSnapshot.created_at), desc(FinalActionReviewPacketSnapshot.id))
        .limit(1)
    )


async def get_review_packet_snapshot_by_source_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    source_review_packet_id: str,
) -> FinalActionReviewPacketSnapshot | None:
    return await db.scalar(
        select(FinalActionReviewPacketSnapshot)
        .where(
            FinalActionReviewPacketSnapshot.tenant_id == tenant_id,
            FinalActionReviewPacketSnapshot.source_review_packet_id == source_review_packet_id,
        )
        .limit(1)
    )


async def get_latest_review_packet_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> FinalActionReviewPacketSnapshot | None:
    return await db.scalar(
        select(FinalActionReviewPacketSnapshot)
        .where(FinalActionReviewPacketSnapshot.tenant_id == tenant_id)
        .order_by(desc(FinalActionReviewPacketSnapshot.created_at), desc(FinalActionReviewPacketSnapshot.id))
        .limit(1)
    )


def serialize_review_packet_snapshot(
    snapshot: FinalActionReviewPacketSnapshot,
) -> FinalActionReviewPacketSnapshotResponse:
    created_at = snapshot.created_at.isoformat() if snapshot.created_at is not None else ""
    return FinalActionReviewPacketSnapshotResponse(
        tenant_id=snapshot.tenant_id,
        source_review_packet_id=snapshot.source_review_packet_id,
        packet_type=snapshot.packet_type,
        packet_hash=snapshot.packet_hash,
        evidence_pack_ids=[str(value) for value in snapshot.evidence_pack_ids],
        generated_by_user_id=snapshot.generated_by_user_id,
        created_at=created_at,
        packet_payload=snapshot.packet_payload,
        guardrails=[
            "read_only_source_review_packet",
            "immutable_packet_snapshot",
            "tenant_scoped_read_model",
            "final_actions_not_executed",
            "no_release_decision_mutation",
            "no_model_activation",
            "no_external_share_record",
            "no_hardware_execution",
        ],
    )


async def persist_review_packet_snapshot(
    db: AsyncSession,
    *,
    tenant_id: int,
    generated_by_user_id: int,
    packet: dict[str, Any],
) -> FinalActionReviewPacketSnapshot:
    packet_hash = compute_review_packet_hash(packet)
    existing = await get_review_packet_snapshot_by_hash(db, tenant_id=tenant_id, packet_hash=packet_hash)
    if existing is not None:
        return existing

    source_review_packet_id = source_review_packet_id_for_hash(packet_hash)
    persisted_payload = deepcopy(jsonable_encoder(packet))
    if not isinstance(persisted_payload, dict):
        persisted_payload = {}
    persisted_payload["source_review_packet_id"] = source_review_packet_id
    persisted_payload["packet_hash"] = packet_hash

    snapshot = FinalActionReviewPacketSnapshot(
        source_review_packet_id=source_review_packet_id,
        tenant_id=tenant_id,
        packet_type=str(packet.get("packet_type") or "review_packet"),
        packet_hash=packet_hash,
        packet_payload=persisted_payload,
        evidence_pack_ids=_evidence_pack_ids(packet),
        generated_by_user_id=generated_by_user_id,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
