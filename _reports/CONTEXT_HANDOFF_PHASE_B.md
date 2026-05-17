# BOS Platform — Phase B Handoff Package

> Self-contained context dump. A new conversation thread (and a new
> strategy LLM) should be able to read **only this file** and pick up
> Phase B work without losing anything.
>
> Generated 2026-05-18. HEAD = `82b619d` on branch
> `chat/bos-v9-stabilize-files`.

---

## Section 1 — Project in one paragraph

**BOS Platform** (Biological Operating System) is an audit-oriented
software stack for **staged bioconversion of heterogeneous organic
wastes**. It pairs (a) a FastAPI-based compute core that exposes the
paper's five core operations as typed HTTP endpoints and (b) an
independent LangGraph-based agent service that orchestrates those
endpoints into operator-visible workflows.

**Current phase**: **Phase A complete (2026-05-17)**. Five V5 APIs +
agent skeleton + cross-process demo + V2 frontend chat surface are
all live. **Next stop: Phase B — causal inference layer** (DoWhy /
EconML / mediation / DML).

**Ultimate goal** (5-year horizon): "BOS Agent + public API" — a
production-deployed bio-process intelligence service that the
paper's audience can call from notebooks and dashboards, with
explicit evidence levels (validated / supported / planned) on every
result and a release-gate audit trail behind every public number.

---

## Section 2 — Repository layout + key commands

| Item | Value |
|---|---|
| **Project root** | `C:\Users\10420\Desktop\bos 0506\bos v9\bos-pipeline-reconciled\` |
| **OS** | Windows 11 (Bash shell available; PowerShell also works) |
| **git HEAD** | `82b619de22c02497f7ad4ea0e9d51698c2e4bcbb` |
| **git branch** | `chat/bos-v9-stabilize-files` |
| **commits on top of `d7b72e1` baseline** | **28** (Phase 0.5: 22, Phase A: 6) |

### Top-level subdirectories

| Path | Purpose |
|---|---|
| `backend/app/` | BOS Core — FastAPI app (engines, routers, schemas, services, alembic migrations) |
| `backend/agent/` | BOS Agent — LangGraph service. **Hard rule: zero `from app.*`** (enforced by `agent/tests/test_isolation.py`) |
| `backend/tests/{unit,integration,contract,e2e}/` | Test suite (230 tests) |
| `frontend/src/` | React + Vite UI. V1 `/bos`, V2 `/bos/v2` |
| `_reports/` | Design / decision / acceptance artefacts (this file lives here) |
| `runtime/_archive/` | Demo logs + isolated demo DB (gitignored) |
| `.agents/` | Skill / runtime metadata (mostly untracked) |
| `reports/`, `BOS_*.md` | Phase 0 process artefacts (mostly untracked, intentionally) |

### Key commands

```bash
# Backend Core
cd backend
python -m uvicorn app.main:app --port 8000

# Backend Agent (separate process)
cd backend
python -m agent.main --port 8001
# requires BOS_CORE_URL=http://localhost:8000/api/v1

# Full Phase A regression (backend)
cd backend
python -m pytest tests/ agent/tests/ -q
# 230 tests; full run ~56 s

# Frontend dev server
cd frontend
npm run dev
# Vite proxy /api -> :8000 and /agent -> :8001

# Frontend production build (Node 24 OOM workaround)
cd frontend
NODE_OPTIONS=--max-old-space-size=8192 npm run build

# Frontend tests
cd frontend
npx vitest run

# No-Docker cross-process demo
cd backend
python scripts/phase_a_two_process_demo.py --core-port 8910 --agent-port 8911

