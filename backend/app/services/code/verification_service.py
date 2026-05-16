"""
Verification coordination for BOS Code sessions.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.code import VERIFICATION_STAGES
from app.models import CodeSession, CodeVerificationRun
from app.services.code.tool_registry import CodeToolRegistry
from app.services.code.workspace_guard import WorkspaceGuard


@dataclass(slots=True)
class VerificationExecutionResult:
    stage: str
    verification_status: str
    summary: str
    log_excerpt: str
    exit_code: int | None = None


class CodeVerificationService:
    STAGE_COMMANDS = {
        "lint": "python -m py_compile app/main.py app/routers/code.py app/services/code/session_service.py",
        "typecheck": "python -m py_compile app/schemas/code.py app/services/code/verification_service.py",
        "unit_test": "python -m pytest tests/unit/test_code_provider.py -q",
        "build": "python -m py_compile app/services/code/automation_service.py app/services/code/orchestration_service.py app/services/code/task_service.py",
        "smoke_test": "python -m py_compile app/models_code.py app/services/code/branch_service.py",
    }

    @staticmethod
    async def ensure_default_runs(db: AsyncSession, *, session_id: int) -> list[CodeVerificationRun]:
        existing = await db.execute(select(CodeVerificationRun).where(CodeVerificationRun.session_id == session_id))
        runs = list(existing.scalars().all())
        if runs:
            return runs

        created: list[CodeVerificationRun] = []
        for stage in VERIFICATION_STAGES:
            run = CodeVerificationRun(session_id=session_id, verification_stage=stage, verification_status="pending")
            db.add(run)
            created.append(run)
        await db.flush()
        return created

    @staticmethod
    async def mark_run(
        db: AsyncSession,
        *,
        run: CodeVerificationRun,
        status: str,
        summary: str | None = None,
        log_excerpt: str | None = None,
    ) -> CodeVerificationRun:
        now = datetime.now(UTC)
        if status == "running" and run.started_at is None:
            run.started_at = now
        if status in {"passed", "failed", "skipped"}:
            if run.started_at is None:
                run.started_at = now
            run.finished_at = now
        run.verification_status = status
        run.summary = summary
        run.log_excerpt = log_excerpt
        await db.flush()
        return run

    @staticmethod
    async def refresh_session_status(db: AsyncSession, *, session: CodeSession) -> CodeSession:
        result = await db.execute(
            select(CodeVerificationRun).where(CodeVerificationRun.session_id == session.id)
        )
        runs = list(result.scalars().all())
        statuses = {run.verification_status for run in runs}
        if "failed" in statuses:
            session.verification_status = "failed"
        elif "running" in statuses:
            session.verification_status = "running"
        elif statuses and statuses <= {"passed"}:
            session.verification_status = "passed"
        elif statuses and statuses <= {"skipped"}:
            session.verification_status = "skipped"
        else:
            session.verification_status = "pending"
        await db.flush()
        return session

    @classmethod
    def _build_registry(
        cls,
        *,
        worktree_root: str,
        role: str,
        safe_bash_timeout_sec: int,
        max_read_bytes: int,
        max_write_bytes: int,
    ) -> CodeToolRegistry:
        guard = WorkspaceGuard(
            worktree_root,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
        )
        return CodeToolRegistry(
            workspace_guard=guard,
            role=role,
            safe_bash_timeout_sec=safe_bash_timeout_sec,
        )

    @classmethod
    async def execute_stage(
        cls,
        db: AsyncSession,
        *,
        session: CodeSession,
        worktree_root: str,
        role: str,
        stage: str,
        safe_bash_timeout_sec: int,
        max_read_bytes: int,
        max_write_bytes: int,
    ) -> VerificationExecutionResult:
        if stage not in cls.STAGE_COMMANDS:
            raise ValueError(f"unsupported verification stage: {stage}")

        runs = await cls.ensure_default_runs(db, session_id=session.id)
        run = next(item for item in runs if item.verification_stage == stage)
        await cls.mark_run(db, run=run, status="running", summary=f"Running {stage}", log_excerpt=None)

        registry = cls._build_registry(
            worktree_root=worktree_root,
            role=role,
            safe_bash_timeout_sec=safe_bash_timeout_sec,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
        )
        command = cls.STAGE_COMMANDS[stage]
        result = registry.execute_safe_bash(command)
        status = "passed" if result.success else "failed"
        log_excerpt = result.output[:2000]
        summary = f"{stage} passed" if result.success else f"{stage} failed"
        await cls.mark_run(
            db,
            run=run,
            status=status,
            summary=summary,
            log_excerpt=log_excerpt,
        )
        await cls.refresh_session_status(db, session=session)
        return VerificationExecutionResult(
            stage=stage,
            verification_status=status,
            summary=summary,
            log_excerpt=log_excerpt,
            exit_code=result.exit_code,
        )

    @classmethod
    async def execute_pipeline(
        cls,
        db: AsyncSession,
        *,
        session: CodeSession,
        worktree_root: str,
        role: str,
        safe_bash_timeout_sec: int,
        max_read_bytes: int,
        max_write_bytes: int,
        stop_on_failure: bool = True,
    ) -> list[VerificationExecutionResult]:
        results: list[VerificationExecutionResult] = []
        for stage in VERIFICATION_STAGES:
            result = await cls.execute_stage(
                db,
                session=session,
                worktree_root=worktree_root,
                role=role,
                stage=stage,
                safe_bash_timeout_sec=safe_bash_timeout_sec,
                max_read_bytes=max_read_bytes,
                max_write_bytes=max_write_bytes,
            )
            results.append(result)
            if stop_on_failure and result.verification_status == "failed":
                break
        return results
