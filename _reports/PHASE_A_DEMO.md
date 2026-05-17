# Phase A — Two-Process Demo (Batch A5)

> Phase A acceptance criteria (Plan v2 §7) reached on **2026-05-17**.
> This doc records the demo paths and the artefact references.

## What "demo" means here

Two real OS processes, real TCP between them:

- **bos-core** on port 8000 — FastAPI app from `backend/app/main.py`,
  exposes the 5 V5 endpoints `/api/v1/{ser,sfi,relay,mc,twin}/...`.
- **bos-agent** on port 8001 — LangGraph service from
  `backend/agent/main.py`, exposes `POST /agent/runs`. The agent's
  shared `httpx.AsyncClient` is configured by `BOS_CORE_URL` and never
  imports `app.*` (Plan v2 §3.4, enforced by
  `agent/tests/test_isolation.py`).

There are **two paths** to bring this stack up:

| Path | Command | Pre-reqs |
|---|---|---|
| A. **No-Docker** (recommended for local dev) | `python backend/scripts/phase_a_two_process_demo.py` | Python 3.11+ with `backend/requirements.txt` and `backend/agent/requirements.txt` installed |
| B. **Docker Compose** | `docker compose -f docker-compose.phase-a.yml up --build` | Docker Desktop |

Both paths converge on the same observable behaviour:
`curl http://localhost:<agent-port>/agent/health` → `200 ok` and
`POST /agent/runs` → markdown report.

---

## Path A — No-Docker demo

### Run

```bash
cd backend
python scripts/phase_a_two_process_demo.py \
    --core-port 8910 \
    --agent-port 8911
```

### What the script does

1. Bootstraps an isolated SQLite at
   `runtime/_archive/phase_a_demo.db` and seeds one operator user +
   tenant.
2. Mints a JWT for that operator via Core's own
   `app.routers.auth.create_access_token`.
3. Launches uvicorn for `app.main:app` on the chosen Core port.
4. Launches `python -m agent.main` on the chosen Agent port with
   `BOS_CORE_URL=http://127.0.0.1:<core-port>/api/v1`.
5. Polls `/api/v1/health/live` and `/agent/health` until both are 200.
6. Direct Core call: `POST /api/v1/ser/compute` with the operator JWT
   → asserts `ser_point` is a float and prints it.
7. Agent run: `POST /agent/runs` with `{"message":"hello operator"}`
   → asserts `intent == "smalltalk"` and prints the report excerpt.
8. Cleanly terminates both subprocesses, leaves logs at
   `runtime/_archive/phase_a_demo_{core,agent}.log`.

### Observed output (2026-05-17 dry run)

```
[demo] bootstrapping isolated DB at runtime/_archive/phase_a_demo.db
[demo] operator JWT minted (205 chars)
[demo] launching Core on :8910
[demo] launching Agent on :8911
[demo] Core healthy at http://127.0.0.1:8910
[demo] Agent healthy at http://127.0.0.1:8911
[demo] direct Core ser_point = 0.25
[demo] agent run intent = smalltalk
[demo] agent run report excerpt = "## BOS Agent run summary\n- **Intent**: `smalltalk`"

=== Phase A two-process demo summary ===
Core URL    : http://127.0.0.1:8910
Agent URL   : http://127.0.0.1:8911
Direct SER  : 0.25
Agent run   : intent='smalltalk', thread='run-084d4e956b51'
DB          : runtime/_archive/phase_a_demo.db
Core log    : runtime/_archive/phase_a_demo_core.log
Agent log   : runtime/_archive/phase_a_demo_agent.log
```

### Why the agent demo uses a smalltalk prompt instead of an SER prompt

The agent's HTTP tool layer does not yet forward an operator bearer
token to Core. The 5 Phase A V5 endpoints sit behind
`require_minimum_role("operator")`. Two safe paths:

1. **Smalltalk path** (what the script uses today) — `router_node` →
   `render_node` → markdown. No Core call required; exercises the
   StateGraph, the FastAPI server, and the markdown renderer
   end-to-end across two processes.
2. **Direct Core path** — script makes the SER call directly with the
   minted JWT to demonstrate that Core compute works end-to-end.

The full agent → authenticated Core round-trip is captured **in
process** by `tests/e2e/test_phase_a_e2e.py::test_ser_value_matches_direct_core_call`
(via `ASGITransport` with the operator headers attached to the
client); the cross-process variant only needs the bearer-forwarding
to be wired, which is Phase A6 work (frontend forwards user JWT to
agent, agent forwards it to Core).

---

## Path B — Docker Compose

### Files

| File | Role |
|---|---|
| `docker-compose.phase-a.yml` | 2-service stack (bos-core, bos-agent), shared bridge network, healthchecks |
| `backend/Dockerfile` | Core image (existed pre-A5; multi-stage Python 3.11) |
| `backend/agent/Dockerfile` | Agent image (new in A5; multi-stage Python 3.11 + agent reqs) |

### Run

```bash
docker compose -f docker-compose.phase-a.yml up --build
```

Then in another terminal:

```bash
curl http://localhost:8001/agent/health
# → {"status":"ok","service":"bos-agent","version":"A.3",...}

curl -X POST http://localhost:8001/agent/runs \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
# → markdown report
```

The agent container picks up `BOS_CORE_URL=http://bos-core:8000/api/v1`
from the compose file and uses Docker's service DNS to find Core.

### Image layout

- **bos-core image** copies `backend/app`, `backend/alembic`,
  `backend/scripts`, `backend/requirements.txt`. Pre-existing —
  unchanged in A5.
- **bos-agent image** copies **only** `backend/agent`. Refusing to
  copy `backend/app` into the agent image is a second layer of
  enforcement on the architectural isolation rule.

