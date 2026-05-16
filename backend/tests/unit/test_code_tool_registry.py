from pathlib import Path

from app.services.code.tool_registry import CodeToolRegistry, resolve_git_executable
from app.services.code.workspace_guard import WorkspaceGuard


def build_registry(tmp_path: Path) -> CodeToolRegistry:
    guard = WorkspaceGuard(str(tmp_path), max_read_bytes=1024, max_write_bytes=1024)
    return CodeToolRegistry(workspace_guard=guard, role="operator", safe_bash_timeout_sec=5)


def test_execute_safe_bash_rejects_unsafe_command(tmp_path: Path):
    registry = build_registry(tmp_path)

    result = registry.execute_safe_bash("rm -rf .")

    assert result.success is False
    assert result.denied_reason == "unsafe_command"
    assert result.exit_code is None


def test_execute_safe_bash_reports_missing_git(tmp_path: Path, monkeypatch):
    registry = build_registry(tmp_path)
    monkeypatch.setattr("app.services.code.tool_registry.resolve_git_executable", lambda: None)

    result = registry.execute_safe_bash("git status")

    assert result.success is False
    assert result.exit_code == 127
    assert result.output == "git executable was not detected. Configure BOS_CODE_GIT_EXECUTABLE or install Git."


def test_resolve_git_executable_prefers_configured_path(tmp_path: Path, monkeypatch):
    git_executable = tmp_path / "git.exe"
    git_executable.write_text("", encoding="utf-8")
    monkeypatch.setattr("app.services.code.tool_registry.settings.BOS_CODE_GIT_EXECUTABLE", str(git_executable))
    monkeypatch.setattr("app.services.code.tool_registry.shutil.which", lambda name: None)
    monkeypatch.setattr("app.services.code.tool_registry.os.environ", {}, raising=False)

    resolved = resolve_git_executable()

    assert resolved == str(git_executable)


def test_translate_command_maps_windows_aliases(monkeypatch):
    monkeypatch.setattr("app.services.code.tool_registry.os.name", "nt")

    assert CodeToolRegistry._translate_command("pwd") == "cd"
    assert CodeToolRegistry._translate_command("ls src") == "dir src"
