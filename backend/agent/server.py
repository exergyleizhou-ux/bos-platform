"""BOS Agent HTTP server (Phase A target).

Phase A will host the LangGraph runtime as a FastAPI application on
port 8001. Endpoints (planned):

  POST /agent/runs                  → start a new agent run
  GET  /agent/runs/{run_id}         → poll run status
  GET  /agent/runs/{run_id}/events  → stream LangGraph events
  POST /agent/runs/{run_id}/confirm → human-in-the-loop confirmation

The server MUST NOT import ``app.*`` directly; it only consumes BOS
Core via HTTP at ``http://localhost:8000/api/v1``.
"""

# TODO(Phase A): build the FastAPI app
