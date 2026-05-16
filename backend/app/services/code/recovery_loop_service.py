"""
Automatic recovery loop orchestration for BOS Code failures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import CodeSession, CodeTask, CodeWorkspace, User
from app.services.code.reflection_service import CodeReflectionService
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.task_service import CodeTaskService
from app.services.code.worker_event_service import CodeWorkerEventService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeRecoveryLoopService:
    # Kept as a compatibility seam for tests and future recovery runners.
    subagent_service = None
    OPEN_TASK_STATUSES = {"created", "running", "review_pending", "in_review", "verification_pending", "blocked"}

    @staticmethod
    def _normalize_failure_class(value: str) -> str:
        mapping = {
            "prompt_misdelivery": "prompt_delivery",
            "client_cancelled": "prompt_delivery",
            "provider_unavailable": "provider_error",
            "provider_cooldown": "provider_error",
        }
        return mapping.get(value, value)

    @staticmethod
    def _signature(*, failure_class: str, origin: str, session_id: int | None, task_id: int | None) -> str:
        return f"{failure_class}:{origin}:{session_id or 'none'}:{task_id or 'none'}"

    @classmethod
    async def _existing_open_recovery_task(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        signature: str,
    ) -> CodeTask | None:
        result = await db.execute(
            select(CodeTask)
            .where(CodeTask.workspace_id == workspace_id)
            .order_by(CodeTask.updated_at.desc(), CodeTask.id.desc())
        )
        tasks = list(result.scalars().all())
        for task in tasks:
            packet = dict(task.task_packet or {})
            if packet.get("recovery_signature") == signature and task.task_status in cls.OPEN_TASK_STATUSES:
                return task
        return None

    @staticmethod
    def _acceptance_criteria(*, failure_class: str) -> list[str]:
        criteria = [
            "Stabilize the failure without waiting for another manual continue prompt.",
            "Keep the blocker, next gate, and recovery evidence explicit in the task handoff.",
        ]
        if failure_class == "verification_failed":
            criteria.append("Inspect the failing verification stage and route the smallest corrective action.")
        elif failure_class == "subagent_recovery":
            criteria.append("Inspect failed subagent slice evidence and restore the executor lane to a healthy state.")
        elif failure_class == "prompt_delivery":
            criteria.append("Recover the blocked session back to ready-for-prompt or clearly explain why it cannot recover.")
        else:
            criteria.append("Perform the safest available recovery action and summarize the remaining risk.")
        return criteria

    @staticmethod
    def _title(*, failure_class: str) -> str:
        mapping = {
            "verification_failed": "Verification recovery task",
            "subagent_recovery": "Subagent recovery task",
            "prompt_delivery": "Prompt delivery recovery task",
            "provider_error": "Provider recovery task",
            "trust_gate": "Trust gate recovery task",
        }
        return mapping.get(failure_class, "Runtime recovery task")

    @staticmethod
    def _objective(
        *,
        failure_class: str,
        summary: str,
        checklist: list[str],
    ) -> str:
        body = [
            f"Recover BOS Code from failure class `{failure_class}`.",
            f"Failure summary: {summary}",
        ]
        if checklist:
            body.append("Recovery checklist:")
            body.extend(f"- {item}" for item in checklist[:5])
        return "\n".join(body)

    @classmethod
    async def ensure_recovery_task(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        user: User,
        session: CodeSession | None,
        failure_class: str,
        origin: str,
        summary: str,
        checklist: list[str],
        source_task_id: int | None = None,
    ) -> CodeTask:
        normalized_failure_class = cls._normalize_failure_class(failure_class)
        signature = cls._signature(
            failure_class=normalized_failure_class,
            origin=origin,
            session_id=session.id if session is not None else None,
            task_id=source_task_id,
        )
        existing = await cls._existing_open_recovery_task(
            db,
            workspace_id=workspace.id,
            signature=signature,
        )
        if existing is not None:
            return existing

        task = await CodeTaskService.create_task(
            db,
            workspace=workspace,
            user=user,
            session_id=session.id if session is not None else None,
            title=cls._title(failure_class=normalized_failure_class),
            objective=cls._objective(
                failure_class=normalized_failure_class,
                summary=summary,
                checklist=checklist,
            ),
            scope="code/recovery",
            acceptance_criteria=cls._acceptance_criteria(failure_class=normalized_failure_class),
            task_packet={
                "recovery_signature": signature,
                "recovery_origin": origin,
                "failure_class": normalized_failure_class,
                "source_task_id": source_task_id,
                "source_session_id": session.id if session is not None else None,
                "recovery_checklist": checklist,
            },
        )
        task.task_status = "running"
        architect = await CodeTaskService._get_worker(db, workspace_id=workspace.id, worker_name="architect")
        if architect is not None and architect.task_id == task.id:
            architect.task_id = None
            architect.worker_status = "ready"
            architect.last_event_summary = f"Autonomy staged recovery task #{task.id} for executor-side recovery."
            await CodeWorkerEventService.append_event(
                db,
                workspace_id=workspace.id,
                task_id=task.id,
                worker_id=architect.id,
                lane="architect",
                event_name="lane.completed",
                status="ready",
                summary=architect.last_event_summary,
                payload={
                    "source": "recovery_loop",
                    "failure_class": normalized_failure_class,
                    "origin": origin,
                    "headline": architect.last_event_summary,
                },
            )
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            lane="tasking",
            event_name="task.routed",
            status="running",
            summary=f"Autonomy staged recovery task #{task.id} for {normalized_failure_class}.",
            payload={
                "source": "recovery_loop",
                "failure_class": normalized_failure_class,
                "origin": origin,
                "headline": f"Recovery task #{task.id} is running in autonomy mode.",
                "recommended_action": "Inspect background recovery slices before requesting review.",
            },
        )
        await CodeRuntimeService.record_policy_signal(
            db,
            workspace_id=workspace.id,
            category="recovery_task_seeded",
            outcome=normalized_failure_class,
        )
        await CodeRuntimeService.record_recovery_task_handoff(
            db,
            workspace_id=workspace.id,
            task_id=task.id,
            failure_class=normalized_failure_class,
            recorded_at=datetime.now(UTC),
        )
        return task

    @classmethod
    async def ensure_postmortem_reflection(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        session: CodeSession | None,
        user: User,
        trigger_source: str,
        task_id: int | None = None,
    ) -> None:
        if session is None:
            return
        await CodeReflectionService.run_reflection(
            db,
            workspace=workspace,
            session=session,
            user=user,
            trigger_source=trigger_source,
            task_id=task_id,
        )
