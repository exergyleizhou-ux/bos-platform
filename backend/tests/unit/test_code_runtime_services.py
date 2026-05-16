import json
import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from types import SimpleNamespace

from app.models import CodeArtifact, CodeBranchState, CodeEvent, CodeSession, CodeTask, CodeToolCall, CodeTurn, CodeVerificationRun, CodeWorker, CodeWorkerEvent
from app.services.brain_runtime import RunLedgerArtifact
from app.services.code.automation_job_service import CodeAutomationJobService
from app.services.code.automation_service import CodeAutomationService
from app.services.code.maintenance_service import CodeMaintenanceService
from app.services.code.memory_service import CodeMemoryService
from app.services.code.mcp_service import CodeMcpService
from app.services.code.orchestration_service import CodeOrchestrationService
from app.services.code.provider_budget_service import CodeProviderBudgetService
from app.services.code.reflection_service import CodeReflectionService
from app.services.code.recovery_loop_service import CodeRecoveryLoopService
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.session_search_service import CodeSessionSearchService
from app.services.code.providers import CodeProviderError, CodeProviderResponse
from app.services.code.session_service import CodeSessionService
from app.services.code.skill_service import CodeSkillService
from app.services.code.subagent_service import CodeSubagentService
from app.services.code.task_service import CodeTaskService
from app.services.code.workflow_orchestrator_service import CodeWorkflowOrchestratorService
from app.services.code.workspace_service import CodeWorkspaceService


async def _make_workspace_session(
    db_session: AsyncSession,
    *,
    user,
) -> tuple:
    workspace = await CodeWorkspaceService.ensure_workspace(db_session, user=user)
    session = CodeSession(
        tenant_id=user.tenant_id,
        user_id=user.id,
        workspace_id=workspace.id,
        provider="openai-team",
        model="gpt-5.5",
        permission_mode="workspace-write",
        session_branch=f"boscode/tenant-{user.tenant_id}/session-test-{user.id}",
        session_status="ready",
        verification_status="pending",
        token_usage={},
        estimated_cost=0.0,
    )
    db_session.add(session)
    await db_session.flush()
    return workspace, session


