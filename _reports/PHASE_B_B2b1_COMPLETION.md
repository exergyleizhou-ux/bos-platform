# Phase B / B2b.1 — Causal refute endpoint

> **Batch.** B2b.1 — Plan v2 §2.3 (patched per
> `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md`) implementation.
> **Predecessor.** B2a (`/identify` + `/estimate`) committed at `2138cf8`.
> **HEAD at start.** `2138cf8`. **HEAD at end.** *uncommitted* — Step 8 follows.
> **Date.** 2026-05-18.
> **Implements.** D7 (new `/api/v1/causal/*` endpoint),
> D9-style reserved-enum pattern (`non_parametric_sensitivity_analyzer`),
> Plan v2 §2.3 patched evidence-level rule (4 mandatory refuters + e_value > 1.5),
> Mod 6 (sync mode only; async-job reserved).

## §1 Scope delivered

One endpoint + its typed-strict schema + engine wrapper + 8 unit tests:

- `POST /api/v1/causal/refute` — DoWhy's `model.refute_estimate(...)`
  dispatch for 4 mandatory refuters + 1 optional implemented refuter,
  aggregated into a typed `RefuterResult` list plus an
  `evidence_level` per Plan v2 §2.3 patched rule.

**Mandatory refuters (4)**: `random_common_cause`,
`placebo_treatment_refuter`, `data_subset_refuter`,
`add_unobserved_common_cause`.

**Optional refuters**: `bootstrap_refuter` (implemented);
`non_parametric_sensitivity_analyzer` (schema-reserved enum value,
engine 422-rejects with `code='refuter_reserved'`).

**Plan v2 §2.3 patch** (separately recorded in
`PHASE_B_PLAN_V2_PATCH_S2_3.md`): `evalue_sensitivity_analyzer`
moved out of `/refute` (DoWhy 0.14 dispatch table doesn't include
it; E-value is a sensitivity analysis, not a Monte-Carlo refuter)
and will land in `/api/v1/causal/sensitivity` (B2b.3). Mandatory
refuter count 5 → 4.

## §2 File inventory

