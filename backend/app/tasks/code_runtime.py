"""
Celery tasks for BOS Code runtime, heartbeat, memory, and reflections.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.db import async_session_factory
from app.models import CodeAutomationJob, CodeSession, CodeWorkspace, User
from app.services.code.automation_job_service import CodeAutomationJobService
from app.services.code.memory_service import CodeMemoryService
from app.services.code.reflection_service import CodeReflectionService
from app.services.code.session_service import CodeSessionService
from app.services.code.subagent_service import CodeSubagentService


async def _pick_runtime_user(db, *, tenant_id: int) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.role.desc(), User.id.asc())
    )
    return result.scalars().first()


async def _latest_session(db, *, workspace_id: int) -> CodeSession | None:
    result = await db.execute(
        select(CodeSession)
        .where(CodeSession.workspace_id == workspace_id)
        .order_by(CodeSession.created_at.desc())
    )
    return result.scalars().first()


@shared_task(name="app.tasks.code_runtime.run_due_automation_jobs")
def run_due_automation_jobs() -> dict:
    async def _run() -> dict:
        session_service = CodeSessionService()
        async with async_session_factory() as db:
            result = await db.execute(
                select(CodeAutomationJob)
                .join(CodeWorkspace, CodeAutomationJob.workspace_id == CodeWorkspace.id)
                .where(
                    CodeAutomationJob.enabled.is_(True),
                    CodeAutomationJob.next_run_at.is_not(None),
                    CodeAutomationJob.next_run_at <= datetime.now(UTC),
                )
            )
            jobs = list(result.scalars().all())
            processed = 0
            for job in jobs:
                workspace_result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.id == job.workspace_id))
                workspace = workspace_result.scalar_one_or_none()
                if workspace is None:
                    continue
                user = await _pick_runtime_user(db, tenant_id=job.tenant_id)
                if user is None:
                    continue
                await CodeAutomationJobService.execute_job(
                    db,
                    workspace=workspace,
                    job=job,
                    user=user,
                    session_service=session_service,
                )
                processed += 1
            await db.commit()
            return {"processed": processed}

    return asyncio.run(_run())


@shared_task(name="app.tasks.code_runtime.refresh_memory_snapshot")
def refresh_memory_snapshot(session_id: int) -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            result = await db.execute(select(CodeSession).where(CodeSession.id == session_id))
            session = result.scalar_one_or_none()
            if session is None:
                return {"status": "missing"}
            snapshot = await CodeMemoryService.refresh_snapshot(db, session=session, force=True)
            await db.commit()
            return {"status": "ok", "snapshot_id": snapshot.id if snapshot else None}

    return asyncio.run(_run())


@shared_task(name="app.tasks.code_runtime.run_reflection")
def run_reflection(session_id: int, trigger_source: str = "automation", task_id: int | None = None) -> dict:
    async def _run() -> dict:
        async with async_session_factory() as db:
            session_result = await db.execute(select(CodeSession).where(CodeSession.id == session_id))
            session = session_result.scalar_one_or_none()
            if session is None:
                return {"status": "missing"}
            workspace_result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.id == session.workspace_id))
            workspace = workspace_result.scalar_one_or_none()
            if workspace is None:
                return {"status": "workspace_missing"}
            user = await _pick_runtime_user(db, tenant_id=session.tenant_id)
            if user is None:
                return {"status": "user_missing"}
            reflection = await CodeReflectionService.run_reflection(
                db,
                workspace=workspace,
                session=session,
                user=user,
                trigger_source=trigger_source,
                task_id=task_id,
            )
            await db.commit()
            return {"status": "ok", "reflection_id": reflection.id}

    return asyncio.run(_run())


@shared_task(name="app.tasks.code_runtime.execute_subagent_run")
def execute_subagent_run(run_id: int) -> dict:
    async def _run() -> dict:
        service = CodeSubagentService()
        async with async_session_factory() as db:
            run = await service.execute_run(db, run_id=run_id)
            await db.commit()
            if run is None:
                return {"status": "missing"}
            return {"status": run.run_status, "run_id": run.id}

    return asyncio.run(_run())
