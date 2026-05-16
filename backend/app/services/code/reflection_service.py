"""
Best-effort reflection pipeline for BOS Code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.services.brain_runtime import RunLedgerArtifact, apply_run_ledger_artifact
from app.models import CodeReflectionRun, CodeSession, CodeTask, CodeToolCall, CodeTurn, CodeVerificationRun, CodeWorkspace, User
from app.services.code.memory_service import CodeMemoryService
from app.services.code.runtime_service import CodeRuntimeService
from app.services.code.skill_service import CodeSkillService
from app.services.code.worker_event_service import CodeWorkerEventService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeReflectionService:
    COMPLEXITY_TOOL_THRESHOLD = 3
    RUN_LEDGER_PATH = Path(__file__).resolve().parents[4] / ".agents" / "runtime" / "run-ledger.md"

    @staticmethod
    def _derive_verified_signal(
        *,
        session: CodeSession,
        task: CodeTask | None,
        verifications: list[CodeVerificationRun],
        tool_calls: list[CodeToolCall],
    ) -> tuple[bool, list[str]]:
        signals: list[str] = []
        latest_statuses = [run.verification_status for run in verifications]
        if any(status == "failed" for status in latest_statuses):
            signals.append("recent_verification_failed")
        if any(status == "passed" for status in latest_statuses):
            signals.append("recent_verification_passed")
        if task is not None and task.task_status == "completed":
            signals.append("task_completed")
        if task is not None and task.task_status == "blocked":
            signals.append("task_blocked")
        if session.verification_status == "passed":
            signals.append("session_verification_passed")
        elif session.verification_status == "failed":
            signals.append("session_verification_failed")
        if len(tool_calls) >= CodeReflectionService.COMPLEXITY_TOOL_THRESHOLD:
            signals.append("tool_complexity_high")

        verified = (
            "recent_verification_failed" not in signals
            and "task_blocked" not in signals
            and (
                "recent_verification_passed" in signals
                or "session_verification_passed" in signals
                or "task_completed" in signals
            )
        )
        return verified, signals

    @staticmethod
    async def list_reflections(db: AsyncSession, *, workspace_id: int) -> list[CodeReflectionRun]:
        result = await db.execute(
            select(CodeReflectionRun)
            .where(CodeReflectionRun.workspace_id == workspace_id)
            .order_by(CodeReflectionRun.created_at.desc(), CodeReflectionRun.id.desc())
        )
        return list(result.scalars().all())

    @classmethod
    async def should_trigger_background_review(
        cls,
        db: AsyncSession,
        *,
        session_id: int,
        trigger_source: str,
    ) -> bool:
        turn_count = await db.scalar(select(CodeTurn.id).where(CodeTurn.session_id == session_id).order_by(CodeTurn.id.desc()).limit(1))
        tool_count_result = await db.execute(
            select(CodeToolCall).where(CodeToolCall.session_id == session_id).order_by(CodeToolCall.created_at.desc()).limit(5)
        )
        recent_tool_calls = list(tool_count_result.scalars().all())
        if trigger_source in {"heartbeat", "cron"}:
            return True
        return bool(turn_count) and len(recent_tool_calls) >= cls.COMPLEXITY_TOOL_THRESHOLD

    @classmethod
    async def run_reflection(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        session: CodeSession,
        user: User,
        trigger_source: str,
        task_id: int | None = None,
    ) -> CodeReflectionRun:
        latest_turn_result = await db.execute(
            select(CodeTurn).where(CodeTurn.session_id == session.id).order_by(CodeTurn.turn_index.desc()).limit(1)
        )
        latest_turn = latest_turn_result.scalar_one_or_none()
        task = None
        if task_id is not None:
            task_result = await db.execute(
                select(CodeTask).where(CodeTask.workspace_id == workspace.id, CodeTask.id == task_id)
            )
            task = task_result.scalar_one_or_none()

        tool_calls_result = await db.execute(
            select(CodeToolCall).where(CodeToolCall.session_id == session.id).order_by(CodeToolCall.created_at.desc()).limit(6)
        )
        tool_calls = list(tool_calls_result.scalars().all())
        verifications_result = await db.execute(
            select(CodeVerificationRun)
            .where(CodeVerificationRun.session_id == session.id)
            .order_by(CodeVerificationRun.finished_at.desc(), CodeVerificationRun.started_at.desc(), CodeVerificationRun.id.desc())
            .limit(6)
        )
        recent_verifications = list(verifications_result.scalars().all())
        latest_snapshot = await CodeMemoryService.refresh_snapshot(db, session=session, force=False)
        similar_skill = await CodeSkillService.find_similar_skill(
            db,
            workspace_id=workspace.id,
            objective=task.objective if task is not None else (latest_turn.user_message if latest_turn else ""),
        )
        verified_signal, verification_signals = cls._derive_verified_signal(
            session=session,
            task=task,
            verifications=recent_verifications,
            tool_calls=tool_calls,
        )

        if not verified_signal:
            output_kind = "memory_update"
            summary = "Stored a BOS Code memory snapshot only; recent work is not verified enough to promote into a skill yet."
        elif similar_skill is not None:
            output_kind = "skill_update"
            summary = f"Updated BOS skill draft '{similar_skill.name}' from recent execution evidence."
        elif len(tool_calls) >= cls.COMPLEXITY_TOOL_THRESHOLD:
            output_kind = "skill_create"
            summary = "Captured a reusable BOS Code workflow as a draft skill."
        else:
            output_kind = "memory_update"
            summary = "Persisted a BOS Code memory snapshot for future turns."

        reflection = CodeReflectionRun(
            workspace_id=workspace.id,
            session_id=session.id,
            task_id=task.id if task is not None else None,
            trigger_source=trigger_source,
            reflection_status="running",
            output_kind=output_kind,
            summary=summary,
            payload={
                "latest_turn_id": latest_turn.id if latest_turn else None,
                "tool_names": [call.tool_name for call in tool_calls],
                "memory_snapshot_id": latest_snapshot.id if latest_snapshot else None,
                "recent_verification_statuses": [run.verification_status for run in recent_verifications],
                "verified_signal": verified_signal,
                "verification_signals": verification_signals,
            },
        )
        db.add(reflection)
        await db.flush()

        if output_kind == "memory_update":
            reflection.reflection_status = "completed"
        else:
            skill_content = cls._build_skill_content(
                task=task,
                latest_turn=latest_turn,
                tool_calls=tool_calls,
                memory_snapshot=latest_snapshot.summary_markdown if latest_snapshot else "",
            )
            if similar_skill is None:
                skill = await CodeSkillService.create_skill(
                    db,
                    workspace=workspace,
                    user=user,
                    name=task.title if task is not None else "BOS Code Runtime Workflow",
                    slug=(task.title if task is not None else "bos-code-runtime-workflow"),
                    description=summary,
                    content_markdown=skill_content,
                    supporting_files={},
                    origin_task_id=task.id if task is not None else None,
                    reflection_run_id=reflection.id,
                    revision_status="draft",
                    skill_status="draft",
                    change_summary=summary,
                )
            else:
                skill = await CodeSkillService.update_skill(
                    db,
                    workspace=workspace,
                    skill=similar_skill,
                    description=summary,
                    skill_status="draft",
                    change_summary=summary,
                    content_markdown=skill_content,
                    supporting_files={},
                    reflection_run_id=reflection.id,
                )
            reflection.skill_id = skill.id
            reflection.reflection_status = "completed"
            reflection.payload = {
                **(reflection.payload or {}),
                "skill_id": skill.id,
                "skill_slug": skill.slug,
            }

        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=workspace.id)
        reflected_at = datetime.now(UTC)
        runtime.last_reflection_at = reflected_at
        runtime_metrics = dict(runtime.runtime_metrics or {})
        runtime_metrics["last_reflection_verified_signal"] = verified_signal
        runtime_metrics["last_reflection_verification_signals"] = verification_signals
        runtime.runtime_metrics = runtime_metrics
        reflection_artifact = cls._stage_reflection_run_artifact(reflection=reflection, workspace=workspace)
        cls._write_run_ledger_artifact(artifact=reflection_artifact, when=reflected_at)
        await CodeRuntimeService.record_run_ledger_artifact(
            db,
            workspace_id=workspace.id,
            artifact=reflection_artifact,
            when=reflected_at,
        )
        await CodeWorkerEventService.append_event(
            db,
            workspace_id=workspace.id,
            task_id=task.id if task is not None else None,
            lane="tasking",
            event_name="reflection.completed",
            status=reflection.output_kind,
            summary=reflection.summary,
            payload={
                "reflection_id": reflection.id,
                "skill_id": reflection.skill_id,
                "memory_snapshot_id": latest_snapshot.id if latest_snapshot else None,
            },
        )
        await CodeRuntimeService.record_policy_signal(
            db,
            workspace_id=workspace.id,
            category="reflection_learning",
            outcome="verified_skill" if output_kind in {"skill_create", "skill_update"} else "memory_only",
        )
        await db.flush()
        return reflection

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

    @staticmethod
    def _stage_reflection_run_artifact(
        *,
        reflection: CodeReflectionRun,
        workspace: CodeWorkspace,
    ) -> RunLedgerArtifact:
        outcome = {
            "skill_create": "Reflection captured a reusable BOS Code workflow as a draft skill.",
            "skill_update": "Reflection updated an existing BOS Code draft skill from recent evidence.",
            "memory_update": "Reflection persisted a BOS Code memory snapshot for future turns.",
        }.get(reflection.output_kind, reflection.summary or "Reflection completed.")
        remaining_risk = (
            "Draft skills still need operator review before activation."
            if reflection.output_kind in {"skill_create", "skill_update"}
            else "Memory is persisted, but downstream task and verification posture may still need operator review."
        )
        return RunLedgerArtifact(
            slice="BOS Code reflection review",
            outcome=outcome,
            verification="Completed the reflection pass and recorded the resulting worker event.",
            remaining_risk=remaining_risk,
            next_step="Inspect the Brain Dashboard and confirm the next memory or skill follow-up.",
            target_surface="brain",
            target_id=str(workspace.id),
            target_route="/bos/brain",
        )

    @staticmethod
    def _build_skill_content(
        *,
        task: CodeTask | None,
        latest_turn: CodeTurn | None,
        tool_calls: list[CodeToolCall],
        memory_snapshot: str,
    ) -> str:
        title = task.title if task is not None else "BOS Code Runtime Workflow"
        objective = task.objective if task is not None else (latest_turn.user_message if latest_turn else "Handle BOS Code work")
        tools = ", ".join(sorted({call.tool_name for call in tool_calls})) or "provider_dispatch"
        return (
            "---\n"
            f"name: {title}\n"
            f"description: Draft skill captured from BOS Code reflection for {title}.\n"
            "---\n\n"
            f"# {title}\n\n"
            "## Objective\n"
            f"- {objective}\n\n"
            "## Steps\n"
            "- Inspect the current BOS Code session, task, branch, and verification posture.\n"
            f"- Reuse the tools that proved useful in this run: {tools}.\n"
            "- Preserve replayable events and verification readiness while making progress.\n"
            "- Keep changes inside the tenant workspace and avoid touching unrelated code.\n\n"
            "## Memory\n"
            f"{memory_snapshot or '- No prior memory snapshot was available.'}\n"
        )
