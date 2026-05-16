# BOS Agent

Independent service running a LangGraph state machine. Phase A target.

## Runtime

- Port: **8001**
- Core dependency: **BOS Core at `http://localhost:8000/api/v1`**
- Process model: separate Python process from BOS Core
- Never imports `app.*` (BOS Core internals). All Core access goes
  through HTTP.

## Launch (Phase A, not yet implemented)

```bash
cd backend
python -m agent.main           # or: uvicorn agent.server:app --port 8001
```

## Phase 0.5 status

Skeleton only. Files in this package contain docstrings and `TODO`
markers — no business logic.

| File | Phase A purpose |
|---|---|
| `graph.py` | LangGraph `StateGraph` definition (router / ser / sfi / relay / cyber_lab / render) |
| `state.py` | Pydantic `AgentState` schema |
| `server.py` | FastAPI HTTP server wrapping the graph |
| `main.py` | `python -m agent.main` entry point |
| `nodes/` | Per-node implementations |
| `tools/` | HTTP tools calling BOS Core API |
| `embodied/a2a_interface.py` | A2A protocol placeholder for PhyAgentOS (Phase 2) |
| `requirements.txt` | langgraph / langchain-core / httpx (NOT installed in Phase 0.5) |
