# Phase B B4 v2 — LangGraph causal agent design (corrected)

> **Status.** Authoritative design for B4. Replaces
> `PHASE_B_B4_DESIGN_v1_VOID.md`, which assumed `agent/` was
> net-new in the repo root.
> **Predecessor.** B4 v1 quarantine commit (this batch's own
> commit, see `git log`). Tag `v0.9.0-paper1` still anchored at
> `92a7a0f`; v1's `ddcbc24` commit is preserved as audit history.
> **Implementation thread.** Deferred to the next thread. This
> doc is the hand-off.
> **Estimated effort.** **3-5 h adjusted** (down from v1's 6-10
> h, because basic infrastructure is already shipped under
> `backend/agent/`).

## §1 Discovery summary — why v2 exists

v1 was written without running `find` over `backend/`. An 8-item
reconnaissance in the v1-Steps-3-4 thread found Phase A A.3's
agent service already shipped at `backend/agent/` (2089 LoC,
mtime May 16-17), which v1 was duplicating. Key findings from
that recon (full record at the end of the v1-quarantine commit
message):

- **FastAPI on :8001** exists — `backend/agent/server.py`,
  endpoints `GET /agent/health` + `POST /agent/runs`.
- **LangGraph StateGraph builder** exists —
  `backend/agent/graph.py`, 90 LoC, START → router →
  {ser, sfi, relay, cyber_lab, render} → END. Compiled via
  `build_graph(checkpointer)` with `InMemorySaver` default.
- **Six nodes** exist — `router`, `ser`, `sfi`, `relay`,
  `cyber_lab`, `render`. All under `backend/agent/nodes/`.
- **LLM factory** exists — `backend/agent/llm.py`, 90 LoC, 4
  providers (Anthropic / OpenAI / Qwen / DeepSeek), env-driven
  model selection. Default `claude-sonnet-4-5`.
- **State** exists — `backend/agent/state.py`, 99 LoC. ⚠️ It is
  a **`TypedDict`**, not a Pydantic model (the v1 code in root
  `agent/state.py` used Pydantic — incompatible with the
  existing graph).
- **HTTP client to backend core** exists — `backend/agent/tools/`,
  `client.py` + per-endpoint wrappers.
- **Tests** exist — `tests/test_graph_boot.py`,
  `test_isolation.py`, `test_schema_parity.py` (3 files,
  286 LoC).
- **Isolation gate** already enforced — production code is 0
  `from app.*` hits; the test-side `from app.schemas import ...`
  in `test_schema_parity.py` is the same dev-host parity pattern
  the v1 root-`agent/` mirror used.

v1's "agent is net-new" was simply wrong.

## §2 Actual scope (vs v1)

| Aspect | v1 (VOID) | v2 (this doc) |
|---|---|---|
| Where | Root `agent/` (net-new) | `backend/agent/` (extend) |
| Effort | 6-10 h | **3-5 h** |
| New files | 12 source + 8 test | **6 source + 2 test** |
| Modified files | 1 (frontend) | **5** (state / graph / nodes/router / nodes/render / tests/test_graph_boot) |
| Infrastructure to build | FastAPI app, LangGraph runtime, LLM factory, persistence, httpx client | 0 — already in `backend/agent/` |
| Tag | optional `v0.9.1-agent` | optional `v0.9.1-agent` (unchanged) |

## §3 Files to extend in `backend/agent/`

### `backend/agent/state.py` (extend)

**Current** (Phase A): `TypedDict` with 30 keys (ser / sfi /
relay / cyber_lab + messages + tool_calls). Plan v2 §3.1 Mod 10
asks for the new causal-side keys to be grouped under a
``CausalSlice`` sub-dict so Phase A's flat-state pattern keeps
working.

**v2 extension** — add a `CausalSlice` `TypedDict` (also with
`total=False`) and a single new key on `BOSState`:

