"""Compliance and product quality gate endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.compliance import (
    BatchAssayCreate,
    BatchAssayResponse,
    ComplianceEvaluateRequest,
    ComplianceRulesResponse,
    ReleaseGateResponse,
)
from app.services.compliance_service import (
    create_batch_assay,
    evaluate_compliance,
    get_compliance_rules,
    list_release_gates,
)

router = APIRouter()


@router.post("/compliance/evaluate", response_model=ReleaseGateResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_compliance_endpoint(
    payload: ComplianceEvaluateRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    gate = await evaluate_compliance(db, tenant_id=current_user.tenant_id, user_id=current_user.id, payload=payload)
    if gate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return gate


@router.get("/compliance/rules", response_model=ComplianceRulesResponse)
async def get_compliance_rules_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
):
    return get_compliance_rules()


@router.post("/batches/{batch_id}/assays", response_model=BatchAssayResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_assay_endpoint(
    batch_id: int,
    payload: BatchAssayCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    assay = await create_batch_assay(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        batch_id=batch_id,
        payload=payload,
    )
    if assay is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return assay


@router.get("/batches/{batch_id}/release-gates", response_model=list[ReleaseGateResponse])
async def list_release_gates_endpoint(
    batch_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    gates = await list_release_gates(db, tenant_id=current_user.tenant_id, batch_id=batch_id)
    if gates is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return gates
