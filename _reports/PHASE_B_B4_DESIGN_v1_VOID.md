# ⚠️ VOID — B4 v1 Design Document (Quarantined)

**Status**: VOID
**Reason**: Phase A precedent missed. This design assumed `agent/`
is a net-new service in the repo root. After Steps 1-2 ship
(commit `ddcbc24`) and Step 3 scratch work, B4 v2 reconnaissance
discovered Phase A A.3 already shipped a complete LangGraph agent
at `backend/agent/` (2089 LoC, FastAPI on :8001, 6 nodes wired —
`router`, `ser`, `sfi`, `relay`, `cyber_lab`, `render`). B4 v1 was
building a duplicate.

**Action taken**:

- `ddcbc24` commit (Steps 1-2 of v1) is **kept** as audit history
  (not reverted; revert would add a destructive commit to the
  chain).
- Root `agent/` directory is **quarantined** — see
  `agent/README.md` for the do-not-extend warning.
- B4 v2 design lives at `_reports/PHASE_B_B4_v2_DESIGN.md` and
  reflects actual scope: extending `backend/agent/` in-place
  (~3-5h adjusted vs the 6-10h v1 estimate).

**Lessons**:

1. Plan v2 §3 said "agent service" but did not specify path; this
   v1 design doc author inferred net-new without running `find`
   over the existing `backend/` tree. Phase A A.3
   (`backend/agent/`, mtime May 16-17) was right there.
2. Step 0 reconnaissance for any new agent/subsystem work should
   grep the existing tree first — the 8-item recon that found the
   precedent took ~30 minutes and would have prevented this.
3. B4 v2 will work in `backend/agent/` and treat this document as
   historical reference only.

**Reuse from this v1 doc that B4 v2 still wants**:

- §3 step rhythm (the 8-step cadence)
- §5 test design (4 buckets: isolation / parity / node unit /
  full-chain + partial-failure)
- §6 risks (R1 - R6 mostly still apply, modulo R1's "LangGraph
  install" which is already satisfied)
- §8's reasoning for why B6 shipped before B4 (still correct)

**DO NOT** treat any of v1's "12 source + 8 test files" inventory
(§4) as authoritative — that list duplicates `backend/agent/`.
B4 v2 §4 supersedes it.

---

# Phase B B4 — LangGraph causal agent design (for next thread)

> **Status.** Design only. NO code shipped in this commit. This
> doc exists so the next thread can execute B4 without re-recon.
> **Predecessor.** B3 + B5 committed at `c4cb86e`.
> **HEAD at design time.** `c4cb86e` (53-test green; v0.9.0-paper1
> tag still on `92a7a0f`).
> **Plan v2 reference.** §3 (LangGraph agent — causal subgraph
> spec, D11 = γ, 5 nodes), §3.1–§3.7 verbatim.
> **Acceptance gates closed by B4.** Plan v2 §7 items #2 (agent
> boots with causal subgraph), #3 (agent isolation maintained),
> partial #4 (refuter-honesty E2E on the golden bench), #11
> (real BOS question end-to-end + `PHASE_B_DEMO.md` transcript).

## §1 Why B4 is its own thread

`agent/` is a **net-new service** in this repo. Five engineering
risks are large enough that the next thread should start fresh
rather than continue here:

1. **Service surface.** `agent/main.py` is a separate FastAPI
   app (or a LangGraph runtime) with its own dependency tree,
   its own port (`8001` per Plan v2 §3 + frontend
   `BOSAssistantV2Page.tsx`), and its own healthcheck.
2. **LLM router.** Plan v2 §3.5 requires an LLM-backed
   `router_node` (Anthropic, given the Phase A precedent) with
   a keyword fallback for `ANTHROPIC_API_KEY` absence. This is
   production-grade not mocked.
3. **httpx cross-service.** Each causal node calls the backend
   FastAPI `/api/v1/causal/*` over HTTP (Plan v2 §3.2). Tests
   must either start the backend or mock httpx — both are new
   patterns in this codebase.
4. **Isolation gate.** Plan v2 §7 #3 requires
   `no from app.*` imports inside `agent/` — schemas must be
   mirrored under `agent/schemas/causal/*`, and a parity test
   (§3.7) keeps them byte-for-byte in sync.
