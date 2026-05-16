"""
Minimal task and worker orchestration foundation for BOS Code v3.
"""

from datetime import UTC, datetime
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.code import (
    ACTION_BEGIN_REVIEW,
    ACTION_MARK_ARCHITECT_BLOCKED,
    ACTION_MARK_ARCHITECT_READY,
    ACTION_MARK_EXECUTOR_BLOCKED,
    ACTION_MARK_EXECUTOR_READY,
    ACTION_MARK_REVIEWER_BLOCKED,
    ACTION_MARK_REVIEWER_READY,
    LANE_EVENT_COMPLETED,
    LANE_EVENT_PROGRESSED,
    LANE_EVENT_REVIEW_ACCEPTED,
    LANE_EVENT_REVIEW_REJECTED,
    LANE_EVENT_REVIEW_REQUESTED,
    LANE_EVENT_STARTED,
    LANE_EVENT_TASK_COMPLETED,
    LANE_EVENT_TASK_CREATED,
    LANE_EVENT_TASK_FAILED,
    LANE_EVENT_TASK_ROUTED,
    REVIEW_DECISION_ACCEPT,
    TASK_STATUS_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_CREATED,
    TASK_STATUS_IN_REVIEW,
    TASK_STATUS_REVIEW_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_VERIFICATION_PENDING,
    WORKER_LANE_ARCHITECT,
    WORKER_LANE_EXECUTOR,
    WORKER_LANE_REVIEWER,
    WORKER_STATUS_ASSIGNED,
    WORKER_STATUS_BLOCKED,
    WORKER_STATUS_COMPLETED,
    WORKER_STATUS_READY,
    WORKER_STATUS_RUNNING,
    WORKER_STATUS_WAITING_REVIEW,
    control_action_policy,
)
from app.models import CodeSession, CodeTask, CodeWorker, CodeWorkspace, User
from app.services.brain_runtime import RunLedgerArtifact, apply_run_ledger_artifact
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.worker_event_service import CodeWorkerEventService


