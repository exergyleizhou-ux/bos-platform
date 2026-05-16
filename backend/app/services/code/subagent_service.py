"""
Background BOS Code subagent runs.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy import select

from app.code import (
    TASK_STATUS_BLOCKED,
    TASK_STATUS_REVIEW_PENDING,
    WORKER_LANE_REVIEWER,
    WORKER_STATUS_ASSIGNED,
    WORKER_STATUS_BLOCKED,
    WORKER_STATUS_WAITING_REVIEW,
)
from app.config import get_settings
from app.models import CodeSession, CodeSubagentRun, CodeTask, CodeWorker, CodeWorkspace, User
from app.services.code.event_service import CodeEventService
from app.services.code.providers import OpenAICodexProvider, ProviderRequest
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.skill_service import CodeSkillService
from app.services.code.worker_event_service import CodeWorkerEventService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()


class CodeSubagentService:
    MAX_PARALLEL_SLICES = 3

    def __init__(self) -> None:
        self.provider = OpenAICodexProvider()

    @staticmethod
    def _celery_broker_reachable() -> bool:
        broker_url = (settings.CELERY_BROKER_URL or "").strip()
        if not broker_url:
            return False

        parsed = urlparse(broker_url)
        if parsed.scheme not in {"redis", "rediss"}:
            return False

        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except OSError:
            return False

    async def _maybe_aggregate_task_runs(
        self,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        task: CodeTask | None,
        session: CodeSession | None,
        worker: CodeWorker | None,
    ) -> None:
        if task is None:
            return

        runs_result = await db.execute(
            select(CodeSubagentRun)
            .where(CodeSubagentRun.task_id == task.id)
            .order_by(CodeSubagentRun.id.asc())
        )
        runs = list(runs_result.scalars().all())
        if not runs:
            return
        if any(run.run_status in {"pending", "running"} for run in runs):
            return

        completed = [run for run in runs if run.run_status == "completed"]
        failed = [run for run in runs if run.run_status == "failed"]
        summary_parts = [run.result_summary for run in runs if run.result_summary]
        handoff_packet = {
            "task_id": task.id,
            "completed_runs": len(completed),
            "failed_runs": len(failed),
            "subagent_run_ids": [run.id for run in runs],
            "slice_summaries": [
                {
                    "run_id": run.id,
                    "criterion": (run.metadata_json or {}).get("criterion"),
                    "status": run.run_status,
                    "summary": run.result_summary,
                }
                for run in runs
            ],
        }
        handoff_packet["review_checklist"] = [
            "Confirm each acceptance criterion has a completed slice summary.",
            "Verify no failed subagent slices remain unresolved.",
            "Inspect the aggregate executor summary before review acceptance.",
        ]
        aggregate_summary = (
            f"Executor subagents finished for task #{task.id}: "
            f"{len(completed)} completed, {len(failed)} failed."
        )
        if summary_parts:
            aggregate_summary += " " + " | ".join(summary_parts[:3])

        if worker is not None:
            worker.last_event_summary = aggregate_summary

        if worker is not None and task is not None and not failed and task.task_status == "running":
            worker.worker_status = WORKER_STATUS_WAITING_REVIEW
            worker.last_event_summary = f"Executor handoff ready for task #{task.id}."
            task.task_status = TASK_STATUS_REVIEW_PENDING
            aggregate_summary += " Reviewer handoff is now ready."
            reviewer_result = await db.execute(
                select(CodeWorker).where(
                    CodeWorker.workspace_id == workspace.id,
                    CodeWorker.worker_name == WORKER_LANE_REVIEWER,
                )
            )
            reviewer = reviewer_result.scalar_one_or_none()
            if reviewer is not None:
                reviewer.task_id = task.id
                reviewer.worker_status = WORKER_STATUS_ASSIGNED
                reviewer.last_event_summary = f"Structured executor handoff ready for task #{task.id}."
            handoff_packet["handoff_ready"] = True
            handoff_packet["review_recommendation"] = "begin_review"
            handoff_packet["review_summary"] = aggregate_summary
            if reviewer is not None:
                await CodeWorkerEventService.append_event(
                    db,
                    workspace_id=workspace.id,
                    task_id=task.id,
                    worker_id=reviewer.id,
                    lane=WORKER_LANE_REVIEWER,
                    event_name="review.packet.ready",
                    status=WORKER_STATUS_ASSIGNED,
                    summary=f"Reviewer-ready packet prepared for task #{task.id}.",
                    payload={
                        **handoff_packet,
                        "phase": "review",
                        "headline": f"Reviewer-ready packet prepared for task #{task.id}.",
                        "recommended_actions": handoff_packet["review_checklist"],
                    },
                )
            await CodeRuntimeService.record_policy_signal(
                db,
                workspace_id=workspace.id,
                category="subagent_handoff",
                outcome="ready",
            )
        elif worker is not None and task is not None and failed:
            worker.worker_status = WORKER_STATUS_BLOCKED
            worker.last_event_summary = f"Executor subagent recovery required for task #{task.id}."
            task.task_status = TASK_STATUS_BLOCKED
            aggregate_summary += " Recovery is required before reviewer handoff."
            handoff_packet["handoff_ready"] = False
            handoff_packet["review_recommendation"] = "hold"
            handoff_packet["recovery_recommendation"] = "inspect_failed_subagent_slices"
            handoff_packet["recovery_checklist"] = [
                "Inspect failed slice summaries and criterion coverage.",
                "Re-run or reroute failed slices before reviewer handoff.",
                "Keep the task blocked until executor evidence is stable.",
            ]
            await CodeRuntimeService.record_policy_signal(
                db,
                workspace_id=workspace.id,
                category="subagent_recovery",
                outcome="blocked",
            )
        else:
            handoff_packet["handoff_ready"] = False

        similar_skill = await CodeSkillService.find_similar_skill(
            db,
            workspace_id=workspace.id,
            objective=task.objective,
        )
        if similar_skill is not None:
            feedback_note = (
                f"Automatic feedback from subagent aggregate for task #{task.id}: "
                f"{len(completed)} completed, {len(failed)} failed."
            )
            await CodeSkillService.record_feedback(
                db,
                skill=similar_skill,
                sentiment="positive" if not failed else "negative",
                note=feedback_note,
            )
            handoff_packet["skill_feedback_applied"] = True
            handoff_packet["skill_feedback_skill_id"] = similar_skill.id
        else:
            handoff_packet["skill_feedback_applied"] = False

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            worker_id=worker.id if worker is not None else None,
            lane="executor",
            event_name="subagent.aggregate",
            status="completed" if not failed else "degraded",
            summary=aggregate_summary,
            payload={
                **handoff_packet,
                "phase": "execution" if not failed else "recovery",
                "failure_class": "tool_runtime" if failed else None,
                "headline": aggregate_summary,
                "recommended_actions": handoff_packet.get("recovery_checklist")
                if failed
                else handoff_packet.get("review_checklist", []),
            },
        )
        if session is not None:
            await CodeEventService.append_event(
                db,
                session_id=session.id,
                event_type="code.subagent.aggregate",
                payload={
                    "summary": aggregate_summary,
                    **handoff_packet,
                },
            )
        if failed and task is not None:
            user_result = await db.execute(select(User).where(User.id == task.user_id))
            user = user_result.scalar_one_or_none()
            if user is not None:
                from app.services.code.recovery_loop_service import CodeRecoveryLoopService

                recovery_task = await CodeRecoveryLoopService.ensure_recovery_task(
                    db,
                    workspace=workspace,
                    user=user,
                    session=session,
                    failure_class="subagent_recovery",
                    origin="subagent_failure",
                    summary=aggregate_summary,
                    checklist=handoff_packet.get("recovery_checklist", []),
                    source_task_id=task.id,
                )
                await CodeRecoveryLoopService.ensure_postmortem_reflection(
                    db,
                    workspace=workspace,
                    session=session,
                    user=user,
                    trigger_source="subagent_failure",
                    task_id=recovery_task.id,
                )
        await db.flush()

    async def create_run(
        self,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        session: CodeSession | None,
        task: CodeTask,
        worker: CodeWorker | None,
        metadata: dict | None = None,
    ) -> CodeSubagentRun:
        objective = task.objective
        if task.acceptance_criteria:
            objective += "\n\nAcceptance criteria:\n" + "\n".join(f"- {item}" for item in task.acceptance_criteria)
        run = CodeSubagentRun(
            workspace_id=workspace.id,
            session_id=session.id if session is not None else None,
            task_id=task.id,
            worker_id=worker.id if worker is not None else None,
            objective=objective,
            run_status="pending",
            metadata_json=metadata or {},
        )
        db.add(run)
        await db.flush()
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            worker_id=worker.id if worker is not None else None,
            lane=worker.worker_name if worker is not None else "executor",
            event_name="subagent.spawned",
            status="pending",
            summary=f"Spawned BOS subagent run #{run.id} for task #{task.id}.",
            payload={"subagent_run_id": run.id, "task_id": task.id},
        )
        return run

    async def create_runs_for_task(
        self,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        session: CodeSession | None,
        task: CodeTask,
        worker: CodeWorker | None,
        metadata: dict | None = None,
    ) -> list[CodeSubagentRun]:
        criteria = [str(item).strip() for item in (task.acceptance_criteria or []) if str(item).strip()]
        slices = criteria[: self.MAX_PARALLEL_SLICES] if criteria else []
        runs: list[CodeSubagentRun] = []
        if not slices:
            run = await self.create_run(
                db,
                workspace=workspace,
                session=session,
                task=task,
                worker=worker,
                metadata=metadata,
            )
            runs.append(run)
            return runs

        for index, criterion in enumerate(slices, start=1):
            run = await self.create_run(
                db,
                workspace=workspace,
                session=session,
                task=task,
                worker=worker,
                metadata={
                    **(metadata or {}),
                    "slice_index": index,
                    "slice_total": len(slices),
                    "criterion": criterion,
                },
            )
            run.objective = (
                f"{task.objective}\n\n"
                f"Subagent slice {index}/{len(slices)}.\n"
                f"Primary acceptance criterion:\n- {criterion}"
            )
            await db.flush()
            runs.append(run)
        return runs

    async def enqueue_or_execute_run(self, db: AsyncSession, *, run_id: int) -> CodeSubagentRun | None:
        if not settings.BOS_CODE_SUBAGENT_ASYNC_DISPATCH:
            run = await self.execute_run(db, run_id=run_id)
            if run is not None:
                metadata = dict(run.metadata_json or {})
                metadata["dispatch_mode"] = "inline_default"
                run.metadata_json = metadata
                await db.flush()
            return run

        try:
            from app.tasks.code_runtime import execute_subagent_run as execute_subagent_run_task

            if not self._celery_broker_reachable():
                raise RuntimeError("celery_broker_unreachable")
            execute_subagent_run_task.delay(run_id)
            result = await db.execute(select(CodeSubagentRun).where(CodeSubagentRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is not None:
                run.run_status = "running"
                if run.started_at is None:
                    run.started_at = datetime.now(UTC)
                metadata = dict(run.metadata_json or {})
                metadata["dispatch_mode"] = "celery"
                run.metadata_json = metadata
                await db.flush()
            return run
        except Exception:
            run = await self.execute_run(db, run_id=run_id)
            if run is not None:
                metadata = dict(run.metadata_json or {})
                metadata["dispatch_mode"] = "inline_fallback"
                run.metadata_json = metadata
                await db.flush()
            return run

    async def execute_run(self, db: AsyncSession, *, run_id: int) -> CodeSubagentRun | None:
        result = await db.execute(select(CodeSubagentRun).where(CodeSubagentRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            return None

        task = None
        if run.task_id is not None:
            task_result = await db.execute(select(CodeTask).where(CodeTask.id == run.task_id))
            task = task_result.scalar_one_or_none()
        session = None
        if run.session_id is not None:
            session_result = await db.execute(select(CodeSession).where(CodeSession.id == run.session_id))
            session = session_result.scalar_one_or_none()
        worker = None
        if run.worker_id is not None:
            worker_result = await db.execute(select(CodeWorker).where(CodeWorker.id == run.worker_id))
            worker = worker_result.scalar_one_or_none()
        workspace_result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.id == run.workspace_id))
        workspace = workspace_result.scalar_one_or_none()
        if workspace is None:
            return None

        run.run_status = "running"
        run.started_at = datetime.now(UTC)
        await db.flush()

        skill_context = ""
        if task is not None:
            skill_context = await CodeSkillService.build_injection_context(
                db,
                workspace_id=workspace.id,
                query=task.objective,
                session_id=session.id if session is not None else None,
                include_drafts=True,
            )
        prompt = (
            "You are a BOS Code background subagent. Work only on the requested implementation slice, "
            "summarize the safest next engineering move, and keep the response concise.\n\n"
        )
        if skill_context:
            prompt += f"{skill_context}\n\n"
        prompt += run.objective

        try:
            response = await self.provider.run(
                ProviderRequest(
                    session_id=run.session_id or 0,
                    prompt=prompt,
                    model=session.model if session is not None else settings.BOS_CODE_DEFAULT_MODEL,
                    provider=session.provider if session is not None else settings.BOS_CODE_DEFAULT_PROVIDER,
                    permission_mode=session.permission_mode if session is not None else "read-only",
                    tool_names=["read_file", "safe_bash"],
                )
            )
            run.result_summary = response.summary
            run.run_status = "completed"
        except Exception as exc:
            run.result_summary = str(exc)
            run.run_status = "failed"

        run.finished_at = datetime.now(UTC)
        await db.flush()

        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=run.task_id,
            worker_id=run.worker_id,
            lane="executor",
            event_name=f"subagent.{run.run_status}",
            status=run.run_status,
            summary=run.result_summary,
            payload={"subagent_run_id": run.id, "task_id": run.task_id},
        )
        if run.session_id is not None:
            await CodeEventService.append_event(
                db,
                session_id=run.session_id,
                event_type="code.subagent.result",
                payload={
                    "subagent_run_id": run.id,
                    "task_id": run.task_id,
                    "run_status": run.run_status,
                    "summary": run.result_summary,
                },
            )
        await self._maybe_aggregate_task_runs(
            db,
            workspace=workspace,
            task=task,
            session=session,
            worker=worker,
        )
        return run
