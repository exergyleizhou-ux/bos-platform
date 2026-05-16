"""
Recovery and readiness policy surface for BOS Code v2.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeBranchState, CodeMcpServer, CodeSession, CodeTask, CodeToolCall, CodeVerificationRun


@dataclass(slots=True)
class RecoverySnapshot:
    status: str
    failure_class: str | None
    headline: str
    recommended_actions: list[str]
    next_safe_action: str | None
    blocking_reasons: list[str]
    evidence: dict


class CodeRecoveryService:
    @staticmethod
    async def _latest_branch_state(db: AsyncSession, *, workspace_id: int, branch_name: str) -> CodeBranchState | None:
        result = await db.execute(
            select(CodeBranchState).where(
                CodeBranchState.workspace_id == workspace_id,
                CodeBranchState.branch_name == branch_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _latest_tool_call(db: AsyncSession, *, session_id: int) -> CodeToolCall | None:
        result = await db.execute(
            select(CodeToolCall)
            .where(CodeToolCall.session_id == session_id)
            .order_by(CodeToolCall.created_at.desc(), CodeToolCall.id.desc())
            .limit(10)
        )
        recent_calls = list(result.scalars().all())
        if not recent_calls:
            return None
        denied_call = next((call for call in recent_calls if call.was_denied), None)
        return denied_call or recent_calls[0]

    @staticmethod
    async def _verification_runs(db: AsyncSession, *, session_id: int) -> list[CodeVerificationRun]:
        result = await db.execute(
            select(CodeVerificationRun).where(CodeVerificationRun.session_id == session_id).order_by(CodeVerificationRun.id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def _mcp_servers(db: AsyncSession, *, workspace_id: int) -> list[CodeMcpServer]:
        result = await db.execute(
            select(CodeMcpServer).where(CodeMcpServer.workspace_id == workspace_id).order_by(CodeMcpServer.server_name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def _session_tasks(db: AsyncSession, *, workspace_id: int, session_id: int) -> list[CodeTask]:
        result = await db.execute(
            select(CodeTask)
            .where(
                CodeTask.workspace_id == workspace_id,
                CodeTask.session_id == session_id,
            )
            .order_by(CodeTask.updated_at.desc(), CodeTask.id.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def classify_failure(
        cls,
        db: AsyncSession,
        *,
        session: CodeSession,
    ) -> tuple[str | None, list[str], dict]:
        evidence: dict = {"session_status": session.session_status, "verification_status": session.verification_status}
        blocking_reasons: list[str] = []

        branch_state = await cls._latest_branch_state(
            db,
            workspace_id=session.workspace_id,
            branch_name=session.session_branch,
        )
        if branch_state is not None:
            evidence["branch_status"] = branch_state.branch_status
            evidence["is_dirty"] = branch_state.is_dirty
            evidence["is_stale_against_base"] = branch_state.is_stale_against_base
            evidence["ahead_count"] = branch_state.ahead_count
            evidence["behind_count"] = branch_state.behind_count

            if branch_state.is_dirty:
                blocking_reasons.append("dirty_workspace")
            if branch_state.is_stale_against_base:
                blocking_reasons.append("stale_branch")
            if branch_state.branch_status == "degraded":
                blocking_reasons.append("git_runtime_unavailable")

        verification_runs = await cls._verification_runs(db, session_id=session.id)
        if verification_runs:
            failed_stage = next((run for run in verification_runs if run.verification_status == "failed"), None)
            if failed_stage is not None:
                evidence["failed_verification_stage"] = failed_stage.verification_stage
                blocking_reasons.append("verification_failed")

        latest_tool_call = await cls._latest_tool_call(db, session_id=session.id)
        if latest_tool_call is not None:
            evidence["latest_tool_name"] = latest_tool_call.tool_name
            evidence["latest_tool_denied"] = latest_tool_call.was_denied
            evidence["latest_tool_denial_reason"] = latest_tool_call.denial_reason

            if latest_tool_call.was_denied and latest_tool_call.denial_reason in {
                "provider_error",
                "provider_cooldown",
                "provider_unavailable",
            }:
                blocking_reasons.append("provider_error")
            elif latest_tool_call.was_denied and latest_tool_call.denial_reason == "prompt_misdelivery":
                blocking_reasons.append("prompt_delivery")
            elif latest_tool_call.was_denied and latest_tool_call.denial_reason == "trust_required":
                blocking_reasons.append("trust_gate")
            elif latest_tool_call.was_denied and latest_tool_call.denial_reason == "client_cancelled":
                blocking_reasons.append("prompt_delivery")
            elif latest_tool_call.was_denied:
                blocking_reasons.append("permission_denied")

        mcp_servers = await cls._mcp_servers(db, workspace_id=session.workspace_id)
        degraded_mcp = [server.server_name for server in mcp_servers if server.connection_status == "degraded"]
        auth_required_mcp = [server.server_name for server in mcp_servers if server.connection_status == "auth_required"]
        if degraded_mcp:
            evidence["degraded_mcp_servers"] = degraded_mcp
            blocking_reasons.append("mcp_failed")
        if auth_required_mcp:
            evidence["auth_required_mcp_servers"] = auth_required_mcp
            blocking_reasons.append("mcp_auth_required")

        if session.session_status == "failed" and "provider_error" not in blocking_reasons:
            blocking_reasons.append("tool_runtime")
        if session.session_status == "trust_required" and "trust_gate" not in blocking_reasons:
            blocking_reasons.append("trust_gate")
        if session.session_status == "blocked" and "prompt_delivery" in blocking_reasons:
            evidence["recovery_mode"] = "soft_reset_available"

        session_tasks = await cls._session_tasks(db, workspace_id=session.workspace_id, session_id=session.id)
        review_gate_tasks = [
            task.id for task in session_tasks if task.task_status in {"review_pending", "in_review"}
        ]
        if review_gate_tasks:
            evidence["review_gate_task_ids"] = review_gate_tasks
        verification_gate_tasks = [
            task.id for task in session_tasks if task.task_status == "verification_pending"
        ]
        if verification_gate_tasks:
            evidence["verification_gate_task_ids"] = verification_gate_tasks

        failure_class = blocking_reasons[0] if blocking_reasons else None
        return failure_class, blocking_reasons, evidence

    @classmethod
    async def suggest_recovery_actions(
        cls,
        db: AsyncSession,
        *,
        session: CodeSession,
    ) -> RecoverySnapshot:
        failure_class, blocking_reasons, evidence = await cls.classify_failure(db, session=session)

        recommended_actions: list[str] = []
        next_safe_action: str | None = None
        status = "ready"
        headline = "Session is ready to continue."

        if "dirty_workspace" in blocking_reasons:
            status = "blocked"
            headline = "Workspace is dirty and needs operator attention."
            recommended_actions.append("Inspect the current diff in the Diff Inspector before continuing.")
            recommended_actions.append("Decide whether to resume this branch or start a fresh session branch.")

        if "stale_branch" in blocking_reasons:
            status = "needs_recovery"
            headline = "Session branch is stale against its base branch."
            recommended_actions.append("Refresh branch posture and review ahead/behind counts.")
            recommended_actions.append("Merge or recreate the session branch before broad verification.")
            next_safe_action = next_safe_action or "refresh_branch"

        if "verification_failed" in blocking_reasons:
            status = "needs_recovery"
            headline = "Verification failed and requires a targeted follow-up."
            recommended_actions.append("Inspect the failing verification stage and its log excerpt.")
            review_gate_task_ids = evidence.get("review_gate_task_ids") or []
            failed_stage = evidence.get("failed_verification_stage")
            if failed_stage and not review_gate_task_ids:
                recommended_actions.append("Rerun the failing stage after addressing the relevant code or config issue.")
                next_safe_action = next_safe_action or "run_verification"
            elif review_gate_task_ids:
                recommended_actions.append("Resolve the active review gate before rerunning verification automatically.")
            else:
                recommended_actions.append("Determine the failing verification stage before attempting automated reruns.")

        if "provider_error" in blocking_reasons:
            status = "degraded"
            headline = "Provider execution failed."
            recommended_actions.append("Check team-pool credentials or provider configuration.")
            recommended_actions.append("Retry the session turn after provider health is restored.")

        if "prompt_delivery" in blocking_reasons:
            status = "needs_recovery"
            headline = "The session appears recoverable without changing code."
            recommended_actions.append("Reset the session back to ready-for-prompt.")
            recommended_actions.append("Resend the intended prompt after the runtime posture stabilizes.")
            next_safe_action = next_safe_action or "reset_session_ready"

        if "permission_denied" in blocking_reasons and failure_class == "permission_denied":
            status = "blocked"
            headline = "An attempted operation was blocked by policy."
            recommended_actions.append("Switch to an allowed tool or use a role with the required permission mode.")
            recommended_actions.append("Review the denial reason in the session timeline before retrying.")

        if "trust_gate" in blocking_reasons:
            status = "blocked"
            headline = "A trust gate must be cleared before the session can continue."
            recommended_actions.append("Resolve the trust prompt before retrying the session.")

        if "mcp_auth_required" in blocking_reasons:
            status = "degraded"
            headline = "An MCP server requires authentication."
            recommended_actions.append("Reconnect the MCP server after satisfying its auth requirements.")

        if "mcp_failed" in blocking_reasons and failure_class == "mcp_failed":
            status = "degraded"
            headline = "An MCP server is in degraded mode."
            recommended_actions.append("Inspect MCP server status and reconnect the affected server.")

        if "git_runtime_unavailable" in blocking_reasons and failure_class == "git_runtime_unavailable":
            status = "degraded"
            headline = "Git runtime is unavailable in the current environment."
            recommended_actions.append("Ensure git is available in PATH on the runtime machine.")

        if not blocking_reasons and session.session_status in {"ready", "completed"}:
            status = "merge_ready"
            headline = "Branch posture is clean and no blocking recovery signals are active."
            recommended_actions.append("Review diff, verification, and artifacts before merge or handoff.")

        return RecoverySnapshot(
            status=status,
            failure_class=failure_class,
            headline=headline,
            recommended_actions=recommended_actions,
            next_safe_action=next_safe_action,
            blocking_reasons=blocking_reasons,
            evidence=evidence,
        )
