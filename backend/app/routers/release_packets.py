"""Release packet attachment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.release_packets import (
    HumanApprovalRequestCreate,
    HumanApprovalRequestResponse,
    ReleasePacketAttachmentResponse,
    SimulationAppendixAttachRequest,
)
from app.services.release_packet_service import (
    attach_simulation_appendix,
    create_human_approval_request,
    list_release_attachments,
)

router = APIRouter()


@router.post(
    "/release-packets/{release_decision_id}/appendices/simulation",
    response_model=ReleasePacketAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_simulation_appendix_endpoint(
    release_decision_id: int,
    payload: SimulationAppendixAttachRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    attachment = await attach_simulation_appendix(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        release_decision_id=release_decision_id,
        simulation_id=payload.simulation_id,
        run_id=payload.run_id,
    )
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision or simulation appendix not found")
    return attachment


@router.get("/release-packets/{release_decision_id}/appendices", response_model=list[ReleasePacketAttachmentResponse])
async def list_release_appendices_endpoint(
    release_decision_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    attachments = await list_release_attachments(
        db,
        tenant_id=current_user.tenant_id,
        release_decision_id=release_decision_id,
    )
    if attachments is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision not found")
    return attachments


@router.post(
    "/release-packets/{release_decision_id}/approval-requests",
    response_model=HumanApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_release_approval_request_endpoint(
    release_decision_id: int,
    payload: HumanApprovalRequestCreate,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    approval = await create_human_approval_request(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        release_decision_id=release_decision_id,
        payload=payload,
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release decision not found")
    return approval