### Healthchecks

Both services declare a `HEALTHCHECK` so `docker compose ps` reports
status. `bos-agent` declares `depends_on: { bos-core: condition:
service_healthy }` so the agent only starts once Core is reachable.

---

## Plan v2 §7 acceptance matrix

| # | Check | How verified | Status |
|---|---|---|---|
| 1 | BOS Core boots | Demo script: `/api/v1/health/live` returns 200 inside 30 s | ✅ |
| 2 | BOS Agent boots | Demo script: `/agent/health` returns 200 inside 30 s | ✅ |
| 3 | Agent does NOT import `app.*` | `agent/tests/test_isolation.py` greps the agent tree | ✅ |
| 4 | Direct Core SER call returns a number | Demo script: `direct_ser=0.25` | ✅ |
| 5 | End-to-end agent chat returns markdown | Demo script: agent run intent=smalltalk + report excerpt | ✅ |
| 6 | V1 frontend still works | (Phase A6) — V1 page unchanged since Phase 0.5 | ⏸ pending A6 |
| 7 | V2 frontend wired | (Phase A6) — V2 stub currently posts to `/agent/runs` placeholder | ⏸ pending A6 |
| 8 | OpenAPI snapshot stable | `tests/contract/test_phase_a_openapi.py` (17 tests) | ✅ |
| 9 | Phase 0.5 backend invariants hold | 230-test regression PASS (Phase A + Phase 0.5) | ✅ |

7 of 9 reached at A5 close. Remaining 2 (frontend V2 wire-up) move to
A6.

---

## Artefacts

| Path | Purpose |
|---|---|
| `docker-compose.phase-a.yml` | Two-service Docker stack |
| `backend/agent/Dockerfile` | Agent runtime image |
| `backend/scripts/phase_a_two_process_demo.py` | No-Docker subprocess demo |
| `runtime/_archive/phase_a_demo.db` | Isolated demo SQLite (auto-created) |
| `runtime/_archive/phase_a_demo_core.log` | Uvicorn log from last demo run |
| `runtime/_archive/phase_a_demo_agent.log` | Agent log from last demo run |
| `tests/e2e/test_phase_a_e2e.py` | In-process hermetic version of the same flow (9 tests) |

---

## A6 — Frontend V2 wired up (2026-05-18)

The V2 stub at `frontend/src/pages/BOSAssistantV2Page.tsx` is now a
real chat surface that POSTs to the BOS Agent.

### Artefacts

| File | Role |
|---|---|
| `frontend/src/pages/BOSAssistantV2Page.tsx` (~210 lines) | Chat surface: input + thread state + ToolCallRecord audit drawer + V1 fallback link |
| `frontend/src/api/agentApi.ts` (~80 lines) | Axios client for `/agent/health` + `/agent/runs`, types mirror `agent/server.py` |
| `frontend/vite.config.ts` (+6 lines) | Dev proxy `/agent/*` → `http://localhost:8001` (override with `VITE_AGENT_URL`) |
| `frontend/src/pages/BOSAssistantV2Page.test.tsx` | 9 vitest tests, `renderToStaticMarkup` style (no `@testing-library/react` dep) |

### Browser flow (manual)

```bash
# Terminal 1
cd backend && python -m uvicorn app.main:app --port 8000

# Terminal 2
cd backend && python -m agent.main --port 8001

# Terminal 3
cd frontend && npm run dev
# open http://localhost:5173/bos/v2
```

Vite proxies `/agent/*` to `http://localhost:8001` so the browser
never crosses an origin. V1 remains the default at `/bos`.

### Tests

- `cd frontend && npx vitest run src/pages/BOSAssistantV2Page.test.tsx`
  → **9/9 PASS in 1.18 s**.
- `cd frontend && npm run build` (with `NODE_OPTIONS=--max-old-space-size=8192`)
  → **built in 20.35 s**. `dist/assets/BOSAssistantV2Page-*.js`
  exists alongside V1.

### Scope honesty

V2 chat works for the **smalltalk path** end-to-end (router → render
→ markdown). The SER / SFI / relay / MC / twin paths require the
agent to forward an operator JWT to Core (the 5 V5 endpoints sit
behind `require_minimum_role("operator")`). Today the agent's
`httpx.AsyncClient` does not forward bearer tokens — that wiring
is Phase B work and is documented but not blocking acceptance #7.

### Plan v2 §7 acceptance matrix — final

| # | Check | Status |
|---|---|---|
| 1 | BOS Core boots | ✅ |
| 2 | BOS Agent boots | ✅ |
| 3 | Agent does NOT import `app.*` (runtime + Docker image) | ✅ |
| 4 | Direct Core SER returns a number | ✅ |
| 5 | End-to-end agent chat returns markdown | ✅ |
| 6 | V1 frontend still works | ✅ — V1 bundle in `dist/` unchanged, route `/bos` |
| 7 | V2 frontend wired | ✅ — chat surface at `/bos/v2`, talks to agent via Vite proxy |
| 8 | OpenAPI snapshot stable | ✅ |
| 9 | Phase 0.5 backend invariants hold | ✅ |

**9 / 9 ✅** — Phase A acceptance complete.

---

## What's next (Phase B)

1. Wire bearer-token forwarding through the agent's shared
   `httpx.AsyncClient` so authenticated SER / SFI / relay / MC /
   twin paths work cross-process in the browser. Today's V2 chat
   surface handles the response shape but the agent has no token to
   send.
2. Replace the deterministic keyword router in `agent/nodes/router.py`
   with a true LLM-backed classifier under `ANTHROPIC_API_KEY`.
3. Begin Phase B causal-inference layer (`/api/v1/causal/*` —
   DoWhy / EconML / mediation / DML).