5. **Conditional edges with asyncio.gather.** Plan v2 §3.2's
   `intent="causal.full"` route fans out
   `refute / mediation / sensitivity` in parallel; LangGraph's
   conditional-edge + `asyncio.gather` semantics is the first
   non-trivial concurrency in this codebase.

A net new thread also gets the strategy LLM back into the loop —
B2b.1 / B2b.2 / B2b.3 all benefited from the brief-then-execute
split. B7 / B3 / B5 worked solo because they bolted onto an
existing, well-mapped surface; B4 doesn't have that luxury.

## §2 Plan v2 §3 verbatim references

Per Plan v2 §3.1–§3.7 (do not re-litigate these in the next
thread — they are locked):

- **§3.1 BOSState refactor (Mod 10).** New `CausalSlice`
  TypedDict groups 15 causal fields under
  `BOSState.causal`. Phase A keys untouched (26 fields stay
  flat).
- **§3.2 Five-node subgraph (D11 = γ).** START → router_node
  →{ser, sfi, relay, cyber_lab, causal_identify, smalltalk}.
  Causal path: identify → estimate →{refute, mediation,
  sensitivity}→ render → END. Conditional edges: 4 intents
  (`causal.ate` / `causal.mediation` / `causal.sensitivity` /
  `causal.full`); `causal.full` uses `asyncio.gather` for the
  three downstream nodes.
- **§3.3 Partial-failure semantics (Mod 10).** identify or
  estimate fail → whole subgraph fails. refute fail →
  evidence_level clamped to `'planned'` + warning. mediation
  / sensitivity fail → field set to `None` + warning. Failure
  signal: HTTP non-2xx from causal service or
  `httpx.ReadTimeout` (90 s sync default).
