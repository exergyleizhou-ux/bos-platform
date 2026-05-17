"""Architecture isolation: backend/agent MUST NOT import ``app.*``.

Plan v2 paragraph 3.4 calls this the hard isolation rule. A grep over
the agent tree must produce zero hits. If a future commit introduces a
``from app.something import x`` (e.g. a quick shortcut to reuse a Core
helper), this test fails the build before it lands.
"""

from __future__ import annotations

import re
from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parent.parent


_FORBIDDEN_PATTERNS = (
    re.compile(r"^\s*from\s+app\.", re.MULTILINE),
    re.compile(r"^\s*import\s+app\.", re.MULTILINE),
    re.compile(r"^\s*import\s+app\b", re.MULTILINE),
)


def test_agent_does_not_import_app_module():
    """Scan runtime code only. The ``agent/tests/`` directory is exempt
    because ``test_schema_parity.py`` intentionally imports both sides
    to compare SCHEMA_VERSION constants (see Plan v2 paragraph 3.4)."""
    offenders: list[tuple[str, int, str]] = []
    for py in AGENT_DIR.rglob("*.py"):
        # Skip __pycache__ and the tests directory itself.
        if "__pycache__" in py.parts:
            continue
        if "tests" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        for pat in _FORBIDDEN_PATTERNS:
            for match in pat.finditer(text):
                line_no = text[: match.start()].count("\n") + 1
                line = text.splitlines()[line_no - 1]
                offenders.append((str(py.relative_to(AGENT_DIR)), line_no, line.strip()))

    assert not offenders, (
        "backend/agent must not import app.* (Plan v2 paragraph 3.4 isolation):\n"
        + "\n".join(f"  {p}:{ln}: {src}" for p, ln, src in offenders)
    )


def test_agent_dir_layout_phase_a_ready():
    """Required Phase A files exist at expected paths."""
    expected = [
        "__init__.py",
        "README.md",
        "requirements.txt",
        "llm.py",
        "persistence.py",
        "state.py",
        "graph.py",
        "server.py",
        "main.py",
        "schemas/__init__.py",
        "schemas/ser.py",
        "schemas/sfi.py",
        "schemas/relay.py",
        "schemas/mc.py",
        "schemas/twin.py",
        "tools/__init__.py",
        "tools/client.py",
        "tools/ser.py",
        "tools/sfi.py",
        "tools/relay.py",
        "tools/mc.py",
        "tools/twin.py",
        "nodes/__init__.py",
        "nodes/router.py",
        "nodes/ser.py",
        "nodes/sfi.py",
        "nodes/relay.py",
        "nodes/cyber_lab.py",
        "nodes/render.py",
    ]
    missing = [rel for rel in expected if not (AGENT_DIR / rel).exists()]
    assert not missing, f"missing Phase A files: {missing}"
