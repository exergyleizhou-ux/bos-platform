"""BOS assistant control plane endpoints."""

from __future__ import annotations

from datetime import date
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import User
from app.schemas.assistant import (
    AssistantConfirmRequest,
    AssistantReviewHumanApprovalItem,
    AssistantReviewWorkbenchResponse,
    AssistantRunCreate,
    AssistantRunResponse,
    AssistantToolCallResponse,
    HumanApprovalResolveRequest,
)
from app.schemas.final_actions import FinalActionReviewPacketSnapshotResponse
from app.services.assistant_service import (
    build_review_workbench_audit_packet,
    confirm_assistant_action,
    create_assistant_run,
    get_assistant_run,
    list_assistant_runs,
    list_assistant_review_workbench,
    list_assistant_tool_calls,
    render_review_workbench_audit_packet_json,
    render_review_workbench_audit_packet_markdown,
    resolve_human_approval_request,
)
from app.services.final_action_review_packet_service import (
    persist_review_packet_snapshot,
    serialize_review_packet_snapshot,
)
from app.services.feature_flags import get_effective_flag_value

router = APIRouter()


async def _persist_current_review_workbench_snapshot(
    db: AsyncSession,
    *,
    current_user: User,
    limit: int,
):
    packet = await build_review_workbench_audit_packet(db, tenant_id=current_user.tenant_id, limit=limit)
    snapshot = await persist_review_packet_snapshot(
        db,
        tenant_id=current_user.tenant_id,
        generated_by_user_id=current_user.id,
        packet=packet,
    )
    packet = {
        **packet,
        "source_review_packet_id": snapshot.source_review_packet_id,
        "packet_hash": snapshot.packet_hash,
    }
    return packet, snapshot


async def _ensure_simulation_lab_enabled(request: Request, db: AsyncSession, tenant_id: int) -> None:
    redis = getattr(request.app.state, "redis", None)
    enabled, _source = await get_effective_flag_value(
        db,
        flag_name="bos_simulation_lab",
        tenant_id=tenant_id,
        redis=redis,
    )
    if not enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bos_simulation_lab_disabled")


@router.post("/assistant/runs", response_model=AssistantRunResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant_run_endpoint(
    payload: AssistantRunCreate,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    if payload.mode == "simulation_lab":
        await _ensure_simulation_lab_enabled(request, db, current_user.tenant_id)
    return await create_assistant_run(db, tenant_id=current_user.tenant_id, user_id=current_user.id, payload=payload)


@router.get("/assistant/runs", response_model=list[AssistantRunResponse])
async def list_assistant_runs_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=10, ge=1, le=50),
):
    return await list_assistant_runs(db, tenant_id=current_user.tenant_id, limit=limit)


@router.get("/assistant/review-workbench", response_model=AssistantReviewWorkbenchResponse)
async def list_assistant_review_workbench_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    status_filter: str = Query(default="pending", alias="status", min_length=1, max_length=50),
    limit: int = Query(default=50, ge=1, le=100),
):
    return await list_assistant_review_workbench(
        db,
        tenant_id=current_user.tenant_id,
        status=status_filter,
        limit=limit,
    )


@router.get("/assistant/review-workbench/audit-packet")
async def export_assistant_review_workbench_audit_packet_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    format: str = Query("md", pattern=r"^(md|json)$"),
    limit: int = Query(default=50, ge=1, le=100),
):
    packet, _snapshot = await _persist_current_review_workbench_snapshot(db, current_user=current_user, limit=limit)
    export_date = date.today().isoformat()
    if format == "json":
        payload = render_review_workbench_audit_packet_json(packet)
        return StreamingResponse(
            iter([payload]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=assistant_review_workbench_audit_{export_date}.json",
            },
        )

    payload = render_review_workbench_audit_packet_markdown(packet)
    return StreamingResponse(
        io.StringIO(payload),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=assistant_review_workbench_audit_{export_date}.md",
        },
    )


@router.post(
    "/assistant/review-workbench/audit-packet/snapshot",
    response_model=FinalActionReviewPacketSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def persist_assistant_review_workbench_audit_packet_snapshot_endpoint(
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
    limit: int = Query(default=50, ge=1, le=100),
):
    _packet, snapshot = await _persist_current_review_workbench_snapshot(
        db,
        current_user=current_user,
        limit=limit,
    )
    return serialize_review_packet_snapshot(snapshot)


@router.post(
    "/assistant/review-workbench/human-approval-requests/{approval_request_id}/resolve",
    response_model=AssistantReviewHumanApprovalItem,
)
async def resolve_human_approval_request_endpoint(
    approval_request_id: str,
    payload: HumanApprovalResolveRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    item = await resolve_human_approval_request(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        approval_request_id=approval_request_id,
        payload=payload,
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Human approval request not found")
    return item


@router.get("/assistant/runs/{run_id}", response_model=AssistantRunResponse)
async def get_assistant_run_endpoint(
    run_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    run = await get_assistant_run(db, tenant_id=current_user.tenant_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant run not found")
    return run


@router.get("/assistant/runs/{run_id}/tool-calls", response_model=list[AssistantToolCallResponse])
async def list_assistant_tool_calls_endpoint(
    run_id: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    calls = await list_assistant_tool_calls(db, tenant_id=current_user.tenant_id, run_id=run_id)
    if calls is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant run not found")
    return calls


@router.post("/assistant/runs/{run_id}/confirm", response_model=AssistantRunResponse)
async def confirm_assistant_action_endpoint(
    run_id: str,
    payload: AssistantConfirmRequest,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    run = await confirm_assistant_action(db, tenant_id=current_user.tenant_id, run_id=run_id, payload=payload)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant run or confirmation not found")
    return run
