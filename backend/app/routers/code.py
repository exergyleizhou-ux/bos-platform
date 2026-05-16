"""
BOS Code router.
"""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.code import LANE_EVENT_MERGE_READINESS_UPDATED
from app.config import get_settings
from app.db import get_async_session
from app.deps import require_minimum_role
from app.models import (
    CodeAgentRuntimeState,
    CodeArtifact,
    CodeAutomationJob,
    CodeEvent,
    CodeMemorySnapshot,
    CodeReflectionRun,
    CodeSession,
    CodeSkill,
    CodeSkillRevision,
    CodeSubagentRun,
    CodeTask,
    CodeToolCall,
    CodeTurn,
    CodeVerificationRun,
    CodeWorker,
    CodeWorkspace,
    CodeWorkspaceLease,
    User,
)
from app.routers.websocket_router import broadcast_code_session_event, broadcast_code_worker_event
from app.schemas import (
    CodeAgentRuntimeStateResponse,
    CodeArtifactResponse,
    CodeAutomationExecutionResponse,
    CodeAutomationJobCreateRequest,
    CodeAutomationJobResponse,
    CodeAutomationJobUpdateRequest,
    CodeBranchStateResponse,
    CodeCancelSessionRequest,
    CodeDiffResponse,
    CodeEventListResponse,
    CodeEventResponse,
    CodeGitStatusResponse,
    CodeLspDiagnosticResponse,
    CodeLspDiagnosticsPayload,
    CodeLspSessionResponse,
    CodeLspSymbolResponse,
    CodeLspSymbolsPayload,
    CodeMcpResourceReadResponse,
    CodeMcpResourceResponse,
    CodeMcpServerConnectRequest,
    CodeMcpServerResponse,
    CodeMemoryRefreshResponse,
    CodeMemorySnapshotResponse,
    CodeOrchestrationSnapshotResponse,
    CodeReadinessResponse,
    CodeRecoveryResponse,
    CodeReflectionRunRequest,
    CodeReflectionRunResponse,
    CodeReleaseArtifactResponse,
    CodeReleaseCheckResponse,
    CodeReleaseReadinessResponse,
    CodeRuntimeResponse,
    CodeSafeBashRequest,
    CodeSessionCreateRequest,
    CodeSessionDetailResponse,
    CodeSessionListResponse,
    CodeSessionResponse,
    CodeSessionSearchRequest,
    CodeSessionSearchResponse,
    CodeSessionSearchResultResponse,
    CodeSessionUpdateRequest,
    CodeSkillCreateRequest,
    CodeSkillFeedbackRequest,
    CodeSkillResponse,
    CodeSkillRevisionResponse,
    CodeSkillUpdateRequest,
    CodeSubagentRunResponse,
    CodeTaskArchitectPlanRequest,
    CodeTaskArchitectPlanResponse,
    CodeTaskArchitectRouteRequest,
    CodeTaskCreateRequest,
    CodeTaskResponse,
    CodeTaskReviewDecisionRequest,
    CodeTaskReviewRequest,
    CodeToolCallResponse,
    CodeToolExecutionResponse,
    CodeTurnCreateRequest,
    CodeTurnResponse,
    CodeVerificationResponse,
    CodeVerificationRunRequest,
    CodeVerificationRunResponse,
    CodeWorkerAssignRequest,
    CodeWorkerEventListResponse,
    CodeWorkerEventResponse,
    CodeWorkerResponse,
    CodeWorkerStatusUpdateRequest,
    CodeWorkspaceFileResponse,
    CodeWorkspaceInitRequest,
    CodeWorkspaceLeaseResponse,
    CodeWorkspaceResponse,
    CodeWorkspaceStatusResponse,
    CodeWorkspaceTreeItem,
    CodeWorkspaceTreeResponse,
)
from app.services.code import (
    CodeAutomationJobService,
    CodeAutomationService,
    CodeBranchService,
    CodeEventService,
    CodeLspService,
    CodeMcpService,
    CodeMemoryService,
    CodeOrchestrationService,
    CodeRecoveryService,
    CodeReflectionService,
    CodeRuntimeService,
    CodeSessionSearchService,
    CodeSessionService,
    CodeSkillService,
    CodeSubagentService,
    CodeTaskService,
    CodeToolRegistry,
    CodeVerificationService,
    CodeWorkerEventService,
    CodeWorkspaceService,
    WorkspaceGuard,
)
from app.services.code.providers import CodeProviderError, ProviderRequest
from app.services.code.providers import list_available_provider_profiles, list_team_chat_models, resolve_provider_profile
from app.services.code.session_service import CodeSessionLeaseConflictError
from app.services.feature_flags import get_effective_flag_value

router = APIRouter(prefix="/code", tags=["BOS Code"])
settings = get_settings()
session_service = CodeSessionService()
subagent_service = CodeSubagentService()
REPO_ROOT = Path(__file__).resolve().parents[3]
REPORTS_ROOT = REPO_ROOT / "reports"
PLAYWRIGHT_ROOT = REPORTS_ROOT / "playwright-check"
STABILIZE_ROOT = REPORTS_ROOT / "stabilize-v9"
RELEASE_DOSSIER_PATH = REPORTS_ROOT / "release-readiness-summary.md"
RELEASE_MANIFEST_PATH = REPORTS_ROOT / "release-readiness-summary.json"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_registry() -> dict[str, tuple[Path, str, str]]:
    manifest = _read_json(RELEASE_MANIFEST_PATH)
    manifest_artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}

    def manifest_artifact_path(key: str, fallback: Path) -> Path:
        relative_path = manifest_artifacts.get(key)
        if isinstance(relative_path, str) and relative_path:
            return REPO_ROOT / relative_path
        return fallback

    return {
        "release_dossier": (RELEASE_DOSSIER_PATH, "Release dossier", "text/markdown"),
        "release_manifest": (RELEASE_MANIFEST_PATH, "Release manifest", "application/json"),
        "bos_v9_rc_manifest": (
            manifest_artifact_path("bos_v9_rc_manifest", STABILIZE_ROOT / "BOS_V9_RC_MANIFEST.json"),
            "BOS v9 RC manifest",
            "application/json",
        ),
        "code_smoke_json": (PLAYWRIGHT_ROOT / "live-code-runtime-ui-actions.json", "Code smoke JSON", "application/json"),
        "code_smoke_png": (PLAYWRIGHT_ROOT / "live-code-runtime-ui-actions.png", "Code smoke screenshot", "image/png"),
        "bos_smoke_json": (PLAYWRIGHT_ROOT / "live-bos-interface-smoke.json", "BOS smoke JSON", "application/json"),
        "bos_smoke_png": (PLAYWRIGHT_ROOT / "live-bos-interface-smoke.png", "BOS smoke screenshot", "image/png"),
        "bos_mechanistic_smoke_json": (
            PLAYWRIGHT_ROOT / "live-bos-mechanistic-smoke.json",
            "BOS mechanistic smoke JSON",
            "application/json",
        ),
        "bos_mechanistic_smoke_bos_png": (
            PLAYWRIGHT_ROOT / "live-bos-mechanistic-smoke-bos.png",
            "BOS mechanistic BOS screenshot",
            "image/png",
        ),
        "bos_mechanistic_smoke_packet_png": (
            PLAYWRIGHT_ROOT / "live-bos-mechanistic-smoke-packet.png",
            "BOS mechanistic packet screenshot",
            "image/png",
        ),
        "bos_mechanistic_smoke_batch_png": (
            PLAYWRIGHT_ROOT / "live-bos-mechanistic-smoke-batch.png",
            "BOS mechanistic batch screenshot",
            "image/png",
        ),
        "provider_live_smoke_json": (
            manifest_artifact_path("provider_live_smoke_json", STABILIZE_ROOT / "provider-live-smoke.json"),
            "Provider live smoke JSON",
            "application/json",
        ),
        "release_reference_joint_smoke_json": (
            manifest_artifact_path(
                "release_reference_joint_smoke_json",
                STABILIZE_ROOT / "release-reference-joint-smoke-missing.json",
            ),
            "Release+Reference joint smoke JSON",
            "application/json",
        ),
        "frontend_build_entry": (REPO_ROOT / "frontend" / "dist" / "index.html", "Frontend build entry", "text/html"),
    }