class CodeTaskService:
    RUN_LEDGER_PATH = Path(__file__).resolve().parents[4] / ".agents" / "runtime" / "run-ledger.md"
    VALID_WORKER_STATUSES = {
        "idle",
        "spawning",
        "trust_required",
        "ready_for_prompt",
        "prompt_accepted",
        "ready",
        "assigned",
        "running",
        "waiting_review",
        "blocked",
        "failed",
        "completed",
    }

    VALID_WORKER_LANES = {
        WORKER_LANE_ARCHITECT,
        WORKER_LANE_EXECUTOR,
        WORKER_LANE_REVIEWER,
    }

    @staticmethod
    def _write_run_ledger_artifact(
        *,
        artifact: RunLedgerArtifact,
        when: datetime,
    ) -> str:
        CodeTaskService.RUN_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = CodeTaskService.RUN_LEDGER_PATH.read_text(encoding="utf-8") if CodeTaskService.RUN_LEDGER_PATH.exists() else ""
        updated = apply_run_ledger_artifact(existing, artifact, when=when)
        CodeTaskService.RUN_LEDGER_PATH.write_text(updated, encoding="utf-8")
        return updated

    @staticmethod
    def _task_target_from_text(task: CodeTask) -> tuple[str, str | None, str]:
        text = " ".join(filter(None, [task.title, task.objective, task.scope])).lower()
        batch_match = re.search(r"\bbatch\s+(\d+)\b", text)
        audit_match = re.search(r"\baudit\s+packet\s+(\d+)\b", text)

        if audit_match:
            target_id = audit_match.group(1)
            return ("audit_packet", target_id, f"/bos/console?auditPacketId={target_id}")

        if batch_match and "signal" in text:
            target_id = batch_match.group(1)
            return ("signal_lab", target_id, f"/bos/signal-lab?batchId={target_id}")

        if batch_match:
            target_id = batch_match.group(1)
            return ("batch", target_id, f"/batches/{target_id}")

        if "release" in text or "audit" in text:
            return ("release", None, "/release")

        if "brain" in text or "memory" in text or "reflection" in text:
            return ("brain", None, "/bos/brain")

        return ("orchestrator", str(task.workspace_id), "/bos/orchestrator")

    @classmethod
    def _stage_task_run_artifact(
        cls,
        *,
        task: CodeTask,
        phase: str,
        outcome: str,
        verification: str,
        remaining_risk: str,
        next_step: str,
    ) -> RunLedgerArtifact:
        target_surface, target_id, target_route = cls._task_target_from_text(task)
        return RunLedgerArtifact(
            slice=f"Task #{task.id}: {task.title}",
            outcome=outcome,
            verification=verification,
            remaining_risk=remaining_risk,
            next_step=f"{phase}: {next_step}",
            target_surface=target_surface,
            target_id=target_id,
            target_route=target_route,
        )

    @staticmethod
    def _build_task_packet(
        *,
        objective: str,
        scope: str | None,
        acceptance_criteria: list[str] | None,
        task_packet: dict | None,
    ) -> dict:
        packet = dict(task_packet or {})
        packet.setdefault("objective", objective)
        packet.setdefault("scope", scope or "code/orchestration")
        packet.setdefault("repo", "canonical BOS repository worktree")
        packet.setdefault("branch_policy", "Use the active session branch and refresh branch posture before merge decisions.")
        packet.setdefault(
            "acceptance_tests",
            [
                "Refresh branch posture before broad verification.",
                "Run the relevant verification gate before treating the task as complete.",
            ],
        )
        packet.setdefault("commit_policy", "Keep changes scoped and reviewer-friendly before handoff.")
        packet.setdefault(
            "reporting_contract",
            "Return a concise implementation summary, changed surfaces, verification posture, and next review action.",
        )
        packet.setdefault(
            "escalation_policy",
            "Escalate only when the task is blocked by ambiguous scope, missing access, or unsafe/destructive uncertainty.",
        )
        if acceptance_criteria:
            tests = packet.get("acceptance_tests")
            if isinstance(tests, list):
                packet["acceptance_tests"] = [
                    *(item for item in tests if isinstance(item, str) and item.strip()),
                    *[item for item in acceptance_criteria if item and item not in tests],
                ]
        return packet

    @staticmethod
    def _draft_acceptance_criteria(task: CodeTask) -> list[str]:
        scope_hint = task.scope or "code/orchestration"
        drafts = [
            f"Architect validates scope for {scope_hint}.",
            "Executor implements the requested change and captures the handoff context.",
            "Reviewer accepts the implementation or returns a concrete rejection reason.",
            "Verification gate passes before the task can complete.",
        ]
        objective = (task.objective or "").lower()
        if "event" in objective or "stream" in objective:
            drafts.insert(1, "Implementation preserves replayable event semantics and lane visibility.")
        if "schema" in objective or "contract" in objective:
            drafts.insert(1, "API or event contracts remain backward compatible for the cockpit.")
        if "frontend" in objective or "panel" in objective or "ui" in objective:
            drafts.insert(1, "UI state stays aligned with orchestration snapshot and lane event flow.")
        if "backend" in objective or "api" in objective or "router" in objective:
            drafts.insert(1, "Backend routes and orchestration policies stay consistent under replay.")
        return drafts

    @staticmethod
    def _suggest_route(task: CodeTask) -> str:
        objective = (task.objective or "").lower()
        scope = (task.scope or "").lower()
        if any(keyword in objective or keyword in scope for keyword in ("review", "audit")):
            return WORKER_LANE_REVIEWER
        return WORKER_LANE_EXECUTOR

    @staticmethod
    async def _get_task(db: AsyncSession, *, workspace_id: int, task_id: int) -> CodeTask | None:
        task_result = await db.execute(
            select(CodeTask).where(
                CodeTask.workspace_id == workspace_id,
                CodeTask.id == task_id,
            )
        )
        return task_result.scalar_one_or_none()

    @staticmethod
    async def _get_worker(db: AsyncSession, *, workspace_id: int, worker_name: str) -> CodeWorker | None:
        worker_result = await db.execute(
            select(CodeWorker).where(
                CodeWorker.workspace_id == workspace_id,
                CodeWorker.worker_name == worker_name,
            )
            .order_by(CodeWorker.created_at.asc(), CodeWorker.id.asc())
        )
        return worker_result.scalars().first()

    @staticmethod
    async def list_tasks(db: AsyncSession, *, workspace_id: int) -> list[CodeTask]:
        result = await db.execute(
            select(CodeTask).where(CodeTask.workspace_id == workspace_id).order_by(CodeTask.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_tasks_for_session(db: AsyncSession, *, session_id: int) -> list[CodeTask]:
        result = await db.execute(
            select(CodeTask).where(CodeTask.session_id == session_id).order_by(CodeTask.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_task(
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        user: User,
        session_id: int | None,
        title: str,
        objective: str,
        scope: str | None,
        acceptance_criteria: list[str] | None = None,
        task_packet: dict | None = None,
    ) -> CodeTask:
        await CodeTaskService.ensure_default_workers(db, workspace=workspace)
        normalized_task_packet = CodeTaskService._build_task_packet(
            objective=objective,
            scope=scope,
            acceptance_criteria=acceptance_criteria,
            task_packet=task_packet,
        )
        task = CodeTask(
            tenant_id=user.tenant_id,
            user_id=user.id,
            workspace_id=workspace.id,
            session_id=session_id,
            title=title,
            objective=objective,
            scope=scope,
            task_packet=normalized_task_packet,
            task_status=TASK_STATUS_CREATED,
            priority="normal",
            acceptance_criteria=acceptance_criteria or [],
        )
        db.add(task)
        await db.flush()
        architect = await CodeTaskService._get_worker(db, workspace_id=workspace.id, worker_name=WORKER_LANE_ARCHITECT)
        if architect is not None:
            architect.task_id = task.id
            architect.worker_status = WORKER_STATUS_RUNNING
            architect.last_event_summary = f"Planning task #{task.id}: {task.title}"
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            worker_id=None,
            lane="tasking",
            event_name=LANE_EVENT_TASK_CREATED,
            status=TASK_STATUS_CREATED,
            summary=f"Task #{task.id} created: {task.title}",
            payload={
                "task_id": task.id,
                "title": task.title,
                "acceptance_criteria": acceptance_criteria or [],
                "phase": "tasking",
                "headline": f"Task #{task.id} opened with a structured packet.",
                "recommended_action": "Let architect validate the route before executor work begins.",
                "task_packet": normalized_task_packet,
            },
        )
        if architect is not None:
            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace.id,
                task_id=task.id,
                worker_id=architect.id,
                lane=WORKER_LANE_ARCHITECT,
                event_name=LANE_EVENT_STARTED,
                status=WORKER_STATUS_RUNNING,
                summary=architect.last_event_summary,
                payload={"task_id": task.id, "worker_name": WORKER_LANE_ARCHITECT},
            )
        return task

    @staticmethod
    async def assign_worker(
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        worker_name: str,
    ) -> CodeWorker:
        worker = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=worker_name)
        if worker is None:
            raise ValueError("worker_not_found")

        task = await CodeTaskService._get_task(db, workspace_id=workspace_id, task_id=task_id)
        if task is None:
            raise ValueError("task_not_found")

        worker.task_id = task.id
        worker.worker_status = WORKER_STATUS_RUNNING
        worker.last_event_summary = f"Assigned to task #{task.id}: {task.title}"
        task.task_status = TASK_STATUS_RUNNING
        await db.flush()
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=worker.id,
            lane=worker.worker_name,
            event_name=LANE_EVENT_TASK_ROUTED,
            status=TASK_STATUS_RUNNING,
            summary=worker.last_event_summary,
            payload={"worker_name": worker.worker_name, "task_id": task.id, "lane": worker.worker_name},
        )
        return worker

    @staticmethod
    async def update_worker_status(
        db: AsyncSession,
        *,
        workspace_id: int,
        worker_name: str,
        worker_status: str,
        last_error: str | None = None,
        last_event_summary: str | None = None,
        lane: str | None = None,
        event_name: str | None = None,
        payload: dict | None = None,
    ) -> CodeWorker:
        if worker_status not in CodeTaskService.VALID_WORKER_STATUSES:
            raise ValueError("worker_status_invalid")

        worker_result = await db.execute(
            select(CodeWorker).where(
                CodeWorker.workspace_id == workspace_id,
                CodeWorker.worker_name == worker_name,
            )
        )
        worker = worker_result.scalar_one_or_none()
        if worker is None:
            raise ValueError("worker_not_found")

        if worker.worker_name not in CodeTaskService.VALID_WORKER_LANES:
            raise ValueError("worker_lane_invalid")

        worker.worker_status = worker_status
        worker.last_error = last_error
        if last_event_summary is not None:
            worker.last_event_summary = last_event_summary

        if worker.task_id is not None:
            task_result = await db.execute(select(CodeTask).where(CodeTask.id == worker.task_id))
            task = task_result.scalar_one_or_none()
            if task is not None:
                task.task_status = CodeTaskService._derive_task_status_from_worker_update(
                    worker_name=worker.worker_name,
                    worker_status=worker_status,
                    current_task_status=task.task_status,
                )
        await db.flush()
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=worker.task_id,
            worker_id=worker.id,
            lane=lane or worker.worker_name,
            event_name=event_name or LANE_EVENT_PROGRESSED,
            status=worker_status,
            summary=worker.last_event_summary,
            payload={
                "worker_name": worker.worker_name,
                "worker_status": worker_status,
                **(payload or {}),
            },
        )
        return worker

    @staticmethod
    def _derive_task_status_from_worker_update(
        *,
        worker_name: str,
        worker_status: str,
        current_task_status: str,
    ) -> str:
        if worker_status in {"failed", "blocked"}:
            return TASK_STATUS_BLOCKED

        if worker_name == WORKER_LANE_REVIEWER:
            if worker_status == WORKER_STATUS_RUNNING and current_task_status == TASK_STATUS_REVIEW_PENDING:
                return TASK_STATUS_IN_REVIEW
            if worker_status == WORKER_STATUS_READY and current_task_status == TASK_STATUS_IN_REVIEW:
                return TASK_STATUS_REVIEW_PENDING
            return current_task_status

        if worker_name == WORKER_LANE_EXECUTOR:
            if worker_status == WORKER_STATUS_READY and current_task_status == TASK_STATUS_BLOCKED:
                return TASK_STATUS_RUNNING
            return current_task_status

        if worker_name == WORKER_LANE_ARCHITECT:
            if worker_status == WORKER_STATUS_READY and current_task_status == TASK_STATUS_BLOCKED:
                return TASK_STATUS_CREATED
            return current_task_status

        return current_task_status

    @staticmethod
    def allowed_actions_for_worker(
        *,
        worker_name: str,
        worker_status: str,
        task_status: str | None,
    ) -> list[str]:
        actions: list[str] = []

        if worker_name == WORKER_LANE_ARCHITECT:
            if worker_status != "blocked":
                actions.append(ACTION_MARK_ARCHITECT_BLOCKED)
            if worker_status != WORKER_STATUS_READY:
                actions.append(ACTION_MARK_ARCHITECT_READY)
        elif worker_name == WORKER_LANE_EXECUTOR:
            if worker_status != "blocked":
                actions.append(ACTION_MARK_EXECUTOR_BLOCKED)
            if worker_status != WORKER_STATUS_READY:
                actions.append(ACTION_MARK_EXECUTOR_READY)
        elif worker_name == WORKER_LANE_REVIEWER:
            if worker_status != "blocked":
                actions.append(ACTION_MARK_REVIEWER_BLOCKED)
            if worker_status != WORKER_STATUS_READY:
                actions.append(ACTION_MARK_REVIEWER_READY)

        if (
            worker_name == WORKER_LANE_REVIEWER
            and worker_status == WORKER_STATUS_ASSIGNED
            and task_status == TASK_STATUS_REVIEW_PENDING
        ):
            actions.append(ACTION_BEGIN_REVIEW)

        return actions

    @staticmethod
    def allowed_action_policies_for_worker(
        *,
        worker_name: str,
        worker_status: str,
        task_status: str | None,
    ) -> dict[str, str]:
        actions = CodeTaskService.allowed_actions_for_worker(
            worker_name=worker_name,
            worker_status=worker_status,
            task_status=task_status,
        )
        return {action: control_action_policy(action) for action in actions}

    @staticmethod
    async def request_review(
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        summary: str | None = None,
        payload: dict | None = None,
    ) -> tuple[CodeTask, CodeWorker, CodeWorker]:
        task = await CodeTaskService._get_task(db, workspace_id=workspace_id, task_id=task_id)
        if task is None:
            raise ValueError("task_not_found")

        executor = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_EXECUTOR)
        reviewer = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_REVIEWER)
        if executor is None or reviewer is None:
            raise ValueError("worker_not_found")

        executor.task_id = task.id
        executor.worker_status = WORKER_STATUS_WAITING_REVIEW
        executor.last_event_summary = summary or f"Task #{task.id} sent to reviewer."

        reviewer.task_id = task.id
        reviewer.worker_status = WORKER_STATUS_ASSIGNED
        reviewer.last_event_summary = summary or f"Review requested for task #{task.id}: {task.title}"

        task.task_status = TASK_STATUS_REVIEW_PENDING
        await db.flush()

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=executor.id,
            lane=WORKER_LANE_EXECUTOR,
            event_name=LANE_EVENT_REVIEW_REQUESTED,
            status=WORKER_STATUS_WAITING_REVIEW,
            summary=executor.last_event_summary,
            payload={
                "task_id": task.id,
                "worker_name": WORKER_LANE_EXECUTOR,
                "phase": "review",
                "headline": f"Review requested for task #{task.id}.",
                "recommended_action": "Keep the executor handoff stable until reviewer pickup begins.",
                **(payload or {}),
            },
        )
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=reviewer.id,
            lane=WORKER_LANE_REVIEWER,
            event_name=LANE_EVENT_STARTED,
            status=WORKER_STATUS_ASSIGNED,
            summary=reviewer.last_event_summary,
            payload={
                "task_id": task.id,
                "worker_name": WORKER_LANE_REVIEWER,
                "phase": "review",
                "headline": f"Reviewer lane picked up task #{task.id}.",
                "recommended_action": "Inspect the reviewer-ready packet before making a decision.",
                **(payload or {}),
            },
        )
        return task, executor, reviewer

    @staticmethod
    async def architect_route_task(
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        acceptance_criteria: list[str] | None = None,
        summary: str | None = None,
        route_to: str = "executor",
        payload: dict | None = None,
    ) -> tuple[CodeTask, CodeWorker, CodeWorker]:
        task = await CodeTaskService._get_task(db, workspace_id=workspace_id, task_id=task_id)
        if task is None:
            raise ValueError("task_not_found")

        architect = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_ARCHITECT)
        target_worker = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=route_to)
        if architect is None or target_worker is None:
            raise ValueError("worker_not_found")

        task.acceptance_criteria = acceptance_criteria or task.acceptance_criteria or []
        task.task_status = TASK_STATUS_RUNNING

        architect.task_id = None
        architect.worker_status = WORKER_STATUS_READY
        architect.last_event_summary = summary or f"Planned task #{task.id} and routed to {route_to}."

        target_worker.task_id = task.id
        target_worker.worker_status = WORKER_STATUS_RUNNING
        target_worker.last_event_summary = f"Accepted routed task #{task.id}: {task.title}"
        await db.flush()

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=architect.id,
            lane=WORKER_LANE_ARCHITECT,
            event_name=LANE_EVENT_COMPLETED,
            status=WORKER_STATUS_READY,
            summary=architect.last_event_summary,
            payload={
                "task_id": task.id,
                "acceptance_criteria": task.acceptance_criteria or [],
                "route_to": route_to,
                **(payload or {}),
            },
        )
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=target_worker.id,
            lane=route_to,
            event_name=LANE_EVENT_TASK_ROUTED,
            status=TASK_STATUS_RUNNING,
            summary=target_worker.last_event_summary,
            payload={
                "task_id": task.id,
                "worker_name": route_to,
                "acceptance_criteria": task.acceptance_criteria or [],
                **(payload or {}),
            },
        )
        return task, architect, target_worker

    @staticmethod
    async def architect_plan_task(
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        regenerate: bool = False,
        summary: str | None = None,
        payload: dict | None = None,
    ) -> tuple[CodeTask, CodeWorker, str, dict]:
        task = await CodeTaskService._get_task(db, workspace_id=workspace_id, task_id=task_id)
        if task is None:
            raise ValueError("task_not_found")

        architect = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_ARCHITECT)
        if architect is None:
            raise ValueError("worker_not_found")

        if regenerate or not task.acceptance_criteria:
            task.acceptance_criteria = CodeTaskService._draft_acceptance_criteria(task)
        route_suggestion = CodeTaskService._suggest_route(task)
        plan_payload = {
            "route_suggestion": route_suggestion,
            "acceptance_criteria": task.acceptance_criteria or [],
        }

        architect.task_id = task.id
        architect.worker_status = WORKER_STATUS_RUNNING
        architect.last_event_summary = summary or f"Architect drafted plan for task #{task.id}: {task.title}"
        await db.flush()

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=architect.id,
            lane=WORKER_LANE_ARCHITECT,
            event_name=LANE_EVENT_PROGRESSED,
            status=WORKER_STATUS_RUNNING,
            summary=architect.last_event_summary,
            payload={
                "task_id": task.id,
                **plan_payload,
                **(payload or {}),
            },
        )
        return task, architect, route_suggestion, plan_payload

    @staticmethod
    async def submit_review_decision(
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        decision: str,
        summary: str | None = None,
        reason: str | None = None,
        reason_code: str | None = None,
        checklist: list[str] | None = None,
        payload: dict | None = None,
    ) -> tuple[CodeTask, CodeWorker, CodeWorker]:
        task = await CodeTaskService._get_task(db, workspace_id=workspace_id, task_id=task_id)
        if task is None:
            raise ValueError("task_not_found")

        executor = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_EXECUTOR)
        reviewer = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_REVIEWER)
        if executor is None or reviewer is None:
            raise ValueError("worker_not_found")

        if decision == REVIEW_DECISION_ACCEPT:
            reviewer.worker_status = WORKER_STATUS_RUNNING if task.task_status == TASK_STATUS_REVIEW_PENDING else reviewer.worker_status
            reviewer.worker_status = WORKER_STATUS_COMPLETED
            reviewer.last_event_summary = summary or f"Review accepted for task #{task.id}: {task.title}"
            executor.worker_status = WORKER_STATUS_READY
            executor.last_event_summary = "Execution accepted by reviewer."
            task.task_status = TASK_STATUS_VERIFICATION_PENDING

            await db.flush()
            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace_id,
                task_id=task.id,
                worker_id=reviewer.id,
                lane=WORKER_LANE_REVIEWER,
                event_name=LANE_EVENT_REVIEW_ACCEPTED,
                status=TASK_STATUS_VERIFICATION_PENDING,
                summary=reviewer.last_event_summary,
                payload={
                    "task_id": task.id,
                    "decision": decision,
                    "reason": reason,
                    "reason_code": reason_code,
                    "checklist": checklist or [],
                    "phase": "review",
                    "headline": f"Review accepted for task #{task.id}.",
                    "recommended_actions": [
                        "Run the verification gate before treating the task as complete.",
                        "Keep the acceptance rationale visible until verification passes.",
                    ],
                    **(payload or {}),
                },
            )
            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace_id,
                task_id=task.id,
                worker_id=reviewer.id,
                lane="tasking",
                event_name=LANE_EVENT_PROGRESSED,
                status=TASK_STATUS_VERIFICATION_PENDING,
                summary=f"Task #{task.id} accepted by reviewer and waiting on verification gate.",
                payload={
                    "task_id": task.id,
                    "decision": decision,
                    "phase": "verification",
                    "headline": f"Task #{task.id} is waiting on verification.",
                    "recommended_action": "Run or confirm verification before preparing merge decisions.",
                    **(payload or {}),
                },
            )
            accepted_artifact = CodeTaskService._stage_task_run_artifact(
                task=task,
                phase="review",
                outcome="Reviewer accepted the implementation and moved the task into verification.",
                verification="Reviewer decision recorded in BOS Code task orchestration.",
                remaining_risk="Verification still needs to pass before the task can be treated as complete.",
                next_step="Run or confirm the verification gate before preparing merge decisions.",
            )
            accepted_at = datetime.now(UTC)
            CodeTaskService._write_run_ledger_artifact(
                artifact=accepted_artifact,
                when=accepted_at,
            )
            await CodeRuntimeService.record_run_ledger_artifact(
                db,
                workspace_id=workspace_id,
                artifact=accepted_artifact,
                when=accepted_at,
            )
            return task, executor, reviewer

        reviewer.worker_status = WORKER_STATUS_READY
        reviewer.last_event_summary = summary or f"Review rejected for task #{task.id}: {task.title}"
        executor.worker_status = WORKER_STATUS_RUNNING
        executor.task_id = task.id
        executor.last_event_summary = reason or "Reviewer requested changes."
        task.task_status = TASK_STATUS_RUNNING

        await db.flush()
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=reviewer.id,
            lane=WORKER_LANE_REVIEWER,
            event_name=LANE_EVENT_REVIEW_REJECTED,
            status=TASK_STATUS_BLOCKED,
            summary=reviewer.last_event_summary,
            payload={
                "task_id": task.id,
                "decision": decision,
                "reason": reason,
                "reason_code": reason_code,
                "checklist": checklist or [],
                "phase": "review",
                "failure_class": "tool_runtime",
                "headline": f"Reviewer requested changes for task #{task.id}.",
                "recommended_actions": [
                    "Inspect the reviewer reason code and checklist before reworking the task.",
                    "Route the task back through executor and keep review history visible.",
                ],
                **(payload or {}),
            },
        )
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace_id,
            task_id=task.id,
            worker_id=executor.id,
            lane=WORKER_LANE_EXECUTOR,
            event_name=LANE_EVENT_PROGRESSED,
            status=TASK_STATUS_RUNNING,
            summary=executor.last_event_summary,
            payload={
                "task_id": task.id,
                "rework_required": True,
                "reason": reason,
                "phase": "execution",
                "headline": f"Executor lane resumed for task #{task.id} after review changes.",
                "recommended_action": "Address reviewer feedback before requesting review again.",
                **(payload or {}),
            },
        )
        rejected_artifact = CodeTaskService._stage_task_run_artifact(
            task=task,
            phase="review",
            outcome="Reviewer rejected the implementation and sent the task back to execution.",
            verification="Reviewer rejection recorded with reason and checklist in BOS Code task orchestration.",
            remaining_risk=reason or "Reviewer feedback must be addressed before the task can return to verification.",
            next_step="Address reviewer feedback, then request review again.",
        )
        rejected_at = datetime.now(UTC)
        CodeTaskService._write_run_ledger_artifact(
            artifact=rejected_artifact,
            when=rejected_at,
        )
        await CodeRuntimeService.record_run_ledger_artifact(
            db,
            workspace_id=workspace_id,
            artifact=rejected_artifact,
            when=rejected_at,
        )
        return task, executor, reviewer

    @staticmethod
    async def apply_verification_result(
        db: AsyncSession,
        *,
        workspace_id: int,
        session_id: int,
        verification_status: str,
    ) -> list[CodeTask]:
        tasks = await CodeTaskService.list_tasks_for_session(db, session_id=session_id)
        pending_tasks = [task for task in tasks if task.workspace_id == workspace_id and task.task_status == "verification_pending"]
        if not pending_tasks:
            return []

        updated: list[CodeTask] = []
        for task in pending_tasks:
            executor = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_EXECUTOR)
            reviewer = await CodeTaskService._get_worker(db, workspace_id=workspace_id, worker_name=WORKER_LANE_REVIEWER)
            if verification_status == "passed":
                task.task_status = TASK_STATUS_COMPLETED
                event_name = LANE_EVENT_TASK_COMPLETED
                status = TASK_STATUS_COMPLETED
                summary = f"Task #{task.id} completed after verification passed."
                payload = {
                    "task_id": task.id,
                    "session_id": session_id,
                    "verification_status": verification_status,
                    "phase": "verification",
                    "headline": f"Task #{task.id} cleared verification.",
                    "recommended_actions": [
                        "Treat the task as complete unless new evidence appears.",
                        "Move into merge-readiness inspection if the branch posture is healthy.",
                    ],
                    "completion_checklist": [
                        "Verification gate passed.",
                        "Reviewer approval already landed.",
                        "Task can be treated as complete unless new evidence appears.",
                    ],
                }
                if executor is not None:
                    executor.worker_status = WORKER_STATUS_READY
                    executor.task_id = None
                    executor.last_event_summary = f"Execution lane reset after task #{task.id} completed."
                if reviewer is not None:
                    reviewer.worker_status = WORKER_STATUS_READY
                    reviewer.task_id = None
                    reviewer.last_event_summary = f"Review lane reset after task #{task.id} completed."
            elif verification_status == "failed":
                task.task_status = TASK_STATUS_BLOCKED
                event_name = LANE_EVENT_TASK_FAILED
                status = TASK_STATUS_BLOCKED
                summary = f"Task #{task.id} blocked because verification failed."
                payload = {
                    "task_id": task.id,
                    "session_id": session_id,
                    "verification_status": verification_status,
                    "phase": "verification",
                    "failure_class": "test",
                    "headline": f"Verification blocked task #{task.id}.",
                    "recommended_actions": [
                        "Inspect failing verification output.",
                        "Route corrective work back through executor before re-review.",
                    ],
                    "recovery_checklist": [
                        "Inspect failing verification output.",
                        "Route corrective work back through executor before re-review.",
                        "Do not mark the task complete until verification passes.",
                    ],
                }
                if executor is not None:
                    executor.worker_status = WORKER_STATUS_BLOCKED
                    executor.task_id = task.id
                    executor.last_event_summary = f"Execution lane blocked by verification for task #{task.id}."
                if reviewer is not None:
                    reviewer.worker_status = WORKER_STATUS_READY
                    reviewer.task_id = None
                    reviewer.last_event_summary = f"Review lane parked while task #{task.id} is in recovery."
            else:
                continue

            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace_id,
                task_id=task.id,
                worker_id=None,
                lane="tasking",
                event_name=event_name,
                status=status,
                summary=summary,
                payload=payload,
            )
            if verification_status == "passed":
                verification_artifact = CodeTaskService._stage_task_run_artifact(
                    task=task,
                    phase="verification",
                    outcome="Verification passed and the task is now complete.",
                    verification="Verification gate status changed to passed in BOS Code task orchestration.",
                    remaining_risk="Only branch posture or new evidence should block merge-oriented follow-up now.",
                    next_step="Treat the task as complete and inspect merge readiness.",
                )
            else:
                verification_artifact = CodeTaskService._stage_task_run_artifact(
                    task=task,
                    phase="verification",
                    outcome="Verification failed and the task is blocked for corrective work.",
                    verification="Verification gate status changed to failed in BOS Code task orchestration.",
                    remaining_risk="Execution must address the failing verification output before re-review.",
                    next_step="Inspect failing verification output and route corrective work back through execution.",
                )
            verification_at = datetime.now(UTC)
            CodeTaskService._write_run_ledger_artifact(
                artifact=verification_artifact,
                when=verification_at,
            )
            await CodeRuntimeService.record_run_ledger_artifact(
                db,
                workspace_id=workspace_id,
                artifact=verification_artifact,
                when=verification_at,
            )
            if verification_status == "failed":
                session = None
                if task.session_id is not None:
                    session_result = await db.execute(select(CodeSession).where(CodeSession.id == task.session_id))
                    session = session_result.scalar_one_or_none()
                user_result = await db.execute(select(User).where(User.id == task.user_id))
                user = user_result.scalar_one_or_none()
                workspace_result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.id == workspace_id))
                workspace = workspace_result.scalar_one_or_none()
                if workspace is not None and user is not None:
                    from app.services.code.recovery_loop_service import CodeRecoveryLoopService

                    recovery_task = await CodeRecoveryLoopService.ensure_recovery_task(
                        db,
                        workspace=workspace,
                        user=user,
                        session=session,
                        failure_class="verification_failed",
                        origin="verification_failure",
                        summary=summary,
                        checklist=payload.get("recovery_checklist", []),
                        source_task_id=task.id,
                    )
                    await CodeRecoveryLoopService.ensure_postmortem_reflection(
                        db,
                        workspace=workspace,
                        session=session,
                        user=user,
                        trigger_source="verification_failure",
                        task_id=recovery_task.id,
                    )
            updated.append(task)

        await db.flush()
        return updated

    @staticmethod
    async def list_workers(db: AsyncSession, *, workspace_id: int) -> list[CodeWorker]:
        result = await db.execute(
            select(CodeWorker).where(CodeWorker.workspace_id == workspace_id).order_by(CodeWorker.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def ensure_default_workers(db: AsyncSession, *, workspace: CodeWorkspace) -> list[CodeWorker]:
        existing = await CodeTaskService.list_workers(db, workspace_id=workspace.id)
        if existing:
            return existing

        workers = [
            CodeWorker(
                workspace_id=workspace.id,
                worker_name=WORKER_LANE_ARCHITECT,
                worker_role="planner",
                worker_status="ready_for_prompt",
                last_event_summary="Planner lane is ready for the next prompt.",
            ),
            CodeWorker(
                workspace_id=workspace.id,
                worker_name=WORKER_LANE_EXECUTOR,
                worker_role="implementer",
                worker_status="ready_for_prompt",
                last_event_summary="Execution lane is ready for the next prompt.",
            ),
            CodeWorker(
                workspace_id=workspace.id,
                worker_name=WORKER_LANE_REVIEWER,
                worker_role="reviewer",
                worker_status="ready_for_prompt",
                last_event_summary="Review lane is ready for the next prompt.",
            ),
        ]
        db.add_all(workers)
        await db.flush()
        for worker in workers:
            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace.id,
                task_id=None,
                worker_id=worker.id,
                lane=worker.worker_name,
                event_name=LANE_EVENT_STARTED,
                status=worker.worker_status,
                summary=worker.last_event_summary,
                payload={
                    "worker_name": worker.worker_name,
                    "worker_role": worker.worker_role,
                    "phase": "startup",
                    "headline": worker.last_event_summary,
                },
            )
        return workers
