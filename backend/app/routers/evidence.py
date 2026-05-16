"""Evidence kernel endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.evidence import EvidencePackCreate, EvidenceItemResponse, EvidencePackResponse, InputSnapshotResponse
from app.services.evidence_service import create_evidence_pack, get_evidence_pack, get_input_snapshot, list_evidence_items

router = APIRouter()


@router.post("/evidence-packs", response_model=EvidencePackResponse, status_code=status.HTTP_201_CREATED)
async def create_evidence_pack_endpoint(
    payload: EvidencePackCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    pack = await create_evidence_pack(db, tenant_id=current_user.tenant_id, user_id=current_user.id, payload=payload)
    await db.commit()
    return pack


@router.get("/evidence-packs/{evidence_pack_id}", response_model=EvidencePackResponse)
async def get_evidence_pack_endpoint(
    evidence_pack_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    pack = await get_evidence_pack(db, tenant_id=current_user.tenant_id, evidence_pack_id=evidence_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence pack not found")
    return pack


@router.get("/evidence-packs/{evidence_pack_id}/items", response_model=list[EvidenceItemResponse])
async def list_evidence_items_endpoint(
    evidence_pack_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    if await get_evidence_pack(db, tenant_id=current_user.tenant_id, evidence_pack_id=evidence_pack_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence pack not found")
    return await list_evidence_items(db, tenant_id=current_user.tenant_id, evidence_pack_id=evidence_pack_id)


@router.get("/input-snapshots/{input_snapshot_id}", response_model=InputSnapshotResponse)
async def get_input_snapshot_endpoint(
    input_snapshot_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    snapshot = await get_input_snapshot(db, tenant_id=current_user.tenant_id, input_snapshot_id=input_snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input snapshot not found")
    return snapshot