```python
class CausalSlice(TypedDict, total=False):
    dag: Optional[Dict[str, Any]]          # serialised DagSpec
    treatment: Optional[str]
    outcome: Optional[str]
    mediators: Optional[list[str]]
    data: Optional[Dict[str, Any]]         # serialised CausalData
    identified: Optional[bool]
    strategy: Optional[str]
    estimand_handle: Optional[Dict[str, Any]]
    ate: Optional[float]
    ate_ci: Optional[Tuple[float, float]]
    estimate_handle: Optional[Dict[str, Any]]
    mediation: Optional[Dict[str, Any]]
    refute_results: Optional[list[Dict[str, Any]]]
    refute_passed: Optional[bool]
    sensitivity: Optional[Dict[str, Any]]
    evidence_level: Optional[Literal["validated","supported","planned"]]
    warnings: Optional[list[str]]

class BOSState(TypedDict, total=False):
    # ... existing 30 keys unchanged ...
    causal: Optional[CausalSlice]
```

⚠️ R1 from v1 (TypedDict vs Pydantic) is now resolved by this
v2 mandate: **v2 uses TypedDict to match Phase A**. The v1 root
`agent/state.py` (which used Pydantic) is not migrated.

### `backend/agent/nodes/router.py` (extend)

**Current**: Phase A router_node classifies into 5 intents
(`ser` / `sfi` / `relay` / `cyber_lab` + smalltalk/noop/render).

**v2 extension**: add 4 causal intents to the system prompt + the
keyword-fallback table, per Plan v2 §3.5:

- `causal.ate` (keywords: 因果 / causal / cause / ATE / why did / 为什么)
- `causal.mediation` (mediation / 中介 / proportion mediated /
  direct effect / indirect effect)
- `causal.sensitivity` (sensitivity / 敏感性 / E-value /
  robustness / unmeasured)
- `causal.full` (explain in depth / full causal / 深度因果)

`Intent` `Literal` in `state.py` extends accordingly.

### `backend/agent/nodes/render.py` (extend)

**Current**: Phase A render_node renders ser / sfi / relay /
cyber_lab reports into a single Markdown string at
`state["report"]`.

