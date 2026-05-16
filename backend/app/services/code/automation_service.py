"""
Guarded automation executor for BOS Code control-plane actions.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.code import (
    ACTION_MARK_ARCHITECT_BLOCKED,
    ACTION_MARK_ARCHITECT_READY,
    ACTION_MARK_EXECUTOR_BLOCKED,
    ACTION_MARK_EXECUTOR_READY,
    ACTION_MARK_REVIEWER_BLOCKED,
    ACTION_MARK_REVIEWER_READY,
    ACTION_REFRESH_BRANCH,
    ACTION_RESET_SESSION_READY,
    ACTION_RUN_VERIFICATION,
    SESSION_STATUS_READY_FOR_PROMPT,
    WORKER_LANE_ARCHITECT,
    WORKER_LANE_EXECUTOR,
    WORKER_LANE_REVIEWER,
)
from app.models import CodeSession, CodeWorkspace
from app.services.code.branch_service import CodeBranchService
from app.services.code.event_service import CodeEventService
from app.services.code.orchestration_service import CodeOrchestrationService
from app.services.code.task_service import CodeTaskService
from app.services.code.verification_service import CodeVerificationService


@dataclass(slots=True)
class AutomationExecutionResult:
    session_id: int | None
    executed_action: str
    execution_status: str
    summary: str
    executed_at: datetime
    resulting_session_status: str | None = None
    resulting_verification_status: str | None = None


class CodeAutomationService:
    WORKER_ACTION_MAP = {
        ACTION_MARK_ARCHITECT_READY: (WORKER_LANE_ARCHITECT, "ready"),
        ACTION_MARK_ARCHITECT_BLOCKED: (WORKER_LANE_ARCHITECT, "blocked"),
        ACTION_MARK_EXECUTOR_READY: (WORKER_LANE_EXECUTOR, "ready"),
        ACTION_MARK_EXECUTOR_BLOCKED: (WORKER_LANE_EXECUTOR, "blocked"),
        ACTION_MARK_REVIEWER_READY: (WORKER_LANE_REVIEWER, "ready"),
        ACTION_MARK_REVIEWER_BLOCKED: (WORKER_LANE_REVIEWER, "blocked"),
    }

    @staticmethod
    async def _latest_session(db: AsyncSession, *, workspace_id: int) -> CodeSession | None:
        result = await db.execute(
            select(CodeSession)
            .where(CodeSession.workspace_id == workspace_id)
            .order_by(CodeSession.created_at.desc())
        )
        return result.scalars().first()

    @classmethod
    async def execute_next_automation(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        role: str,
        safe_bash_timeout_sec: int,
        max_read_bytes: int,
        max_write_bytes: int,
    ) -> AutomationExecutionResult:
        snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
        if snapshot.next_automation_action is None:
            raise ValueError("no_automation_action_available")
        if not snapshot.automation_ready:
            raise ValueError("automation_not_ready")

        action = snapshot.next_automation_action
        session = await cls._latest_session(db, workspace_id=workspace.id)

        if action == ACTION_REFRESH_BRANCH:
            if session is None:
                raise ValueError("automation_requires_session")
            await CodeBranchService.refresh_branch_state(
                db,
                workspace=workspace,
                branch_name=session.session_branch,
                role=role,
                safe_bash_timeout_sec=safe_bash_timeout_sec,
                max_read_bytes=max_read_bytes,
                max_write_bytes=max_write_bytes,
            )
            return AutomationExecutionResult(
                session_id=session.id,
                executed_action=action,
                execution_status="completed",
                summary="Automation refreshed branch posture.",
                executed_at=datetime.now(UTC),
                resulting_session_status=session.session_status,
                resulting_verification_status=session.verification_status,
            )

        if action == ACTION_RUN_VERIFICATION:
            if session is None:
                raise ValueError("automation_requires_session")
            await CodeVerificationService.execute_pipeline(
                db,
                session=session,
                worktree_root=workspace.worktree_root,
                role=role,
                safe_bash_timeout_sec=safe_bash_timeout_sec,
                max_read_bytes=max_read_bytes,
                max_write_bytes=max_write_bytes,
                stop_on_failure=True,
            )
            await CodeTaskService.apply_verification_result(
                db,
                workspace_id=workspace.id,
                session_id=session.id,
                verification_status=session.verification_status,
            )
            return AutomationExecutionResult(
                session_id=session.id,
                executed_action=action,
                execution_status="completed",
                summary="Automation executed the verification pipeline.",
                executed_at=datetime.now(UTC),
                resulting_session_status=session.session_status,
                resulting_verification_status=session.verification_status,
            )

        if action == ACTION_RESET_SESSION_READY:
            if session is None:
                raise ValueError("automation_requires_session")
            session.session_status = SESSION_STATUS_READY_FOR_PROMPT
            await CodeEventService.append_event(
                db,
                session_id=session.id,
                event_type="code.session.status",
                payload={
                    "session_status": SESSION_STATUS_READY_FOR_PROMPT,
                    "phase": "recovery",
                    "headline": "Automation reset the session back to ready-for-prompt.",
                    "recommended_actions": [
                        "Resend the prompt once the runtime posture looks stable.",
                    ],
                    "source": "automation_executor",
                    "action": action,
                },
            )
            return AutomationExecutionResult(
                session_id=session.id,
                executed_action=action,
                execution_status="completed",
                summary="Automation reset the session back to ready-for-prompt.",
                executed_at=datetime.now(UTC),
                resulting_session_status=session.session_status,
                resulting_verification_status=session.verification_status,
            )

        if action in cls.WORKER_ACTION_MAP:
            worker_name, worker_status = cls.WORKER_ACTION_MAP[action]
            worker = await CodeTaskService.update_worker_status(
                db,
                workspace_id=workspace.id,
                worker_name=worker_name,
                worker_status=worker_status,
                last_event_summary=f"Automation set {worker_name} lane to {worker_status}.",
                lane=worker_name,
                event_name="lane.progressed" if worker_status == "ready" else "lane.blocked",
                payload={"source": "automation_executor", "action": action},
            )
            return AutomationExecutionResult(
                session_id=session.id if session else None,
                executed_action=action,
                execution_status="completed",
                summary=f"Automation executed {action} for {worker.worker_name}.",
                executed_at=datetime.now(UTC),
                resulting_session_status=session.session_status if session else None,
                resulting_verification_status=session.verification_status if session else None,
            )

        raise ValueError("automation_action_unsupported")