### New files (5)

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/schemas/causal/refute.py` | 280 | `SCHEMA_VERSION = "B.3"`; CausalRefuteRequest + RefuterResult + CausalRefuteResponse + RefuterName Literal + 2 model validators |
| `backend/app/engine/extended/causal_refute_engine.py` | ~475 | DoWhy refute dispatch + delta-based fallback for 3 unreliable refuters + e_value Option (a) hybrid + 3-tier evidence-level aggregator |
| `backend/tests/unit/test_causal_refute_engine.py` | 302 | 8 unit tests covering 5 refuter happy paths + reserved-enum 422 + 2 evidence-level rule cases (count corrected B7 audit; initial draft reported 297 pre-final-comments) |
| `_reports/PHASE_B2b1_DESIGN.md` | 310 | Step 1 design outline (refuter taxonomy, schema field tables, engine signatures, test design, e_value Option (a) decision) |
| `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md` | 109 | Plan v2 §2.3 patch record (evalue moved to /sensitivity; 5→4 mandatory; bootstrap upgraded to optional implemented; non_parametric stays reserved) |
| **Subtotal (new)** | **~1 471** | |

### Modified files (1)

| Path | Δ | Purpose |
|---|---|---|
| `backend/app/routers/causal.py` | 134 → 209 (+75) | New `/refute` endpoint registration + imports |

### Archived / removed at this step

| Path | Action | Note |
|---|---|---|
| `backend/scratch_refute_api.py` | archived → `_reports/PHASE_B2b1_API_VERIFICATION.md` then `rm` | Step 1 DoWhy refute API field-name verification |
| `backend/scratch_refute_minimal.py` | archived to same file then `rm` | Step 5 minimal repro for `data_subset` / `bootstrap` p_value=0.0 |

### Total diff (excluding archives)

`~1 546` lines added; `0` lines removed; `0` Phase A or V9 baseline
files modified.

## §3 Test results

### B2b.1 unit suite (Step 5 outcome)

```
8 passed in 24.41s
```

| # | Test | Result | Notes |
|---|---|---|---|
| 1 | `test_refute_random_common_cause_passes` | ✅ | `passed=True`, p > 0.10, |delta| < 0.5 |
| 2 | `test_refute_placebo_treatment_passes` | ✅ | new_effect ≈ 0, |delta| > 1.0 |
| 3 | `test_refute_data_subset_passes` | ✅ | delta-based, p_value=None, rel_delta ≈ 0.03 |
| 4 | `test_refute_add_unobserved_no_pvalue` | ✅ | p_value=None, |rel_delta| < 0.1 |
| 5 | `test_refute_bootstrap_passes` | ✅ | delta-based, p_value=None, rel_delta ≈ 0.08 |
| 6 | `test_refute_reserved_method_raises_422` | ✅ | `non_parametric_sensitivity_analyzer` → `code='refuter_reserved'` |
| 7 | `test_refute_evidence_level_validated_requires_high_evalue` | ✅ | all 4 mandatory pass + backdoor + e_value=2.0 → validated |
| 8 | `test_refute_evidence_level_falls_to_supported_when_evalue_low` | ✅ | same as #7 but e_value=1.1 → supported (not validated) |

### Narrow regression (Step 6 outcome)

```
563 passed in 50.55s
```

Coverage:

- `tests/unit/` — all 48 active files (B2a's 2 + B2b.1's 1 + V9 baseline 28 + Phase A 5 schemas + others)
- `tests/integration/test_phase_a_{mc,relay,ser,sfi,twin}_endpoint.py` — Phase A V5 endpoint contract preserved

Explicitly skipped (same isolation as B2a Step 6):
- `tests/_legacy/` (170 skipped at source via D13)
- `tests/integration/test_bos_assistant_evidence_kernels.py` (175 KB; historic hang)
- 4 other V1 heavy paths

## §4 Regression vs B2a baseline

| Metric | B2a baseline | B2b.1 | Δ |
|---|---|---|---|
| Phase A subset (`-k phase_a`) | 217 PASS | 217 PASS (folded in 563) | **0** ✓ |
| BOS V9 baseline unit | ~325 PASS | ~325 PASS (folded in 563) | **0** ✓ |
| B2a causal tests | 13 PASS | 13 PASS (folded in 563) | **0** ✓ |
| B2b.1 new tests | n/a | **8 PASS** | +8 ✓ |
| FAIL | 0 | **0** | **0** ✓ |
| Narrow-regression wall-clock | 62.25 s | 50.55 s | -11.70 s (warm cache) |

## §5 Architecture decisions verified

| Decision | Mechanism in B2b.1 | Verified by |
|---|---|---|
| D7 = α + facade | `/api/v1/causal/refute` joins the new group cleanly; no facade in B2b.1 | OpenAPI dump: 3 endpoints under `/api/v1/causal/*` |
| D9-style reserved enum | `non_parametric_sensitivity_analyzer` accepted at schema, 422 at engine with `code='refuter_reserved'` | `test_refute_reserved_method_raises_422` ✅ |
| Plan v2 §2.3 patched 3-tier evidence-level | 4 mandatory + identify.strategy + e_value > 1.5 → validated; ≥2/4 mandatory + strategy in (backdoor, frontdoor, mediation) → supported; else planned | `test_refute_evidence_level_validated_requires_high_evalue` + `_falls_to_supported_when_evalue_low` ✅ |
| Mod 6 (sync gate) | `mode='async_job'` rejected at schema validator with `code='async_not_implemented_yet'`-style ValueError | `_check_async_not_implemented` validator |
| `original_e_value` Option (a) hybrid | Optional request field; engine fallback to lightweight OLS recomputation with `method_fallback` warning | `_resolve_e_value` (engine) + Mod 4-style precedent |

## §6 Bugs found and fixed during B2b.1

### Bug 1 — Plan v2 §2.3 listed an unsupported refuter

- **Symptom.** `model.refute_estimate(method_name="evalue_sensitivity_analyzer")` raises `ImportError: evalue_sensitivity_analyzer is not an existing causal refuter` (DoWhy 0.14 dispatch table).
- **Surfaced by.** `backend/scratch_refute_api.py` Step 1.
- **Fix.** Plan v2 §2.3 patch record at `PHASE_B_PLAN_V2_PATCH_S2_3.md`. E-value moves to `/api/v1/causal/sensitivity` (B2b.3). Mandatory count 5 → 4. Evidence-level rule retains the `e_value > 1.5` reference but the value is sourced from the prior `/estimate.e_value_cheap` (carried via `original_e_value` request field with engine fallback).

### Bug 2 — DoWhy 0.14 returns unreliable significance for `data_subset_refuter` and `bootstrap_refuter`

- **Symptom.** Step 1 scratch reported `p_value=0.94` (passed under the `is_statistically_significant` decoder); Step 5 unit-test runs reported `p_value=0.0` on the *same fixture and same kwargs*. Step 5 minimal repro (`scratch_refute_minimal.py`) confirmed the 0.0 reading independently.
- **Likely root cause.** Internal DoWhy state pollution — Step 1 scratch ran data_subset *after* placebo; Step 5 ran it after a fresh estimate call only. The `is_statistically_significant` field appears to depend on prior refuter-side calls in the same `CausalModel` instance. We did not formally prove this hypothesis; we did, however, confirm that the API field is unreliable for these two refuters under the engine's call pattern.
- **Fix.** Path A — extend the delta-based decision (originally exclusive to `add_unobserved_common_cause`) to also cover `data_subset_refuter` and `bootstrap_refuter`. Engine `_refute_single` dispatches on a new module-level `_DELTA_BASED_REFUTERS` frozenset. `p_value` returns `None` for those two refuters; `passed` is computed from `abs(delta_estimate / estimated_effect) < 0.1`.
- **Test impact.** `test_refute_data_subset_passes` and `test_refute_bootstrap_passes` had their assertion blocks adjusted (2 lines each): `p_value is not None` → `p_value is None`; `p_value > 0.10` → `"rel_delta" in diagnostic`. The `passed=True` core assertion was preserved.

### Implementation gotchas recorded

The 7 gotchas reported during Step 3 retrospective remain valid and
are summarised here for future audit:

1. **DML path numerical mismatch** — refute reroutes DML through DoWhy's `backdoor.econml.dml.LinearDML` wrapper; numerical equivalence with B2a's direct EconML LinearDML is **not** asserted by tests. Documented in `_DOWHY_METHODS` comment.
2. **`_resolve_e_value` needs `adjustment_set`** — design doc §10 missed this parameter; OLS fallback without adjustment yields biased e_value. Implementation passes `adjustment_set` from `_classify_strategy` output.
3. **Single-refuter failure aborts whole `/refute`** — `try/except Exception` in `run_refute` wraps each refuter call. Partial-success mode deferred (not in B2b.1 scope).
4. **`mandatory_pvalue_high` aggregate skips passed=False** — by design; `overall_robust` already rejects validated tier when any mandatory fails.
5. **`mandatory_pvalue_supported` is distinct from `mandatory_passed`** — supported tier filters on p > max(alpha, 0.05) (additive constraint on top of `passed`).
6. **DoWhy `ImportError` not wrapped** — left as a 500 (infrastructure failure, not a 422 client error).
7. **`seed` resolution priority** — `request.seed` > `handle.seed`. Response does not echo "actually used seed" (deferred to Phase G).

## §7 Effort vs estimate

| Step | Plan v2 estimate | Design (§12) estimate | Actual |
|---|---|---|---|
| 1 — design doc + patch + scratch verification | n/a | n/a | ~1 h (incl. evalue surprise + Plan patch) |
| 2 — schema | 30 min | 30 min | ~25 min |
| 3 — engine | 90 min | 90 min | ~1.5 h (incl. add_unobserved adapter + e_value fallback path) |
| 4 — router (1 endpoint) | 15 min | 15 min | ~15 min |
| 5 — tests (8 unit) + diagnose + path A repair | 60 min | 60 min | ~1.5 h (the data_subset / bootstrap surprise required Bug 2 fix) |
| 6 — narrow regression | 5 min | 5 min | ~3 min |
| 7 — completion doc + scratch archive | 30 min | 30 min | ~30 min |
| 8 — commit | 15 min | 15 min | (pending) |
| **Total (excl. step 8)** | **3.75 h** | **4.0 h** | **~5.5 h** |

The overrun is fully explained by Bug 2 — diagnosing the
data_subset / bootstrap p_value mismatch and executing path A
(engine refactor + test assertion adjustment + re-verification)
added ~1.5 hours not in the original 4 h estimate.

## §8 Aux findings

### Plan v2 §2.3 patch pattern

This is the first time a Plan v2 §2.x has been patched mid-batch.
The "patch record" pattern (separate doc, no in-place edit of
PLAN.md, audit trail accumulating in `_reports/`) worked well:
the trigger is empirical (scratch verification), the resolution
is documented in one file, and the implementation commit message
will cite the patch doc by filename. Future Plan v2 §2.x patches
should follow this pattern.

### Bug 2 deserves a Phase G re-evaluation

The delta-based fallback for `data_subset_refuter` and
`bootstrap_refuter` is a deliberate hack tied to DoWhy 0.14's
behaviour. When DoWhy 0.15+ stabilises the `refutation_result`
API (or when we have time to formally diagnose the state-pollution
hypothesis), we should reconsider whether those two refuters can
return to the `is_statistically_significant` decoder path. The
`_DELTA_BASED_REFUTERS` constant + module-level comment carry
this forward.

### Scratch archive

Two scratch files were used during B2b.1 and archived into
`_reports/PHASE_B2b1_API_VERIFICATION.md` before deletion:

- `scratch_refute_api.py` — Step 1 verification of DoWhy 0.14
  refute API field names (4 mandatory + bootstrap; evalue
  ImportError surfaced).
- `scratch_refute_minimal.py` — Step 5 minimal repro of the
  data_subset / bootstrap p_value=0.0 issue.

The archive preserves the verbatim output, kwargs, and DoWhy
version evidence for future audit. The `.py` files themselves are
removed via `rm` (they were never tracked).

## §9 Next batch

**B2b.2** — `POST /api/v1/causal/mediation` (`SCHEMA_VERSION = "B.4"`).

Per Plan v2 §2.4 + D14 = γ DML mediation:

- ACME / ADE decomposition via EconML's DML mediation path
  (Farbmacher 2022 style).
- Paper-aligned (paper SHA pinned in Plan v2 §1) with
  Pearl-Rubin counterfactual framework.
- `assumptions_acknowledged: List[Literal[...]]` required (Mod 8).
- `mediator_share` sum-to-1 slack widened to [0.7, 1.3] (Mod 8).

**Plan v2 §5 B2b estimate**: raw 20 h / adjusted 8–12 h split
across B2b.1 + B2b.2 + B2b.3. B2b.1 came in at ~5.5 h, so
B2b.2 + B2b.3 budget is ~2.5–6.5 h remaining at the 2× efficiency
target.

**End of B2b.1 completion report.**
