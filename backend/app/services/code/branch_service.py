"""
Branch posture and readiness services for BOS Code v2.
"""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeBranchState, CodeWorkspace
from app.services.code.tool_registry import CodeToolRegistry
from app.services.code.workspace_guard import WorkspaceGuard


@dataclass(slots=True)
class BranchReadiness:
    readiness: str
    blocking_reasons: list[str]
    branch_status: str


class CodeBranchService:
    @staticmethod
    def _build_registry(workspace: CodeWorkspace, role: str, timeout_sec: int, max_read_bytes: int, max_write_bytes: int) -> CodeToolRegistry:
        guard = WorkspaceGuard(
            workspace.worktree_root,
            max_read_bytes=max_read_bytes,
            max_write_bytes=max_write_bytes,
        )
        return CodeToolRegistry(workspace_guard=guard, role=role, safe_bash_timeout_sec=timeout_sec)

    @staticmethod
    def _extract_first_match(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_ahead_behind(output: str) -> tuple[int | None, int | None]:
        match = re.search(r"ahead (\d+)", output)
        ahead = int(match.group(1)) if match else 0
        match = re.search(r"behind (\d+)", output)
        behind = int(match.group(1)) if match else 0
        return ahead, behind

    @staticmethod
    def summarize_branch_status(*, success: bool, is_dirty: bool, behind_count: int | None) -> str:
        if not success:
            return "degraded"
        if is_dirty:
            return "dirty"
        if behind_count and behind_count > 0:
            return "stale"
        return "clean"

    @classmethod
    async def refresh_branch_state(
        cls,
        db: AsyncSession,
        *,
        workspace: CodeWorkspace,
        branch_name: str,
        role: str,
        safe_bash_timeout_sec: int,
        max_read_bytes: int,
        max_write_bytes: int,
    ) -> CodeBranchState:
        registry = cls._build_registry(
            workspace,
            role,
            safe_bash_timeout_sec,
            max_read_bytes,
            max_write_bytes,
        )

        status_result = registry.execute_git_status()
        diff_result = registry.execute_git_diff_summary()

        head_result = registry.execute_safe_bash("git rev-parse HEAD")
        base_result = registry.execute_safe_bash(f"git rev-parse {workspace.base_branch}")
        merge_base_result = registry.execute_safe_bash(f"git merge-base {branch_name} {workspace.base_branch}")
        ahead_behind_result = registry.execute_safe_bash(
            f"git rev-list --left-right --count {branch_name}...{workspace.base_branch}"
        )

        is_dirty = bool(diff_result.output.strip()) if diff_result.success else False
        ahead_count: int | None = None
        behind_count: int | None = None
        if ahead_behind_result.success:
            parts = ahead_behind_result.output.strip().split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                ahead_count = int(parts[0])
                behind_count = int(parts[1])
            else:
                ahead_count, behind_count = cls._parse_ahead_behind(status_result.output)

        branch_status = cls.summarize_branch_status(
            success=status_result.success,
            is_dirty=is_dirty,
            behind_count=behind_count,
        )

        result = await db.execute(
            select(CodeBranchState).where(
                CodeBranchState.workspace_id == workspace.id,
                CodeBranchState.branch_name == branch_name,
            )
        )
        branch_state = result.scalar_one_or_none()
        if branch_state is None:
            branch_state = await cls._get_or_create_branch_state(
                db,
                workspace_id=workspace.id,
                branch_name=branch_name,
                base_branch=workspace.base_branch,
            )

        branch_state.base_branch = workspace.base_branch
        branch_state.head_commit = head_result.output.strip() if head_result.success else None
        branch_state.base_commit = base_result.output.strip() if base_result.success else None
        branch_state.merge_base_commit = merge_base_result.output.strip() if merge_base_result.success else None
        branch_state.is_dirty = is_dirty
        branch_state.is_stale_against_base = bool(behind_count and behind_count > 0)
        branch_state.ahead_count = ahead_count
        branch_state.behind_count = behind_count
        branch_state.branch_status = branch_status
        await db.flush()
        return branch_state

    @staticmethod
    async def _get_or_create_branch_state(
        db: AsyncSession,
        *,
        workspace_id: int,
        branch_name: str,
        base_branch: str,
    ) -> CodeBranchState:
        dialect_name = db.bind.dialect.name if db.bind is not None else ""
        values = {
            "workspace_id": workspace_id,
            "branch_name": branch_name,
            "base_branch": base_branch,
        }

        if dialect_name == "sqlite":
            stmt = sqlite_insert(CodeBranchState).values(**values).on_conflict_do_nothing(
                index_elements=["workspace_id", "branch_name"]
            )
            await db.execute(stmt)
        elif dialect_name == "postgresql":
            stmt = pg_insert(CodeBranchState).values(**values).on_conflict_do_nothing(
                index_elements=["workspace_id", "branch_name"]
            )
            await db.execute(stmt)
        else:
            branch_state = CodeBranchState(**values)
            db.add(branch_state)
            await db.flush()
            return branch_state

        result = await db.execute(
            select(CodeBranchState).where(
                CodeBranchState.workspace_id == workspace_id,
                CodeBranchState.branch_name == branch_name,
            )
        )
        return result.scalar_one()

    @staticmethod
    def summarize_branch_readiness(branch_state: CodeBranchState) -> BranchReadiness:
        blocking_reasons: list[str] = []
        readiness = "ready"

        if branch_state.branch_status == "degraded":
            readiness = "degraded"
            blocking_reasons.append("git_runtime_unavailable")
        if branch_state.is_stale_against_base:
            readiness = "needs_recovery"
            blocking_reasons.append("stale_branch")
        if branch_state.is_dirty:
            readiness = "blocked"
            blocking_reasons.append("dirty_workspace")
        if branch_state.branch_status == "clean" and not blocking_reasons:
            readiness = "merge_ready"

        return BranchReadiness(
            readiness=readiness,
            blocking_reasons=blocking_reasons,
            branch_status=branch_state.branch_status,
        )
