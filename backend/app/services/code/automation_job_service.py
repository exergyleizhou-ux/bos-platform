"""
Scheduled automation jobs and BOS heartbeat execution.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import (
    CodeAgentRuntimeState,
    CodeAutomationJob,
    CodeBranchState,
    CodeSession,
    CodeTask,
    CodeTurn,
    CodeVerificationRun,
    CodeWorker,
    CodeWorkspace,
    User,
)
from app.services.brain_runtime import RunLedgerArtifact, apply_run_ledger_artifact
from app.services.code.automation_service import CodeAutomationService
from app.services.code.event_service import CodeEventService
from app.services.code.maintenance_service import CodeMaintenanceService
from app.services.code.memory_service import CodeMemoryService
from app.services.code.orchestration_service import CodeOrchestrationService
from app.services.code.planner_critic_service import CodePlannerCriticService
from app.services.code.reflection_service import CodeReflectionService
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.subagent_service import CodeSubagentService
from app.services.code.task_service import CodeTaskService
from app.services.code.worker_event_service import CodeWorkerEventService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.code.session_service import CodeSessionService



class CodeAutomationJobService:
    RUN_LEDGER_PATH = Path(__file__).resolve().parents[4] / ".agents" / "runtime" / "run-ledger.md"
    HEARTBEAT_PRIORITY = {
        "blocked": 5,
        "verification_pending": 4,
        "review_pending": 3,
        "running": 2,
        "created": 1,
    }
    planner_critic = CodePlannerCriticService()
    subagent_service = CodeSubagentService()

    @staticmethod
    def _humanize_action(action: str | None) -> str | None:
        return action.replace("_", " ") if action else None

    @classmethod
    def _build_continuation_prompt(
        cls,
        *,
        heartbeat_packet: dict,
        snapshot,
        job: CodeAutomationJob,
    ) -> str:
        planner_steps = heartbeat_packet.get("planner_steps") or []
        critic_checks = heartbeat_packet.get("critic_checks") or []
        difficulty_signals = heartbeat_packet.get("difficulty_signals") or []
        next_action = snapshot.next_automation_action or snapshot.next_human_action or "inspect_context"
        lines = [
            "[system automation] Continue the current BOS Code work without waiting for another human continue prompt.",
            "Keep pushing the active slice until you clear the next gate, hit a real blocker, or need a meaningful human decision.",
            (
                f"Focus task: #{snapshot.focus_task_id} {snapshot.focus_task_title} ({snapshot.focus_task_status})."
                if snapshot.focus_task_id is not None and snapshot.focus_task_title is not None
                else "Focus task: no explicit task is active yet; inspect the runtime posture first."
            ),
            f"Merge posture: {snapshot.merge_readiness}. Verification gate: {snapshot.verification_gate}.",
            f"Next recommended action: {cls._humanize_action(next_action)}.",
            (
                "Loop budget: "
                f"{heartbeat_packet.get('loop_budget', 'standard')}. "
                f"Convergence signal: {heartbeat_packet.get('convergence_signal', 'unknown')}."
            ),
        ]
        if planner_steps:
            lines.append("Planner steps:")
            lines.extend(f"- {step}" for step in planner_steps[:4])
        if critic_checks:
            lines.append("Critic checks:")
            lines.extend(f"- {check}" for check in critic_checks[:4])
        if difficulty_signals:
            lines.append("Difficulty signals:")
            lines.extend(f"- {signal}" for signal in difficulty_signals[:4])
        if job.prompt_template:
            lines.append(f"Automation note: {job.prompt_template}")
        return "\n".join(lines)

    @staticmethod
    def _build_idle_maintenance_prompt(*, objective: str, mode: str) -> str:
        return "\n".join(
            [
                "[system automation] No active foreground BOS Code task requires immediate lane routing.",
                "Use the runtime's maintenance objective to keep improving the workspace without waiting for a human continue prompt.",
                f"Maintenance mode: {mode}.",
                f"Objective: {objective}",
                "Make the next safe improvement, verification sweep, or recovery move, then summarize what changed and what should happen next.",
            ]
        )

    @staticmethod
    def _derive_seed_task_title(*, mode: str, objective: str) -> str:
        if mode == "recover_verification":
            return "Verification recovery sweep"
        if mode == "repair_skill":
            return "Skill repair and hardening"
        if mode == "recover_session":
            return "Session recovery follow-up"
        return objective[:120].rstrip(".") or "Idle maintenance sweep"

    @staticmethod
    def _build_seed_acceptance_criteria(*, mode: str, objective: str) -> list[str]:
        criteria = [
            "Advance the autonomy objective without waiting for a manual continue prompt.",
            "Keep the next gate, blocker, or verification step explicit in the handoff.",
        ]
        if mode == "recover_verification":
            criteria.append("Inspect the failing verification signal and prepare the safest corrective action.")
        elif mode == "repair_skill":
            criteria.append("Use recent runtime evidence to strengthen the weakest reusable skill or procedure.")
        elif mode == "recover_session":
            criteria.append("Restore the blocked session to a healthy ready-for-prompt or clearly document why it cannot recover.")
        else:
            criteria.append("Run the highest-value maintenance or readiness sweep suggested by the current runtime state.")
        if "branch" in objective.lower():
            criteria.append("Refresh branch posture before trusting merge-oriented conclusions.")
        return criteria

    @classmethod
    async def _should_seed_autonomy_task(
        cls,
        *,
        runtime: CodeAgentRuntimeState,
        objective: str,
        now: datetime,
    ) -> bool:
        metrics = dict(runtime.runtime_metrics or {})
        previous_objective = str(metrics.get("last_seeded_autonomy_objective") or "")
        previous_at_raw = metrics.get("last_seeded_autonomy_at")
        if previous_objective != objective or not previous_at_raw:
            return True
        try:
            previous_at = datetime.fromisoformat(str(previous_at_raw))
        except ValueError:
            return True
        if previous_at.tzinfo is None:
            previous_at = previous_at.replace(tzinfo=UTC)
        else:
            previous_at = previous_at.astimezone(UTC)
        return now - previous_at >= timedelta(hours=6)

    @classmethod
    async def _seed_autonomy_task_if_idle(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        user: User,
        session: CodeSession,
        runtime: CodeAgentRuntimeState,
        maintenance_result: dict,
        seeded_at: datetime,
    ) -> CodeTask | None:
        if int(maintenance_result.get("open_task_count") or 0) > 0:
            return None

        mode = str(maintenance_result.get("next_autonomy_mode") or "idle_maintenance")
        objective = str(maintenance_result.get("next_autonomy_objective") or "").strip()
        if not objective:
            return None
        if not await cls._should_seed_autonomy_task(runtime=runtime, objective=objective, now=seeded_at):
            return None

        title = cls._derive_seed_task_title(mode=mode, objective=objective)
        acceptance_criteria = cls._build_seed_acceptance_criteria(mode=mode, objective=objective)
        task = await CodeTaskService.create_task(
            db,
            workspace=workspace,
            user=user,
            session_id=session.id,
            title=title,
            objective=objective,
            scope="code/runtime",
            acceptance_criteria=acceptance_criteria,
        )
        task, _architect, _worker = await CodeTaskService.architect_route_task(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            acceptance_criteria=task.acceptance_criteria,
            summary=f"Autonomy seeded task #{task.id} from maintenance mode `{mode}`.",
            route_to="executor",
            payload={"source": "autonomy_maintenance", "autonomy_mode": mode},
        )
        worker = await CodeTaskService._get_worker(db, workspace_id=workspace.id, worker_name="executor")
        runs = await cls.subagent_service.create_runs_for_task(
            db,
            workspace=workspace,
            session=session,
            task=task,
            worker=worker,
            metadata={"source": "autonomy_seed", "autonomy_mode": mode},
        )
        for run in runs:
            await cls.subagent_service.enqueue_or_execute_run(db, run_id=run.id)
        await CodeRuntimeService.record_seeded_autonomy_task(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            objective=objective,
            seeded_at=seeded_at,
        )
        return task

    @classmethod
    def _write_run_ledger_artifact(
        cls,
        *,
        artifact: RunLedgerArtifact,
        when: datetime,
    ) -> str:
        cls.RUN_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = cls.RUN_LEDGER_PATH.read_text(encoding="utf-8") if cls.RUN_LEDGER_PATH.exists() else ""
        updated = apply_run_ledger_artifact(existing, artifact, when=when)
        cls.RUN_LEDGER_PATH.write_text(updated, encoding="utf-8")
        return updated

    @classmethod
    def _stage_heartbeat_run_artifact(
        cls,
        *,
        workspace: CodeWorkspace,
        summary: str,
        decision: str,
        heartbeat_packet: dict,
        snapshot,
        executed_action: str | None,
        when: datetime,
    ) -> RunLedgerArtifact:
        focus_title = snapshot.focus_task_title or heartbeat_packet.get("focus_task_title") or "BOS Code heartbeat"
        outcome = {
            "run": "Heartbeat evaluated active BOS Code work.",
            "skip": "Heartbeat found no active BOS Code work.",
        }.get(decision, f"Heartbeat finished with decision '{decision}'.")
        if executed_action:
            outcome = f"Heartbeat auto-executed {cls._humanize_action(executed_action)}."
        elif decision == "run":
            outcome = "Heartbeat queued the next BOS Code follow-up."

        verification = "Built the heartbeat packet and orchestration snapshot for BOS Code."
        if executed_action:
            verification = (
                "Built the heartbeat packet and orchestration snapshot, then executed the next automation-safe action."
            )

        next_action = (
            cls._humanize_action(executed_action)
            or cls._humanize_action(getattr(snapshot, "next_automation_action", None))
            or cls._humanize_action(getattr(snapshot, "next_human_action", None))
            or "inspect orchestration state"
        )
        remaining_risk = getattr(snapshot, "merge_summary", None) or summary
        return RunLedgerArtifact(
            slice=f"BOS Code heartbeat: {focus_title}",
            outcome=outcome,
            verification=verification,
            remaining_risk=remaining_risk,
            next_step=f"{next_action.capitalize()} in the BOS Orchestrator.",
            target_surface="orchestrator",
            target_id=str(workspace.id),
            target_route="/bos/orchestrator",
        )

    @classmethod
    def _stage_maintenance_run_artifact(
        cls,
        *,
        summary: str,
        maintenance_result: dict,
    ) -> RunLedgerArtifact:
        next_objective = str(maintenance_result.get("next_autonomy_objective") or "Keep the autonomy runtime healthy.")
        return RunLedgerArtifact(
            slice="BOS Code maintenance: autonomy brain refresh",
            outcome="Maintenance refreshed project memory, staged reports, and proposed the next autonomy objective.",
            verification="Updated runtime brain documents and staged maintenance artifacts for operator review.",
            remaining_risk=summary,
            next_step=next_objective,
            target_surface="brain",
            target_id=None,
            target_route="/bos/brain",
        )

    @staticmethod
    async def get_job(db: AsyncSession, *, workspace_id: int, job_id: int) -> CodeAutomationJob | None:
        result = await db.execute(
            select(CodeAutomationJob).where(
                CodeAutomationJob.workspace_id == workspace_id,
                CodeAutomationJob.id == job_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _latest_session(db: AsyncSession, *, workspace_id: int) -> CodeSession | None:
        result = await db.execute(
            select(CodeSession)
            .where(CodeSession.workspace_id == workspace_id)
            .order_by(CodeSession.created_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def _latest_turn(db: AsyncSession, *, session_id: int) -> CodeTurn | None:
        result = await db.execute(
            select(CodeTurn)
            .where(CodeTurn.session_id == session_id)
            .order_by(CodeTurn.created_at.desc(), CodeTurn.id.desc())
        )
        return result.scalars().first()

    @staticmethod
    def _should_enqueue_continuation(
        *,
        session: CodeSession,
        latest_turn: CodeTurn | None,
        now: datetime,
    ) -> tuple[bool, str | None]:
        if session.session_status not in {"ready_for_prompt", "ready"}:
            return False, f"session_status_{session.session_status}"
        if latest_turn is None:
            return True, None
        if latest_turn.turn_status == "running":
            return False, "latest_turn_running"
        created_at = latest_turn.created_at
        if created_at is not None:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            else:
                created_at = created_at.astimezone(UTC)
            if now - created_at < timedelta(seconds=90):
                return False, "recent_turn_throttle"
        return True, None

    @staticmethod
    def _provider_pause_reason(runtime: CodeAgentRuntimeState, *, now: datetime) -> str | None:
        metrics = dict(runtime.runtime_metrics or {})
        pause_until_raw = metrics.get("provider_pause_until")
        if not pause_until_raw:
            return None
        try:
            pause_until = datetime.fromisoformat(str(pause_until_raw))
        except ValueError:
            return None
        if pause_until.tzinfo is None:
            pause_until = pause_until.replace(tzinfo=UTC)
        else:
            pause_until = pause_until.astimezone(UTC)
        if pause_until > now:
            failure_class = str(metrics.get("last_provider_failure_class") or "provider_error")
            return f"provider_backpressure_{failure_class}"
        return None

    @staticmethod
    def _build_heartbeat_packet(
        *,
        tasks: list[CodeTask],
        workers: list[CodeWorker],
        branches: list[CodeBranchState],
        verifications: list[CodeVerificationRun],
        policy_learning: dict[str, dict[str, int]] | None = None,
    ) -> dict:
        focus_task = None
        if tasks:
            focus_task = sorted(
                tasks,
                key=lambda task: (-CodeAutomationJobService.HEARTBEAT_PRIORITY.get(task.task_status, 0), -int(task.id)),
            )[0]

        critic_notes: list[str] = []
        critic_checks: list[str] = []
        planner_steps: list[str] = []
        difficulty_signals: list[str] = []
        planner_recommendation = "inspect_context"
        risk_level = "low"
        policy_learning = policy_learning or {}

        if any(task.task_status == "blocked" for task in tasks):
            difficulty_signals.append("blocked_task")
            critic_notes.append("Blocked task detected; do not assume automation can safely continue without recovery.")
            critic_checks.extend(
                [
                    "Inspect blocked task evidence before resuming execution.",
                    "Confirm no failed subagent slices remain unresolved.",
                ]
            )
            planner_steps.extend(
                [
                    "Refresh branch posture and inspect the blocked task evidence.",
                    "Stabilize executor state before attempting a new handoff.",
                ]
            )
            planner_recommendation = "refresh_branch"
            risk_level = "high"
        elif any(run.verification_status == "failed" for run in verifications):
            difficulty_signals.append("verification_failed")
            critic_notes.append("Verification failure detected; prioritize remediation before merge-oriented actions.")
            critic_checks.extend(
                [
                    "Treat verification output as the primary source of truth.",
                    "Avoid reviewer acceptance messaging until verification is green.",
                ]
            )
            planner_steps.extend(
                [
                    "Run or inspect verification first.",
                    "Only continue merge-oriented work after the gate clears.",
                ]
            )
            planner_recommendation = "run_verification"
            risk_level = "high"
        elif any(branch.branch_status in {"dirty", "stale", "degraded"} for branch in branches):
            difficulty_signals.append("branch_posture_degraded")
            critic_notes.append("Branch posture is degraded; refresh git posture before relying on downstream summaries.")
            critic_checks.extend(
                [
                    "Do not trust stale or dirty branch posture for merge decisions.",
                    "Prefer refresh_branch before any automation-safe next move.",
                ]
            )
            planner_steps.extend(
                [
                    "Refresh git posture.",
                    "Re-check automation readiness after branch evidence updates.",
                ]
            )
            planner_recommendation = "refresh_branch"
            risk_level = "medium"
        elif any(task.task_status == "review_pending" for task in tasks):
            difficulty_signals.append("review_handoff_pending")
            critic_notes.append("Reviewer handoff is pending; keep the review lane visible before pushing further execution.")
            critic_checks.extend(
                [
                    "Do not continue executor work when reviewer handoff is already pending.",
                    "Keep reviewer packet and checklist visible.",
                ]
            )
            planner_steps.extend(
                [
                    "Surface reviewer-ready packet.",
                    "If automation is allowed, begin the review lane next.",
                ]
            )
            planner_recommendation = "begin_review"
            risk_level = "medium"
        elif any(task.task_status == "verification_pending" for task in tasks):
            difficulty_signals.append("verification_pending")
            critic_notes.append("Verification is the next gate; avoid calling the task done until the gate clears.")
            critic_checks.extend(
                [
                    "Do not mark the task complete while verification is pending.",
                    "Treat verification as the single remaining gate.",
                ]
            )
            planner_steps.extend(
                [
                    "Run verification next.",
                    "Refresh readiness once verification results land.",
                ]
            )
            planner_recommendation = "run_verification"
            risk_level = "medium"
        elif any(task.task_status == "running" for task in tasks):
            difficulty_signals.append("active_execution")
            critic_notes.append("Execution is still in motion; prefer concise status and the safest next move.")
            critic_checks.extend(
                [
                    "Check whether executor work already produced a reviewer-ready packet.",
                    "Avoid duplicate review requests when a handoff already exists.",
                ]
            )
            planner_steps.extend(
                [
                    "Inspect execution posture.",
                    "If executor handoff is ready, move toward review; otherwise keep execution visible.",
                ]
            )
            planner_recommendation = "request_review"
            risk_level = "medium"
        elif any(task.task_status == "created" for task in tasks):
            difficulty_signals.append("planning_not_explicit")
            critic_notes.append("Planning still needs to happen before execution can be trusted.")
            critic_checks.extend(
                [
                    "Do not dispatch execution before acceptance criteria exist.",
                    "Architect planning should happen before executor routing.",
                ]
            )
            planner_steps.extend(
                [
                    "Draft acceptance criteria.",
                    "Route the task after planning is explicit.",
                ]
            )
            planner_recommendation = "architect_plan"
            risk_level = "medium"

        decision = "run" if (tasks or workers or branches or verifications) else "skip"
        focus_summary = ""
        if focus_task is not None:
            focus_summary = f" Focus task: #{focus_task.id} {focus_task.title} ({focus_task.task_status})."
        summary = (
            f"Heartbeat found {len(tasks)} open tasks, {len(workers)} active workers, "
            f"{len(branches)} branch blockers, and {len(verifications)} verification items.{focus_summary}"
            if decision == "run"
            else "Heartbeat found no active BOS Code work."
        )
        if decision == "skip":
            critic_notes = ["No active blockers or in-flight work detected."]
            critic_checks = ["No active execution, review, or verification blockers detected."]
            planner_steps = ["Keep the workspace idle until the next task or event arrives."]

        handoff_learning = policy_learning.get("subagent_handoff", {})
        recovery_learning = policy_learning.get("subagent_recovery", {})
        heartbeat_execution = policy_learning.get("heartbeat_execution", {})
        review_decision = policy_learning.get("review_decision", {})
        verification_result = policy_learning.get("verification_result", {})
        auto_executed = int(heartbeat_execution.get("auto_executed", 0))
        nudged = int(heartbeat_execution.get("nudge_only", 0))
        handoff_ready = int(handoff_learning.get("ready", 0))
        recovery_blocked = int(recovery_learning.get("blocked", 0))
        review_accepts = int(review_decision.get("accept", 0))
        review_rejects = int(review_decision.get("reject", 0))
        verification_passes = int(verification_result.get("passed", 0))
        verification_failures = int(verification_result.get("failed", 0))

        if recovery_blocked > handoff_ready:
            difficulty_signals.append("historical_recovery_drag")
            risk_level = "high"
            planner_recommendation = "refresh_branch" if planner_recommendation == "request_review" else planner_recommendation
            critic_notes.append("Historical recovery signals outweigh successful handoffs; bias toward stabilization.")
            critic_checks.append("Prefer recovery-oriented actions when recent executor slices tend to fail.")
        elif handoff_ready >= max(2, recovery_blocked + 1) and decision == "run":
            critic_notes.append("Historical handoff signals are healthy; reviewer-ready paths can be trusted more often.")
            if planner_recommendation == "request_review":
                planner_steps.insert(0, "Trust the recent executor handoff pattern and inspect reviewer packet first.")

        if review_rejects > review_accepts:
            difficulty_signals.append("review_history_negative")
            risk_level = "high" if risk_level == "medium" else risk_level
            critic_notes.append("Recent reviewer decisions lean negative; tighten handoff quality before review requests.")
            critic_checks.append("Check reviewer packet completeness and unresolved checklist items.")
        elif review_accepts >= max(2, review_rejects + 1) and decision == "run":
            critic_notes.append("Recent reviewer decisions lean positive; review-oriented paths have been succeeding.")

        if verification_failures > verification_passes:
            difficulty_signals.append("verification_history_negative")
            risk_level = "high"
            critic_notes.append("Historical verification failures outweigh passes; treat verification as a primary planning concern.")
            critic_checks.append("Bias toward verification-first planning until pass rate improves.")
        elif verification_passes >= max(2, verification_failures + 1) and decision == "run":
            critic_notes.append("Recent verification outcomes are healthy; merge-oriented gating is more trustworthy.")

        if auto_executed > nudged and decision == "run":
            critic_notes.append("Automation has recently succeeded without human intervention; automation-safe next moves are more trustworthy.")
        elif nudged > auto_executed and decision == "run":
            difficulty_signals.append("human_nudge_bias")
            critic_notes.append("Recent heartbeats needed human-facing nudges more often than autonomous execution.")

        open_task_count = len(tasks)
        branch_issue_count = len(branches)
        active_verification_count = len(verifications)
        if open_task_count >= 3:
            difficulty_signals.append("multi_task_surface")
        if branch_issue_count >= 2:
            difficulty_signals.append("multi_branch_issue")
        if active_verification_count >= 2:
            difficulty_signals.append("multi_verification_issue")

        unique_difficulty_signals = list(dict.fromkeys(difficulty_signals))
        if decision == "skip":
            loop_budget = "exit"
            convergence_signal = "idle"
        else:
            high_pressure = risk_level == "high" or len(unique_difficulty_signals) >= 3
            stable_execution = (
                risk_level == "low"
                and open_task_count <= 1
                and branch_issue_count == 0
                and active_verification_count == 0
            )
            if high_pressure:
                loop_budget = "deep"
                convergence_signal = "needs_more_evidence"
            elif stable_execution:
                loop_budget = "short"
                convergence_signal = "ready_to_exit"
            else:
                loop_budget = "standard"
                convergence_signal = "continue_until_next_gate"

        if loop_budget == "deep":
            critic_checks.append("Use extra evaluate -> implement -> verify depth until the risk signal materially changes.")
        elif loop_budget == "short":
            critic_checks.append("Exit once the next decisive gate is green; do not add narrative-only passes.")

        return {
            "decision": decision,
            "summary": summary,
            "focus_task_id": focus_task.id if focus_task is not None else None,
            "focus_task_title": focus_task.title if focus_task is not None else None,
            "focus_task_status": focus_task.task_status if focus_task is not None else None,
            "planner_recommendation": planner_recommendation,
            "planner_steps": planner_steps,
            "critic_notes": critic_notes,
            "critic_checks": critic_checks,
            "risk_level": risk_level,
            "loop_budget": loop_budget,
            "convergence_signal": convergence_signal,
            "difficulty_signals": unique_difficulty_signals,
            "policy_learning_snapshot": policy_learning,
        }

    @staticmethod
    async def _heartbeat_decision(db: AsyncSession, *, workspace_id: int) -> tuple[str, str, dict]:
        task_result = await db.execute(
            select(CodeTask).where(
                CodeTask.workspace_id == workspace_id,
                CodeTask.task_status.in_(("created", "running", "review_pending", "verification_pending", "blocked")),
            )
        )
        tasks = list(task_result.scalars().all())
        worker_result = await db.execute(
            select(CodeWorker).where(
                CodeWorker.workspace_id == workspace_id,
                CodeWorker.worker_status.in_(("running", "waiting_review", "blocked")),
            )
        )
        workers = list(worker_result.scalars().all())
        branch_result = await db.execute(
            select(CodeBranchState).where(
                CodeBranchState.workspace_id == workspace_id,
                CodeBranchState.branch_status.in_(("dirty", "stale", "degraded")),
            )
        )
        branches = list(branch_result.scalars().all())
        verification_result = await db.execute(
            select(CodeVerificationRun).join(CodeSession, CodeVerificationRun.session_id == CodeSession.id).where(
                CodeSession.workspace_id == workspace_id,
                CodeVerificationRun.verification_status.in_(("failed", "running", "pending")),
            )
        )
        verifications = list(verification_result.scalars().all())
        policy_learning = await CodeRuntimeService.get_policy_learning_snapshot(db, workspace_id=workspace_id)
        packet = CodeAutomationJobService._build_heartbeat_packet(
            tasks=tasks,
            workers=workers,
            branches=branches,
            verifications=verifications,
            policy_learning=policy_learning,
        )
        packet = await CodeAutomationJobService.planner_critic.derive_heartbeat_packet(
            workspace_id=workspace_id,
            heuristic_packet=packet,
        )
        return packet["decision"], packet["summary"], packet

    @classmethod
    async def execute_job(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        job: CodeAutomationJob,
        user: User,
        session_service: CodeSessionService,
    ) -> tuple[CodeAutomationJob, CodeSession | None, str]:
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=workspace.id)
        latest_session = await cls._latest_session(db, workspace_id=workspace.id)
        summary = "Automation did not run."
        session_used = latest_session

        try:
            if job.job_type == "heartbeat":
                decision, heartbeat_summary, heartbeat_packet = await cls._heartbeat_decision(db, workspace_id=workspace.id)
                runtime.last_heartbeat_decision = decision
                heartbeat_at = datetime.now(UTC)
                runtime.last_heartbeat_at = heartbeat_at
                summary = heartbeat_summary
                heartbeat_metrics = dict(runtime.runtime_metrics or {})
                heartbeat_metrics["last_heartbeat_summary"] = heartbeat_summary
                heartbeat_metrics["last_heartbeat_risk_level"] = heartbeat_packet["risk_level"]
                heartbeat_metrics["last_heartbeat_planner_recommendation"] = heartbeat_packet["planner_recommendation"]
                heartbeat_metrics["last_heartbeat_planner_steps"] = heartbeat_packet["planner_steps"]
                heartbeat_metrics["last_heartbeat_critic_notes"] = heartbeat_packet["critic_notes"]
                heartbeat_metrics["last_heartbeat_critic_checks"] = heartbeat_packet["critic_checks"]
                heartbeat_metrics["last_heartbeat_decision_source"] = heartbeat_packet.get("decision_source", "heuristic")
                heartbeat_metrics["last_heartbeat_loop_budget"] = heartbeat_packet.get("loop_budget")
                heartbeat_metrics["last_heartbeat_convergence_signal"] = heartbeat_packet.get("convergence_signal")
                heartbeat_metrics["last_heartbeat_difficulty_signals"] = heartbeat_packet.get("difficulty_signals", [])
                heartbeat_metrics["last_heartbeat_policy_learning_snapshot"] = heartbeat_packet["policy_learning_snapshot"]
                snapshot = await CodeOrchestrationService.build_snapshot(db, workspace_id=workspace.id)
                heartbeat_metrics["last_heartbeat_focus_task_id"] = snapshot.focus_task_id
                heartbeat_metrics["last_heartbeat_focus_task_title"] = snapshot.focus_task_title
                heartbeat_metrics["last_heartbeat_next_automation_action"] = snapshot.next_automation_action
                executed_action: str | None = None
                runtime.runtime_metrics = heartbeat_metrics
                if decision == "run":
                    if snapshot.automation_ready and snapshot.next_automation_action is not None:
                        automation_result = await CodeAutomationService.execute_next_automation(
                            db,
                            workspace=workspace,
                            role=user.role,
                            safe_bash_timeout_sec=30,
                            max_read_bytes=262144,
                            max_write_bytes=131072,
                        )
                        summary = (
                            f"{heartbeat_summary} "
                            f"Heartbeat also executed automation action {automation_result.executed_action}."
                        )
                        session_used = latest_session if latest_session is not None else session_used
                        executed_action = automation_result.executed_action
                        heartbeat_metrics["last_heartbeat_executed_action"] = automation_result.executed_action
                        heartbeat_metrics["last_heartbeat_execution_status"] = automation_result.execution_status
                        runtime.runtime_metrics = heartbeat_metrics
                        await CodeRuntimeService.record_policy_signal(
                            db,
                            workspace_id=workspace.id,
                            category="heartbeat_execution",
                            outcome="auto_executed",
                        )
                    else:
                        if latest_session is None:
                            latest_session = await session_service.create_session(
                                db,
                                user=user,
                                acquire_write_lease=False,
                            )
                        session_used = latest_session
                        latest_turn = await cls._latest_turn(db, session_id=latest_session.id)
                        should_continue, suppression_reason = cls._should_enqueue_continuation(
                            session=latest_session,
                            latest_turn=latest_turn,
                            now=heartbeat_at,
                        )
                        if should_continue:
                            pause_reason = cls._provider_pause_reason(runtime, now=heartbeat_at)
                            if pause_reason is not None:
                                summary = f"{heartbeat_summary} Continuation was deferred because {pause_reason}."
                                heartbeat_metrics["last_heartbeat_execution_status"] = "provider_paused"
                                runtime.runtime_metrics = heartbeat_metrics
                                await CodeRuntimeService.record_policy_signal(
                                    db,
                                    workspace_id=workspace.id,
                                    category="heartbeat_execution",
                                    outcome="provider_paused",
                                )
                            else:
                                prompt = cls._build_continuation_prompt(
                                    heartbeat_packet=heartbeat_packet,
                                    snapshot=snapshot,
                                    job=job,
                                )
                                await session_service.create_turn(db, session=latest_session, user_message=prompt)
                                await CodeEventService.append_event(
                                    db,
                                    session_id=latest_session.id,
                                    event_type="code.automation.heartbeat",
                                    payload={"job_id": job.id, "summary": heartbeat_summary},
                                )
                                await CodeRuntimeService.record_policy_signal(
                                    db,
                                    workspace_id=workspace.id,
                                    category="heartbeat_execution",
                                    outcome="nudge_only",
                                )
                        else:
                            summary = (
                                f"{heartbeat_summary} Continuation was deferred because {suppression_reason}."
                            )
                            heartbeat_metrics["last_heartbeat_execution_status"] = "suppressed"
                            runtime.runtime_metrics = heartbeat_metrics
                            await CodeRuntimeService.record_policy_signal(
                                db,
                                workspace_id=workspace.id,
                                category="heartbeat_execution",
                                outcome="suppressed",
                            )
                elif decision == "skip":
                    runtime_metrics = dict(runtime.runtime_metrics or {})
                    next_autonomy_objective = runtime_metrics.get("next_autonomy_objective")
                    next_autonomy_mode = str(runtime_metrics.get("next_autonomy_mode") or "idle_maintenance")
                    if next_autonomy_objective:
                        if latest_session is None:
                            latest_session = await session_service.create_session(
                                db,
                                user=user,
                                acquire_write_lease=False,
                            )
                        latest_turn = await cls._latest_turn(db, session_id=latest_session.id)
                        should_continue, suppression_reason = cls._should_enqueue_continuation(
                            session=latest_session,
                            latest_turn=latest_turn,
                            now=heartbeat_at,
                        )
                        if should_continue:
                            pause_reason = cls._provider_pause_reason(runtime, now=heartbeat_at)
                            if pause_reason is not None:
                                summary = f"{heartbeat_summary} Maintenance continuation was deferred because {pause_reason}."
                                heartbeat_metrics["last_heartbeat_execution_status"] = "provider_paused"
                                runtime.runtime_metrics = heartbeat_metrics
                                await CodeRuntimeService.record_policy_signal(
                                    db,
                                    workspace_id=workspace.id,
                                    category="heartbeat_execution",
                                    outcome="provider_paused",
                                )
                            else:
                                session_used = latest_session
                                prompt = cls._build_idle_maintenance_prompt(
                                    objective=str(next_autonomy_objective),
                                    mode=next_autonomy_mode,
                                )
                                await session_service.create_turn(db, session=latest_session, user_message=prompt)
                                summary = (
                                    "Heartbeat found no active foreground BOS Code work. "
                                    "Queued the next maintenance objective instead."
                                )
                                heartbeat_metrics["last_heartbeat_execution_status"] = "idle_maintenance"
                                runtime.runtime_metrics = heartbeat_metrics
                                await CodeRuntimeService.record_policy_signal(
                                    db,
                                    workspace_id=workspace.id,
                                    category="heartbeat_execution",
                                    outcome="idle_maintenance",
                                )
                        else:
                            summary = (
                                f"{heartbeat_summary} Maintenance continuation was deferred because {suppression_reason}."
                            )
                            heartbeat_metrics["last_heartbeat_execution_status"] = "suppressed"
                            runtime.runtime_metrics = heartbeat_metrics
                            await CodeRuntimeService.record_policy_signal(
                                db,
                                workspace_id=workspace.id,
                                category="heartbeat_execution",
                                outcome="suppressed",
                            )
                await CodeRuntimeService.mark_job_run(db, job=job, status=decision)
                await CodeRuntimeService.record_policy_signal(
                    db,
                    workspace_id=workspace.id,
                    category="heartbeat_decision",
                    outcome=decision,
                )
                heartbeat_artifact = cls._stage_heartbeat_run_artifact(
                    workspace=workspace,
                    summary=summary,
                    decision=decision,
                    heartbeat_packet=heartbeat_packet,
                    snapshot=snapshot,
                    executed_action=executed_action,
                    when=heartbeat_at,
                )
                cls._write_run_ledger_artifact(artifact=heartbeat_artifact, when=heartbeat_at)
                await CodeRuntimeService.record_run_ledger_artifact(
                    db,
                    workspace_id=workspace.id,
                    artifact=heartbeat_artifact,
                    when=heartbeat_at,
                )
                heartbeat_metrics = dict(runtime.runtime_metrics or {})
            elif job.job_type == "reflection":
                if latest_session is None:
                    raise ValueError("automation_requires_session")
                session_used = latest_session
                reflection = await CodeReflectionService.run_reflection(
                    db,
                    workspace=workspace,
                    session=latest_session,
                    user=user,
                    trigger_source=job.target_scope or "automation",
                )
                summary = reflection.summary or "Reflection completed."
                await CodeRuntimeService.mark_job_run(db, job=job, status="completed")
                await CodeRuntimeService.record_policy_signal(
                    db,
                    workspace_id=workspace.id,
                    category="reflection_job",
                    outcome="completed",
                )
            elif job.job_type == "maintenance":
                if latest_session is None:
                    latest_session = await session_service.create_session(
                        db,
                        user=user,
                        acquire_write_lease=False,
                    )
                session_used = latest_session
                maintenance_result = await CodeMaintenanceService.run_maintenance(
                    db,
                    workspace_id=workspace.id,
                )
                generated_at = datetime.fromisoformat(maintenance_result["generated_at"])
                await CodeRuntimeService.record_maintenance_summary(
                    db,
                    workspace_id=workspace.id,
                    summary=maintenance_result["summary"],
                    generated_at=generated_at,
                    report_markdown_path=maintenance_result["report_markdown_path"],
                    report_json_path=maintenance_result["report_json_path"],
                    project_brain_path=maintenance_result["project_brain_path"],
                    decision_journal_path=maintenance_result["decision_journal_path"],
                    evolution_log_path=maintenance_result["evolution_log_path"],
                    next_autonomy_mode=maintenance_result["next_autonomy_mode"],
                    next_autonomy_objective=maintenance_result["next_autonomy_objective"],
                    workflow_mode=maintenance_result["workflow_mode"],
                    workflow_skills=maintenance_result["workflow_skills"],
                    workflow_rationale=maintenance_result["workflow_rationale"],
                    experience_quality=maintenance_result["experience_quality"],
                )
                summary = maintenance_result["summary"]
                maintenance_at = generated_at.astimezone(UTC)
                maintenance_artifact = cls._stage_maintenance_run_artifact(
                    summary=summary,
                    maintenance_result=maintenance_result,
                )
                cls._write_run_ledger_artifact(
                    artifact=maintenance_artifact,
                    when=maintenance_at,
                )
                await CodeRuntimeService.record_run_ledger_artifact(
                    db,
                    workspace_id=workspace.id,
                    artifact=maintenance_artifact,
                    when=maintenance_at,
                )
                await CodeEventService.append_event(
                    db,
                    session_id=latest_session.id,
                    event_type="code.automation.maintenance",
                    payload={
                        "job_id": job.id,
                        "summary": summary,
                        "next_autonomy_mode": maintenance_result["next_autonomy_mode"],
                        "next_autonomy_objective": maintenance_result["next_autonomy_objective"],
                        "report_markdown_path": maintenance_result["report_markdown_path"],
                    },
                )
                seeded_task = await cls._seed_autonomy_task_if_idle(
                    db,
                    workspace=workspace,
                    user=user,
                    session=latest_session,
                    runtime=runtime,
                    maintenance_result=maintenance_result,
                    seeded_at=maintenance_at,
                )
                if seeded_task is not None:
                    summary = f"{summary} Seeded task #{seeded_task.id} for executor follow-up."
                await CodeRuntimeService.mark_job_run(db, job=job, status="completed")
                await CodeRuntimeService.record_policy_signal(
                    db,
                    workspace_id=workspace.id,
                    category="maintenance_job",
                    outcome="completed",
                )
            else:
                if latest_session is None:
                    latest_session = await session_service.create_session(
                        db,
                        user=user,
                        acquire_write_lease=False,
                    )
                session_used = latest_session
                prompt = job.prompt_template or "[system automation] Run the scheduled BOS Code task."
                await session_service.create_turn(db, session=latest_session, user_message=prompt)
                await CodeMemoryService.refresh_snapshot(db, session=latest_session, force=False)
                summary = "Automation created a scheduled BOS Code turn."
                await CodeRuntimeService.mark_job_run(db, job=job, status="completed")
                await CodeRuntimeService.record_policy_signal(
                    db,
                    workspace_id=workspace.id,
                    category="scheduled_job",
                    outcome="completed",
                )
        except Exception as exc:
            await CodeRuntimeService.mark_job_run(db, job=job, status="failed", error=str(exc))
            await CodeRuntimeService.record_policy_signal(
                db,
                workspace_id=workspace.id,
                category="job_failure",
                outcome=job.job_type,
            )
            raise

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            lane="tasking",
            event_name="automation.executed",
            status=job.job_type,
            summary=summary,
            payload={"job_id": job.id, "job_name": job.name, "session_id": session_used.id if session_used else None},
        )
        await db.flush()
        return job, session_used, summary