**v2 extension**: detect `state.get("causal")` is non-None and
append a Causal block per Plan v2 §3.4 template (with embedded
` ```mermaid ` fence + the `format_ci(low, high, *, decimals=3)`
helper). The `render_dag_as_mermaid(dag_dict)` helper from
Plan v2 §3.6 also lives in this module.

### `backend/agent/graph.py` (extend)

**Current**: 5 conditional edges from `router` → 5 nodes →
`render` → `END`.

**v2 extension**:

- Add 5 new nodes: `causal_identify`, `causal_estimate`,
  `causal_refute`, `causal_mediation`, `causal_sensitivity`.
- Add a `causal_fanout_full` node that runs
  `asyncio.gather(refute, mediation, sensitivity,
   return_exceptions=True)`.
- Add a `causal_fanout_mediation` node that runs
  `asyncio.gather(mediation, refute,
   return_exceptions=True)` for the `causal.mediation` intent
  (per Plan v2 §3.2 parallel branch).
- Extend `_INTENT_TO_NODE` to dispatch 4 causal intents into the
  identify entry point.
- Extend `_route_from_intent` plus a new
  `_dispatch_after_estimate(state)` conditional edge that picks
  `refute` / `sensitivity` / `causal_fanout_mediation` /
  `causal_fanout_full` based on `state["intent"]`.
- Wrap `causal_identify` + `causal_estimate` with
  `_wrap_node_for_errors` so unhandled exceptions land in
  `state["causal"]["warnings"]` instead of crashing the graph.

### `backend/agent/tests/test_graph_boot.py` (extend)

Add 4 boot-time assertions: graph compiles with 5 new nodes
present + 4 new intents recognised by the router prompt.

### `backend/agent/tests/test_isolation.py` (no semantic change)

Already AST-walks `backend/agent/`. New `nodes/causal_*.py`
modules will auto-discover and the existing parametrised case
catches any `from app.*` regression.

### `backend/agent/tests/test_schema_parity.py` (extend)

Already compares Phase A schemas with `app.schemas.{ser,sfi,...}`.
Extend the manifest to also cover the 6 causal mirrors (see §4).

## §4 New files in `backend/agent/`

### Schema mirrors (`backend/agent/schemas/causal/`)

Six files mirroring `backend/app/schemas/causal/`:

- `common.py` (mirror of `backend/app/schemas/causal_common.py`)
- `identify.py` (B.1)
- `estimate.py` (B.2)
- `refute.py` (B.3)
- `mediation.py` (B.4)
- `sensitivity.py` (B.5)

These are byte-identical to backend modulo the import path swap
(`from app.schemas.causal_common import ...` →
`from agent.schemas.causal.common import ...`). The v1 root
`agent/schemas/causal/*.py` files are valuable reference — they
have the swap done already — but the v2 path moves them to
`backend/agent/schemas/causal/`. Copy + move, not re-derive.

### Causal nodes (`backend/agent/nodes/`)

Five files matching the existing Phase A naming convention:

- `causal_identify.py` (raises on failure — hard prereq)
- `causal_estimate.py` (raises on failure — hard prereq)
- `causal_refute.py` (try/except → state["causal"]["warnings"])
- `causal_mediation.py` (try/except → warnings)
- `causal_sensitivity.py` (try/except → warnings)

Each node is `async def`, accepts a `BOSState` (TypedDict),
returns a partial dict that LangGraph merges. The v1 root
`agent/nodes/causal_*_node.py` modules are valuable reference,
but **the v2 versions adapt to the TypedDict state shape**:

- Read inputs as `state["causal"]["dag"]` etc.
- Write outputs as
  `{"causal": {**state.get("causal", {}), "estimate_handle":
  resp.estimate_handle.model_dump()}}`.
- Reuse `backend/agent/tools/client.py`'s shared
  `httpx.AsyncClient` (already in Phase A; do NOT create a
  per-node client — that was the v1 mistake).

## §5 Reuse from Phase A

100% of the agent service infrastructure is already shipped.
v2 reuses without modification:

| Module | What it provides |
|---|---|
| `backend/agent/main.py` | uvicorn launcher (`python -m agent.main`) |
| `backend/agent/server.py` | FastAPI app + `/agent/health` + `/agent/runs` |
| `backend/agent/llm.py` | LLM factory (Anthropic / OpenAI / Qwen / DeepSeek) |
| `backend/agent/persistence.py` | InMemorySaver checkpointer |
| `backend/agent/tools/client.py` | Shared `httpx.AsyncClient` + `BOS_CORE_URL` |

v2 wires causal node logic into this stack; it does not rebuild
any of it.

## §6 Step plan (4 steps, ~3-5 h)

| Step | Scope | Effort |
|---|---|---|
| 1 | Schema mirror (6 files) + `BOSState.CausalSlice` extension + parametrise the existing `test_schema_parity.py` to cover the 6 mirrors | ~60 min |
| 2 | Five causal nodes (`backend/agent/nodes/causal_*.py`) using the shared `tools.client` + TypedDict state writes; per-node partial-failure semantics per Plan v2 §3.3 | ~90 min |
| 3 | Extend `nodes/router.py` (4 intents + keyword table), `nodes/render.py` (causal Markdown block + `format_ci` + `render_dag_as_mermaid`), `graph.py` (5 new nodes + 2 fanouts + conditional dispatch + error wrapper) | ~60 min |
| 4 | Extend `tests/test_graph_boot.py` for causal-intent boot; narrow regression (backend 53 + frontend 32 + Phase A agent 3 + new agent suite); completion doc; commit (optional `v0.9.1-agent` tag) | ~60-90 min |

**Total: 3-5 h adjusted.** No new step is gated on LangGraph
familiarity any more — the existing `graph.py` already
demonstrates the right pattern, and v2 follows it.

## §7 Acceptance criteria (Plan v2 §7 references)

v2 closes the following items that were left partial after the
B7 / B3 / B5 / B6 ships:

| # | Item | How v2 closes it |
|---|---|---|
| 2 | Agent boots with causal subgraph wired | `test_graph_boot.py` extended — 11 nodes (6 Phase A + 5 causal) compile cleanly under `build_graph()`. |
| 3 | Agent isolation maintained | Existing `test_isolation.py` auto-discovers new causal node modules; v2 imports only `agent.*` and `httpx`. |
| 4 | Refutation honesty (literature-grounded) | `causal_refute` node calls the mandatory 4 refuters per the B2b.1-patched rule; the engine's evidence-level clamp passes through unchanged. |
| 11 | Real BOS question E2E + `PHASE_B_DEMO.md` | Step 4 deliverable. The agent transcript captures one paper-aligned claim (default: Signal-API → κ → SER mediation chain). |

## §8 Risks (R1 - R5)

- **R1.** `TypedDict` vs Pydantic state. v1 wrote Pydantic;
  Phase A uses TypedDict. **Mitigation**: v2 must use
  TypedDict. Do not import `BOSState` from the v1 root
  `agent/state.py` — that module is quarantined.
- **R2.** `asyncio.gather` inside a LangGraph node. The Phase A
  graph has no precedent of this. **Mitigation**: write the
  fanout as a single async node that internally awaits
  `gather(...)`. Step 3 of the v2 plan is the right place; if
  it misbehaves, a 10-line spike on the existing `relay` node
  shape will validate.
- **R3.** Anthropic API key fallback chain in CI / dev.
  **Mitigation**: same as Phase A — env `ANTHROPIC_API_KEY`;
  router falls back to keyword classification on missing key
  per the existing `llm.py` chain.
- **R4.** Schema parity across **two** mirror sources
  (`backend/agent/schemas/{ser,sfi,...}` already mirror
  `backend/app/schemas/*`; the new
  `backend/agent/schemas/causal/*` will mirror
  `backend/app/schemas/causal/*` + `causal_common`).
  **Mitigation**: extend the existing parametrised
  `test_schema_parity.py` rather than adding a second test
  file.
- **R5.** `render_node` already exists. v2 must **merge** new
  causal-block logic into it, not replace it. **Mitigation**:
  add a `_render_causal_block(state)` helper called from the
  end of the existing `render_node` body when
  `state.get("causal")` is non-empty.

## §9 Phase G triggers (NOT in v2)

- Quarantined root `agent/` cleanup via `git rm` (waits until
  v2 ships and a release window confirms no consumer points
  at it).
- Schema mirror dedup: both Phase A and B causal schemas live
  in two trees (`backend/app/schemas/*` + `backend/agent/schemas/*`).
  A Phase G refactor could expose a shared `causal_common`
  package both can import without violating isolation.
- The `BOS_CORE_URL` httpx target is currently hardcoded under
  `backend/agent/tools/client.py`. Phase G can swap for a
  service-discovery layer.
- Frontend `BOSAssistantV2Page.tsx` integration (R6 from v1):
  detect ` ```mermaid ` fences in the agent's `report` and
  hand the JSON DAG to the B6 `CausalMermaidPanel`. ~30 LoC
  regex + JSX, deferred to a Phase G frontend pass.

## §10 Hand-off summary

The next thread should be able to run:

```bash
cd "C:\Users\10420\Desktop\bos 0506\bos v9\bos-pipeline-reconciled"
git log --oneline -10                    # confirm HEAD past v1-quarantine commit
cat _reports/PHASE_B_B4_v2_DESIGN.md     # this doc
cat _reports/PHASE_B_B4_DESIGN_v1_VOID.md   # v1 historical reference (the §3 step rhythm + §5 test design + §6 risks are still useful)
ls backend/agent/                         # confirm Phase A surface intact
```

and then start with §6 Step 1 (schema mirror + state extension).
All 53 backend tests + 32 frontend tests remain green; the v1
root `agent/` is quarantined and untouched.

**End of B4 v2 design hand-off.**
