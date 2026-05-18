# Phase B B7 — Post-commit audit

> Triggered by user request after the B7 commit (`92a7a0f`) and
> `v0.9.0-paper1` tag landed. Goal: surface every documentation
> inconsistency, line-count drift, dead reference, version skew,
> and Plan-v2 acceptance gap accumulated across B2a → B7. No
> Phase B code was rewritten as a result of the audit; only
> documentation drift and one engine-version constant were
> changed.

## §1 Findings summary

| # | Severity | Item | Action |
|---|---|---|---|
| 1 | High (doc lies about repo state) | `_reports/PAPER_PINNING.md` §8 said the scratch script "is **kept** in the B7 commit", but Step 3d had already removed it. | Fixed inline: §8 rewritten to record the deletion + regeneration contract. |
| 2 | Medium (semver skew) | `CAUSAL_ENGINE_VERSION = "0.1.0"` since B2a, never bumped despite the 5-endpoint surface shipping. Every causal Response reported `engine_version="0.1.0"` while the platform tag is `v0.9.0-paper1`. | Fixed inline: bumped to `"0.9.0"` with an in-line version history docstring. No test hard-coded the value (both `test_causal_mediation_engine.py` and `test_causal_sensitivity_engine.py` imported `CAUSAL_ENGINE_VERSION` symbolically). |
| 3 | Low (informational doc drift) | `PHASE_B_B2b3_COMPLETION.md` §2 file inventory under-reported three line counts captured at draft time, before final passes: engine `703 → 705`, test `358 → 427`, design `460 → 462`, API verification `100 → 131`. Subtotal `1631 → 1733`; total `2167 → 2271`. | Fixed inline: §2 rows updated and an audit-note paragraph appended to the "Total diff" line. |
| 4 | Informational (Plan v2 nit) | Plan v2 §7 acceptance item #8 claims "217 phase_a tests"; the actual `-k phase_a` collection at audit time is `216 tests` (`pytest --collect-only`). All 216 PASS. Plan v2 typo or one test pruned during B0.3 / B0.5 baseline cleanup. | Not fixed in code — Plan v2 is the historical record. Recorded here so future audits don't chase a missing 217th test. |
| 5 | Out-of-scope (deliberate, not a defect) | Plan v2 §7 items #2, #3, #5, #10, #11 are gated on Phase B B3 / B4 / B5 — those batches were not part of B2a / B2b / B7 scope. None of the artefacts exist (`_reports/PHASE_B_DEMO.md`, `_reports/phase_b_openapi_snapshot.json`, `backend/tests/contract/test_phase_b_openapi.py`, `backend/tests/contract/test_phase_a_freeze.py`, `backend/tests/e2e/test_phase_b_e2e.py`, `agent/`). | Not in audit scope to fix — recorded in §3 below as remaining Phase B work outside the Paper-1 shipping cut. |

No code changes were required to causal engines, schemas, routers,
or unit tests. The 44-test narrow regression after the three doc /
constant fixes ran 44 PASS in 139s; the wider `-k phase_a` subset
ran 216 PASS in 46s.

## §2 Verified facts (audit "good news")

These are explicitly *checked*, not assumed:

- Git HEAD = `92a7a0f` = tag `v0.9.0-paper1` (pointed by `git
  rev-list -1 v0.9.0-paper1`).
- Working tree clean apart from the three audit-fix files (now
  the target of this audit commit).
- Five Phase B commits in linear chain: `2138cf8` → `27f3a62` →
  `d372dba` → `83c3c83` → `92a7a0f`.
- No `TODO` / `FIXME` / `XXX` / `HACK` / `TBD` strings in any
  `backend/app/.../causal*.py` file (5 schemas + 5 engines + 1
  router).
- `SCHEMA_VERSION` values present and sequential across the five
  endpoints: `B.1` (identify), `B.2` (estimate), `B.3` (refute),
  `B.4` (mediation), `B.5` (sensitivity).
- Engine isolation: `causal_sensitivity_engine.py` (and the
  other four engines) import only from `app.*`; no `from agent.*`
  cross-talk (Plan v2 §7 #3 anchor preserved even though the
  agent itself is not built yet).