- **§3.4 render_node markdown convention (Mod 11).** CI
  rendering locked to `[low, high]` (square brackets, comma +
  space). Single helper `format_ci(low, high, decimals=3)`.
  Causal-block template with embedded ` ```mermaid ` fenced
  block. A `test_render_conventions.py` greps for stray
  `(low, high)` patterns and fails CI.
- **§3.5 router_node LLM prompt (Mod 10).** Bilingual prompt
  (English + Chinese examples). 4 causal intents + 4
  non-causal intents + smalltalk. Keyword fallback table
  (Chinese & English).
- **§3.6 Mermaid helper (D12 = β-lite).**
  `render_dag_as_mermaid(dag) -> str` ~30 LoC. Same node-shape
  / edge-style rules already shipped frontend-side in
  `frontend/src/components/bos/CausalMermaidPanel.tsx`
  (B6) — keep these aligned so the markdown produced by the
  agent is byte-identical to what the frontend draws.
- **§3.7 Schema mirror.** `agent/schemas/causal/*` mirrors
  `backend/app/schemas/causal/*` byte-for-byte modulo paths.
  `agent/tests/test_schema_parity.py` parametrised by module
  name picks up any new module automatically.

## §3 Step breakdown for the next thread (estimated 6–10 h)

Mirror the B2b.2 / B2b.3 8-step rhythm:

| Step | Scope | Effort |
|---|---|---|
| 1 | Recon + design refinement (this doc + frontend-mermaid alignment) | 30 min |
| 2 | `agent/` skeleton + `agent/main.py` (FastAPI app + healthcheck) + `agent/schemas/causal/*` mirror | 60–90 min |
| 3 | Five causal nodes (`agent/nodes/causal_*.py`); `httpx` client; partial-failure semantics | 120–180 min |
| 4 | `router_node` LLM prompt + keyword fallback; `BOSState.CausalSlice` typed-dict; LangGraph graph wiring with conditional edges + `asyncio.gather` | 90–120 min |
| 5 | `render_node` markdown + `format_ci` helper + `render_dag_as_mermaid` helper; `test_render_conventions.py` | 45–60 min |
| 6 | Agent unit + integration tests (`agent/tests/*`): schema parity, isolation gate, node-level mocks, full-chain happy path + 3 partial-failure scenarios | 120–150 min |
| 7 | Narrow regression (backend 53 tests still green; agent suite green); completion doc + scratch archive | 45 min |
| 8 | Commit + (optional) `v0.9.1-agent` tag if the author wants a milestone | 15 min |

**Total**: 8.0–11.5 h adjusted. The wide range is driven by
LangGraph familiarity and how clean the LLM-router mocking
strategy turns out. The thread should pre-allocate 30 min in
Step 1 to decide whether `agent/main.py` boots a LangGraph
runtime directly or wraps it in FastAPI (Plan v2 §3.2 implies
the latter; confirm).

## §4 File inventory (target)

### New files (estimated 12 source + 8 test)

| Path | Purpose |
|---|---|
| `agent/main.py` | FastAPI / LangGraph entry; healthcheck on `:8001` |
| `agent/state.py` | `BOSState` + `CausalSlice` TypedDicts |
| `agent/router.py` | LangGraph graph builder; conditional edges |
| `agent/nodes/router_node.py` | LLM router + keyword fallback |
| `agent/nodes/causal_identify_node.py` | `httpx.post /api/v1/causal/identify` |
| `agent/nodes/causal_estimate_node.py` | `httpx.post /api/v1/causal/estimate` |
| `agent/nodes/causal_refute_node.py` | `httpx.post /api/v1/causal/refute` |
| `agent/nodes/causal_mediation_node.py` | `httpx.post /api/v1/causal/mediation` |
| `agent/nodes/causal_sensitivity_node.py` | `httpx.post /api/v1/causal/sensitivity` |
| `agent/nodes/render.py` | Markdown renderer + `format_ci` + `render_dag_as_mermaid` |
| `agent/schemas/causal/identify.py` | Mirror of `backend/app/schemas/causal/identify.py` |
| `agent/schemas/causal/estimate.py` | Mirror |
| `agent/schemas/causal/refute.py` | Mirror |
| `agent/schemas/causal/mediation.py` | Mirror |
| `agent/schemas/causal/sensitivity.py` | Mirror |
| `agent/schemas/causal/common.py` | Mirror of `causal_common.py` |
| `agent/tests/test_isolation.py` | Asserts no `from app.*` in `agent/` |
| `agent/tests/test_schema_parity.py` | Diffs `agent/schemas/causal/*` vs `backend/app/schemas/causal/*` |
| `agent/tests/test_render_conventions.py` | Greps for stray `(low, high)` CI patterns |
| `agent/tests/test_router_node.py` | LLM happy path + keyword fallback |
| `agent/tests/test_causal_nodes.py` | Per-node httpx-mocked tests (5 nodes) |
| `agent/tests/test_full_chain_e2e.py` | identify → estimate →{refute,mediation,sensitivity}→ render (4 intents) |
| `agent/tests/test_partial_failure.py` | refute / mediation / sensitivity individual fail paths (3 scenarios) |

### Modified files

| Path | Δ | Purpose |
|---|---|---|
| `frontend/src/pages/BOSAssistantV2Page.tsx` | small | wire `CausalMermaidPanel` (from B6) into the V2 response renderer when the agent emits a ` ```mermaid ` block |

### Deliverable docs

- `_reports/PHASE_B_B4_COMPLETION.md` — same structure as
  B2b.1 / B2b.2 / B2b.3 completion docs.
- `_reports/PHASE_B_DEMO.md` — Plan v2 §7 #11 deliverable
  (real BOS question, captured agent transcript, embedded
  mermaid). Should include the engine output numbers + the
  agent's markdown verdict for one paper-aligned claim
  (default: Signal-API → κ → SER mediation chain).

## §5 Test design (target)

8 test files split across 4 buckets:

1. **Isolation (1)** — `test_isolation.py`: AST-walks every
   `.py` under `agent/` and asserts no `from app.` or
   `import app.` statements. Closes Plan v2 §7 #3.

2. **Schema parity (1)** — `test_schema_parity.py`:
   parametrised by module name; compares
   `agent.schemas.causal.<name>` against
   `app.schemas.causal.<name>` field-by-field (name + type +
   constraints + default). `SCHEMA_VERSION` strings must
   match (`B.1` through `B.5`).

3. **Node unit (5)** — `test_causal_nodes.py`: one happy-path
   test per node with `httpx_mock`-style fakes. Each test
   verifies:
   - the correct URL is called (`http://localhost:8000/api/v1/causal/<name>`),
   - the request body matches the typed request schema,
   - the response is parsed into the typed response and
     written into the right `CausalSlice` fields per §3.2,
   - partial-failure semantics fire correctly per §3.3.

4. **Full chain + partial failure (4)** —
   - `test_router_node.py`: LLM mock + keyword fallback for
     the 8-intent matrix.
   - `test_full_chain_e2e.py`: each of the 4 intents
     (`causal.ate` / `mediation` / `sensitivity` / `full`)
     produces a markdown response with the expected blocks.
   - `test_partial_failure.py`: refute / mediation /
     sensitivity individual failure paths produce the right
     `evidence_level` clamps + warnings.
   - `test_render_conventions.py`: greps for stray
     `(low, high)` patterns; pins the `[low, high]` CI
     convention from Plan v2 §3.4.

## §6 Risks & open questions for the next thread

- **R1.** LangGraph version pin. `requirements.txt` currently
  carries LangGraph from Phase A's chat surface; verify the
  installed version supports conditional edges + async nodes
  (LangGraph ≥ 0.0.40 should be fine, but check). If pinned
  version is too old, bump it in Step 2 with its own narrow
  regression on Phase A's existing graph.
- **R2.** `asyncio.gather` inside a LangGraph conditional
  edge. Plan v2 §3.2 describes the pattern but does not
  reference a working precedent in this repo. The next
  thread should write a 10-line spike in Step 1 to validate
  before designing the full conditional-edge tree.
- **R3.** Schema parity drift detection across Phase B
  schema revisions (B.1–B.5). The parity test must be strict
  enough to catch a field rename but lenient enough that
  comment / docstring edits don't break it. The
  `model_json_schema()` output is the canonical contract.
- **R4.** LLM key absence in CI / dev. Keyword fallback must
  cover 100% of the 8-intent matrix so test_router_node can
  pass without `ANTHROPIC_API_KEY`. The fallback table in
  Plan v2 §3.5 is the contract.
- **R5.** httpx default timeout. Plan v2 §3.3 says 90 s for
  sync; for the agent unit tests with mocked responses this
  is irrelevant, but `test_full_chain_e2e.py` against a real
  backend would need either a per-call timeout knob or a
  bigger pytest timeout.
- **R6.** Frontend integration (B6 follow-up). The next
  thread should make a small edit to
  `BOSAssistantV2Page.tsx` to detect ` ```mermaid ` fences
  in the agent's markdown and pipe the JSON DAG into
  `CausalMermaidPanel`. This is ≈ 30 LoC of regex + JSX,
  scoped after the agent ships.

## §7 Phase G follow-ups (NOT in B4)

- Replace `httpx`'s per-call URL hardcode with a config-driven
  service-discovery layer (B4 hardcodes `http://localhost:8000`
  matching Plan v2 §3 explicit examples).
- Phase A retroactive grouping: move SER / SFI / Relay /
  CyberLab state under sub-slices similar to `CausalSlice`.
- Tighten `test_render_conventions.py` to AST-walk instead
  of grep (avoids false positives in code comments).
- The B6 frontend panel currently only accepts a `DagSpec`
  object directly. Phase G can add a `renderMermaidFromMarkdown`
  utility that extracts ` ```mermaid ` fences from agent
  markdown so the V2 page can pipe agent output straight in.

## §8 Why B6 is shipped before B4

The natural dependency order is reversed: B4 produces the
mermaid markdown, B6 renders it. Plan v2's batch order put
B6 after B4 / B5. The author chose to ship B6 first because:

- B6 is pure presentation; it can be unit-tested standalone
  against any synthetic `DagSpec`, no agent required.
- B6 closes Plan v2 §7 #7 (optional gate) before B4 lands —
  better visibility into the Mermaid-rendering layer's
  correctness without conflating with the LangGraph wiring
  it eventually consumes from.
- The `dagToMermaidSource` converter shipped in B6
  (`frontend/src/components/bos/CausalMermaidPanel.tsx`) is
  the byte-for-byte JS equivalent of Plan v2 §3.6's Python
  `render_dag_as_mermaid`. The next thread should keep both
  in sync (any update to the node-shape / edge-style
  conventions must land in both).

## §9 Hand-off summary

The next thread should be able to run:

```bash
cd "C:\Users\10420\Desktop\bos 0506\bos v9\bos-pipeline-reconciled"
git log --oneline -10                # confirm HEAD is at or beyond c4cb86e
cat _reports/PHASE_B_B4_DESIGN.md    # this doc
cat _reports/PHASE_B_PLAN.md         # Plan v2 §3 sections 3.1–3.7
```

and then start Step 1 (recon + design refinement). The
backend's 5 causal endpoints + paper pin + 53-test green
state is a stable substrate; B4 is purely additive on top.

**End of B4 design hand-off.**
