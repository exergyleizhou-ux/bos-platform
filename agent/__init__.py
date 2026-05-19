"""BOS Agent service — Phase B B4.

Net-new FastAPI service that calls the backend's
/api/v1/causal/* endpoints via httpx. Lives in its own process on
port 8001 (backend stays on 8000).

Plan v2 §7 #3 isolation gate: no module under ``agent/`` may
``import app`` or ``from app.*``. Schemas are mirrored under
``agent/schemas/`` and a parity test
(``agent/tests/test_schema_parity.py``) keeps the mirror in sync.

Step 2 ship: skeleton only — directory structure, ``main.py``
healthcheck app, schema mirror, isolation + parity tests. Steps 3-8
(causal nodes, router, render, full test suite) land in the next
thread per ``_reports/PHASE_B_B4_DESIGN.md`` §3.
"""