@pytest.mark.asyncio
async def test_heartbeat_decision_detects_active_work(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    db_session.add(
        CodeTask(
            tenant_id=scientist_user.tenant_id,
            user_id=scientist_user.id,
            workspace_id=workspace.id,
            session_id=session.id,
            title="Review runtime",
            objective="Check BOS runtime",
            scope="code/runtime",
            task_status="review_pending",
            priority="normal",
            acceptance_criteria=[],
        )
    )
    await db_session.flush()

    decision, summary, packet = await CodeAutomationJobService._heartbeat_decision(db_session, workspace_id=workspace.id)
    assert decision == "run"
    assert "open tasks" in summary
    assert "Focus task" in summary
    assert packet["decision_source"] in {"heuristic", "heuristic_fallback"}
    assert packet["planner_recommendation"] in {
        "architect_plan",
        "request_review",
        "begin_review",
        "run_verification",
        "refresh_branch",
        "inspect_context",
    }
    assert isinstance(packet["critic_notes"], list)
    assert isinstance(packet["planner_steps"], list)
    assert isinstance(packet["critic_checks"], list)
    assert packet["loop_budget"] in {"short", "standard", "deep", "exit"}
    assert packet["convergence_signal"] in {
        "ready_to_exit",
        "continue_until_next_gate",
        "needs_more_evidence",
        "idle",
    }


@pytest.mark.asyncio
async def test_workspace_seeds_maintenance_job(
    db_session: AsyncSession,
    scientist_user,
):
    workspace = await CodeWorkspaceService.ensure_workspace(db_session, user=scientist_user)

    jobs = await CodeRuntimeService.list_jobs(db_session, workspace_id=workspace.id)
    names = {job.name: job for job in jobs}

    assert "autonomy-maintenance" in names
    assert names["autonomy-maintenance"].job_type == "maintenance"
    assert names["autonomy-maintenance"].interval_sec == 10800


@pytest.mark.asyncio
async def test_workflow_orchestrator_prefers_recovery_mode_for_blocked_signals(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Recovery task",
        objective="Recover from verification failure",
        scope="code/recovery",
        task_status="running",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    plan = CodeWorkflowOrchestratorService.plan(
        query="fix the failing runtime",
        open_tasks=[task],
        latest_session=session,
        recent_verifications=[],
        recent_events=[],
        skills=[],
    )

    assert plan.mode == "recovery"
    assert "bos-systematic-debugging" in plan.recommended_skills
    assert "bos-verification-gate" in plan.recommended_skills


@pytest.mark.asyncio
async def test_create_task_populates_structured_task_packet(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)

    task = await CodeTaskService.create_task(
        db_session,
        workspace=workspace,
        user=scientist_user,
        session_id=session.id,
        title="Structured packet task",
        objective="Add structured runtime packet coverage",
        scope="code/runtime",
        acceptance_criteria=["Run the relevant verification gate", "Keep reviewer handoff readable"],
        task_packet=None,
    )

    assert task.task_packet is not None
    assert task.task_packet["objective"] == "Add structured runtime packet coverage"
    assert task.task_packet["scope"] == "code/runtime"
    assert "branch_policy" in task.task_packet
    assert "reporting_contract" in task.task_packet
    assert "Run the relevant verification gate" in task.task_packet["acceptance_tests"]


@pytest.mark.asyncio
async def test_mcp_connect_server_surfaces_degraded_runtime_contract(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)

    degraded = await CodeMcpService.connect_server(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        server_name="broken-demo",
        transport="stub",
    )
    auth = await CodeMcpService.connect_server(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        server_name="auth-demo",
        transport="stub",
    )

    assert degraded.connection_status == "degraded"
    assert degraded.capabilities["failure_class"] == "mcp_startup"
    assert degraded.capabilities["startup_phase"] == "degraded_startup"
    assert degraded.capabilities["recovery_recommendations"]

    assert auth.connection_status == "auth_required"
    assert auth.capabilities["failure_class"] == "trust_gate"
    assert auth.capabilities["degraded_scope"] == "authentication"


@pytest.mark.asyncio
async def test_automation_can_soft_reset_prompt_delivery_session(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    session.session_status = "blocked"
    turn = CodeTurn(
        session_id=session.id,
        turn_index=1,
        user_message="Continue the runtime flow",
        assistant_summary="The prompt may have landed in the wrong runtime surface.",
        turn_status="failed",
    )
    db_session.add(turn)
    await db_session.flush()
    db_session.add(
        CodeToolCall(
            session_id=session.id,
            turn_id=turn.id,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary="Continue the runtime flow",
            result_summary="Prompt was delivered to the wrong shell target.",
            was_denied=True,
            denial_reason="prompt_misdelivery",
        )
    )
    await db_session.flush()

    snapshot = await CodeOrchestrationService.build_snapshot(db_session, workspace_id=workspace.id)
    assert snapshot.next_automation_action == "reset_session_ready"
    assert snapshot.automation_ready is True

    result = await CodeAutomationService.execute_next_automation(
        db_session,
        workspace=workspace,
        role="scientist",
        safe_bash_timeout_sec=5,
        max_read_bytes=1024,
        max_write_bytes=1024,
    )
    await db_session.flush()
    await db_session.refresh(session)

    assert result.executed_action == "reset_session_ready"
    assert session.session_status == "ready_for_prompt"

    session_events = await db_session.execute(
        select(CodeEvent).where(CodeEvent.session_id == session.id).order_by(CodeEvent.id.asc())
    )
    status_events = [
        event for event in session_events.scalars().all() if event.event_type == "code.session.status"
    ]
    assert any(
        event.payload.get("session_status") == "ready_for_prompt"
        and event.payload.get("source") == "automation_executor"
        for event in status_events
    )


@pytest.mark.asyncio
async def test_orchestration_prefers_session_reset_over_diff_when_prompt_delivery_is_recoverable(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    session.session_status = "blocked"
    db_session.add(
        CodeBranchState(
            workspace_id=workspace.id,
            branch_name=session.session_branch,
            base_branch=workspace.base_branch,
            head_commit="abc",
            base_commit="def",
            merge_base_commit="aaa",
            is_dirty=True,
            is_stale_against_base=False,
            ahead_count=0,
            behind_count=0,
            branch_status="dirty",
        )
    )
    db_session.add(
        CodeToolCall(
            session_id=session.id,
            turn_id=None,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary="Resume the thread",
            result_summary="Prompt was delivered to the wrong runtime surface.",
            was_denied=True,
            denial_reason="prompt_misdelivery",
        )
    )
    await db_session.flush()

    snapshot = await CodeOrchestrationService.build_snapshot(db_session, workspace_id=workspace.id)

    assert snapshot.next_automation_action == "reset_session_ready"
    assert snapshot.automation_ready is True


@pytest.mark.asyncio
async def test_session_failure_seeds_recovery_task(
    db_session: AsyncSession,
    scientist_user,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    postmortem_calls = {"count": 0}

    class FakeSubagentService:
        async def create_runs_for_task(self, db, *, workspace, session, task, worker, metadata=None):
            return [SimpleNamespace(id=701)]

        async def enqueue_or_execute_run(self, db, *, run_id):
            return SimpleNamespace(id=run_id, run_status="running")

    async def fake_postmortem(cls, db, *, workspace, session, user, trigger_source, task_id=None):
        postmortem_calls["count"] += 1
        return None

    monkeypatch.setattr(CodeRecoveryLoopService, "subagent_service", FakeSubagentService())
    monkeypatch.setattr(CodeRecoveryLoopService, "ensure_postmortem_reflection", classmethod(fake_postmortem))

    service = CodeSessionService()
    turn, _prompt = await service.initialize_turn(
        db_session,
        session=session,
        user_message="Continue the runtime thread",
    )
    await service.fail_turn(
        db_session,
        session=session,
        turn=turn,
        user_message="Continue the runtime thread",
        exc=CodeProviderError(
            "prompt misdelivery",
            blocked_reason="prompt_misdelivery",
            user_message="The prompt may have landed in the wrong runtime surface.",
        ),
    )
    await db_session.flush()

    tasks = await CodeTaskService.list_tasks(db_session, workspace_id=workspace.id)
    assert any(task.scope == "code/recovery" for task in tasks)
    recovery_task = next(task for task in tasks if task.scope == "code/recovery")
    assert recovery_task.task_status == "running"
    assert "prompt_delivery" in recovery_task.objective
    assert postmortem_calls["count"] == 1


@pytest.mark.asyncio
async def test_recovery_snapshot_surfaces_next_safe_action_for_prompt_delivery(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    session.session_status = "blocked"
    db_session.add(
        CodeToolCall(
            session_id=session.id,
            turn_id=None,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary="Resume the thread",
            result_summary="Prompt was delivered to the wrong shell target.",
            was_denied=True,
            denial_reason="prompt_misdelivery",
        )
    )
    await db_session.flush()

    from app.services.code.recovery_service import CodeRecoveryService

    recovery = await CodeRecoveryService.suggest_recovery_actions(db_session, session=session)

    assert recovery.failure_class == "prompt_delivery"
    assert recovery.next_safe_action == "reset_session_ready"


@pytest.mark.asyncio
async def test_recovery_snapshot_prefers_latest_denied_tool_signal_over_newer_non_denied_calls(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    db_session.add(
        CodeToolCall(
            session_id=session.id,
            turn_id=None,
            tool_name="provider_dispatch",
            tool_class="provider",
            input_summary="Resume the thread",
            result_summary="Prompt was delivered to the wrong runtime surface.",
            was_denied=True,
            denial_reason="prompt_misdelivery",
        )
    )
    await db_session.flush()
    db_session.add(
        CodeToolCall(
            session_id=session.id,
            turn_id=None,
            tool_name="git_ops",
            tool_class="git",
            input_summary="Refresh git posture",
            result_summary="workspace is dirty",
            was_denied=False,
        )
    )
    session.session_status = "blocked"
    await db_session.flush()

    from app.services.code.recovery_service import CodeRecoveryService

    recovery = await CodeRecoveryService.suggest_recovery_actions(db_session, session=session)

    assert recovery.failure_class == "prompt_delivery"
    assert recovery.next_safe_action == "reset_session_ready"
    assert recovery.evidence["latest_tool_denial_reason"] == "prompt_misdelivery"


@pytest.mark.asyncio
async def test_recovery_snapshot_surfaces_refresh_branch_for_stale_branch(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    db_session.add(
        CodeBranchState(
            workspace_id=workspace.id,
            branch_name=session.session_branch,
            base_branch=workspace.base_branch,
            head_commit="abc",
            base_commit="def",
            merge_base_commit="aaa",
            is_dirty=False,
            is_stale_against_base=True,
            ahead_count=0,
            behind_count=3,
            branch_status="stale",
        )
    )
    await db_session.flush()

    from app.services.code.recovery_service import CodeRecoveryService

    recovery = await CodeRecoveryService.suggest_recovery_actions(db_session, session=session)

    assert recovery.failure_class == "stale_branch"
    assert recovery.next_safe_action == "refresh_branch"


@pytest.mark.asyncio
async def test_recovery_snapshot_surfaces_run_verification_for_failed_verification(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    db_session.add(
        CodeVerificationRun(
            session_id=session.id,
            verification_stage="lint",
            verification_status="failed",
            summary="lint failed",
            log_excerpt="example lint failure",
        )
    )
    session.verification_status = "failed"
    await db_session.flush()

    from app.services.code.recovery_service import CodeRecoveryService

    recovery = await CodeRecoveryService.suggest_recovery_actions(db_session, session=session)

    assert recovery.failure_class == "verification_failed"
    assert recovery.next_safe_action == "run_verification"


@pytest.mark.asyncio
async def test_recovery_snapshot_blocks_automatic_verification_when_review_gate_is_active(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    session.verification_status = "failed"
    db_session.add(
        CodeTask(
            tenant_id=scientist_user.tenant_id,
            user_id=scientist_user.id,
            workspace_id=workspace.id,
            session_id=session.id,
            title="Reviewer is still evaluating",
            objective="Hold the review gate before verification reruns.",
            scope="code/runtime",
            task_status="review_pending",
            priority="normal",
            acceptance_criteria=[],
        )
    )
    db_session.add(
        CodeVerificationRun(
            session_id=session.id,
            verification_stage="lint",
            verification_status="failed",
            summary="lint failed",
            log_excerpt="example lint failure",
        )
    )
    await db_session.flush()

    from app.services.code.recovery_service import CodeRecoveryService

    recovery = await CodeRecoveryService.suggest_recovery_actions(db_session, session=session)

    assert recovery.failure_class == "verification_failed"
    assert recovery.next_safe_action is None
    assert "review_gate_task_ids" in recovery.evidence
    assert any("review gate" in action.lower() for action in recovery.recommended_actions)


@pytest.mark.asyncio
async def test_runtime_policy_signal_metrics_accumulate(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    runtime = await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="heartbeat_execution",
        outcome="auto_executed",
    )
    runtime = await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="heartbeat_execution",
        outcome="auto_executed",
    )
    runtime = await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="subagent_handoff",
        outcome="ready",
    )
    metrics = runtime.runtime_metrics["policy_learning"]
    assert metrics["heartbeat_execution"]["auto_executed"] == 2
    assert metrics["subagent_handoff"]["ready"] == 1


@pytest.mark.asyncio
async def test_runtime_can_record_run_ledger_artifact_summary(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    artifact = RunLedgerArtifact(
        slice="Task #12: Batch 101 signal review",
        outcome="Verification passed and the task is now complete.",
        verification="Verification gate status changed to passed in BOS Code task orchestration.",
        remaining_risk="Only branch posture or new evidence should block merge-oriented follow-up now.",
        next_step="verification: Treat the task as complete and inspect merge readiness.",
        target_surface="signal_lab",
        target_id="101",
        target_route="/bos/signal-lab?batchId=101",
    )

    runtime = await CodeRuntimeService.record_run_ledger_artifact(
        db_session,
        workspace_id=workspace.id,
        artifact=artifact,
        when=datetime.fromisoformat("2026-04-16T21:00:00+08:00"),
    )

    summary = runtime.runtime_metrics["last_run_ledger_artifact"]
    assert summary["slice"] == "Task #12: Batch 101 signal review"
    assert summary["target_surface"] == "signal_lab"
    assert summary["target_id"] == "101"
    assert summary["target_route"] == "/bos/signal-lab?batchId=101"


@pytest.mark.asyncio
async def test_verification_failure_seeds_recovery_task(
    db_session: AsyncSession,
    scientist_user,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    postmortem_calls = {"count": 0}

    class FakeSubagentService:
        async def create_runs_for_task(self, db, *, workspace, session, task, worker, metadata=None):
            return [SimpleNamespace(id=801)]

        async def enqueue_or_execute_run(self, db, *, run_id):
            return SimpleNamespace(id=run_id, run_status="running")

    async def fake_postmortem(cls, db, *, workspace, session, user, trigger_source, task_id=None):
        postmortem_calls["count"] += 1
        return None

    monkeypatch.setattr(CodeRecoveryLoopService, "subagent_service", FakeSubagentService())
    monkeypatch.setattr(CodeRecoveryLoopService, "ensure_postmortem_reflection", classmethod(fake_postmortem))

    task = await CodeTaskService.create_task(
        db_session,
        workspace=workspace,
        user=scientist_user,
        session_id=session.id,
        title="Verification gate task",
        objective="Run verification and recover if it fails",
        scope="code/runtime",
        acceptance_criteria=["pass verification"],
    )
    task.task_status = "verification_pending"
    await db_session.flush()

    updated = await CodeTaskService.apply_verification_result(
        db_session,
        workspace_id=workspace.id,
        session_id=session.id,
        verification_status="failed",
    )
    await db_session.flush()

    assert updated
    tasks = await CodeTaskService.list_tasks(db_session, workspace_id=workspace.id)
    recovery_tasks = [item for item in tasks if item.scope == "code/recovery"]
    assert recovery_tasks
    assert any("verification_failed" in item.objective for item in recovery_tasks)
    assert postmortem_calls["count"] == 1


@pytest.mark.asyncio
async def test_heartbeat_packet_uses_policy_learning_signals(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Runtime execution follow-up",
        objective="Runtime execution follow-up",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="subagent_handoff",
        outcome="ready",
    )
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="subagent_handoff",
        outcome="ready",
    )
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="heartbeat_execution",
        outcome="auto_executed",
    )
    decision, _summary, packet = await CodeAutomationJobService._heartbeat_decision(
        db_session,
        workspace_id=workspace.id,
    )
    assert decision == "run"
    assert packet["policy_learning_snapshot"]["subagent_handoff"]["ready"] == 2
    assert any("Historical handoff signals are healthy" in note for note in packet["critic_notes"])


@pytest.mark.asyncio
async def test_heartbeat_packet_reflects_review_and_verification_history(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Verification-sensitive task",
        objective="Verification-sensitive task",
        scope="code/runtime",
        task_status="verification_pending",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="review_decision",
        outcome="reject",
    )
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="review_decision",
        outcome="reject",
    )
    await CodeRuntimeService.record_policy_signal(
        db_session,
        workspace_id=workspace.id,
        category="verification_result",
        outcome="failed",
    )
    decision, _summary, packet = await CodeAutomationJobService._heartbeat_decision(
        db_session,
        workspace_id=workspace.id,
    )
    assert decision == "run"
    assert any("reviewer decisions lean negative" in note.lower() for note in packet["critic_notes"])
    assert any("verification failures outweigh passes" in note.lower() for note in packet["critic_notes"])
    assert packet["loop_budget"] == "deep"
    assert packet["convergence_signal"] == "needs_more_evidence"
    assert "verification_history_negative" in packet["difficulty_signals"]


@pytest.mark.asyncio
async def test_idle_heartbeat_packet_exits_quickly_when_no_active_work(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)

    decision, summary, packet = await CodeAutomationJobService._heartbeat_decision(
        db_session,
        workspace_id=workspace.id,
    )

    assert decision == "skip"
    assert "no active BOS Code work" in summary
    assert packet["loop_budget"] == "exit"
    assert packet["convergence_signal"] == "idle"


@pytest.mark.asyncio
async def test_heartbeat_continuation_is_suppressed_when_recent_turn_exists(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Long-running continuation task",
        objective="Continue the active autonomy slice without duplicate prompts",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    recent_turn = CodeTurn(
        session_id=session.id,
        turn_index=1,
        user_message="Continue the active autonomy slice",
        assistant_summary="Still working through the current gate.",
        turn_status="completed",
    )
    db_session.add(recent_turn)
    await db_session.flush()

    job = await CodeRuntimeService.create_job(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        payload={
            "name": "test-heartbeat-throttle",
            "job_type": "heartbeat",
            "enabled": True,
            "schedule_kind": "manual",
            "target_scope": "heartbeat",
        },
    )

    class FailIfCalledSessionService:
        async def create_session(self, *args, **kwargs):
            raise AssertionError("Heartbeat throttle should not need a new session")

        async def create_turn(self, *args, **kwargs):
            raise AssertionError("Heartbeat throttle should suppress duplicate continuation turns")

    _job, used_session, summary = await CodeAutomationJobService.execute_job(
        db_session,
        workspace=workspace,
        job=job,
        user=scientist_user,
        session_service=FailIfCalledSessionService(),
    )
    await db_session.flush()

    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    assert used_session == session
    assert "Continuation was deferred because recent_turn_throttle." in summary
    assert runtime.runtime_metrics["last_heartbeat_execution_status"] == "suppressed"


def test_stage_heartbeat_run_artifact_targets_orchestrator(tmp_path):
    artifact_path = tmp_path / "run-ledger.md"
    original_path = CodeAutomationJobService.RUN_LEDGER_PATH
    CodeAutomationJobService.RUN_LEDGER_PATH = artifact_path
    try:
        artifact = CodeAutomationJobService._stage_heartbeat_run_artifact(
            workspace=SimpleNamespace(id=17),
            summary="Heartbeat found active BOS Code work.",
            decision="run",
            heartbeat_packet={"focus_task_title": "Review runtime posture"},
            snapshot=SimpleNamespace(
                focus_task_title="Review runtime posture",
                next_automation_action="run_verification",
                next_human_action=None,
                merge_summary="Merge is pending because verification has not cleared yet.",
            ),
            executed_action=None,
            when=datetime.fromisoformat("2026-04-16T18:00:00+08:00"),
        )
        CodeAutomationJobService._write_run_ledger_artifact(
            artifact=artifact,
            when=datetime.fromisoformat("2026-04-16T18:00:00+08:00"),
        )

        content = artifact_path.read_text(encoding="utf-8")
        assert "BOS Code heartbeat: Review runtime posture" in content
        assert "- Target Surface: orchestrator" in content
        assert "- Target ID: 17" in content
        assert "- Target Route: /bos/orchestrator" in content
        assert "Run verification in the BOS Orchestrator." in content
    finally:
        CodeAutomationJobService.RUN_LEDGER_PATH = original_path


def test_stage_reflection_run_artifact_targets_brain(tmp_path):
    artifact_path = tmp_path / "run-ledger.md"
    original_path = CodeReflectionService.RUN_LEDGER_PATH
    CodeReflectionService.RUN_LEDGER_PATH = artifact_path
    try:
        artifact = CodeReflectionService._stage_reflection_run_artifact(
            workspace=SimpleNamespace(id=21),
            reflection=SimpleNamespace(
                output_kind="memory_update",
                summary="Persisted a BOS Code memory snapshot for future turns.",
            ),
        )
        CodeReflectionService._write_run_ledger_artifact(
            artifact=artifact,
            when=datetime.fromisoformat("2026-04-16T18:05:00+08:00"),
        )

        content = artifact_path.read_text(encoding="utf-8")
        assert "BOS Code reflection review" in content
        assert "- Target Surface: brain" in content
        assert "- Target ID: 21" in content
        assert "- Target Route: /bos/brain" in content
        assert "Inspect the Brain Dashboard" in content
    finally:
        CodeReflectionService.RUN_LEDGER_PATH = original_path


def test_task_target_from_text_prefers_signal_and_release_surfaces():
    signal_task = SimpleNamespace(
        id=1,
        title="Batch 101 signal review",
        objective="Qualify the signal handoff for batch 101",
        scope="code/runtime",
        workspace_id=7,
    )
    release_task = SimpleNamespace(
        id=2,
        title="Release trust sweep",
        objective="Tighten release and audit posture",
        scope="code/runtime",
        workspace_id=7,
    )
    fallback_task = SimpleNamespace(
        id=3,
        title="Runtime cleanup",
        objective="Refresh the BOS Code cockpit",
        scope="code/runtime",
        workspace_id=7,
    )

    assert CodeTaskService._task_target_from_text(signal_task) == (
        "signal_lab",
        "101",
        "/bos/signal-lab?batchId=101",
    )
    assert CodeTaskService._task_target_from_text(release_task) == (
        "release",
        None,
        "/release",
    )
    assert CodeTaskService._task_target_from_text(fallback_task) == (
        "orchestrator",
        "7",
        "/bos/orchestrator",
    )


@pytest.mark.asyncio
async def test_review_decision_writes_run_ledger_artifact(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    workers = await CodeTaskService.ensure_default_workers(db_session, workspace=workspace)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Batch 101 signal review",
        objective="Qualify signal handoff for batch 101",
        scope="code/runtime",
        task_status="review_pending",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    executor = next(worker for worker in workers if worker.worker_name == "executor")
    reviewer = next(worker for worker in workers if worker.worker_name == "reviewer")
    executor.task_id = task.id
    executor.worker_status = "waiting_review"
    reviewer.task_id = task.id
    reviewer.worker_status = "assigned"
    await db_session.flush()

    original_path = CodeTaskService.RUN_LEDGER_PATH
    CodeTaskService.RUN_LEDGER_PATH = tmp_path / "run-ledger.md"
    try:
        await CodeTaskService.submit_review_decision(
            db_session,
            workspace_id=workspace.id,
            task_id=task.id,
            decision="accept",
        )
        content = CodeTaskService.RUN_LEDGER_PATH.read_text(encoding="utf-8")
        assert f"Task #{task.id}: Batch 101 signal review" in content
        assert "- Target Surface: signal_lab" in content
        assert "- Target ID: 101" in content
        assert "- Target Route: /bos/signal-lab?batchId=101" in content
        assert "review: Run or confirm the verification gate before preparing merge decisions." in content
        runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
        assert runtime.runtime_metrics["last_run_ledger_artifact"]["target_surface"] == "signal_lab"
        assert runtime.runtime_metrics["last_run_ledger_artifact"]["target_id"] == "101"
    finally:
        CodeTaskService.RUN_LEDGER_PATH = original_path


@pytest.mark.asyncio
async def test_apply_verification_result_writes_release_artifact(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    workers = await CodeTaskService.ensure_default_workers(db_session, workspace=workspace)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Release trust sweep",
        objective="Tighten release and audit posture",
        scope="code/runtime",
        task_status="verification_pending",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    executor = next(worker for worker in workers if worker.worker_name == "executor")
    reviewer = next(worker for worker in workers if worker.worker_name == "reviewer")
    executor.task_id = task.id
    executor.worker_status = "ready"
    reviewer.task_id = task.id
    reviewer.worker_status = "completed"
    await db_session.flush()

    original_path = CodeTaskService.RUN_LEDGER_PATH
    CodeTaskService.RUN_LEDGER_PATH = tmp_path / "run-ledger.md"
    try:
        updated = await CodeTaskService.apply_verification_result(
            db_session,
            workspace_id=workspace.id,
            session_id=session.id,
            verification_status="passed",
        )
        assert updated
        content = CodeTaskService.RUN_LEDGER_PATH.read_text(encoding="utf-8")
        assert f"Task #{task.id}: Release trust sweep" in content
        assert "- Target Surface: release" in content
        assert "- Target Route: /release" in content
        assert "verification: Treat the task as complete and inspect merge readiness." in content
        runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
        assert runtime.runtime_metrics["last_run_ledger_artifact"]["target_surface"] == "release"
        assert runtime.runtime_metrics["last_run_ledger_artifact"]["target_route"] == "/release"
    finally:
        CodeTaskService.RUN_LEDGER_PATH = original_path


@pytest.mark.asyncio
async def test_memory_snapshot_respects_safe_boundary(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    for idx in range(1, 6):
        turn = CodeTurn(
            session_id=session.id,
            turn_index=idx,
            user_message=f"turn-{idx}",
            assistant_summary=f"summary-{idx}",
            turn_status="completed",
        )
        db_session.add(turn)
        await db_session.flush()
        db_session.add(
            CodeToolCall(
                session_id=session.id,
                turn_id=turn.id,
                tool_name="safe_bash",
                tool_class="runtime",
                input_summary=f"echo {idx}",
                result_summary=f"ok-{idx}",
            )
        )
    await db_session.flush()

    snapshot = await CodeMemoryService.refresh_snapshot(db_session, session=session, force=False)
    assert snapshot is not None
    assert snapshot.source_turn_start == 1
    assert snapshot.source_turn_end == 3
    assert "Turn 3" in snapshot.history_excerpt
    assert "turn-4" not in snapshot.summary_markdown


@pytest.mark.asyncio
async def test_session_search_returns_matching_session(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    turn = CodeTurn(
        session_id=session.id,
        turn_index=1,
        user_message="Build the automation heartbeat panel",
        assistant_summary="Added runtime panel summary",
        turn_status="completed",
    )
    db_session.add(turn)
    await db_session.flush()
    db_session.add(
        CodeArtifact(
            session_id=session.id,
            artifact_type="diff",
            changed_files=["frontend/src/components/code/CodeAlwaysOnPanel.tsx"],
            diff_summary="heartbeat panel added to cockpit",
            verification_summary={"status": "pending"},
        )
    )
    await db_session.flush()

    results = await CodeSessionSearchService.search(
        db_session,
        tenant_id=scientist_user.tenant_id,
        query="heartbeat panel",
        limit=3,
    )
    assert results
    assert results[0]["session_id"] == session.id
    assert results[0]["matched_turn_ids"]


@pytest.mark.asyncio
async def test_reflection_run_can_create_skill_draft(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Implement runtime memory loop",
        objective="Implement runtime memory loop and scheduled reflection workflow",
        scope="code/runtime",
        task_status="completed",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    turn = CodeTurn(
        session_id=session.id,
        turn_index=1,
        user_message="Implement the memory loop",
        assistant_summary="Completed the runtime memory loop.",
        turn_status="completed",
    )
    db_session.add(turn)
    await db_session.flush()
    for tool_name in ("read_file", "safe_bash", "git_ops"):
        db_session.add(
            CodeToolCall(
                session_id=session.id,
                turn_id=turn.id,
                tool_name=tool_name,
                tool_class="runtime",
                input_summary=tool_name,
                result_summary="ok",
            )
        )
    await db_session.flush()

    reflection = await CodeReflectionService.run_reflection(
        db_session,
        workspace=workspace,
        session=session,
        user=scientist_user,
        trigger_source="manual",
        task_id=task.id,
    )
    await db_session.flush()
    skill = await CodeSkillService.get_skill(db_session, workspace_id=workspace.id, skill_id=reflection.skill_id)
    assert reflection.output_kind in {"skill_create", "skill_update"}
    assert reflection.reflection_status == "completed"
    assert reflection.payload["verified_signal"] is True
    assert "task_completed" in reflection.payload["verification_signals"]
    assert skill is not None
    assert skill.skill_status == "draft"

    worker_events = await db_session.execute(
        select(CodeWorkerEvent).where(CodeWorkerEvent.workspace_id == workspace.id)
    )
    assert any(event.payload.get("reflection_id") == reflection.id for event in worker_events.scalars().all())


@pytest.mark.asyncio
async def test_reflection_run_downgrades_to_memory_when_work_is_unverified(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Repair unstable runtime loop",
        objective="Repair unstable runtime loop after a failing verification gate",
        scope="code/runtime",
        task_status="blocked",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    turn = CodeTurn(
        session_id=session.id,
        turn_index=1,
        user_message="Repair the runtime loop",
        assistant_summary="Made a few changes but verification is still failing.",
        turn_status="completed",
    )
    db_session.add(turn)
    await db_session.flush()
    for tool_name in ("read_file", "safe_bash", "git_ops"):
        db_session.add(
            CodeToolCall(
                session_id=session.id,
                turn_id=turn.id,
                tool_name=tool_name,
                tool_class="runtime",
                input_summary=tool_name,
                result_summary="ok",
            )
        )
    db_session.add(
        CodeVerificationRun(
            session_id=session.id,
            verification_stage="pytest",
            verification_status="failed",
            summary="tests failed",
            log_excerpt="example failing verification",
        )
    )
    session.verification_status = "failed"
    await db_session.flush()

    reflection = await CodeReflectionService.run_reflection(
        db_session,
        workspace=workspace,
        session=session,
        user=scientist_user,
        trigger_source="manual",
        task_id=task.id,
    )
    await db_session.flush()

    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    assert reflection.output_kind == "memory_update"
    assert reflection.skill_id is None
    assert reflection.payload["verified_signal"] is False
    assert "recent_verification_failed" in reflection.payload["verification_signals"]
    assert runtime.runtime_metrics["last_reflection_verified_signal"] is False


@pytest.mark.asyncio
async def test_skill_service_rejects_out_of_bounds_supporting_files(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    with pytest.raises(ValueError) as exc:
        await CodeSkillService.create_skill(
            db_session,
            workspace=workspace,
            user=scientist_user,
            name="Unsafe Skill",
            slug="unsafe-skill",
            description="Should fail",
            content_markdown="---\nname: Unsafe Skill\ndescription: fail\n---\n\n# Unsafe",
            supporting_files={"../escape.txt": "nope"},
        )
    assert str(exc.value) == "skill_supporting_file_path_invalid"


@pytest.mark.asyncio
async def test_active_skill_is_injected_into_follow_up_prompt(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Runtime Review Skill",
        slug="runtime-review-skill",
        description="Review runtime posture and summarize the safest next action.",
        content_markdown="---\nname: Runtime Review Skill\ndescription: Review runtime posture.\n---\n\n# Runtime Review Skill\n\n- Inspect runtime posture.\n- Summarize the safest next action.",
        supporting_files={},
        skill_status="active",
        revision_status="active",
    )
    await db_session.flush()

    captured = {}

    class FakeProvider:
        async def run(self, request):
            captured["prompt"] = request.prompt
            return CodeProviderResponse(
                summary="ok",
                output_text="ok",
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                estimated_cost=0.0,
                blocked_reason=None,
            )

    service = CodeSessionService()
    service.provider = FakeProvider()

    turn, _output = await service.create_turn(
        db_session,
        session=session,
        user_message="Please review the runtime posture and next action.",
    )

    assert turn.turn_status == "completed"
    assert "Relevant BOS Code skills" in captured["prompt"]
    assert "Runtime Review Skill" in captured["prompt"]
    await db_session.refresh(skill)
    assert skill.usage_count >= 1
    assert skill.last_used_at is not None


@pytest.mark.asyncio
async def test_project_brain_and_cross_session_recall_are_injected_into_prompt(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    other_session = CodeSession(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        provider="openai",
        model="gpt-5.5",
        permission_mode="workspace-write",
        session_branch=f"boscode/tenant-{scientist_user.tenant_id}/session-cross-{scientist_user.id}",
        session_status="ready",
        verification_status="pending",
        token_usage={},
        estimated_cost=0.0,
    )
    db_session.add(other_session)
    await db_session.flush()
    db_session.add(
        CodeTurn(
            session_id=other_session.id,
            turn_index=1,
            user_message="Improve the heartbeat continuation flow across threads",
            assistant_summary="Adjusted the heartbeat follow-up strategy across sessions.",
            turn_status="completed",
        )
    )
    await db_session.flush()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "project-brain.md").write_text(
        "# Project Brain\n\n## Mission\n\n- Keep BOS Code autonomous across threads.\n\n## Current Focus\n\n- Reduce manual continue prompts.\n\n## Next Slices\n\n- Improve cross-session recall.\n\n## Stable Facts\n\n- Heartbeat and maintenance are active.\n\n## Constraints\n\n- Keep review gates explicit.\n\n## Known Good Commands\n\n- pytest runtime slice.\n\n## Repeated Pitfalls\n\n- Losing thread memory hurts autonomy.\n",
        encoding="utf-8",
    )
    (runtime_dir / "evolution-log.md").write_text(
        "# Evolution Log\n\n## Active Heuristics\n\n- Prefer continuation when the task is still active.\n\n## Recent Learnings\n\n- Cross-session recall is valuable.\n",
        encoding="utf-8",
    )
    (runtime_dir / "run-ledger.md").write_text(
        "# Autonomy Run Ledger\n\n## Latest Run\n\n- Slice: heartbeat follow-up\n- Outcome: continued active task\n- Verification: test\n- Remaining Risk: low\n- Next Step: keep going\n- Target Surface: orchestrator\n- Target ID: 1\n- Target Route: /bos/orchestrator\n\n## Recent Runs\n\n- 2026-04-16 20:00 | heartbeat follow-up | continued active task | keep going | orchestrator | 1 | /bos/orchestrator\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(CodeMaintenanceService, "RUNTIME_DIR", runtime_dir)

    captured = {}

    class FakeProvider:
        async def run(self, request):
            captured["prompt"] = request.prompt
            return CodeProviderResponse(
                summary="ok",
                output_text="ok",
                usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                estimated_cost=0.0,
                blocked_reason=None,
            )

    service = CodeSessionService()
    service.provider = FakeProvider()

    turn, _output = await service.create_turn(
        db_session,
        session=session,
        user_message="Improve the heartbeat continuation flow",
    )

    assert turn.turn_status == "completed"
    assert "Project Brain" in captured["prompt"]
    assert "Cross-Session Recall" in captured["prompt"]
    assert "Improve the heartbeat continuation flow across threads" in captured["prompt"]
    assert "Current request:\nImprove the heartbeat continuation flow" in captured["prompt"]


@pytest.mark.asyncio
async def test_positive_feedback_biases_skill_selection(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    positive_skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Runtime Positive Skill",
        slug="runtime-positive-skill",
        description="Handle runtime automation review",
        content_markdown="---\nname: Runtime Positive Skill\ndescription: Handle runtime automation review\n---\n\n# Runtime Positive Skill",
        supporting_files={},
        skill_status="active",
        revision_status="active",
    )
    negative_skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Runtime Negative Skill",
        slug="runtime-negative-skill",
        description="Handle runtime automation review",
        content_markdown="---\nname: Runtime Negative Skill\ndescription: Handle runtime automation review\n---\n\n# Runtime Negative Skill",
        supporting_files={},
        skill_status="active",
        revision_status="active",
    )
    await CodeSkillService.record_feedback(db_session, skill=positive_skill, sentiment="positive")
    await CodeSkillService.record_feedback(db_session, skill=positive_skill, sentiment="positive")
    await CodeSkillService.record_feedback(db_session, skill=negative_skill, sentiment="negative")
    await db_session.flush()

    chosen = await CodeSkillService.find_similar_skill(
        db_session,
        workspace_id=workspace.id,
        objective="runtime automation review",
    )
    assert chosen is not None
    assert chosen.id == positive_skill.id


@pytest.mark.asyncio
async def test_repeated_negative_feedback_auto_demotes_active_skill(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Fragile Runtime Skill",
        slug="fragile-runtime-skill",
        description="An active skill that should auto-demote after repeated bad feedback.",
        content_markdown="---\nname: Fragile Runtime Skill\ndescription: fragile\n---\n\n# Fragile Runtime Skill",
        supporting_files={},
        skill_status="active",
        revision_status="active",
    )
    await CodeSkillService.record_feedback(db_session, skill=skill, sentiment="negative", note="Did not help.")
    await CodeSkillService.record_feedback(db_session, skill=skill, sentiment="negative", note="Still not helping.")
    await db_session.flush()
    await db_session.refresh(skill)

    assert skill.negative_feedback_count >= 2
    assert skill.skill_status == "draft"


@pytest.mark.asyncio
async def test_repeated_positive_feedback_auto_promotes_draft_skill(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, _session = await _make_workspace_session(db_session, user=scientist_user)
    skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Recovering Runtime Skill",
        slug="recovering-runtime-skill",
        description="A draft skill that should auto-promote after repeated good feedback.",
        content_markdown="---\nname: Recovering Runtime Skill\ndescription: recovering\n---\n\n# Recovering Runtime Skill",
        supporting_files={},
        skill_status="draft",
        revision_status="draft",
    )
    await CodeSkillService.record_feedback(db_session, skill=skill, sentiment="positive", note="Useful.")
    await CodeSkillService.record_feedback(db_session, skill=skill, sentiment="positive", note="Useful again.")
    await db_session.flush()
    await db_session.refresh(skill)

    assert skill.positive_feedback_count >= 2
    assert skill.skill_status == "active"


@pytest.mark.asyncio
async def test_maintenance_job_updates_runtime_metrics_and_reports(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    runtime.runtime_metrics = {
        "last_heartbeat_loop_budget": "deep",
        "last_heartbeat_convergence_signal": "needs_more_evidence",
        "last_heartbeat_difficulty_signals": ["verification_history_negative", "review_history_negative"],
        "last_reflection_verified_signal": False,
        "last_reflection_verification_signals": ["recent_verification_failed", "task_blocked"],
    }
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Always-on maintenance task",
        objective="Keep the autonomy loop healthy without manual continue prompts",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=["Stay autonomous", "Refresh maintenance report"],
    )
    db_session.add(task)
    await db_session.flush()

    runtime_dir = tmp_path / "runtime"
    staging_dir = tmp_path / "runtime-staging"
    monkeypatch.setattr(CodeMaintenanceService, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(CodeMaintenanceService, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_MARKDOWN_PATH", staging_dir / "autonomy-maintenance-latest.md")
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_JSON_PATH", staging_dir / "autonomy-maintenance-latest.json")

    job = await CodeRuntimeService.create_job(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        payload={
            "name": "test-maintenance",
            "job_type": "maintenance",
            "enabled": True,
            "schedule_kind": "manual",
            "target_scope": "maintenance",
        },
    )
    session_service = CodeSessionService()
    _job, used_session, summary = await CodeAutomationJobService.execute_job(
        db_session,
        workspace=workspace,
        job=job,
        user=scientist_user,
        session_service=session_service,
    )
    await db_session.flush()

    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    metrics = runtime.runtime_metrics or {}
    report_markdown = (staging_dir / "autonomy-maintenance-latest.md").read_text(encoding="utf-8")
    report_json = json.loads((staging_dir / "autonomy-maintenance-latest.json").read_text(encoding="utf-8"))

    assert used_session == session
    assert "Maintenance refreshed project memory" in summary
    assert metrics["last_maintenance_summary"] == summary
    assert metrics["last_maintenance_report_markdown_path"].endswith("autonomy-maintenance-latest.md")
    assert metrics["next_autonomy_mode"] == "continue_active"
    assert "Continue task" in metrics["next_autonomy_objective"]
    assert metrics["workflow_mode"] in {"recovery", "execution", "planning", "verification", "subagent_execution"}
    assert isinstance(metrics["workflow_skills"], list)
    assert isinstance(metrics["experience_quality"], dict)
    assert (runtime_dir / "project-brain.md").exists()
    assert (runtime_dir / "decision-journal.md").exists()
    assert (runtime_dir / "evolution-log.md").exists()
    assert (staging_dir / "autonomy-maintenance-latest.md").exists()
    assert (staging_dir / "autonomy-maintenance-latest.json").exists()
    assert "## Autonomy Loop Posture" in report_markdown
    assert "- Loop budget: deep" in report_markdown
    assert "verification_history_negative" in report_markdown
    assert "## Reflection Learning Gate" in report_markdown
    assert "memory only; skill promotion is currently blocked" in report_markdown
    assert report_json["last_heartbeat_loop_budget"] == "deep"
    assert report_json["last_reflection_verified_signal"] is False


@pytest.mark.asyncio
async def test_maintenance_job_creates_session_when_none_exists(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
    monkeypatch,
):
    workspace = await CodeWorkspaceService.ensure_workspace(db_session, user=scientist_user)

    runtime_dir = tmp_path / "runtime"
    staging_dir = tmp_path / "runtime-staging"
    monkeypatch.setattr(CodeMaintenanceService, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(CodeMaintenanceService, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_MARKDOWN_PATH", staging_dir / "autonomy-maintenance-latest.md")
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_JSON_PATH", staging_dir / "autonomy-maintenance-latest.json")

    job = await CodeRuntimeService.create_job(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        payload={
            "name": "test-maintenance-no-session",
            "job_type": "maintenance",
            "enabled": True,
            "schedule_kind": "manual",
            "target_scope": "maintenance",
        },
    )

    session_service = CodeSessionService()
    _job, used_session, _summary = await CodeAutomationJobService.execute_job(
        db_session,
        workspace=workspace,
        job=job,
        user=scientist_user,
        session_service=session_service,
    )
    await db_session.flush()

    assert used_session is not None
    events = await db_session.execute(
        select(CodeEvent).where(CodeEvent.session_id == used_session.id).order_by(CodeEvent.id.asc())
    )
    assert any(event.event_type == "code.automation.maintenance" for event in events.scalars().all())


@pytest.mark.asyncio
async def test_maintenance_job_seeds_executor_task_when_idle(
    db_session: AsyncSession,
    scientist_user,
    tmp_path,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    subagent_calls = {"created": 0, "enqueued": 0}

    runtime_dir = tmp_path / "runtime"
    staging_dir = tmp_path / "runtime-staging"
    monkeypatch.setattr(CodeMaintenanceService, "RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(CodeMaintenanceService, "STAGING_DIR", staging_dir)
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_MARKDOWN_PATH", staging_dir / "autonomy-maintenance-latest.md")
    monkeypatch.setattr(CodeMaintenanceService, "REPORT_JSON_PATH", staging_dir / "autonomy-maintenance-latest.json")

    class FakeSubagentService:
        async def create_runs_for_task(self, db, *, workspace, session, task, worker, metadata=None):
            subagent_calls["created"] += 1
            return [SimpleNamespace(id=501), SimpleNamespace(id=502)]

        async def enqueue_or_execute_run(self, db, *, run_id):
            subagent_calls["enqueued"] += 1
            return SimpleNamespace(id=run_id, run_status="running")

    monkeypatch.setattr(CodeAutomationJobService, "subagent_service", FakeSubagentService())

    job = await CodeRuntimeService.create_job(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        payload={
            "name": "test-maintenance-seed-task",
            "job_type": "maintenance",
            "enabled": True,
            "schedule_kind": "manual",
            "target_scope": "maintenance",
        },
    )

    session_service = CodeSessionService()
    _job, used_session, summary = await CodeAutomationJobService.execute_job(
        db_session,
        workspace=workspace,
        job=job,
        user=scientist_user,
        session_service=session_service,
    )
    await db_session.flush()

    tasks = await CodeTaskService.list_tasks(db_session, workspace_id=workspace.id)
    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)

    assert used_session == session
    assert len(tasks) == 1
    assert tasks[0].task_status == "running"
    assert tasks[0].session_id == session.id
    assert "Seeded task #" in summary
    assert runtime.runtime_metrics["last_seeded_autonomy_task_id"] == tasks[0].id
    assert runtime.runtime_metrics["last_seeded_autonomy_objective"] == tasks[0].objective
    assert subagent_calls["created"] == 1
    assert subagent_calls["enqueued"] == 2


@pytest.mark.asyncio
async def test_idle_heartbeat_queues_maintenance_objective(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    runtime.runtime_metrics = {
        "next_autonomy_mode": "idle_maintenance",
        "next_autonomy_objective": "Run idle BOS maintenance and inspect the highest-value optimization.",
    }
    await db_session.flush()

    captured = {}

    class FakeSessionService:
        async def create_session(self, *args, **kwargs):
            raise AssertionError("Idle heartbeat should reuse the latest session")

        async def create_turn(self, db, *, session, user_message):
            captured["session_id"] = session.id
            captured["prompt"] = user_message
            return SimpleNamespace(id=999), "ok"

    job = await CodeRuntimeService.create_job(
        db_session,
        workspace=workspace,
        tenant_id=scientist_user.tenant_id,
        payload={
            "name": "test-idle-heartbeat",
            "job_type": "heartbeat",
            "enabled": True,
            "schedule_kind": "manual",
            "target_scope": "heartbeat",
        },
    )

    _job, used_session, summary = await CodeAutomationJobService.execute_job(
        db_session,
        workspace=workspace,
        job=job,
        user=scientist_user,
        session_service=FakeSessionService(),
    )
    await db_session.flush()

    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    assert used_session == session
    assert captured["session_id"] == session.id
    assert "Maintenance mode: idle_maintenance." in captured["prompt"]
    assert "Run idle BOS maintenance and inspect the highest-value optimization." in captured["prompt"]
    assert "Queued the next maintenance objective instead." in summary
    assert runtime.runtime_metrics["last_heartbeat_execution_status"] == "idle_maintenance"


@pytest.mark.asyncio
async def test_provider_budget_can_pause_turn_creation(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    runtime.runtime_metrics = {
        "provider_budget_window_started_at": datetime.now().astimezone().isoformat(),
        "provider_budget_request_count": 999,
        "provider_budget_estimated_cost": 999.0,
    }
    await db_session.flush()

    service = CodeSessionService()
    turn, message = await service.create_turn(
        db_session,
        session=session,
        user_message="Do another provider-heavy runtime turn",
    )
    await db_session.flush()
    await db_session.refresh(session)

    assert turn.turn_status == "failed"
    assert session.session_status == "blocked"
    assert "budget" in message.lower() or "cooling down" in message.lower()
    runtime = await CodeRuntimeService.ensure_runtime_state(db_session, workspace_id=workspace.id)
    assert runtime.runtime_metrics.get("provider_budget_pause_until")


@pytest.mark.asyncio
async def test_subagent_service_aggregates_completed_runs(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Parallel executor task",
        objective="Parallel executor task",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=["criterion one", "criterion two", "criterion three"],
    )
    db_session.add(task)
    worker = CodeWorker(
        workspace_id=workspace.id,
        task_id=task.id,
        worker_name="executor",
        worker_role="executor",
        worker_status="running",
    )
    db_session.add(worker)
    await db_session.flush()

    service = CodeSubagentService()
    runs = await service.create_runs_for_task(
        db_session,
        workspace=workspace,
        session=session,
        task=task,
        worker=worker,
        metadata={"source": "test"},
    )
    for index, run in enumerate(runs, start=1):
        run.run_status = "completed"
        run.result_summary = f"slice-{index}-done"
        run.started_at = run.finished_at = task.updated_at
    await db_session.flush()

    await service._maybe_aggregate_task_runs(
        db_session,
        workspace=workspace,
        task=task,
        session=session,
        worker=worker,
    )

    worker_events = await db_session.execute(
        select(CodeWorkerEvent)
        .where(CodeWorkerEvent.workspace_id == workspace.id, CodeWorkerEvent.event_name == "subagent.aggregate")
    )
    aggregate_event = worker_events.scalars().first()
    assert aggregate_event is not None
    assert aggregate_event.payload["completed_runs"] == len(runs)
    assert aggregate_event.payload["handoff_ready"] is True
    assert aggregate_event.payload["skill_feedback_applied"] is False
    assert isinstance(aggregate_event.payload["review_checklist"], list)


@pytest.mark.asyncio
async def test_subagent_service_marks_task_blocked_when_slice_fails(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Parallel executor failure task",
        objective="Parallel executor failure task",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=["criterion one", "criterion two"],
    )
    db_session.add(task)
    worker = CodeWorker(
        workspace_id=workspace.id,
        task_id=task.id,
        worker_name="executor",
        worker_role="executor",
        worker_status="running",
    )
    db_session.add(worker)
    await db_session.flush()

    service = CodeSubagentService()
    runs = await service.create_runs_for_task(
        db_session,
        workspace=workspace,
        session=session,
        task=task,
        worker=worker,
        metadata={"source": "test"},
    )
    runs[0].run_status = "completed"
    runs[0].result_summary = "slice-success"
    runs[1].run_status = "failed"
    runs[1].result_summary = "slice-failure"
    await db_session.flush()

    await service._maybe_aggregate_task_runs(
        db_session,
        workspace=workspace,
        task=task,
        session=session,
        worker=worker,
    )
    await db_session.refresh(task)
    await db_session.refresh(worker)

    assert task.task_status == "blocked"
    assert worker.worker_status == "blocked"
    worker_events = await db_session.execute(
        select(CodeWorkerEvent)
        .where(CodeWorkerEvent.workspace_id == workspace.id, CodeWorkerEvent.event_name == "subagent.aggregate")
    )
    aggregate_event = worker_events.scalars().first()
    assert aggregate_event is not None
    assert isinstance(aggregate_event.payload["recovery_checklist"], list)


@pytest.mark.asyncio
async def test_subagent_failure_seeds_recovery_task(
    db_session: AsyncSession,
    scientist_user,
    monkeypatch,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    postmortem_calls = {"count": 0}

    class FakeRecoverySubagentService:
        async def create_runs_for_task(self, db, *, workspace, session, task, worker, metadata=None):
            return [SimpleNamespace(id=901)]

        async def enqueue_or_execute_run(self, db, *, run_id):
            return SimpleNamespace(id=run_id, run_status="running")

    async def fake_postmortem(cls, db, *, workspace, session, user, trigger_source, task_id=None):
        postmortem_calls["count"] += 1
        return None

    monkeypatch.setattr(CodeRecoveryLoopService, "subagent_service", FakeRecoverySubagentService())
    monkeypatch.setattr(CodeRecoveryLoopService, "ensure_postmortem_reflection", classmethod(fake_postmortem))

    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Parallel executor failure task",
        objective="Parallel executor failure task",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=["criterion one", "criterion two"],
    )
    db_session.add(task)
    worker = CodeWorker(
        workspace_id=workspace.id,
        task_id=task.id,
        worker_name="executor",
        worker_role="executor",
        worker_status="running",
    )
    db_session.add(worker)
    await db_session.flush()

    service = CodeSubagentService()
    runs = await service.create_runs_for_task(
        db_session,
        workspace=workspace,
        session=session,
        task=task,
        worker=worker,
        metadata={"source": "test"},
    )
    runs[0].run_status = "completed"
    runs[0].result_summary = "slice-success"
    runs[1].run_status = "failed"
    runs[1].result_summary = "slice-failure"
    await db_session.flush()

    await service._maybe_aggregate_task_runs(
        db_session,
        workspace=workspace,
        task=task,
        session=session,
        worker=worker,
    )
    await db_session.flush()

    tasks = await CodeTaskService.list_tasks(db_session, workspace_id=workspace.id)
    recovery_tasks = [item for item in tasks if item.scope == "code/recovery"]
    assert recovery_tasks
    assert any("subagent_recovery" in item.objective for item in recovery_tasks)
    assert postmortem_calls["count"] == 1


@pytest.mark.asyncio
async def test_subagent_aggregate_applies_automatic_skill_feedback(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    skill = await CodeSkillService.create_skill(
        db_session,
        workspace=workspace,
        user=scientist_user,
        name="Aggregate Runtime Skill",
        slug="aggregate-runtime-skill",
        description="Parallel executor task",
        content_markdown="---\nname: Aggregate Runtime Skill\ndescription: Parallel executor task\n---\n\n# Aggregate Runtime Skill",
        supporting_files={},
        skill_status="active",
        revision_status="active",
    )
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Parallel executor task",
        objective="Parallel executor task",
        scope="code/runtime",
        task_status="running",
        priority="normal",
        acceptance_criteria=["criterion one"],
    )
    db_session.add(task)
    worker = CodeWorker(
        workspace_id=workspace.id,
        task_id=task.id,
        worker_name="executor",
        worker_role="executor",
        worker_status="running",
    )
    db_session.add(worker)
    await db_session.flush()

    service = CodeSubagentService()
    runs = await service.create_runs_for_task(
        db_session,
        workspace=workspace,
        session=session,
        task=task,
        worker=worker,
        metadata={"source": "test"},
    )
    runs[0].run_status = "completed"
    runs[0].result_summary = "slice-success"
    await db_session.flush()

    await service._maybe_aggregate_task_runs(
        db_session,
        workspace=workspace,
        task=task,
        session=session,
        worker=worker,
    )
    await db_session.refresh(skill)

    assert skill.positive_feedback_count >= 1


@pytest.mark.asyncio
async def test_apply_verification_result_resets_or_blocks_worker_lanes(
    db_session: AsyncSession,
    scientist_user,
):
    workspace, session = await _make_workspace_session(db_session, user=scientist_user)
    workers = await CodeTaskService.ensure_default_workers(db_session, workspace=workspace)
    task = CodeTask(
        tenant_id=scientist_user.tenant_id,
        user_id=scientist_user.id,
        workspace_id=workspace.id,
        session_id=session.id,
        title="Verification gate task",
        objective="Verification gate task",
        scope="code/runtime",
        task_status="verification_pending",
        priority="normal",
        acceptance_criteria=[],
    )
    db_session.add(task)
    await db_session.flush()
    executor = next(worker for worker in workers if worker.worker_name == "executor")
    reviewer = next(worker for worker in workers if worker.worker_name == "reviewer")
    executor.task_id = task.id
    reviewer.task_id = task.id
    await db_session.flush()

    await CodeTaskService.apply_verification_result(
        db_session,
        workspace_id=workspace.id,
        session_id=session.id,
        verification_status="passed",
    )
    await db_session.refresh(task)
    await db_session.refresh(executor)
    await db_session.refresh(reviewer)
    assert task.task_status == "completed"
    assert executor.worker_status == "ready"
    assert reviewer.worker_status == "ready"

    task.task_status = "verification_pending"
    executor.task_id = task.id
    reviewer.task_id = task.id
    await db_session.flush()

    await CodeTaskService.apply_verification_result(
        db_session,
        workspace_id=workspace.id,
        session_id=session.id,
        verification_status="failed",
    )
    await db_session.refresh(task)
    await db_session.refresh(executor)
    await db_session.refresh(reviewer)
    assert task.task_status == "blocked"
    assert executor.worker_status == "blocked"
    assert reviewer.worker_status == "ready"