- Every causal endpoint registered in OpenAPI:
  `/api/v1/causal/{identify, estimate, refute, mediation,
  sensitivity}` (5 endpoints, verified via `app.openapi()` dump).
- The DAG library exists at the path the design docs reference:
  `_reports/PHASE_B_DAGS/dag_001_ser_baseline.json`,
  `dag_002_mediation_signal_kappa_ser.json`,
  `dag_003_relay_three_stage.json`.
- `CITATION.cff` `version: "0.9.0-paper1"` matches the git tag.
- `README.md` "Paper 1 Reproduction" section's `git checkout
  v0.9.0-paper1` block targets a tag that actually exists.
- The paper SHA gate test PASSES at the new pin
  `2FD4387028B2B160388C65CCB0F269967E05B55FDEAF6BA62B1570BCB533118D`.
- All cross-batch reference doc paths in `README.md` and each
  completion doc resolve to files that actually exist
  (`PHASE_B_PLAN.md`, `PHASE_B_PLAN_V2_PATCH_S2_3.md`,
  `PHASE_B2b{1,2,3}_DESIGN.md`, `PHASE_B_B2b{1,2,3}_COMPLETION.md`,
  `PAPER_PINNING.md`).

## §3 Plan v2 §7 acceptance — 12 items honest status

The original Plan v2 had 12 PASS/FAIL acceptance items intended to
gate the *full* Phase B (B0.3 through B7). The B2a / B2b / B7
batches alone do not cover all 12. This table is the honest
mapping at the current commit (`92a7a0f` + this audit follow-up):

| # | Item (per Plan v2 §7) | Current status | Evidence |
|---|---|---|---|
| 1 | BOS Core boots on numpy 2.x | ✅ Implicit PASS | 44 unit tests run inside the backend without numpy errors; B1 batch deps landing committed (commit chain `2373aed` → ... → `92a7a0f`). |
| 2 | Agent boots with causal subgraph wired (5 nodes) | ❌ Not shipped | `agent/` directory does not exist. B4 batch outstanding. |
| 3 | Agent isolation maintained (no `from app.*`) | ⏳ Pre-emptively preserved | Engine side does not import `from agent.*`. Confirmation deferred until B4 ships the agent. |
| 4 | Refutation honesty (5 mandatory refuters + e_value > 1.5) | ⚠️ Patched + partial | Plan v2 §2.3 patched 5→4 mandatory refuters at B2b.1 (PHASE_B_PLAN_V2_PATCH_S2_3.md); B2b.1 unit tests cover the four refuters + the validated-tier rule including e_value > 1.5. **End-to-end run on B0.7 DAG #1 has not been executed** (item #5 dependency). |
| 5 | E2E causal full chain test | ❌ Not shipped | `backend/tests/e2e/test_phase_b_e2e.py` does not exist. B5 batch outstanding. |
| 6 | V1 frontend unchanged | ⏳ Not regressed | Phase B did not touch `frontend/`. `vitest` not re-run during B2a / B2b / B7; trust-no-modify check is *implicit*. |
| 7 | V2 frontend Mermaid causal panel (B6) | ❌ Not shipped (Plan v2 marks this deferrable) | B6 batch outstanding. |
| 8 | Phase A 217 phase_a tests pass unchanged | ✅ 216/216 PASS, 0 FAIL | `pytest -k phase_a`: 216 collected, 216 PASS in 46.39 s. Plan v2 typo: claimed 217, actual count was 216 at audit time (one test likely pruned during B0.3 baseline cleanup). |
| 9 | Baseline floor stable post-D13 (0 FAIL) | ⏳ Partial | The 44 causal tests + 216 phase_a tests = **260 PASS / 0 FAIL** verified. The wider `tests/ agent/tests/ -q` sweep Plan v2 prescribes was *not* re-run after each B2b batch (Step 6 in each batch scoped to causal engine files only). Best-effort PASS extrapolation only. |
| 10 | OpenAPI snapshot + drift gate | ❌ Not shipped | `_reports/phase_b_openapi_snapshot.json` and `backend/tests/contract/test_phase_b_openapi.py` do not exist. B3 batch outstanding. |
| 11 | Real BOS question answered E2E | ❌ Not shipped | `_reports/PHASE_B_DEMO.md` does not exist. Requires B4 + B5 to land first. |
| 12 | Paper version pinned | ✅ PASS with re-pin caveat | Gate test PASSES on the **new** pin `2fd43870...118d`. Plan v2's literal PASS condition cites the **old** pin `ba13a10f...10d7` — that was re-pinned in B7 per `PAPER_PINNING.md` §3 (2026-05-18 minor metadata delta, no Plan v3 review needed). |

**Headline.** Of the 12 items, **2 verifiable PASS** (#8, #12), **2
implicit / trust-only PASS** (#1, #6), **1 partial PASS** (#9), **2
preserved-pre-emptively** (#3, #4 modulo end-to-end), **5
genuinely-not-shipped** (#2, #5, #7, #10, #11). The Paper 1
ship via `v0.9.0-paper1` is **specifically the causal-layer cut**
— items #5, #10, #11 are gated on B3-B5 which land in the next
Phase B half-batch.

## §4 What this commit changes (B7 audit follow-up)

Three small edits + this audit doc:

1. `_reports/PAPER_PINNING.md` §8 — rewritten (scratch deleted,
   not kept; regeneration contract recorded).
2. `backend/app/schemas/causal_common.py` — `CAUSAL_ENGINE_VERSION`
   bumped `"0.1.0"` → `"0.9.0"` with a history docstring.
3. `_reports/PHASE_B_B2b3_COMPLETION.md` §2 — four line counts
   corrected, subtotal and total recomputed, audit-note paragraph
   appended.
4. `_reports/PHASE_B_B7_AUDIT.md` — this file.

No causal engine, schema, router, or unit test was changed. No
git tag was moved. No previous commit was amended (`v0.9.0-paper1`
remains anchored on `92a7a0f`).

## §5 Recommended follow-ups (NOT in this audit commit)

In rough priority order:

1. **B3 — OpenAPI snapshot + drift gate.** The Plan v2 §7 item
   #10 file paths are well-defined and the implementation is
   contained (snapshot JSON + 1 contract test). 1-2 h work.
2. **B5 — E2E causal full chain.** Items #4 end-to-end + #5 +
   #11 fall out of this. Requires a synthetic-or-real fixture
   that exercises identify → estimate → refute → mediation →
   sensitivity in sequence. 3-4 h work.
3. **B4 — Agent causal subgraph (5 nodes).** Items #2 + #3 land
   together. Larger surface (LangGraph routing, agent
   integration). Deferred to a separate planning round.
4. **`.gitignore` hygiene.** ~50+ historic untracked entries
   (`.agents/`, `reports/stabilize-v9/`, `_reports/PHASE_0_5_*`,
   etc.) pollute `git status`. Single commit to add
   `.gitignore` entries for the noise paths. Phase G hygiene.
5. **Plan v2 §7 #6 / #7 frontend verification.** Re-run `vitest`
   inside `frontend/` once to discharge item #6's "trust-only"
   status. Item #7 (B6 Mermaid panel) is optional per Plan v2.
6. **Plan v2 #8 217↔216 reconciliation.** Either update the Plan
   doc to read "216" or hunt down the dropped test. Likely a
   non-issue (test removed during B0.3 baseline cleanup), but
   the audit chain should note it.

## §6 Audit metadata

- Audit run at HEAD: `92a7a0f` + 3 working-tree edits (this commit
  squashes the 3 edits with this doc).
- Audit duration: ~25 min (4 rounds: grep / cross-check / Plan v2
  §7 mapping / regression).
- Tools used: `git status / log / diff / rev-list`, `wc -l`,
  `pytest --collect-only`, `pytest -k phase_a`, `grep` over
  `_reports/` and `backend/app/`.
- Tests run during audit:
  - 44 causal+gate tests after each inline edit (139.21 s, all
    PASS).
  - 216 phase_a tests for Plan v2 §7 #8 verification (46.39 s,
    all PASS).
- No production data was modified. No commits were amended. No
  tags were moved. No branches were force-pushed. The audit is
  read-mostly with three surgical doc / constant fixes appended.
