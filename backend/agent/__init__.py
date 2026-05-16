"""BOS Agent — independent LangGraph service (Phase A target).

This package is a SKELETON only. No business logic yet. Phase A will
fill in the actual LangGraph ``StateGraph``, the node implementations,
and the HTTP server.

Runtime model:
  - Independent process (port 8001).
  - Communicates with BOS Core (FastAPI, port 8000) over HTTP.
  - MUST NOT import ``app.*`` (BOS Core internals). Every Core
    dependency goes through the public HTTP API.

To import this package, run from the ``backend/`` directory so the
top-level package name resolves as ``agent`` (mirrors the existing
``app`` package convention).
"""
