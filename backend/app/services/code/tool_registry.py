"""
Tool registry and guarded execution helpers for BOS Code.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.services.code.permissions import CodePermissionPolicy
from app.services.code.workspace_guard import WorkspaceGuard

settings = get_settings()

SAFE_BASH_PREFIXES = (
    "pwd",
    "ls",
    "git status",
    "git diff",
    "rg",
    "pytest",
    "ruff",
    "mypy",
    "python -m pytest",
)


def _candidate_git_paths() -> list[str]:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

    candidates = [
        settings.BOS_CODE_GIT_EXECUTABLE,
        shutil.which("git") or "",
        os.path.join(program_files, "Git", "cmd", "git.exe"),
        os.path.join(program_files, "Git", "bin", "git.exe"),
        os.path.join(program_files_x86, "Git", "cmd", "git.exe"),
        os.path.join(program_files_x86, "Git", "bin", "git.exe"),
        os.path.join(local_app_data, "Programs", "Git", "cmd", "git.exe"),
        os.path.join(local_app_data, "Programs", "Git", "bin", "git.exe"),
    ]

    github_desktop_root = Path(local_app_data) / "GitHubDesktop"
    if github_desktop_root.exists():
        candidates.extend(
            str(path)
            for path in sorted(github_desktop_root.glob("app-*/resources/app/git/cmd/git.exe"), reverse=True)
        )

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        normalized = os.path.normpath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def resolve_git_executable() -> str | None:
    for candidate in _candidate_git_paths():
        if os.path.isfile(candidate):
            return candidate
    return None


@dataclass(slots=True)
class ToolExecutionResult:
    tool_name: str
    success: bool
    output: str
    exit_code: int | None = None
    denied_reason: str | None = None


class CodeToolRegistry:
    def __init__(self, *, workspace_guard: WorkspaceGuard, role: str, safe_bash_timeout_sec: int) -> None:
        self.workspace_guard = workspace_guard
        self.role = role
        self.safe_bash_timeout_sec = safe_bash_timeout_sec

    def execute_safe_bash(self, command: str) -> ToolExecutionResult:
        decision = CodePermissionPolicy.evaluate(role=self.role, tool_name="safe_bash")
        if not decision.allowed:
            return ToolExecutionResult("safe_bash", False, "", denied_reason=decision.reason)

        normalized = " ".join(command.strip().split())
        if not normalized or not normalized.startswith(SAFE_BASH_PREFIXES):
            return ToolExecutionResult("safe_bash", False, "", denied_reason="unsafe_command")

        translated_command = self._translate_command(normalized)
        git_executable = resolve_git_executable()

        if git_executable is None and translated_command.startswith("git "):
            return ToolExecutionResult(
                "safe_bash",
                False,
                "git executable was not detected. Configure BOS_CODE_GIT_EXECUTABLE or install Git.",
                exit_code=127,
            )
        if git_executable is not None and translated_command.startswith("git "):
            translated_command = f'"{git_executable}" {translated_command[4:]}'

        completed = subprocess.run(
            translated_command,
            shell=True,
            cwd=self.workspace_guard.worktree_root,
            timeout=self.safe_bash_timeout_sec,
            env=self._sanitized_env(),
            capture_output=True,
            text=True,
        )
        output = (completed.stdout + completed.stderr)[:12000]
        return ToolExecutionResult("safe_bash", completed.returncode == 0, output, completed.returncode)

    def execute_git_status(self) -> ToolExecutionResult:
        result = self.execute_safe_bash("git status --short --branch")
        return ToolExecutionResult(
            tool_name="git_ops",
            success=result.success,
            output=result.output,
            exit_code=result.exit_code,
            denied_reason=result.denied_reason,
        )

    def execute_git_diff_summary(self) -> ToolExecutionResult:
        result = self.execute_safe_bash("git diff --stat")
        return ToolExecutionResult(
            tool_name="git_ops",
            success=result.success,
            output=result.output,
            exit_code=result.exit_code,
            denied_reason=result.denied_reason,
        )

    def _sanitized_env(self) -> dict[str, str]:
        allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "COMSPEC", "WINDIR", "HOME", "USERPROFILE", "TMP", "TEMP"}
        return {key: value for key, value in os.environ.items() if key.upper() in allowed}

    @staticmethod
    def _translate_command(command: str) -> str:
        if os.name != "nt":
            return command

        alias_map = {
            "pwd": "cd",
            "ls": "dir",
        }
        for alias, replacement in alias_map.items():
            if command == alias:
                return replacement
            if command.startswith(f"{alias} "):
                return command.replace(alias, replacement, 1)
        return command
