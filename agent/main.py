"""BOS Agent service entry — Phase B B4 Step 2 (skeleton only).

FastAPI app on port 8001 (backend stays on 8000 per Plan v2 §3).
Step 2 ship: healthcheck only. Step 3-5 will add the LangGraph
runtime, the five causal nodes, the router, and the render node.

Run (Phase B / Phase G dev):
    uvicorn agent.main:app --host 0.0.0.0 --port 8001 --reload

The isolation gate (Plan v2 §7 #3, ``test_isolation.py``) requires
that no module under ``agent/`` imports from ``app.*``. This module
imports only stdlib + FastAPI + the agent's own packages.
"""

from __future__ import annotations

from fastapi import FastAPI

# Agent version is independent of the backend's
# ``CAUSAL_ENGINE_VERSION`` because the agent is a separate service
# with its own deployment cadence. The first ship (Step 2 skeleton)
# is 0.1.0; Step 8 may bump alongside an optional ``v0.9.1-agent``
# git tag.
AGENT_VERSION = "0.1.0"


app = FastAPI(
    title="BOS Agent",
    description=(
        "BOS Platform agent service. Wraps the backend's "
        "/api/v1/causal/* endpoints in a LangGraph causal subgraph "
        "exposed over a single chat-style endpoint. Phase B B4 "
        "Step 2 ship is skeleton only — graph wiring + node logic "
        "follow in Steps 3-5."
    ),
    version=AGENT_VERSION,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe. Returns a constant payload."""
    return {"status": "ok", "service": "bos-agent", "version": AGENT_VERSION}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    """Readiness probe. Step 2 skeleton always reports ready —
    the graph runtime isn't wired up yet so there's nothing
    asynchronous to wait for. Step 3+ will replace this with a
    real check that the backend's /api/v1/causal/* endpoints are
    reachable via the configured httpx client.
    """
    return {"status": "ready", "service": "bos-agent", "version": AGENT_VERSION}