# Docker compose stack
docker compose -f docker-compose.phase-a.yml up --build
```

---

## Section 3 — Completed work snapshot

### Phase 0.5 (22 commits, cleanup + decisions)

| Hash | Title |
|---|---|
| `7a08e5f` | Phase 0.5: cleanup + 5 decisions applied (backend slice) |
| `be92860` | chore: ASCII-ify mojibake headers + drop dead build configs |
| `814d36b` | fix: backend baseline catch-up |
| `7ad17e7` | fix: frontend baseline catch-up |
| `831aa52` | fix: infra baseline catch-up |
| `a18fb52` | chore: gitignore remotion-runtime/ + .tsbuildinfo artifacts |
| `2d71ee0` | chore: add optional native-model / MinerU requirements files |
| `96b4a02` | chore: gitignore backend dev artifacts + ML model weights |
| `d21f217` | feat: backend baseline — typed schemas + BOS models |
| `909ba7d` | feat: backend baseline — Alembic migrations |
| `9c799f2` | feat: backend baseline — BOS core routers |
| `561b9fb` | feat: backend baseline — infrastructure modules |
| `f62fb77` | feat: backend baseline — developer scripts |
| `a0f65eb` | feat: backend baseline — BOS V1 services |
| `ea9bc97` | feat: backend baseline — Code Cockpit subsystem (deferred) |
| `9586586` | test: backend baseline test suite |
| `b86db81` | feat: BOS frontend baseline — core implementation |
| `8a44e12` | feat: BOS V1 assistant implementation |
| `c9ec026` | feat: immersive login scene (Three.js + MediaPipe gestures) |
| `152c7b9` | feat: BOS frontend baseline — Code Cockpit subsystem (deferred) |
| `c7a4809` | test: BOS frontend baseline test suite |
| `2e9dd69` | feat: BOS Assistant V1/V2 dual-track routing |

**Distribution**: 17 backend / 5 frontend commits.

**5 Phase 0.5 decisions** (the originals that made A possible):

1. **MetaPathFinder for engine alias** — Phase 0.5 moved 43 engines
   into `engine/core/` + `engine/extended/`. Rather than rewriting
   every caller's `from app.engine.X` import, a `sys.meta_path`
   finder redirects legacy names to their new homes. All 5 Phase A
   API engines benefit from this — they live under `engine/core/`
   but legacy code still works.
2. **Frontend-/Backend- separation hardened** — Phase 0.5 committed
   the V9 baseline cleanly so Phase A could add the V5 layer on top
   without churn.
3. **V1/V2 dual-track routing** — Phase 0.5 introduced the
   `BOSAssistantV1Page` / `BOSAssistantV2Page` split. V1 is the
   working operator surface; V2 became the Phase A landing pad.
4. **A2A placeholder** — `backend/agent/embodied/a2a_interface.py`
   was stubbed for Phase 2 embodied-agent integration (PhyAgentOS).
   Not in scope for Phase B.
5. **Code Cockpit deferred** — the AI-coding subsystem
   (`backend/app/{services,routers}/code*`, `frontend/src/components/code/`)
   was kept in tree but flagged for separate evaluation. Phase B
   does not touch it.

### Phase A (6 commits, the V5 contract + agent)

| Hash | Batch | Title |
|---|---|---|
| `6888fae` | **A1** | feat: Phase A1 — five core V5 APIs with strict schemas |
| `4129803` | **A2** | feat: Phase A2 — OpenAPI snapshot + 17 contract tests |
| `2be3737` | **A3** | feat: Phase A3 — LangGraph Agent skeleton |
| `eab7ac4` | **A4** | feat: Phase A4 — Agent <-> Core hermetic e2e integration |
| `c3a8709` | **A5** | feat: Phase A5 — docker-compose demo + cross-process verification |
| `82b619d` | **A6** | feat: Phase A6 — V2 frontend wired to LangGraph Agent |

#### A1 — Five V5 APIs (190 tests)

| Endpoint | Tests | Paper map |
|---|---|---|
| `POST /api/v1/ser/compute` | 37 | Eq. 1-3, 7 |
| `POST /api/v1/sfi/check` | 36 | Eq. 5-6 + k_decay band |
| `POST /api/v1/relay/simulate` | 40 | M1 → M2 → M3 + mass_balance |
| `POST /api/v1/mc/propagate` | 38 | Generic propagate() |
| `POST /api/v1/twin/run` | 39 | Stateless EKF |

Schemas: strict Pydantic with `@model_validator` (mass/N
conservation, k_decay band order, observation-length alignment,
3-stage ledger). Legacy stateful twin endpoints carry
`deprecated=True` + sunset 2027-05-17.

#### A2 — OpenAPI freeze (17 contract tests)

`_reports/phase_a_openapi_snapshot.json` (82 KB, 8 paths, 40
transitive schemas). Drift detection on request/response property
keys + required lists + numeric ranges + Literal sets.

#### A3 — LangGraph Agent skeleton (14 agent tests)

Independent FastAPI process on port 8001:

- `BOSState` TypedDict (~26 fields).
- 6 async nodes: `router / ser / sfi / relay / cyber_lab / render`.
- Shared `httpx.AsyncClient`; `set_client()` injector.
- `get_chat_model(role)` factory; default `claude-sonnet-4-5`.
- `get_checkpointer()` factory; Phase A = `InMemorySaver`.
- Zero `from app.*` (grep gate + Docker image only COPYs
  `backend/agent/`).

#### A4 — Hermetic e2e (9 e2e tests)

`tests/e2e/test_phase_a_e2e.py` runs both services in-process via
`httpx.ASGITransport` over Core's FastAPI app. Numerical consistency
agent vs direct Core ≤ 1e-6. Cyber-lab parallel branches via
`asyncio.gather`. Error injection (Core 422 → Agent graceful).

#### A5 — Cross-process demo

- `docker-compose.phase-a.yml` — 2 services with healthchecks.
- `backend/agent/Dockerfile` — multi-stage, only COPYs
  `backend/agent/`.
- `backend/scripts/phase_a_two_process_demo.py` — no-Docker
  subprocess demo. Real run 2026-05-17:
  `Core healthy at :8910, ser_point = 0.25; Agent healthy at :8911,
  intent = smalltalk`.

#### A6 — V2 frontend chat (9 vitest)

- `frontend/src/pages/BOSAssistantV2Page.tsx` — full chat UI
  (~220 LoC).
- `frontend/src/api/agentApi.ts` — axios client for `/agent/runs`.
- `frontend/vite.config.ts` — `/agent/*` proxy → `:8001`.
- Build PASS in 20.35 s.

### Phase A summary

| Metric | Value |
|---|---|
| Tests total | **239** (backend 230 + frontend 9) |
| Full regression | ~56 s |
| Plan v2 §7 acceptance | **9 / 9 PASS** |
| Actual effort | **~17.75 h** vs plan **80 h** (efficiency **4.5×**) |

---

## Section 4 — Decisions register (D-series)

### Phase 0.5 — 5 decisions

| ID | Decision | Reasoning |
|---|---|---|
| 0.5/D1 | MetaPathFinder for engine moves | Preserves every legacy `from app.engine.X` import without rewriting callers; moving 43 files cleanly into core/ + extended/ became safe |
| 0.5/D2 | Separate backend/agent later, keep ports clean now | Phase 0.5 didn't create agent code yet, but left the Phase A landing pad coherent |
| 0.5/D3 | V1/V2 dual-track frontend | Operator-visible default stays unchanged; new agent surface gets `/bos/v2` opt-in. Prevents UX regression risk during the agent rollout |
| 0.5/D4 | A2A placeholder for embodied agent | Reserves architecture seat for Phase 2 PhyAgentOS without coding it yet |
| 0.5/D5 | Code Cockpit subsystem deferred | The AI-coding sub-app was preserved untouched — it's not part of the Phase A-G compute roadmap, so explicit "not in scope" prevents drift |

### Phase A — 5 decisions (the live ones for Phase B)

| ID | Decision | Reasoning |
|---|---|---|
| **A/D1** | `/api/v1/*` V5 endpoints **coexist** with legacy endpoints + **explicit sunset** | Two-track + sunset is the only choice that doesn't break the frontend immediately *and* doesn't lock V9 in forever. Sunset schedule: T0+6mo deprecation header, T0+12mo removal |
| **A/D2** | Pydantic schemas **strict** (`ge/le/gt/lt/pattern/examples` + `@model_validator`) | Paper has explicit numeric bounds (`0 ≤ D' ≤ 1`, `k_decay > 0`, `dm_out ≤ dm_in`). Strict schemas reject malformed inputs at the API boundary, before they hit the engine. ~2× schema LoC traded for catch-at-boundary debuggability |
| **A/D3** | State persistence = **in-memory** + `get_checkpointer()` factory abstraction | Phase A doesn't need cross-session state. Factory makes Phase B's Redis/Postgres swap a single env var (`STATE_BACKEND=...`) without graph or node changes |
| **A/D4** | Wire protocol = **HTTP REST + Pydantic** + **mandatory async-from-day-1** | Existing FastAPI surface. No new infra. Synchronous `httpx.post` is forbidden in `backend/agent/` so `cyber_lab_node` can fan out parallel Core calls via `asyncio.gather` |
| **A/D5** | Implementation order = **SER → SFI → Relay → MC → Twin** | SER is the warm-up (most stable engine). SFI is small (envelope check). Relay is multi-engine orchestration. MC is the generic wrapper that re-uses the SER MC plumbing. Twin (EKF) is the most complex, goes last |

**Phase B will likely add D6–D10** (estimator choice, DAG sourcing,
schema strictness for causal types, test strategy for non-deterministic
causal estimates, agent node design). Plan v2 has a placeholder for
these — to be answered during Plan v1 → self-review → Plan v2.

---

## Section 5 — Current architecture state

### BOS Core (port 8000)

**Five V5 endpoints** (all `POST`, all under `/api/v1/`):

| Path | Engine(s) | Paper map | Schema module |
|---|---|---|---|
| `/api/v1/ser/compute` | `engine/core/ser_engine.py` + `monte_carlo_engine.py` | Eq. 1-3, 7 | `schemas/ser.py` (A.1) |
| `/api/v1/sfi/check` | `engine/core/sfi_engine.py` (new in A1) wraps `flight_envelope.py` | Eq. 5-6 | `schemas/sfi.py` (A.2) |
| `/api/v1/relay/simulate` | `engine/core/relay_engine.py` (new in A1) wraps `digital_twin_engine.py` + `kinetics_engine.py` + `mass_balance.py` | M1 → M2 → M3 | `schemas/relay.py` (A.3) |
| `/api/v1/mc/propagate` | `engine/core/monte_carlo_engine.py::propagate()` (added in A1) | Eq. 7 | `schemas/mc.py` (A.4) |
| `/api/v1/twin/run` | `engine/core/digital_twin_engine.py` (predict_step + update_step) | EKF | `schemas/twin.py` (A.5) |

**Engine layout**:
- `backend/app/engine/core/` — 19 paper-core engines + species/feedstock data tables
- `backend/app/engine/extended/` — 23 satellite engines (bayesian, NN surrogate, supervisor, calibration, etc.)
- `backend/app/engine/__init__.py` — MetaPathFinder that redirects `app.engine.<name>` → `app.engine.<core|extended>.<name>`

**Schema versions**: `SCHEMA_VERSION = "A.1" … "A.5"` constants on
each Phase A schema module — used for agent-side parity check.

**Legacy paths with `deprecated=True`** (Plan v2 D1 sunset):
`/api/v1/twin/{twin_id}/{predict,update,simulate}`. Sunset 2027-05-17.

### BOS Agent (port 8001)

**Process model**: independent uvicorn instance.
`BOS_CORE_URL=http://localhost:8000/api/v1` env var configures the
shared `httpx.AsyncClient`.

**LangGraph topology**:

```
START → router_node ─ (conditional edges keyed on intent) ─┐
                                                            ├→ ser_node      → render_node → END
                                                            ├→ sfi_node      → render_node → END
                                                            ├→ relay_node    → render_node → END
                                                            ├→ cyber_lab_node → render_node → END
                                                            └→ render_node                → END
```

**Six nodes** (all `async def`):

| Node | Calls | Owns state keys |
|---|---|---|
| `router_node` | LLM (Claude Sonnet 4.5 default) or keyword fallback | `intent` |
| `ser_node` | `POST /ser/compute` | `ser`, `ser_ci`, `evidence_level` |
| `sfi_node` | `POST /sfi/check` | `sfi_pass`, `sfi_zone` |
| `relay_node` | `POST /relay/simulate` | `simulation_result` |
| `cyber_lab_node` | `asyncio.gather(SER, MC)` | `cyber_experiment` |
| `render_node` | (no HTTP) | `report` |

**Architecture rules**:
- `agent/` runtime code: zero `from app.*` (`agent/tests/test_isolation.py` enforces).
- Docker image: only COPYs `backend/agent/` (no `app/`).
- All tools `async def`; synchronous `httpx.post` forbidden.
- Schema mirrors in `agent/schemas/*.py` carry the same `SCHEMA_VERSION` constants as Core; `agent/tests/test_schema_parity.py` compares them across the boundary.

**Factories** (one-line swap surface for Phase B):

| Factory | Phase A behaviour | Phase B+ extension |
|---|---|---|
| `agent.llm.get_chat_model(role)` | anthropic `claude-sonnet-4-5` | switch via `LLM_PROVIDER`, `LLM_MODEL_*` envs |
| `agent.persistence.get_checkpointer()` | `InMemorySaver` | `STATE_BACKEND=redis|postgres` |
| `agent.tools.client.get_client()` / `set_client()` | new `AsyncClient` per process | tests inject `ASGITransport`; Phase B will inject auth-forwarding default headers |

### Frontend (Vite dev :5173, dist/ via `npm run build`)

| Route | Component | Notes |
|---|---|---|
| `/bos` (default) | `BOSAssistantV1Page.tsx` | wrapper around `components/bos/assistant/BOSAssistantView.tsx` (4 376 LoC). UNCHANGED since Phase 0.5 |
| `/bos/v2` (opt-in) | `BOSAssistantV2Page.tsx` | LangGraph chat UI added in A6 (~220 LoC) |

Vite dev proxies: `/api/*` → `:8000`, `/agent/*` → `:8001` (override with `VITE_AGENT_URL`).

---

## Section 6 — Working mode (humans + LLMs collaboration pattern)

### Roles

| Role | Responsibility |
|---|---|
| **User** | Strategy + decisions + supervision. Does not write code directly. Shapes the code by approving / rejecting plans and decisions. |
| **Claude Code (local CLI)** | Execution. File reads/writes, command runs, git ops, test runs. Operates inside the project directory. |
| **Strategy LLM (this conversation)** | Strategy + design + decision recommendations + plan authoring + adversarial review + commit/test-report auditing |

### Cadence

| Step | Rule |
|---|---|
| 1 | Strategy LLM proposes a batch with explicit scope. |
| 2 | User confirms or amends scope. |
| 3 | Claude Code executes the batch and **stops at the boundary**. Never silently chains into the next batch. |
| 4 | Strategy LLM (or Claude Code) generates a structured report (commit hashes, test counts, decisions taken, open questions). |
| 5 | User reads the report and replies `继续 XX` or course-corrects. |
| 6 | Repeat. |

### Plan / decision pattern (from Phase A)

```
Plan v1 (Claude Code drafts from user spec)
  → Adversarial self-review (Claude Code switches to "senior staff
     engineer not in love with their own work" persona, finds
     ≥1 issue per section + a counter-argument for every
     recommendation in D1–DN)
  → User makes the D-series decisions
  → Plan v2 (Claude Code merges adversarial findings + user
     decisions; assessed at ~96/100 in Phase A)
  → Implementation in batches (each batch stop-and-report)
```

### Hard rules observed in Phase A

- **No scope creep.** Every batch had a written spec; Claude Code did not extend the work beyond it.
- **No silent chaining.** "继续 A6" means start A6, not finish A6 plus dabble in A7.
- **Evidence before claims.** Every "PASS" was backed by a test run; every "OK" was backed by a curl or import smoke.
- **Honesty over polish.** When a check is partial (e.g. cross-process JWT forwarding not done in A6), the DEMO doc says so explicitly.
- **Strict separation of concerns.** Backend changes go in `backend/`, frontend in `frontend/`, design in `_reports/`. Cross-cutting changes are batched per concern.

---

## Section 7 — Required reading on Phase B start

### Must-read (start here, in order)

| Path | Why |
|---|---|
| `_reports/CONTEXT_HANDOFF_PHASE_B.md` | **This document.** |
| `_reports/PHASE_A_PLAN.md` (902 lines, v2 96/100) | The Plan v2 template. **Phase B Plan should follow the same shape.** |
| `_reports/PHASE_A_DEMO.md` | Phase A acceptance evidence + Plan v2 §7 9/9 matrix. Shows the report style users expect. |
| `_reports/PHASE_A_API_FREEZE.md` | API contract + drift workflow. **Phase B will need its own API freeze for `/api/v1/causal/*`.** |

### Reference (open when needed)

| Path | Purpose |
|---|---|
| `_reports/BOS_Phase0_Architecture_Gap_Report.md` | Phase 0 reconnaissance template (the style Phase B's recon should match) |
| `backend/app/schemas/{ser,sfi,relay,mc,twin}.py` | Phase A schema patterns: strict Pydantic, `@model_validator`, `SCHEMA_VERSION` |
| `backend/agent/` (whole tree) | How an independent service is structured: factory abstraction, schema mirror, isolation tests |
| `backend/tests/contract/test_phase_a_openapi.py` | Drift detection style — Phase B's causal API will need its own |
| `docker-compose.phase-a.yml` + `backend/agent/Dockerfile` | Container deployment template |

### Archived (know they exist, don't need to read)

| Path | What it is |
|---|---|
| `_reports/PHASE_0_5_*.md` (3 files) | Phase 0.5 dirty-tree classification + B1 inventory |
| `reports/stabilize-v9/*` (128 files) | Phase 0 test/benchmark run artefacts. Untracked. |
| `.agents/` | Skill / runtime metadata. Untracked. |

---

## Section 8 — Phase B about to start

### User's Phase B scope

- **Phase B = causal inference layer**: DoWhy + EconML + mediation + DML.
- New endpoint group: `/api/v1/causal/*` (DAG / mediation / DML / DR / Granger / sensitivity).
- New `causal_node` in the agent's LangGraph.
- Honest evidence levels on every estimate (planned / supported / validated).
- Plan effort estimate: **100–150 h** raw; **20–30 h** at Phase A's observed 4.5× efficiency.

### Phase B status today

- **No code written yet.**
- **No plan written yet.**
- **No packages installed yet** (DoWhy / EconML are absent from
  `backend/requirements.txt` — and **must stay absent until the user
  approves**, per the no-pollution rule).
- Phase A `230 + 9 = 239` tests are the floor; Phase B starts from
  green.

### The first command the new thread should issue

**Phase B Step 1: Reconnaissance.** Spec:

```
Output file: _reports/PHASE_B_RECONNAISSANCE.md
Style: matches BOS_Phase0_Architecture_Gap_Report.md
Sections required (5):

1. DoWhy / EconML reconnaissance
   - Install both into a *throwaway* venv (NOT
     backend/requirements.txt).
   - Record versions + transitive deps.
   - List the 4 DoWhy steps (model / identify / estimate / refute).
   - List EconML's estimator menu (DML / DR / metalearners / …).
   - Compatibility check vs BOS Core's Python 3.11 + Pydantic 2.6.
   - Run each library's quickstart example; record command + output.

2. BOS data flow — candidate causal roles
   - Scan backend/app/schemas/{ser,sfi,relay,mc,twin}.py.
   - For every variable mark candidate roles: treatment / outcome /
     covariate / mediator / confounder. A variable may carry several.
   - No DAG design yet — just candidates.

3. Paper causal-language harvest
   - Grep BOS_Paper1_JCP_FINAL.docx (or current draft) for
     causal verbs: 导致 / 驱动 / 影响 / 决定 / cause / drive /
     increase / reduce / promote / inhibit.
   - One line per claim, with section + "author claim" vs
     "cited claim".

4. Phase A data inventory vs Phase B needs
   - List every field Phase A's 5 APIs already accept/emit.
   - For each, classify Phase B availability:
     "have it now" / "need historical batch data" /
     "need new experiments" / "fully synthetic only".

5. Risks + unknowns
   - 5-10 open questions with categories
     ("user decision tomorrow" / "clears up mid-run" /
     "needs outside expertise").
   - Each with 1-2 lines of suggested treatment.

What Step 1 must NOT do:
  ⛔ no Plan
  ⛔ no DAG design
  ⛔ no estimator choice
  ⛔ no Phase A code changes
  ⛔ no installs into backend/requirements.txt
  ⛔ no Phase B implementation
  ⛔ no route additions

After Step 1: user reads the recon → confirms or adjusts → then
Strategy LLM drafts Phase B Plan v1 → adversarial self-review →
Plan v2 → D-series decisions → implementation in batches.
```

---

## Section 9 — Long-term goals + roadmap

### Four-tier goal stack

| Tier | Goal | Status |
|---|---|---|
| Short term (weeks) | Paper 1 (JCP) submission, independent of software | **2.5 h** estimated, unblocked anytime |
| Mid term (months) | Phases A → G complete on the software side | A done; B–G ahead |
| Long term (~year) | GitHub v1.0 + paper acceptance synchronously | Conditioned on Phase A–G plus 1–2 polish months |
| Ultimate (~5 yr) | Publicly deployed BOS Agent API; external operators using it | Conditioned on v1.0 launch + 6+ months of public iteration |

### Timeline (optimistic, assuming Phase A's 4.5× efficiency holds)

| Month | Milestone |
|---|---|
| 0 (now) | Phase A done ✅ |
| 1–2 | Phase B (causal) + Phase C (Bayesian + Conformal) |
| 3–4 | Phase D (NN / Transformer) + Phase E (optimal control) |
| 5–6 | Phase F (info theory) + Phase G (agent UI polish + PhyAgentOS A2A) |
| 7 | GitHub v1.0 + paper acceptance announced together |
| 8+ | Public API deployment exploration |

### Identified risks

| Risk | Probability | Source |
|---|---|---|
| Time inflation (4.5× degrades to 2× or worse on harder phases) | ~60% | Phase B is genuinely harder than A (causal inference is research-grade) |
| Direction drift (V5 contract reshaped mid-stream) | ~40% | Paper revisions may force schema updates |
| Competitive window closing | ~30% | Insect-bioconversion + LLM-agent space is heating up |
| Motivation decay over 6+ months | ~35% | Solo plus single-strategy-LLM bandwidth is the main wear point |

### Risk mitigation

- **Hard deadline**: target 2027-02-28 for v1.0 GitHub launch.
- **Paper-first lane**: submit JCP independently of software (does
  not block phases B–G).
- **60-day reassessment**: every two months, write a 1-page
  "current trajectory vs plan" doc and decide whether to keep
  course / cut scope / pivot.
- **Private GitHub continuity**: keep committing to a private
  remote so a future collaborator (or new strategy LLM) can pick
  up without context loss.

---

## Section 10 — Work environment

| Item | Value |
|---|---|
| OS | Windows 11 (Bash shell available via Git Bash / WSL; PowerShell also works) |
| Python | 3.11+ (verified via `app.main:app` boot); a project venv may live at `backend/.venv` or `.venv` (check before running) |
| Node | **24.14.1** — has a known **Zone OOM** when running `npm run build` or `tsc --noEmit` at default heap. Workaround: `NODE_OPTIONS=--max-old-space-size=8192`. Sometimes flaky (Phase 0.5 always failed; Phase A6 succeeded). **Phase B should not block on this.** |
| Frontend test runner | `vitest` (no `@testing-library/react` dep; tests use `renderToStaticMarkup`) |
| Backend test runner | `pytest 8.0.1` with `pytest-asyncio` |
| User working hours | (to be filled by user — placeholder: typically evening + late night) |
| Strategy LLM in current chat | Claude (claude.ai web UI) |
| Local executor | Claude Code CLI |
| `ANTHROPIC_API_KEY` | Required only for the agent's LLM router; can be omitted (deterministic keyword router fallback). Not stored in repo. |
| Database | SQLite for dev / demo; Postgres URL `DATABASE_URL` for production (see `backend/app/db.py`) |

### Standing constraints

- **Never** install Phase B packages (DoWhy / EconML / PyMC / etc.)
  into `backend/requirements.txt` without explicit user approval.
- **Never** modify Phase A backend or frontend code while doing
  Phase B reconnaissance.
- **Never** push to a remote without explicit user instruction.
- **Always** keep `from app.*` out of `backend/agent/`.
- **Always** report at batch boundaries; do not chain.

---

**End of handoff.** A new conversation can read this file, run
`git status` + `git log --oneline -10`, then immediately issue the
"Phase B Step 1 reconnaissance" spec in Section 8.
