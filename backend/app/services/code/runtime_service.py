"""
Runtime posture and automation CRUD for BOS Code.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.services.brain_runtime import RunLedgerArtifact
from app.models import (
    CodeAgentRuntimeState,
    CodeAutomationJob,
    CodeReflectionRun,
    CodeSubagentRun,
    CodeWorkspace,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeRuntimeService:
    DEFAULT_JOBS: tuple[dict[str, Any], ...] = (
        {
            "name": "heartbeat-monitor",
            "job_type": "heartbeat",
            "enabled": True,
            "schedule_kind": "heartbeat",
            "target_scope": "heartbeat",
            "prompt_template": "[system automation] Heartbeat detected active BOS Code work. Summarize posture, the next safe action, and the explicit target surface/id/route that an autonomy run artifact should point to.",
        },
        {
            "name": "reflection-review",
            "job_type": "reflection",
            "enabled": True,
            "schedule_kind": "interval",
            "interval_sec": 900,
            "target_scope": "automation",
            "prompt_template": "Review recent BOS Code work, capture memory or skill updates if useful, and keep any autonomy handoff aligned to explicit target surface/id/route metadata.",
        },
        {
            "name": "autonomy-maintenance",
            "job_type": "maintenance",
            "enabled": True,
            "schedule_kind": "interval",
            "interval_sec": 10800,
            "target_scope": "maintenance",
            "prompt_template": "Refresh the BOS autonomy brain, update cross-thread memory, and stage maintenance reports for operators.",
        },
    )

    @staticmethod
    async def ensure_runtime_state(db: AsyncSession, *, workspace_id: int) -> CodeAgentRuntimeState:
        result = await db.execute(
            select(CodeAgentRuntimeState).where(CodeAgentRuntimeState.workspace_id == workspace_id)
        )
        runtime = result.scalar_one_or_none()
        if runtime is not None:
            return runtime

        runtime = CodeAgentRuntimeState(workspace_id=workspace_id)
        db.add(runtime)
        await db.flush()
        return runtime

    @staticmethod
    def _metrics(runtime: CodeAgentRuntimeState) -> dict[str, Any]:
        return dict(runtime.runtime_metrics or {})

    @classmethod
    async def record_run_ledger_artifact(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        artifact: RunLedgerArtifact,
        when: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_run_ledger_artifact"] = {
            "slice": artifact.slice,
            "outcome": artifact.outcome,
            "target_surface": artifact.target_surface,
            "target_id": artifact.target_id,
            "target_route": artifact.target_route,
            "recorded_at": when.isoformat(),
        }
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_maintenance_summary(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        summary: str,
        generated_at: datetime,
        report_markdown_path: str,
        report_json_path: str,
        project_brain_path: str,
        decision_journal_path: str,
        evolution_log_path: str,
        next_autonomy_mode: str,
        next_autonomy_objective: str,
        workflow_mode: str,
        workflow_skills: list[str],
        workflow_rationale: list[str],
        experience_quality: dict[str, Any],
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_maintenance_summary"] = summary
        metrics["last_maintenance_generated_at"] = generated_at.isoformat()
        metrics["last_maintenance_report_markdown_path"] = report_markdown_path
        metrics["last_maintenance_report_json_path"] = report_json_path
        metrics["last_maintenance_project_brain_path"] = project_brain_path
        metrics["last_maintenance_decision_journal_path"] = decision_journal_path
        metrics["last_maintenance_evolution_log_path"] = evolution_log_path
        metrics["next_autonomy_mode"] = next_autonomy_mode
        metrics["next_autonomy_objective"] = next_autonomy_objective
        metrics["workflow_mode"] = workflow_mode
        metrics["workflow_skills"] = workflow_skills
        metrics["workflow_rationale"] = workflow_rationale
        metrics["experience_quality"] = experience_quality
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_seeded_autonomy_task(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        objective: str,
        seeded_at: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_seeded_autonomy_task_id"] = task_id
        metrics["last_seeded_autonomy_objective"] = objective
        metrics["last_seeded_autonomy_at"] = seeded_at.isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_recovery_task_handoff(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        task_id: int,
        failure_class: str,
        recorded_at: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_recovery_task_id"] = task_id
        metrics["last_recovery_failure_class"] = failure_class
        metrics["last_recovery_task_at"] = recorded_at.isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_automation_execution(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        session_id: int | None,
        executed_action: str,
        execution_status: str,
        summary: str,
        executed_at: datetime,
        resulting_session_status: str | None,
        resulting_verification_status: str | None,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_automation_execution"] = {
            "session_id": session_id,
            "executed_action": executed_action,
            "execution_status": execution_status,
            "summary": summary,
            "executed_at": executed_at.isoformat(),
            "resulting_session_status": resulting_session_status,
            "resulting_verification_status": resulting_verification_status,
        }
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_provider_backpressure(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        failure_class: str,
        cooldown_until: datetime | None,
        recorded_at: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["last_provider_failure_class"] = failure_class
        metrics["last_provider_backpressure_at"] = recorded_at.isoformat()
        metrics["provider_backpressure_count"] = int(metrics.get("provider_backpressure_count", 0) or 0) + 1
        if cooldown_until is not None:
            metrics["provider_pause_until"] = cooldown_until.isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def clear_provider_backpressure(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        cleared_at: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics.pop("provider_pause_until", None)
        metrics["last_provider_resume_at"] = cleared_at.isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_provider_budget_pause(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        pause_until: datetime,
        recorded_at: datetime,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        metrics["provider_budget_pause_until"] = pause_until.isoformat()
        metrics["last_provider_budget_pause_at"] = recorded_at.isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def record_policy_signal(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        category: str,
        outcome: str,
    ) -> CodeAgentRuntimeState:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        policy = dict(metrics.get("policy_learning") or {})
        bucket = dict(policy.get(category) or {})
        bucket[outcome] = int(bucket.get(outcome, 0) or 0) + 1
        policy[category] = bucket
        metrics["policy_learning"] = policy
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime

    @classmethod
    async def get_policy_learning_snapshot(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
    ) -> dict[str, dict[str, int]]:
        runtime = await cls.ensure_runtime_state(db, workspace_id=workspace_id)
        metrics = cls._metrics(runtime)
        policy = metrics.get("policy_learning") or {}
        return {str(category): {str(name): int(value) for name, value in (bucket or {}).items()} for category, bucket in policy.items()}

    @classmethod
    async def ensure_default_jobs(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        tenant_id: int,
    ) -> list[CodeAutomationJob]:
        existing = await cls.list_jobs(db, workspace_id=workspace.id)
        by_name = {job.name: job for job in existing}
        created_or_existing: list[CodeAutomationJob] = list(existing)
        for payload in cls.DEFAULT_JOBS:
            if payload["name"] in by_name:
                continue
            job = await cls.create_job(
                db,
                workspace=workspace,
                tenant_id=tenant_id,
                payload=payload,
            )
            created_or_existing.append(job)
        return created_or_existing

    @staticmethod
    def compute_next_run_at(
        *,
        schedule_kind: str,
        interval_sec: int | None,
        cron_expr: str | None,
        now: datetime | None = None,
    ) -> datetime | None:
        now = now or datetime.now(UTC)
        if schedule_kind == "interval" and interval_sec:
            return now + timedelta(seconds=interval_sec)
        if schedule_kind == "manual":
            return None
        if schedule_kind == "heartbeat":
            return now + timedelta(seconds=30)
        if schedule_kind == "cron" and cron_expr:
            fields = cron_expr.split()
            if len(fields) != 5:
                return None
            minute, hour, *_rest = fields
            if minute.startswith("*/") and hour == "*":
                try:
                    step = max(int(minute[2:]), 1)
                except ValueError:
                    return None
                return now + timedelta(minutes=step)
            if minute.isdigit() and hour == "*":
                target = now.replace(minute=int(minute), second=0, microsecond=0)
                if target <= now:
                    target += timedelta(hours=1)
                return target
            if minute.isdigit() and hour.isdigit():
                target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target
        return None

    @classmethod
    async def list_jobs(cls, db: AsyncSession, *, workspace_id: int) -> list[CodeAutomationJob]:
        result = await db.execute(
            select(CodeAutomationJob)
            .where(CodeAutomationJob.workspace_id == workspace_id)
            .order_by(CodeAutomationJob.created_at.asc(), CodeAutomationJob.id.asc())
        )
        return list(result.scalars().all())

    @classmethod
    async def create_job(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        tenant_id: int,
        payload: dict[str, Any],
    ) -> CodeAutomationJob:
        now = datetime.now(UTC)
        job = CodeAutomationJob(
            tenant_id=tenant_id,
            workspace_id=workspace.id,
            name=payload["name"],
            job_type=payload.get("job_type") or "cron",
            enabled=payload.get("enabled", True),
            schedule_kind=payload.get("schedule_kind") or "manual",
            cron_expr=payload.get("cron_expr"),
            interval_sec=payload.get("interval_sec"),
            timezone=payload.get("timezone"),
            prompt_template=payload.get("prompt_template"),
            target_scope=payload.get("target_scope"),
            next_run_at=cls.compute_next_run_at(
                schedule_kind=payload.get("schedule_kind") or "manual",
                interval_sec=payload.get("interval_sec"),
                cron_expr=payload.get("cron_expr"),
                now=now,
            )
            if payload.get("enabled", True)
            else None,
            last_status="idle",
        )
        db.add(job)
        await db.flush()
        return job

    @classmethod
    async def update_job(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        job_id: int,
        payload: dict[str, Any],
    ) -> CodeAutomationJob | None:
        result = await db.execute(
            select(CodeAutomationJob).where(
                CodeAutomationJob.workspace_id == workspace_id,
                CodeAutomationJob.id == job_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None

        for field in (
            "enabled",
            "schedule_kind",
            "cron_expr",
            "interval_sec",
            "timezone",
            "prompt_template",
            "target_scope",
            "last_error",
        ):
            if field in payload and payload[field] is not None:
                setattr(job, field, payload[field])

        if "enabled" in payload and payload["enabled"] is False:
            job.next_run_at = None
        else:
            job.next_run_at = cls.compute_next_run_at(
                schedule_kind=job.schedule_kind,
                interval_sec=job.interval_sec,
                cron_expr=job.cron_expr,
            )
        await db.flush()
        return job

    @classmethod
    async def mark_job_run(
        cls,
        db: AsyncSession,
        *,
        job: CodeAutomationJob,
        status: str,
        error: str | None = None,
    ) -> CodeAutomationJob:
        now = datetime.now(UTC)
        job.last_run_at = now
        job.last_status = status
        job.last_error = error
        job.next_run_at = (
            cls.compute_next_run_at(
                schedule_kind=job.schedule_kind,
                interval_sec=job.interval_sec,
                cron_expr=job.cron_expr,
                now=now,
            )
            if job.enabled
            else None
        )
        await db.flush()
        return job

    @staticmethod
    async def get_runtime_payload(
        db: AsyncSession,
        *,
        workspace_id: int,
    ) -> tuple[CodeAgentRuntimeState, list[CodeAutomationJob], list[CodeSubagentRun], int]:
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=workspace_id)
        jobs = await CodeRuntimeService.list_jobs(db, workspace_id=workspace_id)
        active_subagents_result = await db.execute(
            select(CodeSubagentRun)
            .where(CodeSubagentRun.workspace_id == workspace_id)
            .order_by(CodeSubagentRun.created_at.desc())
            .limit(5)
        )
        reflections_result = await db.execute(
            select(func.count(CodeReflectionRun.id)).where(
                CodeReflectionRun.workspace_id == workspace_id,
                CodeReflectionRun.reflection_status.in_(("pending", "running")),
            )
        )
        return runtime, jobs, list(active_subagents_result.scalars().all()), int(reflections_result.scalar() or 0)
