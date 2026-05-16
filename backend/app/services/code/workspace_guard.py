"""
Workspace boundary enforcement for BOS Code.
"""

from pathlib import Path


class WorkspaceGuardError(ValueError):
    """Raised when a path escapes the tenant workspace."""


class WorkspaceGuard:
    def __init__(self, worktree_root: str, *, max_read_bytes: int, max_write_bytes: int) -> None:
        self.worktree_root = Path(worktree_root).resolve()
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes

    def resolve_path(self, relative_path: str) -> Path:
        candidate = (self.worktree_root / relative_path).resolve()
        if self.worktree_root not in candidate.parents and candidate != self.worktree_root:
            raise WorkspaceGuardError(f"path escapes workspace: {relative_path}")
        return candidate

    def assert_readable(self, relative_path: str) -> Path:
        candidate = self.resolve_path(relative_path)
        if candidate.is_dir():
            raise WorkspaceGuardError(f"path is a directory: {relative_path}")
        if candidate.exists() and candidate.stat().st_size > self.max_read_bytes:
            raise WorkspaceGuardError(f"file exceeds read limit: {relative_path}")
        return candidate

    def assert_writable(self, relative_path: str, *, content_size: int) -> Path:
        if content_size > self.max_write_bytes:
            raise WorkspaceGuardError(f"content exceeds write limit: {relative_path}")
        candidate = self.resolve_path(relative_path)
        if candidate.exists() and candidate.is_dir():
            raise WorkspaceGuardError(f"path is a directory: {relative_path}")
        return candidate
