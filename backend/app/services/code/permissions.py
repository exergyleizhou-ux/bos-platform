"""
Role-aware permission policy for BOS Code.
"""

from dataclasses import dataclass

READ_ONLY_TOOLS = {"read_file", "glob_search", "grep_search", "safe_bash", "git_ops"}
WORKSPACE_WRITE_TOOLS = {"write_file", "edit_file"}


@dataclass(slots=True)
class CodePermissionDecision:
    allowed: bool
    tool_name: str
    permission_mode: str
    reason: str | None = None


class CodePermissionPolicy:
    """Role-to-permission resolver."""

    @staticmethod
    def mode_for_role(role: str) -> str:
        if role == "admin":
            return "danger-full-access"
        if role == "scientist":
            return "workspace-write"
        return "read-only"

    @classmethod
    def evaluate(cls, *, role: str, tool_name: str) -> CodePermissionDecision:
        permission_mode = cls.mode_for_role(role)

        if permission_mode == "danger-full-access":
            return CodePermissionDecision(True, tool_name, permission_mode)

        if permission_mode == "workspace-write":
            if tool_name == "danger_bash":
                return CodePermissionDecision(False, tool_name, permission_mode, "admin_only")
            return CodePermissionDecision(True, tool_name, permission_mode)

        if tool_name in READ_ONLY_TOOLS:
            return CodePermissionDecision(True, tool_name, permission_mode)

        return CodePermissionDecision(False, tool_name, permission_mode, "read_only_mode")