async def _ensure_bos_code_enabled(request: Request, db: AsyncSession, tenant_id: int) -> None:
    redis = getattr(request.app.state, "redis", None)
    enabled, _source = await get_effective_flag_value(
        db,
        flag_name="bos_code",
        tenant_id=tenant_id,
        redis=redis,
    )
    if not enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOS Code is disabled for this tenant")


async def _get_workspace_or_404(db: AsyncSession, tenant_id: int) -> CodeWorkspace:
    result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.tenant_id == tenant_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code workspace not initialized")
    return workspace


async def _get_workspace_lease(db: AsyncSession, workspace_id: int) -> CodeWorkspaceLease | None:
    result = await db.execute(select(CodeWorkspaceLease).where(CodeWorkspaceLease.workspace_id == workspace_id))
    return result.scalar_one_or_none()


async def _get_session_or_404(db: AsyncSession, tenant_id: int, session_id: int) -> CodeSession:
    result = await db.execute(
        select(CodeSession).where(CodeSession.id == session_id, CodeSession.tenant_id == tenant_id)
    )
    code_session = result.scalar_one_or_none()
    if code_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Code session not found")
    return code_session


def _serialize_workspace(workspace: CodeWorkspace, lease: CodeWorkspaceLease | None) -> CodeWorkspaceResponse:
    return CodeWorkspaceResponse(
        id=workspace.id,
        tenant_id=workspace.tenant_id,
        repo_root=workspace.repo_root,
        worktree_root=workspace.worktree_root,
        base_branch=workspace.base_branch,
        default_branch=workspace.default_branch,
        active_branch=workspace.active_branch,
        workspace_status=workspace.workspace_status,
        base_commit=workspace.base_commit,
        head_commit=workspace.head_commit,
        dirty_state=workspace.dirty_state,
        created_at=workspace.created_at,
        updated_at=workspace.updated_at,
        lease=CodeWorkspaceLeaseResponse.model_validate(lease) if lease else None,
    )


