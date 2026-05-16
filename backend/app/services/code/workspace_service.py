"""
Workspace initialization and reconciliation for BOS Code.
"""

import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import CodeWorkspace, CodeWorkspaceLease, User
from app.services.code.runtime_service import CodeRuntimeService

settings = get_settings()

MIRRORED_DIRS = ("app", "tests")
MIRRORED_FILES = ("alembic.ini",)
BACKEND_ROOT = Path(__file__).resolve().parents[3]


class CodeWorkspaceService:
    @staticmethod
    def _safe_copy_file(src: str, dst: str) -> str:
        try:
            shutil.copy2(src, dst)
        except OSError:
            return dst
        return dst

    @staticmethod
    async def get_workspace(db: AsyncSession, *, tenant_id: int) -> CodeWorkspace | None:
        result = await db.execute(select(CodeWorkspace).where(CodeWorkspace.tenant_id == tenant_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def ensure_workspace(db: AsyncSession, *, user: User) -> CodeWorkspace:
        from app.services.code.task_service import CodeTaskService

        workspace = await CodeWorkspaceService.get_workspace(db, tenant_id=user.tenant_id)
        if workspace is not None:
            CodeWorkspaceService._seed_workspace_mirror(Path(workspace.repo_root), Path(workspace.worktree_root))
            await CodeRuntimeService.ensure_runtime_state(db, workspace_id=workspace.id)
            await CodeRuntimeService.ensure_default_jobs(db, workspace=workspace, tenant_id=user.tenant_id)
            await CodeTaskService.ensure_default_workers(db, workspace=workspace)
            return workspace

        repo_root = BACKEND_ROOT
        worktree_root = repo_root / settings.BOS_CODE_WORKTREE_ROOT / f"tenant-{user.tenant_id}"
        worktree_root.resolve().mkdir(parents=True, exist_ok=True)
        CodeWorkspaceService._seed_workspace_mirror(repo_root, worktree_root)
        workspace = CodeWorkspace(
            tenant_id=user.tenant_id,
            repo_root=repo_root.as_posix(),
            worktree_root=worktree_root.as_posix(),
            base_branch=f"boscode/tenant-{user.tenant_id}/base",
            default_branch=f"boscode/tenant-{user.tenant_id}/base",
            active_branch=f"boscode/tenant-{user.tenant_id}/base",
            workspace_status="ready",
            dirty_state=False,
        )
        db.add(workspace)
        await db.flush()

        lease = CodeWorkspaceLease(
            workspace_id=workspace.id,
            lease_status="available",
        )
        db.add(lease)
        await db.flush()
        await CodeRuntimeService.ensure_runtime_state(db, workspace_id=workspace.id)
        await CodeRuntimeService.ensure_default_jobs(db, workspace=workspace, tenant_id=user.tenant_id)
        await CodeTaskService.ensure_default_workers(db, workspace=workspace)
        return workspace

    @staticmethod
    def _seed_workspace_mirror(repo_root: Path, worktree_root: Path) -> None:
        worktree_root.mkdir(parents=True, exist_ok=True)
        for dirname in MIRRORED_DIRS:
            source = repo_root / dirname
            destination = worktree_root / dirname
            if source.exists():
                shutil.copytree(
                    source,
                    destination,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache"),
                    copy_function=CodeWorkspaceService._safe_copy_file,
                )

        for filename in MIRRORED_FILES:
            source = repo_root / filename
            destination = worktree_root / filename
            if source.exists():
                CodeWorkspaceService._safe_copy_file(str(source), str(destination))
