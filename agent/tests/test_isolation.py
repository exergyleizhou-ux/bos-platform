"""Agent isolation gate (Plan v2 §7 #3).

AST-walks every ``.py`` module under ``agent/`` and asserts none of
them import from ``app.*``. The agent service is independent of the
backend; it talks to the backend strictly over HTTP via ``httpx``
(Step 3+ ship). The schema parity test
(``test_schema_parity.py``) keeps the mirrored types in sync without
violating this rule.

If this gate fires, the offending file is reported with the exact
import line. Either:

- mirror the type into ``agent/schemas/...`` and import from there, OR
- if the type doesn't belong in the agent surface, drop the import
  entirely.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


AGENT_ROOT = Path(__file__).resolve().parent.parent
# Resolve to ``<repo>/agent``.


def _iter_agent_modules() -> list[Path]:
    """Every ``.py`` under ``agent/``, excluding ``__pycache__``."""
    return sorted(
        p for p in AGENT_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _imports_app(tree: ast.AST) -> list[ast.AST]:
    """Return every ImportFrom / Import node that references ``app``."""
    offenders: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and (
                node.module == "app" or node.module.startswith("app.")
            ):
                offenders.append(node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app" or alias.name.startswith("app."):
                    offenders.append(node)
                    break
    return offenders


@pytest.mark.parametrize("module_path", _iter_agent_modules())
def test_agent_module_does_not_import_app(module_path: Path) -> None:
    """Each agent module must not depend on ``app.*``."""
    source = module_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(module_path))
    except SyntaxError as exc:
        pytest.fail(
            f"agent module {module_path} could not be parsed: {exc}"
        )
    offenders = _imports_app(tree)
    if offenders:
        details = []
        for node in offenders:
            if isinstance(node, ast.ImportFrom):
                line = f"from {node.module} import ..."
            else:
                names = ", ".join(a.name for a in node.names)
                line = f"import {names}"
            details.append(f"  line {node.lineno}: {line}")
        joined = "\n".join(details)
        pytest.fail(
            f"agent module {module_path.relative_to(AGENT_ROOT.parent)} "
            f"imports from app.*:\n{joined}\n"
            f"Mirror the needed type under agent/schemas/... or drop "
            f"the import. See agent/tests/test_schema_parity.py for "
            f"the mirror contract."
        )


def test_isolation_test_discovered_agent_modules() -> None:
    """Meta-check: the AST walker actually found agent modules so the
    parametrised test above isn't silently empty (which would yield a
    misleading 0-fail green)."""
    modules = _iter_agent_modules()
    assert len(modules) >= 5, (
        f"expected at least 5 agent .py modules; found {len(modules)}: "
        f"{[m.name for m in modules]}"
    )