def _build_tool_registry(workspace: CodeWorkspace, role: str) -> CodeToolRegistry:
    guard = WorkspaceGuard(
        workspace.worktree_root,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    return CodeToolRegistry(
        workspace_guard=guard,
        role=role,
        safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
    )


def _apply_requested_runtime_selection(
    code_session: CodeSession,
    *,
    provider_name: str | None,
    model_name: str | None,
) -> None:
    if provider_name is None and model_name is None:
        return
    profile = resolve_provider_profile(provider_name or code_session.provider)
    code_session.provider = profile.name
    code_session.model = (model_name or profile.default_model).strip()


def _serialize_lsp_session(session) -> CodeLspSessionResponse:
    state = getattr(session, "__dict__", {})
    return CodeLspSessionResponse(
        id=state.get("id", session.id),
        workspace_id=state.get("workspace_id", session.workspace_id),
        language=state.get("language", session.language),
        server_name=state.get("server_name", session.server_name),
        status=state.get("status", session.status),
        root_uri=state.get("root_uri"),
        error_message=state.get("error_message"),
        last_heartbeat_at=state.get("last_heartbeat_at"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


def _serialize_mcp_server(server) -> CodeMcpServerResponse:
    state = getattr(server, "__dict__", {})
    capabilities = state.get("capabilities") or {}
    return CodeMcpServerResponse(
        id=state.get("id", server.id),
        tenant_id=state.get("tenant_id", server.tenant_id),
        workspace_id=state.get("workspace_id", server.workspace_id),
        server_name=state.get("server_name", server.server_name),
        transport=state.get("transport", server.transport),
        connection_status=state.get("connection_status", server.connection_status),
        capabilities=capabilities,
        startup_phase=capabilities.get("startup_phase"),
        discovery_status=capabilities.get("discovery_status"),
        resource_count=int(capabilities.get("resource_count") or 0),
        tool_count=int(capabilities.get("tool_count") or 0),
        failure_class=capabilities.get("failure_class"),
        degraded_scope=capabilities.get("degraded_scope"),
        recovery_recommendations=[
            item
            for item in (capabilities.get("recovery_recommendations") or [])
            if isinstance(item, str) and item.strip()
        ],
        error_message=state.get("error_message"),
        last_connected_at=state.get("last_connected_at"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


def _serialize_task(task) -> CodeTaskResponse:
    state = getattr(task, "__dict__", {})
    return CodeTaskResponse(
        id=state.get("id", task.id),
        tenant_id=state.get("tenant_id", task.tenant_id),
        user_id=state.get("user_id", task.user_id),
        workspace_id=state.get("workspace_id", task.workspace_id),
        session_id=state.get("session_id"),
        title=state.get("title", task.title),
        objective=state.get("objective", task.objective),
        scope=state.get("scope"),
        task_packet=state.get("task_packet"),
        task_status=state.get("task_status", task.task_status),
        priority=state.get("priority", task.priority),
        acceptance_criteria=state.get("acceptance_criteria") or [],
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


def _serialize_worker(worker, *, task_status: str | None = None) -> CodeWorkerResponse:
    state = getattr(worker, "__dict__", {})
    worker_name = state.get("worker_name", worker.worker_name)
    worker_status = state.get("worker_status", worker.worker_status)
    return CodeWorkerResponse(
        id=state.get("id", worker.id),
        workspace_id=state.get("workspace_id", worker.workspace_id),
        task_id=state.get("task_id"),
        worker_name=worker_name,
        worker_role=state.get("worker_role", worker.worker_role),
        worker_status=worker_status,
        allowed_actions=CodeTaskService.allowed_actions_for_worker(
            worker_name=worker_name,
            worker_status=worker_status,
            task_status=task_status,
        ),
        allowed_action_policies=CodeTaskService.allowed_action_policies_for_worker(
            worker_name=worker_name,
            worker_status=worker_status,
            task_status=task_status,
        ),
        last_error=state.get("last_error"),
        last_event_summary=state.get("last_event_summary"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


async def _task_status_by_task_id(db: AsyncSession, *, task_id: int | None) -> str | None:
    if task_id is None:
        return None
    result = await db.execute(select(CodeTask.task_status).where(CodeTask.id == task_id))
    return result.scalar_one_or_none()


def _serialize_worker_event(event) -> CodeWorkerEventResponse:
    state = getattr(event, "__dict__", {})
    payload = state.get("payload") or {}
    return CodeWorkerEventResponse(
        id=state.get("id", event.id),
        workspace_id=state.get("workspace_id", event.workspace_id),
        task_id=state.get("task_id"),
        worker_id=state.get("worker_id"),
        lane=state.get("lane", event.lane),
        event_name=state.get("event_name", event.event_name),
        status=state.get("status", event.status),
        summary=state.get("summary"),
        payload=payload,
        reflection_id=payload.get("reflection_id"),
        subagent_run_id=payload.get("subagent_run_id"),
        skill_id=payload.get("skill_id"),
        event_data_version=int(payload.get("event_data_version") or 1),
        phase=payload.get("phase"),
        severity=payload.get("severity"),
        failure_class=payload.get("failure_class"),
        headline=payload.get("headline"),
        recommended_action=payload.get("recommended_action"),
        recommended_actions=[
            item for item in (payload.get("recommended_actions") or []) if isinstance(item, str) and item.strip()
        ],
        degraded_scope=payload.get("degraded_scope"),
        blocking=bool(payload.get("blocking", False)),
        created_at=state.get("created_at"),
    )


def _serialize_runtime_state(runtime: CodeAgentRuntimeState) -> CodeAgentRuntimeStateResponse:
    state = getattr(runtime, "__dict__", {})
    return CodeAgentRuntimeStateResponse(
        id=state.get("id", runtime.id),
        workspace_id=state.get("workspace_id", runtime.workspace_id),
        heartbeat_enabled=state.get("heartbeat_enabled", runtime.heartbeat_enabled),
        memory_enabled=state.get("memory_enabled", runtime.memory_enabled),
        reflections_enabled=state.get("reflections_enabled", runtime.reflections_enabled),
        last_heartbeat_decision=state.get("last_heartbeat_decision"),
        last_heartbeat_at=state.get("last_heartbeat_at"),
        last_memory_sync_at=state.get("last_memory_sync_at"),
        last_reflection_at=state.get("last_reflection_at"),
        last_compressed_turn_index=state.get("last_compressed_turn_index"),
        runtime_metrics=state.get("runtime_metrics") or {},
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
    )


def _serialize_memory_snapshot(snapshot: CodeMemorySnapshot) -> CodeMemorySnapshotResponse:
    return CodeMemorySnapshotResponse.model_validate(snapshot)


def _serialize_automation_job(job: CodeAutomationJob) -> CodeAutomationJobResponse:
    return CodeAutomationJobResponse.model_validate(job)


def _serialize_subagent_run(run: CodeSubagentRun) -> CodeSubagentRunResponse:
    state = getattr(run, "__dict__", {})
    return CodeSubagentRunResponse(
        id=state.get("id", run.id),
        workspace_id=state.get("workspace_id", run.workspace_id),
        session_id=state.get("session_id"),
        task_id=state.get("task_id"),
        worker_id=state.get("worker_id"),
        objective=state.get("objective", run.objective),
        run_status=state.get("run_status", run.run_status),
        result_summary=state.get("result_summary"),
        metadata_json=state.get("metadata_json") or {},
        started_at=state.get("started_at"),
        finished_at=state.get("finished_at"),
        created_at=state.get("created_at"),
    )


def _serialize_skill_revision(revision: CodeSkillRevision | None) -> CodeSkillRevisionResponse | None:
    if revision is None:
        return None
    state = getattr(revision, "__dict__", {})
    return CodeSkillRevisionResponse(
        id=state.get("id", revision.id),
        skill_id=state.get("skill_id", revision.skill_id),
        reflection_run_id=state.get("reflection_run_id"),
        revision_number=state.get("revision_number", revision.revision_number),
        revision_status=state.get("revision_status", revision.revision_status),
        change_summary=state.get("change_summary"),
        content_markdown=state.get("content_markdown", revision.content_markdown),
        supporting_files=state.get("supporting_files") or {},
        created_at=state.get("created_at"),
    )


async def _serialize_skill(db: AsyncSession, skill: CodeSkill) -> CodeSkillResponse:
    latest_revision = await CodeSkillService.latest_revision(db, skill_id=skill.id)
    state = getattr(skill, "__dict__", {})
    return CodeSkillResponse(
        id=state.get("id", skill.id),
        tenant_id=state.get("tenant_id", skill.tenant_id),
        workspace_id=state.get("workspace_id", skill.workspace_id),
        origin_task_id=state.get("origin_task_id"),
        created_by_user_id=state.get("created_by_user_id"),
        name=state.get("name", skill.name),
        slug=state.get("slug", skill.slug),
        description=state.get("description"),
        skill_status=state.get("skill_status", skill.skill_status),
        directory_path=state.get("directory_path", skill.directory_path),
        latest_revision_number=state.get("latest_revision_number", skill.latest_revision_number),
        usage_count=state.get("usage_count", skill.usage_count),
        positive_feedback_count=state.get("positive_feedback_count", skill.positive_feedback_count),
        negative_feedback_count=state.get("negative_feedback_count", skill.negative_feedback_count),
        last_used_at=state.get("last_used_at"),
        last_feedback_at=state.get("last_feedback_at"),
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
        latest_revision=_serialize_skill_revision(latest_revision),
    )


async def _serialize_reflection(db: AsyncSession, reflection: CodeReflectionRun) -> CodeReflectionRunResponse:
    state = getattr(reflection, "__dict__", {})
    skill = None
    if state.get("skill_id"):
        skill = await CodeSkillService.get_skill(db, workspace_id=reflection.workspace_id, skill_id=state["skill_id"])
    return CodeReflectionRunResponse(
        id=state.get("id", reflection.id),
        workspace_id=state.get("workspace_id", reflection.workspace_id),
        session_id=state.get("session_id", reflection.session_id),
        task_id=state.get("task_id"),
        skill_id=state.get("skill_id"),
        trigger_source=state.get("trigger_source", reflection.trigger_source),
        reflection_status=state.get("reflection_status", reflection.reflection_status),
        output_kind=state.get("output_kind", reflection.output_kind),
        summary=state.get("summary"),
        payload=state.get("payload") or {},
        created_at=state.get("created_at"),
        updated_at=state.get("updated_at"),
        skill=(await _serialize_skill(db, skill)) if skill is not None else None,
    )


async def _maybe_emit_merge_readiness_event(
    *,
    db: AsyncSession,
    workspace_id: int,
    previous_snapshot: CodeOrchestrationSnapshotResponse | None,
) -> CodeOrchestrationSnapshotResponse:
    current_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace_id)
    if previous_snapshot is None:
        return current_snapshot

    if (
        previous_snapshot.merge_readiness == current_snapshot.merge_readiness
        and previous_snapshot.verification_gate == current_snapshot.verification_gate
        and previous_snapshot.merge_blockers == current_snapshot.merge_blockers
    ):
        return current_snapshot

    await CodeWorkerEventService.append_event(
        db,
        workspace_id=workspace_id,
        lane="tasking",
        event_name=LANE_EVENT_MERGE_READINESS_UPDATED,
        status=current_snapshot.merge_readiness,
        summary=(
            f"Merge readiness is now {current_snapshot.merge_readiness}"
            + (f" ({', '.join(current_snapshot.merge_blockers)})" if current_snapshot.merge_blockers else "")
        ),
        payload={
            "previous_merge_readiness": previous_snapshot.merge_readiness,
            "merge_readiness": current_snapshot.merge_readiness,
            "previous_verification_gate": previous_snapshot.verification_gate,
            "verification_gate": current_snapshot.verification_gate,
            "previous_merge_blockers": previous_snapshot.merge_blockers,
            "merge_blockers": current_snapshot.merge_blockers,
        },
    )
    await db.flush()
    return await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace_id)


async def _broadcast_events_since(*, tenant_id: int, session_id: int, after_seq: int | None, db: AsyncSession) -> None:
    events = await CodeEventService.list_events(
        db,
        session_id=session_id,
        after_seq=after_seq,
        limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
    )
    for event in events:
        await broadcast_code_session_event(
            tenant_id=tenant_id,
            session_id=session_id,
            event={
                "id": event.id,
                "seq_no": event.seq_no,
                "event_type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            },
        )


async def _broadcast_worker_events_since(
    *,
    tenant_id: int,
    workspace_id: int,
    after_id: int | None,
    db: AsyncSession,
) -> None:
    events = await CodeWorkerEventService.list_events(
        db,
        workspace_id=workspace_id,
        after_id=after_id,
        limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
    )
    for event in events:
        await broadcast_code_worker_event(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            event={
                "id": event.id,
                "workspace_id": event.workspace_id,
                "task_id": event.task_id,
                "worker_id": event.worker_id,
                "lane": event.lane,
                "event_name": event.event_name,
                "status": event.status,
                "summary": event.summary,
                "payload": event.payload or {},
                "created_at": event.created_at.isoformat() if event.created_at else None,
            },
        )


async def _maybe_execute_executor_subagent(
    *,
    db: AsyncSession,
    workspace: CodeWorkspace,
    task_id: int,
    worker_name: str,
) -> list[CodeSubagentRun]:
    if worker_name != "executor":
        return []

    task_result = await db.execute(
        select(CodeTask).where(
            CodeTask.workspace_id == workspace.id,
            CodeTask.id == task_id,
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        return []

    session = None
    if task.session_id is not None:
        session_result = await db.execute(select(CodeSession).where(CodeSession.id == task.session_id))
        session = session_result.scalar_one_or_none()

    worker_result = await db.execute(
        select(CodeWorker).where(
            CodeWorker.workspace_id == workspace.id,
            CodeWorker.worker_name == worker_name,
        )
    )
    worker = worker_result.scalar_one_or_none()
    runs = await subagent_service.create_runs_for_task(
        db,
        workspace=workspace,
        session=session,
        task=task,
        worker=worker,
        metadata={"source": "executor_handoff"},
    )
    for run in runs:
        await subagent_service.enqueue_or_execute_run(db, run_id=run.id)
    return runs


@router.post("/workspace/init", response_model=CodeWorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def init_workspace(
    body: CodeWorkspaceInitRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await CodeWorkspaceService.ensure_workspace(db, user=current_user)
    if body.base_branch:
        workspace.base_branch = body.base_branch
    if body.default_branch:
        workspace.default_branch = body.default_branch
        workspace.active_branch = body.default_branch
    await db.commit()
    await db.refresh(workspace)
    lease = await _get_workspace_lease(db, workspace.id)
    return _serialize_workspace(workspace, lease)


@router.get("/workspace", response_model=CodeWorkspaceResponse)
async def get_workspace(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    lease = await _get_workspace_lease(db, workspace.id)
    return _serialize_workspace(workspace, lease)


@router.get("/workspace/status", response_model=CodeWorkspaceStatusResponse)
async def get_workspace_status(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    lease = await _get_workspace_lease(db, workspace.id)
    latest_event = await db.execute(
        select(CodeEvent).join(CodeSession).where(CodeSession.workspace_id == workspace.id).order_by(CodeEvent.created_at.desc())
    )
    latest = latest_event.scalars().first()
    can_write = current_user.role in {"scientist", "admin"}
    workspace_response = _serialize_workspace(workspace, lease)
    return CodeWorkspaceStatusResponse(
        workspace=workspace_response,
        lease=workspace_response.lease,
        can_write=can_write,
        permission_mode=(
            "danger-full-access" if current_user.role == "admin" else "workspace-write" if current_user.role == "scientist" else "read-only"
        ),
        latest_event_time=latest.created_at if latest else None,
    )


@router.get("/workspace/tree", response_model=CodeWorkspaceTreeResponse)
async def get_workspace_tree(
    request: Request,
    path: str = Query(".", description="Relative path inside tenant worktree"),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    guard = WorkspaceGuard(
        workspace.worktree_root,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    directory = guard.resolve_path(path)
    if not directory.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace path not found")
    if not directory.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requested path is not a directory")

    items = [
        CodeWorkspaceTreeItem(
            path=entry.relative_to(guard.worktree_root).as_posix(),
            name=entry.name,
            node_type="directory" if entry.is_dir() else "file",
            has_children=entry.is_dir() and any(entry.iterdir()),
            size_bytes=None if entry.is_dir() else entry.stat().st_size,
        )
        for entry in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    ]
    return CodeWorkspaceTreeResponse(root=Path(path).as_posix(), items=items)


@router.get("/workspace/file", response_model=CodeWorkspaceFileResponse)
async def get_workspace_file(
    request: Request,
    path: str = Query(..., description="Relative file path inside tenant worktree"),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    guard = WorkspaceGuard(
        workspace.worktree_root,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    file_path = guard.assert_readable(path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace file not found")
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return CodeWorkspaceFileResponse(
        path=path,
        content=content,
        truncated=False,
        size_bytes=file_path.stat().st_size,
    )


@router.get("/sessions", response_model=CodeSessionListResponse)
async def list_sessions(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    sessions = await session_service.list_sessions(db, tenant_id=current_user.tenant_id)
    active = next((item.id for item in sessions if item.session_status in {"created", "spawning", "ready", "running", "blocked"}), None)
    return CodeSessionListResponse(
        items=[CodeSessionResponse.model_validate(item) for item in sessions],
        active_session_id=active,
    )


@router.post("/sessions", response_model=CodeSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CodeSessionCreateRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    before_seq = None
    try:
        code_session = await session_service.create_session(
            db,
            user=current_user,
            acquire_write_lease=body.acquire_write_lease and current_user.role in {"scientist", "admin"},
            provider_name=body.provider,
            model_name=body.model,
        )
    except CodeSessionLeaseConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CodeProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.user_message) from exc
    await db.commit()
    await db.refresh(code_session)
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=code_session.id, after_seq=before_seq, db=db)
    return CodeSessionResponse.model_validate(code_session)


@router.get("/sessions/{session_id}", response_model=CodeSessionDetailResponse)
async def get_session(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    lease = await _get_workspace_lease(db, workspace.id)

    turns_result = await db.execute(select(CodeTurn).where(CodeTurn.session_id == session_id).order_by(CodeTurn.turn_index.asc()))
    tool_result = await db.execute(select(CodeToolCall).where(CodeToolCall.session_id == session_id).order_by(CodeToolCall.created_at.asc()))
    event_result = await db.execute(select(CodeEvent).where(CodeEvent.session_id == session_id).order_by(CodeEvent.seq_no.desc()))
    memory_result = await db.execute(
        select(CodeMemorySnapshot).where(CodeMemorySnapshot.session_id == session_id).order_by(CodeMemorySnapshot.created_at.desc())
    )
    reflection_result = await db.execute(
        select(CodeReflectionRun).where(CodeReflectionRun.session_id == session_id).order_by(CodeReflectionRun.created_at.desc())
    )
    subagent_result = await db.execute(
        select(CodeSubagentRun).where(CodeSubagentRun.session_id == session_id).order_by(CodeSubagentRun.created_at.desc())
    )
    latest_event = event_result.scalars().first()

    workspace_response = _serialize_workspace(workspace, lease)
    return CodeSessionDetailResponse(
        session=CodeSessionResponse.model_validate(code_session),
        workspace=workspace_response,
        lease=workspace_response.lease,
        turns=[CodeTurnResponse.model_validate(item) for item in turns_result.scalars().all()],
        tool_calls=[CodeToolCallResponse.model_validate(item) for item in tool_result.scalars().all()],
        latest_event=CodeEventResponse.model_validate(latest_event) if latest_event else None,
        memory_snapshots=[_serialize_memory_snapshot(item) for item in memory_result.scalars().all()],
        reflection_runs=[await _serialize_reflection(db, item) for item in reflection_result.scalars().all()],
        subagent_runs=[_serialize_subagent_run(item) for item in subagent_result.scalars().all()],
    )


@router.patch("/sessions/{session_id}", response_model=CodeSessionResponse)
async def update_session(
    body: CodeSessionUpdateRequest,
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    existing_events = await CodeEventService.list_events(
        db,
        session_id=session_id,
        after_seq=None,
        limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
    )
    before_seq = existing_events[-1].seq_no if existing_events else None

    next_title = body.title.strip() if body.title else None
    code_session.title = next_title or None
    await CodeEventService.append_event(
        db,
        session_id=code_session.id,
        event_type="code.session.titled",
        payload={"title": code_session.title},
    )
    await db.commit()
    await db.refresh(code_session)
    await _broadcast_events_since(
        tenant_id=current_user.tenant_id,
        session_id=code_session.id,
        after_seq=before_seq,
        db=db,
    )
    return CodeSessionResponse.model_validate(code_session)


@router.post("/sessions/{session_id}/turns", response_model=CodeTurnResponse)
async def create_turn(
    body: CodeTurnCreateRequest,
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    _apply_requested_runtime_selection(code_session, provider_name=body.provider, model_name=body.model)
    existing_events = await CodeEventService.list_events(db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
    before_seq = existing_events[-1].seq_no if existing_events else None
    turn, _provider_output = await session_service.create_turn(db, session=code_session, user_message=body.user_message)
    await db.commit()
    await db.refresh(turn)
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db)
    return CodeTurnResponse.model_validate(turn)


@router.get("/sessions/{session_id}/stream")
async def stream_turn(
    request: Request,
    session_id: int,
    user_message: str = Query(..., min_length=1, max_length=20000),
    provider: str | None = Query(default=None, max_length=100),
    model: str | None = Query(default=None, max_length=150),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    _apply_requested_runtime_selection(code_session, provider_name=provider, model_name=model)
    existing_events = await CodeEventService.list_events(
        db,
        session_id=session_id,
        after_seq=None,
        limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
    )
    before_seq = existing_events[-1].seq_no if existing_events else None

    async def event_stream():
        turn, prompt = await session_service.initialize_turn(
            db,
            session=code_session,
            user_message=user_message,
        )
        output_chunks: list[str] = []
        try:
            async for chunk in session_service.provider.stream(
                ProviderRequest(
                    session_id=code_session.id,
                    prompt=prompt,
                    model=code_session.model,
                    provider=code_session.provider,
                    permission_mode=code_session.permission_mode,
                    tool_names=["read_file", "glob_search", "grep_search", "safe_bash", "git_ops"],
                )
            ):
                output_chunks.append(chunk)
                payload = json.dumps({"type": "delta", "delta": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            await session_service.complete_turn(
                db,
                session=code_session,
                turn=turn,
                user_message=user_message,
                output_text="".join(output_chunks),
            )
            await db.commit()
            await db.refresh(turn)
            await _broadcast_events_since(
                tenant_id=current_user.tenant_id,
                session_id=code_session.id,
                after_seq=before_seq,
                db=db,
            )
            yield "data: {\"type\":\"done\"}\n\n"
        except CodeProviderError as exc:
            await session_service.fail_turn(
                db,
                session=code_session,
                turn=turn,
                user_message=user_message,
                exc=exc,
            )
            await db.commit()
            await db.refresh(turn)
            await _broadcast_events_since(
                tenant_id=current_user.tenant_id,
                session_id=code_session.id,
                after_seq=before_seq,
                db=db,
            )
            payload = json.dumps(
                {"type": "error", "detail": exc.user_message, "reason": exc.blocked_reason},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            if output_chunks:
                await session_service.complete_turn(
                    db,
                    session=code_session,
                    turn=turn,
                    user_message=user_message,
                    output_text="".join(output_chunks),
                )
            else:
                await session_service.fail_turn(
                    db,
                    session=code_session,
                    turn=turn,
                    user_message=user_message,
                    exc=CodeProviderError(
                        "Streaming cancelled by client",
                        blocked_reason="client_cancelled",
                        user_message="Generation stopped.",
                    ),
                )
            await db.commit()
            await db.refresh(turn)
            await _broadcast_events_since(
                tenant_id=current_user.tenant_id,
                session_id=code_session.id,
                after_seq=before_seq,
                db=db,
            )
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/cancel", response_model=CodeSessionResponse)
async def cancel_session(
    body: CodeCancelSessionRequest,
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    existing_events = await CodeEventService.list_events(db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
    before_seq = existing_events[-1].seq_no if existing_events else None
    code_session = await session_service.cancel_session(db, session=code_session, reason=body.reason)
    await db.commit()
    await db.refresh(code_session)
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db)
    return CodeSessionResponse.model_validate(code_session)


@router.get("/sessions/{session_id}/events", response_model=CodeEventListResponse)
async def list_session_events(
    request: Request,
    session_id: int,
    after_seq: int | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    await _get_session_or_404(db, current_user.tenant_id, session_id)
    events = await CodeEventService.list_events(db, session_id=session_id, after_seq=after_seq, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
    next_seq = events[-1].seq_no if events else after_seq
    return CodeEventListResponse(
        items=[CodeEventResponse.model_validate(item) for item in events],
        after_seq=after_seq,
        next_seq=next_seq,
    )


@router.get("/sessions/{session_id}/diff", response_model=CodeDiffResponse)
async def get_session_diff(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    await _get_session_or_404(db, current_user.tenant_id, session_id)
    artifact_result = await db.execute(
        select(CodeArtifact)
        .where(CodeArtifact.session_id == session_id, CodeArtifact.artifact_type == "diff")
        .order_by(CodeArtifact.created_at.desc())
    )
    artifact = artifact_result.scalars().first()
    if artifact is None:
        return CodeDiffResponse(session_id=session_id)
    return CodeDiffResponse(
        session_id=session_id,
        base_commit=artifact.base_commit,
        head_commit=artifact.head_commit,
        changed_files=artifact.changed_files or [],
        diff_summary=artifact.diff_summary,
        patch=None,
    )


@router.get("/sessions/{session_id}/artifacts", response_model=list[CodeArtifactResponse])
async def get_session_artifacts(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    await _get_session_or_404(db, current_user.tenant_id, session_id)
    result = await db.execute(select(CodeArtifact).where(CodeArtifact.session_id == session_id).order_by(CodeArtifact.created_at.desc()))
    return [CodeArtifactResponse.model_validate(item) for item in result.scalars().all()]


@router.get("/sessions/{session_id}/verification", response_model=CodeVerificationResponse)
async def get_session_verification(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    result = await db.execute(
        select(CodeVerificationRun).where(CodeVerificationRun.session_id == session_id).order_by(CodeVerificationRun.id.asc())
    )
    runs = result.scalars().all()
    return CodeVerificationResponse(
        session_id=session_id,
        overall_status=code_session.verification_status,
        stages=[CodeVerificationRunResponse.model_validate(item) for item in runs],
    )


@router.post("/sessions/{session_id}/verification/run", response_model=CodeVerificationResponse)
async def run_verification_pipeline(
    body: CodeVerificationRunRequest,
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_events = await CodeEventService.list_events(
        db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT
    )
    before_seq = before_events[-1].seq_no if before_events else None

    if body.stage:
        result = await CodeVerificationService.execute_stage(
            db,
            session=code_session,
            worktree_root=workspace.worktree_root,
            role=current_user.role,
            stage=body.stage,
            safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
            max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
            max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
        )
        await CodeEventService.append_event(
            db,
            session_id=session_id,
            event_type="code.verification.finished",
            payload={
                "stage": result.stage,
                "verification_status": result.verification_status,
                "summary": result.summary,
                "exit_code": result.exit_code,
            },
        )
    else:
        results = await CodeVerificationService.execute_pipeline(
            db,
            session=code_session,
            worktree_root=workspace.worktree_root,
            role=current_user.role,
            safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
            max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
            max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
            stop_on_failure=body.stop_on_failure,
        )
        for result in results:
            await CodeEventService.append_event(
                db,
                session_id=session_id,
                event_type="code.verification.finished",
                payload={
                    "stage": result.stage,
                    "verification_status": result.verification_status,
                    "summary": result.summary,
                    "exit_code": result.exit_code,
                },
            )

    await CodeTaskService.apply_verification_result(
        db,
        workspace_id=workspace.id,
        session_id=session_id,
        verification_status=code_session.verification_status,
    )
    await CodeRuntimeService.record_policy_signal(
        db,
        workspace_id=workspace.id,
        category="verification_result",
        outcome=code_session.verification_status,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )

    await db.commit()
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db)

    result = await db.execute(
        select(CodeVerificationRun).where(CodeVerificationRun.session_id == session_id).order_by(CodeVerificationRun.id.asc())
    )
    runs = result.scalars().all()
    await db.refresh(code_session)
    return CodeVerificationResponse(
        session_id=session_id,
        overall_status=code_session.verification_status,
        stages=[CodeVerificationRunResponse.model_validate(item) for item in runs],
    )


@router.post("/sessions/{session_id}/tools/safe-bash", response_model=CodeToolExecutionResponse)
async def run_safe_bash(
    body: CodeSafeBashRequest,
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    registry = _build_tool_registry(workspace, current_user.role)
    existing_events = await CodeEventService.list_events(db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
    before_seq = existing_events[-1].seq_no if existing_events else None
    result = registry.execute_safe_bash(body.command)

    await session_service.record_tool_call(
        db,
        session_id=session_id,
        turn_id=None,
        tool_name=result.tool_name,
        tool_class="shell",
        input_summary=body.command[:500],
        result_summary=result.output[:1000],
        exit_code=result.exit_code,
        was_denied=result.denied_reason is not None,
        denial_reason=result.denied_reason,
    )
    if result.denied_reason is not None:
        await CodeEventService.append_event(
            db,
            session_id=session_id,
            event_type="code.permission.denied",
            payload={"tool_name": result.tool_name, "reason": result.denied_reason},
        )
    await CodeEventService.append_event(
        db,
        session_id=session_id,
        event_type="code.tool.finished",
        payload={
            "tool_name": result.tool_name,
            "exit_code": result.exit_code,
            "success": result.success,
            "denied_reason": result.denied_reason,
        },
    )
    await db.commit()
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db)
    return CodeToolExecutionResponse(
        tool_name=result.tool_name,
        success=result.success,
        output=result.output,
        exit_code=result.exit_code,
        denied_reason=result.denied_reason,
    )


@router.get("/sessions/{session_id}/git/status", response_model=CodeGitStatusResponse)
async def get_git_status(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    registry = _build_tool_registry(workspace, current_user.role)
    existing_events = await CodeEventService.list_events(db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
    before_seq = existing_events[-1].seq_no if existing_events else None
    status_result = registry.execute_git_status()
    diff_result = registry.execute_git_diff_summary()

    await session_service.record_tool_call(
        db,
        session_id=session_id,
        turn_id=None,
        tool_name="git_ops",
        tool_class="git",
        input_summary="git status --short --branch",
        result_summary=status_result.output[:1000],
        exit_code=status_result.exit_code,
        was_denied=status_result.denied_reason is not None,
        denial_reason=status_result.denied_reason,
    )
    if status_result.denied_reason is not None:
        await CodeEventService.append_event(
            db,
            session_id=session_id,
            event_type="code.permission.denied",
            payload={"tool_name": "git_ops", "reason": status_result.denied_reason},
        )
    await CodeEventService.append_event(
        db,
        session_id=session_id,
        event_type="code.tool.finished",
        payload={
            "tool_name": "git_ops",
            "exit_code": status_result.exit_code,
            "success": status_result.success,
            "denied_reason": status_result.denied_reason,
        },
    )
    await db.commit()
    await _broadcast_events_since(tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db)
    return CodeGitStatusResponse(
        session_id=code_session.id,
        branch=code_session.session_branch,
        success=status_result.success,
        output=status_result.output,
        diff_summary=diff_result.output,
        exit_code=status_result.exit_code,
    )


@router.get("/sessions/{session_id}/git/branch-state", response_model=CodeBranchStateResponse)
async def get_branch_state(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    branch_state = await CodeBranchService.refresh_branch_state(
        db,
        workspace=workspace,
        branch_name=code_session.session_branch,
        role=current_user.role,
        safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    await db.commit()
    await db.refresh(branch_state)
    return CodeBranchStateResponse.model_validate(branch_state)


@router.post("/sessions/{session_id}/git/refresh", response_model=CodeBranchStateResponse)
async def refresh_branch_state(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_events = await CodeEventService.list_events(
        db, session_id=session_id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT
    )
    before_seq = before_events[-1].seq_no if before_events else None
    branch_state = await CodeBranchService.refresh_branch_state(
        db,
        workspace=workspace,
        branch_name=code_session.session_branch,
        role=current_user.role,
        safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    readiness = CodeBranchService.summarize_branch_readiness(branch_state)
    await CodeEventService.append_event(
        db,
        session_id=session_id,
        event_type="code.session.status",
        payload={
            "branch_status": branch_state.branch_status,
            "is_dirty": branch_state.is_dirty,
            "is_stale_against_base": branch_state.is_stale_against_base,
            "readiness": readiness.readiness,
        },
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await db.refresh(branch_state)
    await _broadcast_events_since(
        tenant_id=current_user.tenant_id, session_id=session_id, after_seq=before_seq, db=db
    )
    return CodeBranchStateResponse.model_validate(branch_state)


@router.get("/sessions/{session_id}/readiness", response_model=CodeReadinessResponse)
async def get_readiness(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    branch_state = await CodeBranchService.refresh_branch_state(
        db,
        workspace=workspace,
        branch_name=code_session.session_branch,
        role=current_user.role,
        safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
        max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
        max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
    )
    readiness = CodeBranchService.summarize_branch_readiness(branch_state)
    recovery = await CodeRecoveryService.suggest_recovery_actions(db, session=code_session)
    await db.commit()
    await db.refresh(branch_state)
    return CodeReadinessResponse(
        session_id=session_id,
        branch_state=CodeBranchStateResponse.model_validate(branch_state),
        readiness=readiness.readiness,
        blocking_reasons=readiness.blocking_reasons,
        failure_class=recovery.failure_class,
        headline=recovery.headline,
        recommended_actions=recovery.recommended_actions,
        evidence=recovery.evidence,
    )


@router.get("/sessions/{session_id}/recovery", response_model=CodeRecoveryResponse)
async def get_recovery(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    code_session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    recovery = await CodeRecoveryService.suggest_recovery_actions(db, session=code_session)
    return CodeRecoveryResponse(
        session_id=session_id,
        status=recovery.status,
        failure_class=recovery.failure_class,
        headline=recovery.headline,
        recommended_actions=recovery.recommended_actions,
        next_safe_action=recovery.next_safe_action,
        blocking_reasons=recovery.blocking_reasons,
        evidence=recovery.evidence,
    )


@router.get("/workspace/mcp/servers", response_model=list[CodeMcpServerResponse])
async def list_mcp_servers(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    servers = await CodeMcpService.list_servers(db, workspace_id=workspace.id)
    return [_serialize_mcp_server(server) for server in servers]


@router.post("/workspace/mcp/servers/connect", response_model=CodeMcpServerResponse)
async def connect_mcp_server(
    body: CodeMcpServerConnectRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    server = await CodeMcpService.connect_server(
        db,
        workspace=workspace,
        tenant_id=current_user.tenant_id,
        server_name=body.server_name,
        transport=body.transport,
    )
    await db.commit()
    return _serialize_mcp_server(server)


@router.post("/workspace/mcp/servers/disconnect", response_model=CodeMcpServerResponse)
async def disconnect_mcp_server(
    body: CodeMcpServerConnectRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    server = await CodeMcpService.disconnect_server(
        db,
        workspace_id=workspace.id,
        server_name=body.server_name,
    )
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
    await db.commit()
    return _serialize_mcp_server(server)


@router.get("/workspace/mcp/resources", response_model=list[CodeMcpResourceResponse])
async def list_mcp_resources(
    request: Request,
    server_name: str = Query(...),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    try:
        resources = await CodeMcpService.list_resources(
            db,
            workspace_id=workspace.id,
            server_name=server_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [CodeMcpResourceResponse.model_validate(item) for item in resources]


@router.get("/workspace/mcp/resource", response_model=CodeMcpResourceReadResponse)
async def read_mcp_resource(
    request: Request,
    server_name: str = Query(...),
    uri: str = Query(...),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    try:
        resource = await CodeMcpService.read_resource(
            db,
            workspace=workspace,
            server_name=server_name,
            uri=uri,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CodeMcpResourceReadResponse.model_validate(resource)


@router.get("/workspace/lsp/diagnostics", response_model=CodeLspDiagnosticsPayload)
async def get_lsp_diagnostics(
    request: Request,
    language: str = Query(default="python"),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    lsp_session, diagnostics = await CodeLspService.get_diagnostics(
        db,
        workspace=workspace,
        language=language,
    )
    await db.commit()
    await db.refresh(lsp_session)
    return CodeLspDiagnosticsPayload(
        session=_serialize_lsp_session(lsp_session),
        diagnostics=[CodeLspDiagnosticResponse.model_validate(item) for item in diagnostics],
    )


@router.get("/workspace/lsp/symbols", response_model=CodeLspSymbolsPayload)
async def get_lsp_symbols(
    request: Request,
    language: str = Query(default="python"),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    lsp_session, symbols = await CodeLspService.get_symbols(
        db,
        workspace=workspace,
        language=language,
    )
    await db.commit()
    await db.refresh(lsp_session)
    return CodeLspSymbolsPayload(
        session=_serialize_lsp_session(lsp_session),
        symbols=[CodeLspSymbolResponse.model_validate(item) for item in symbols],
    )


@router.get("/workspace/tasks", response_model=list[CodeTaskResponse])
async def list_code_tasks(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    tasks = await CodeTaskService.list_tasks(db, workspace_id=workspace.id)
    return [_serialize_task(task) for task in tasks]


@router.post("/workspace/tasks", response_model=CodeTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_code_task(
    body: CodeTaskCreateRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    task = await CodeTaskService.create_task(
        db,
        workspace=workspace,
        user=current_user,
        session_id=body.session_id,
        title=body.title,
        objective=body.objective,
        scope=body.scope,
        acceptance_criteria=body.acceptance_criteria,
        task_packet=body.task_packet.model_dump() if body.task_packet else None,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_task(task)


@router.post("/workspace/tasks/{task_id}/architect-route", response_model=CodeTaskResponse)
async def architect_route_code_task(
    body: CodeTaskArchitectRouteRequest,
    request: Request,
    task_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    task, _architect, _target_worker = await CodeTaskService.architect_route_task(
        db,
        workspace_id=workspace.id,
        task_id=task_id,
        acceptance_criteria=body.acceptance_criteria,
        summary=body.summary,
        route_to=body.route_to,
        payload=body.payload,
    )
    await _maybe_execute_executor_subagent(
        db=db,
        workspace=workspace,
        task_id=task.id,
        worker_name=body.route_to,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_task(task)


@router.post("/workspace/tasks/{task_id}/architect-plan", response_model=CodeTaskArchitectPlanResponse)
async def architect_plan_code_task(
    body: CodeTaskArchitectPlanRequest,
    request: Request,
    task_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    task, _architect, route_suggestion, plan_payload = await CodeTaskService.architect_plan_task(
        db,
        workspace_id=workspace.id,
        task_id=task_id,
        regenerate=body.regenerate,
        summary=body.summary,
        payload=body.payload,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return CodeTaskArchitectPlanResponse(
        task=_serialize_task(task),
        route_to=route_suggestion,
        plan_summary=_architect.last_event_summary or f"Architect drafted plan for task #{task.id}",
        acceptance_criteria=task.acceptance_criteria or [],
        payload=plan_payload,
    )


@router.post("/workspace/tasks/{task_id}/review-request", response_model=CodeTaskResponse)
async def request_code_task_review(
    body: CodeTaskReviewRequest,
    request: Request,
    task_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    task, _executor, _reviewer = await CodeTaskService.request_review(
        db,
        workspace_id=workspace.id,
        task_id=task_id,
        summary=body.summary,
        payload=body.payload,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_task(task)


@router.post("/workspace/tasks/{task_id}/review-decision", response_model=CodeTaskResponse)
async def submit_code_task_review_decision(
    body: CodeTaskReviewDecisionRequest,
    request: Request,
    task_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    task, _executor, _reviewer = await CodeTaskService.submit_review_decision(
        db,
        workspace_id=workspace.id,
        task_id=task_id,
        decision=body.decision,
        summary=body.summary,
        reason=body.reason,
        reason_code=body.reason_code,
        checklist=body.checklist,
        payload=body.payload,
    )
    await CodeRuntimeService.record_policy_signal(
        db,
        workspace_id=workspace.id,
        category="review_decision",
        outcome=body.decision,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_task(task)


@router.get("/workspace/workers", response_model=list[CodeWorkerResponse])
async def list_code_workers(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    workers = await CodeTaskService.ensure_default_workers(db, workspace=workspace)
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    serialized_workers = []
    for worker in workers:
        serialized_workers.append(
            _serialize_worker(
                worker,
                task_status=await _task_status_by_task_id(db, task_id=getattr(worker, "task_id", None)),
            )
        )
    return serialized_workers


@router.get("/workspace/orchestration", response_model=CodeOrchestrationSnapshotResponse)
async def get_code_orchestration_snapshot(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    return await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)


@router.post("/workspace/orchestration/execute-next-automation", response_model=CodeAutomationExecutionResponse)
async def execute_next_automation_action(
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)

    session = await db.execute(
        select(CodeSession)
        .where(CodeSession.workspace_id == workspace.id)
        .order_by(CodeSession.created_at.desc())
    )
    latest_session = session.scalars().first()
    before_events = (
        await CodeEventService.list_events(
            db,
            session_id=latest_session.id,
            after_seq=None,
            limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
        )
        if latest_session is not None
        else []
    )
    before_seq = before_events[-1].seq_no if before_events else None

    try:
        result = await CodeAutomationService.execute_next_automation(
            db,
            workspace=workspace,
            role=current_user.role,
            safe_bash_timeout_sec=settings.BOS_CODE_SAFE_BASH_TIMEOUT_SEC,
            max_read_bytes=settings.BOS_CODE_MAX_FILE_READ_BYTES,
            max_write_bytes=settings.BOS_CODE_MAX_FILE_WRITE_BYTES,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"no_automation_action_available", "automation_not_ready", "automation_action_unsupported"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    if result.session_id is not None:
        await CodeEventService.append_event(
            db,
            session_id=result.session_id,
            event_type="code.session.status",
            payload={
                "source": "automation_executor",
                "executed_action": result.executed_action,
                "execution_status": result.execution_status,
                "summary": result.summary,
            },
        )

    await CodeRuntimeService.record_automation_execution(
        db,
        workspace_id=workspace.id,
        session_id=result.session_id,
        executed_action=result.executed_action,
        execution_status=result.execution_status,
        summary=result.summary,
        executed_at=result.executed_at,
        resulting_session_status=result.resulting_session_status,
        resulting_verification_status=result.resulting_verification_status,
    )

    snapshot = await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()

    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    if result.session_id is not None:
        await _broadcast_events_since(
            tenant_id=current_user.tenant_id,
            session_id=result.session_id,
            after_seq=before_seq,
            db=db,
        )

    return CodeAutomationExecutionResponse(
        workspace_id=workspace.id,
        session_id=result.session_id,
        executed_action=result.executed_action,
        execution_status=result.execution_status,
        summary=result.summary,
        executed_at=result.executed_at,
        resulting_session_status=result.resulting_session_status,
        resulting_verification_status=result.resulting_verification_status,
        snapshot=snapshot,
    )


@router.get("/workspace/runtime", response_model=CodeRuntimeResponse)
async def get_code_runtime(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    runtime, jobs, active_subagents, pending_reflections = await CodeRuntimeService.get_runtime_payload(
        db,
        workspace_id=workspace.id,
    )
    try:
        team_models = await list_team_chat_models()
    except CodeProviderError:
        team_models = []
    return CodeRuntimeResponse(
        workspace_id=workspace.id,
        runtime_state=_serialize_runtime_state(runtime),
        automation_jobs=[_serialize_automation_job(job) for job in jobs],
        active_subagents=[_serialize_subagent_run(run) for run in active_subagents],
        pending_reflections=pending_reflections,
        available_providers=[
            {
                "name": profile.name,
                "label": profile.label,
                "base_url": profile.base_url,
                "default_model": profile.default_model,
                "is_default": profile.is_default,
            }
            for profile in list_available_provider_profiles()
        ],
        team_models=team_models,
    )


@router.get("/release-readiness", response_model=CodeReleaseReadinessResponse)
async def get_code_release_readiness(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    manifest = _read_json(RELEASE_MANIFEST_PATH)
    if not manifest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="release_readiness_not_generated")

    report_markdown = RELEASE_DOSSIER_PATH.read_text(encoding="utf-8") if RELEASE_DOSSIER_PATH.exists() else ""
    artifacts = []
    for key, (path, label, content_type) in _artifact_registry().items():
        if not path.exists():
            continue
        artifacts.append(
            CodeReleaseArtifactResponse(
                key=key,
                label=label,
                relative_path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                download_url=f"/api/v1/code/release-artifacts/{key}",
                content_type=content_type,
            )
        )

    checks = [
        CodeReleaseCheckResponse(
            status=item.get("status", "UNKNOWN"),
            name=item.get("name", "unknown"),
            summary=item.get("summary", ""),
        )
        for item in manifest.get("checks", [])
    ]

    return CodeReleaseReadinessResponse(
        generated_at=manifest.get("generated_at"),
        release_state=manifest.get("release_state", "UNKNOWN"),
        backend_version=manifest.get("backend_version", "unknown"),
        frontend_version=manifest.get("frontend_version", "unknown"),
        git_branch=manifest.get("git_branch", "unknown"),
        git_commit=manifest.get("git_commit", "unknown"),
        preflight_pass_count=manifest.get("preflight_pass_count", 0),
        preflight_warn_count=manifest.get("preflight_warn_count", 0),
        preflight_fail_count=manifest.get("preflight_fail_count", 0),
        known_warnings=manifest.get("known_warnings", []),
        known_limitations=manifest.get("known_limitations", []),
        recommended_next_action=manifest.get("recommended_next_action"),
        checks=checks,
        report_markdown=report_markdown,
        report_path=str(RELEASE_DOSSIER_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        code_smoke_path=manifest.get("code_smoke_path"),
        bos_smoke_path=manifest.get("bos_smoke_path"),
        artifacts=artifacts,
    )


@router.get("/release-artifacts/{artifact_key}")
async def download_code_release_artifact(
    request: Request,
    artifact_key: str,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    registry = _artifact_registry()
    artifact = registry.get(artifact_key)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="release_artifact_not_found")
    path, _label, content_type = artifact
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="release_artifact_missing")
    return FileResponse(path, media_type=content_type, filename=path.name)


@router.get("/workspace/automations", response_model=list[CodeAutomationJobResponse])
async def list_code_automation_jobs(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    jobs = await CodeRuntimeService.list_jobs(db, workspace_id=workspace.id)
    return [_serialize_automation_job(job) for job in jobs]


@router.post("/workspace/automations", response_model=CodeAutomationJobResponse, status_code=status.HTTP_201_CREATED)
async def create_code_automation_job(
    body: CodeAutomationJobCreateRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    job = await CodeRuntimeService.create_job(
        db,
        workspace=workspace,
        tenant_id=current_user.tenant_id,
        payload=body.model_dump(),
    )
    await db.commit()
    await db.refresh(job)
    return _serialize_automation_job(job)


@router.patch("/workspace/automations/{job_id}", response_model=CodeAutomationJobResponse)
async def update_code_automation_job(
    body: CodeAutomationJobUpdateRequest,
    request: Request,
    job_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    job = await CodeRuntimeService.update_job(
        db,
        workspace_id=workspace.id,
        job_id=job_id,
        payload=body.model_dump(exclude_unset=True),
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="automation_job_not_found")
    await db.commit()
    await db.refresh(job)
    return _serialize_automation_job(job)


@router.post("/workspace/automations/{job_id}/run", response_model=CodeAutomationJobResponse)
async def run_code_automation_job(
    request: Request,
    job_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    job = await CodeAutomationJobService.get_job(db, workspace_id=workspace.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="automation_job_not_found")
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    existing_session = await db.execute(
        select(CodeSession).where(CodeSession.workspace_id == workspace.id).order_by(CodeSession.created_at.desc())
    )
    latest_session = existing_session.scalars().first()
    before_events = (
        await CodeEventService.list_events(db, session_id=latest_session.id, after_seq=None, limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT)
        if latest_session is not None
        else []
    )
    before_seq = before_events[-1].seq_no if before_events else None
    try:
        job, used_session, _summary = await CodeAutomationJobService.execute_job(
            db,
            workspace=workspace,
            job=job,
            user=current_user,
            session_service=session_service,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(job)
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    if used_session is not None:
        await _broadcast_events_since(
            tenant_id=current_user.tenant_id,
            session_id=used_session.id,
            after_seq=before_seq,
            db=db,
        )
    return _serialize_automation_job(job)


@router.post("/workspace/workers/assign", response_model=CodeWorkerResponse)
async def assign_code_worker(
    body: CodeWorkerAssignRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    worker = await CodeTaskService.assign_worker(
        db,
        workspace_id=workspace.id,
        task_id=body.task_id,
        worker_name=body.worker_name,
    )
    await _maybe_execute_executor_subagent(
        db=db,
        workspace=workspace,
        task_id=body.task_id,
        worker_name=body.worker_name,
    )
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_worker(worker, task_status=await _task_status_by_task_id(db, task_id=getattr(worker, "task_id", None)))


@router.post("/workspace/workers/{worker_name}/status", response_model=CodeWorkerResponse)
async def update_code_worker_status(
    body: CodeWorkerStatusUpdateRequest,
    request: Request,
    worker_name: str,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    before_snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
    before_id = await CodeWorkerEventService.get_latest_event_id(db, workspace_id=workspace.id)
    try:
        worker = await CodeTaskService.update_worker_status(
            db,
            workspace_id=workspace.id,
            worker_name=worker_name,
            worker_status=body.worker_status,
            last_error=body.last_error,
            last_event_summary=body.last_event_summary,
            lane=body.lane,
            event_name=body.event_name,
            payload=body.payload,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail in {"worker_not_found", "worker_lane_invalid"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    await _maybe_emit_merge_readiness_event(
        db=db,
        workspace_id=workspace.id,
        previous_snapshot=before_snapshot,
    )
    await db.commit()
    await _broadcast_worker_events_since(
        tenant_id=current_user.tenant_id,
        workspace_id=workspace.id,
        after_id=before_id,
        db=db,
    )
    return _serialize_worker(worker, task_status=await _task_status_by_task_id(db, task_id=getattr(worker, "task_id", None)))


@router.get("/workspace/worker-events", response_model=CodeWorkerEventListResponse)
async def list_code_worker_events(
    request: Request,
    after_id: int | None = Query(default=None),
    lane: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    worker_name: str | None = Query(default=None),
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)

    worker_id: int | None = None
    if worker_name:
        worker_result = await db.execute(
            select(CodeWorker).where(
                CodeWorker.workspace_id == workspace.id,
                CodeWorker.worker_name == worker_name,
            )
        )
        worker = worker_result.scalar_one_or_none()
        if worker is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
        worker_id = worker.id

    events = await CodeWorkerEventService.list_events(
        db,
        workspace_id=workspace.id,
        after_id=after_id,
        lane=lane,
        task_id=task_id,
        worker_id=worker_id,
        limit=settings.BOS_CODE_EVENT_REPLAY_LIMIT,
    )
    next_id = events[-1].id if events else after_id
    return CodeWorkerEventListResponse(
        items=[_serialize_worker_event(item) for item in events],
        after_id=after_id,
        next_id=next_id,
    )


@router.get("/memory/{session_id}", response_model=list[CodeMemorySnapshotResponse])
async def list_code_memory_snapshots(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    await _get_session_or_404(db, current_user.tenant_id, session_id)
    snapshots = await CodeMemoryService.list_snapshots(db, session_id=session_id)
    return [_serialize_memory_snapshot(item) for item in snapshots]


@router.post("/memory/{session_id}/refresh", response_model=CodeMemoryRefreshResponse)
async def refresh_code_memory_snapshot(
    request: Request,
    session_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    session = await _get_session_or_404(db, current_user.tenant_id, session_id)
    snapshot = await CodeMemoryService.refresh_snapshot(db, session=session, force=True)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="memory_snapshot_unavailable")
    await db.commit()
    await db.refresh(snapshot)
    return CodeMemoryRefreshResponse(session_id=session_id, snapshot=_serialize_memory_snapshot(snapshot))


@router.post("/session-search", response_model=CodeSessionSearchResponse)
async def search_code_sessions(
    body: CodeSessionSearchRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    results = await CodeSessionSearchService.search(
        db,
        tenant_id=current_user.tenant_id,
        query=body.query,
        limit=body.limit,
    )
    return CodeSessionSearchResponse(
        query=body.query,
        results=[CodeSessionSearchResultResponse(**item) for item in results],
    )


@router.get("/workspace/reflections", response_model=list[CodeReflectionRunResponse])
async def list_code_reflections(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    reflections = await CodeReflectionService.list_reflections(db, workspace_id=workspace.id)
    return [await _serialize_reflection(db, item) for item in reflections]


@router.post("/workspace/reflections/run", response_model=CodeReflectionRunResponse)
async def run_code_reflection(
    body: CodeReflectionRunRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    session = await _get_session_or_404(db, current_user.tenant_id, body.session_id)
    reflection = await CodeReflectionService.run_reflection(
        db,
        workspace=workspace,
        session=session,
        user=current_user,
        trigger_source=body.trigger_source,
        task_id=body.task_id,
    )
    await db.commit()
    await db.refresh(reflection)
    return await _serialize_reflection(db, reflection)


@router.get("/workspace/skills", response_model=list[CodeSkillResponse])
async def list_code_skills(
    request: Request,
    current_user: User = Depends(require_minimum_role("operator")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    skills = await CodeSkillService.list_skills(db, workspace_id=workspace.id)
    return [await _serialize_skill(db, item) for item in skills]


@router.post("/workspace/skills", response_model=CodeSkillResponse, status_code=status.HTTP_201_CREATED)
async def create_code_skill(
    body: CodeSkillCreateRequest,
    request: Request,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    try:
        skill = await CodeSkillService.create_skill(
            db,
            workspace=workspace,
            user=current_user,
            name=body.name,
            slug=body.slug,
            description=body.description,
            content_markdown=body.content_markdown,
            supporting_files=body.supporting_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(skill)
    return await _serialize_skill(db, skill)


@router.patch("/workspace/skills/{skill_id}", response_model=CodeSkillResponse)
async def update_code_skill(
    body: CodeSkillUpdateRequest,
    request: Request,
    skill_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    skill = await CodeSkillService.get_skill(db, workspace_id=workspace.id, skill_id=skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="skill_not_found")
    try:
        skill = await CodeSkillService.update_skill(
            db,
            workspace=workspace,
            skill=skill,
            description=body.description,
            skill_status=body.skill_status,
            change_summary=body.change_summary,
            content_markdown=body.content_markdown,
            supporting_files=body.supporting_files or {},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(skill)
    return await _serialize_skill(db, skill)


@router.post("/workspace/skills/{skill_id}/feedback", response_model=CodeSkillResponse)
async def feedback_code_skill(
    body: CodeSkillFeedbackRequest,
    request: Request,
    skill_id: int,
    current_user: User = Depends(require_minimum_role("scientist")),
    db: AsyncSession = Depends(get_async_session),
):
    await _ensure_bos_code_enabled(request, db, current_user.tenant_id)
    workspace = await _get_workspace_or_404(db, current_user.tenant_id)
    skill = await CodeSkillService.get_skill(db, workspace_id=workspace.id, skill_id=skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="skill_not_found")
    try:
        skill = await CodeSkillService.record_feedback(
            db,
            skill=skill,
            sentiment=body.sentiment,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(skill)
    return await _serialize_skill(db, skill)
