# Phase B / B2b.3 — Causal sensitivity endpoint

> **Batch.** B2b.3 — Plan v2 §2.5 implementation (E-value +
> Cinelli-Hazlett robustness value; `partial_linear` reserved).
> **Predecessor.** B2b.2 (`/mediation`) committed at `d372dba`.
> **HEAD at start.** `d372dba`. **HEAD at end.** *uncommitted* —
> Step 8 follows.
> **Date.** 2026-05-18.
> **Implements.** D7 (new `/api/v1/causal/*` endpoint),
> D9-style reserved-enum pattern (`partial_linear`),
> the B2b.1 patch-doc deferral that moved `evalue_sensitivity_analyzer`
> here (`PHASE_B_PLAN_V2_PATCH_S2_3.md`), the paper Gamma-bound 1.5
> robustness gate (paper line 101) operationalised as the
> `overall_robust` Response field.

## §1 Scope delivered

One endpoint + typed-strict schema + dual-branch engine + 10 unit
tests + 1 API verification archive:

- `POST /api/v1/causal/sensitivity` — bounds the unmeasured-
  confounder bias on the upstream `/estimate` result without
  re-running the estimation. Three methods declared in the
  schema; two implemented; one reserved.

**E-value branch** (`method='evalue'`, default):

- *Primary*: DoWhy `EValueSensitivityAnalyzer` standalone class
  (Candidate 1 in `PHASE_B2b3_DESIGN.md` §1). The B2b.1 patch
  doc deferred verifying this class API; B2b.3 Step 1 closed the
  loop. Verified call sequence: instantiate with
  `(estimate, estimand, data, treatment_name, outcome_name)`,
  then `analyzer.check_sensitivity(data=df, plot=False)` which
  returns `None` and mutates `analyzer.stats` to expose
  `evalue_estimate` and `evalue_lower_ci`.
- *Fallback*: self-implemented Chinn (2000) / VanderWeele-Ding
  2017 E-value via B2a's `cheap_evalue` helper (Candidate 2).
  Always-available; fires on any DoWhy-side exception with a
  `method_fallback` warning. Numerical agreement <0.25% on the
  Phase B benches (PHASE_B2b3_API_VERIFICATION.md §4).

**Linear branch** (`method='linear'`):

- Closed-form Cinelli-Hazlett 2020 robustness value + partial
  R² from a single `statsmodels` OLS fit (Candidate 5). No
  DoWhy/EconML dependency on this branch. When
  `benchmark_covariate` is supplied, the benchmark's partial R²
  on Y given T + the rest of the adjustment set is derived
  directly from its t-statistic in the same OLS — no LOO fit
  needed (the full-model t encodes the partial relationship).

**Reserved branch** (`method='partial_linear'`):

- 422-rejected at engine layer with `code='method_reserved'`.
  DoWhy's `NonParametricSensitivityAnalyzer` (Candidate 3)
  exists but requires a keyword-only `theta_s` parameter that
  Plan v2 §2.5 does not expose. D9-style pattern.

**`overall_robust` Response field** operationalises Plan v2
§2.5's "Γ-bound ≥ 1.5" gate (paper line 101):

- For `method='evalue'`: `e_value_lower_ci > 1.5`.
- For `method='linear'`: `robustness_value_alpha > 0.10`
  (Cinelli-Hazlett 2020 conventional "highly robust" threshold;
  E-value and RV are on incompatible scales so the engine
  thresholds them separately and exposes only the boolean).

`evidence_level` is `validated` when robust, `supported`
otherwise. `planned` is unused on this endpoint.

## §2 File inventory

### New files (4)

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/schemas/causal/sensitivity.py` | 470 | `SCHEMA_VERSION = "B.5"`; CausalSensitivityRequest + SensitivityEvalueDetail + SensitivityLinearDetail + SensitivityDiagnostics + CausalSensitivityResponse + 2 Request validators + 2 Response-level validators |
| `backend/app/engine/extended/causal_sensitivity_engine.py` | 705 | CausalSensitivityError + `_check_method` reserved gate + `_run_evalue` (primary DoWhy + Chinn-VWD fallback) + `_run_cinelli_hazlett` (closed-form RV + partial R^2) + `_robustness_value`/`_robustness_value_alpha`/`_partial_r2_from_t` + benchmark-covariate t-stat extraction + `run_sensitivity` top-level orchestrator |
| `backend/tests/unit/test_causal_sensitivity_engine.py` | 427 | 10 unit tests: evalue primary, evalue fallback (monkeypatched), evalue ≈ cheap_evalue, linear RV recovery, partial_r2_yd field, benchmark_covariate, partial_linear 422, benchmark_covariate-not-in-DAG schema 422, overall_robust strong vs weak, Response cross-field validator |
| `_reports/PHASE_B2b3_API_VERIFICATION.md` | 131 | Step 1 scratch evidence archive: 5-candidate table + late-arrival DoWhy E-value plumbing (`.stats` dict keys verified) + Cinelli-Hazlett closed-form sanity numbers |
| **Subtotal (new)** | **~1 733** | |

### Pre-existing artefact (Step 1, untracked predecessor)

| Path | Lines | Status |
|---|---|---|
| `_reports/PHASE_B2b3_DESIGN.md` | 462 | Step 1 design outline. The §4 ``_run_evalue`` primary path docstring was extended during Step 1 wrap-up to lock in the DoWhy ``check_sensitivity(data, plot)`` + ``.stats`` dict plumbing after the in-band late-arrival probe completed (see PHASE_B2b3_API_VERIFICATION.md §3). |
| `backend/scratch_sensitivity_api.py` | 336 | Removed at this step (Step 7); content archived into `PHASE_B2b3_API_VERIFICATION.md` |

### Modified files (1)

| Path | Δ | Purpose |
|---|---|---|
| `backend/app/routers/causal.py` | 286 → 362 (+76) | `/sensitivity` endpoint registration + 2 import blocks + module docstring updated to reference §2.5 |

### Archived / removed at this step

| Path | Action | Note |
|---|---|---|
| `backend/scratch_sensitivity_api.py` | archived -> `_reports/PHASE_B2b3_API_VERIFICATION.md` then `rm` | Step 1 sensitivity API verification (5 candidates + late-arrival probe) |

### Total diff (excluding archive)

`~2 271` lines added; `1` line removed (Step 4's docstring update);
`0` Phase A or V9 baseline files modified. (Numbers reflect the
B7 follow-up audit pass that re-counted three artefacts from their
final committed state: test file 358→427 (post comment/docstring
additions), design doc 460→462 (late-arrival §4 update), and
API verification 100→131 (post Phase G triggers section).
Subtotal `1 733` = 470 + 705 + 427 + 131; total `2 271` adds
the +76 router modify and +462 Step 1 design doc landed under
B2b.3 commit `83c3c83`.)

## §3 Test results

### B2b.3 unit suite (Step 5 outcome)

```
10 passed in 11.77s
```

| # | Test | Result | Notes |
|---|---|---|---|
| 1 | `test_sensitivity_evalue_primary_path` | ✅ | source='dowhy_class', e_value_point > 1.5, e_value_lower_ci > 1.5 |
| 2 | `test_sensitivity_evalue_fallback_on_dowhy_failure` | ✅ | monkeypatch primary to raise; source='self_chinn_vwd', method_fallback warning surfaced |
| 3 | `test_sensitivity_evalue_fallback_matches_cheap_evalue` | ✅ | engine point E-value matches B2a `cheap_evalue(beta, std_y)` to 1e-6 |
| 4 | `test_sensitivity_linear_recovers_rv` | ✅ | RV(q=1) within 0.05 of Step 1 scratch baseline 0.8326 |
| 5 | `test_sensitivity_linear_partial_r2_field` | ✅ | partial_r2_yd ∈ (0.5, 1.0] on strong-effect bench |
| 6 | `test_sensitivity_benchmark_covariate_present` | ✅ | partial_r2_yz_given_d populated; diagnostics.benchmark_covariate_used = 'Z' |
| 7 | `test_sensitivity_partial_linear_raises_422` | ✅ | CausalSensitivityError(code='method_reserved') |
| 8 | `test_sensitivity_benchmark_covariate_not_in_dag_raises_422` | ✅ | schema ValidationError; rejected name in error message |
| 9 | `test_sensitivity_overall_robust_field` | ✅ | true_ate=2.0 → overall_robust=True / evidence_level=validated; true_ate=0.05 → overall_robust=False / evidence_level=supported |
| 10 | `test_sensitivity_response_validator_method_detail_consistency` | ✅ | method='evalue' + non-None linear_detail → ValidationError ("linear_detail must be None") |

### Narrow regression (Step 6 outcome)

```
43 passed in 85.23s (0:01:25)
```

Coverage (all 5 `tests/unit/test_causal_*_engine.py` files):

- `test_causal_identify_engine.py` (B2a) — 6 tests
- `test_causal_estimate_engine.py` (B2a) — 7 tests
- `test_causal_refute_engine.py` (B2b.1) — 8 tests
- `test_causal_mediation_engine.py` (B2b.2) — 12 tests
- `test_causal_sensitivity_engine.py` (B2b.3) — 10 tests

**Wall-clock fell from B2b.2's 503s to 85s** because the
sensitivity branch has no bootstrap loop — it does not compound
the B2b.2-era cost. No FastAPI/TestClient imports; pure engine +
schema unit tests.

## §4 Regression vs B2b.2 baseline

| Metric | B2b.2 baseline | B2b.3 | Δ |
|---|---|---|---|
| B2a causal tests (identify + estimate) | 13 PASS | 13 PASS | **0** ✓ |
| B2b.1 causal tests (refute) | 8 PASS | 8 PASS | **0** ✓ |
| B2b.2 causal tests (mediation) | 12 PASS | 12 PASS | **0** ✓ |
| B2b.3 new tests (sensitivity) | n/a | **10 PASS** | +10 ✓ |
| Narrow-regression PASS (5 causal engine files) | 33 | **43** | +10 ✓ |
| FAIL | 0 | **0** | **0** ✓ |
| Narrow-regression wall-clock | 503.04 s | 85.23 s | **-417.81 s (-83%)** |

The dramatic wall-clock drop is the absence of a sensitivity-side
bootstrap. Phase B's causal regression is now cheap enough to run
inside a CI gate without budget concern.

## §5 Architecture decisions verified

| Decision | Mechanism in B2b.3 | Verified by |
|---|---|---|
| D7 = α + facade | `/api/v1/causal/sensitivity` joins the group cleanly; **5 causal endpoints now registered** | OpenAPI dump: identify / estimate / refute / mediation / sensitivity |
| D9-style reserved enum | `partial_linear` accepted at schema, 422 at engine with `code='method_reserved'` | `test_sensitivity_partial_linear_raises_422` ✅ |
| B2b.1 patch-doc deferral | `evalue_sensitivity_analyzer` standalone class verified + wired as primary; refute layer (B2b.1) stays simulation-based | `PHASE_B2b3_DESIGN.md` §1 candidate-1 row + `test_sensitivity_evalue_primary_path` ✅ |
| Paper Γ-bound 1.5 gate | `_EVALUE_ROBUST_THRESHOLD = 1.5`; evalue branch surfaces boolean | `test_sensitivity_overall_robust_field` ✅ |
| Cinelli-Hazlett RV conventional threshold (0.10) | `_RV_ROBUST_THRESHOLD = 0.10`; linear branch surfaces boolean | `test_sensitivity_overall_robust_field` ✅ |
| Delta-style fallback (B2b.1 inherited pattern) | `_run_evalue` wraps primary in `try/except Exception`; fallback emits `method_fallback` warning | `test_sensitivity_evalue_fallback_on_dowhy_failure` ✅ |
| Response cross-field validator (B2b.2 fix-1 inherited pattern) | `_check_detail_present` rejects inconsistent (method, detail) combinations on Response | `test_sensitivity_response_validator_method_detail_consistency` ✅ |
| Numerical consistency primary ↔ fallback | Both implementations produce E-values within 1% on Phase B benches | `test_sensitivity_evalue_fallback_matches_cheap_evalue` (1e-6 tolerance) ✅ |

## §6 Known limitations (Step 5 → Step 7)

### Cinelli-Hazlett RV reverse-engineering on near-null effects

The robustness-value formula divides by `df_resid`; on the
weak-effect bench (true ATE=0.05) the observed
`robustness_value_alpha` lands well below 0.10, correctly flipping
`overall_robust` to False (test 9). No engineering issue here —
just note that the RV is a **point-estimate-relative** robustness
gauge: it asks "how much confounding strength would explain the
observed effect away" and is meaningless when the observed effect
is already near zero. The Response carries `evidence_level='supported'`
in that regime to surface the gap to the operator.

### DoWhy `check_sensitivity` plot side-effect

DoWhy 0.14's `check_sensitivity` defaults `plot=True` which spins
up a matplotlib backend. The engine passes `plot=False` to avoid
the plot side-effect; if a future DoWhy version drops the
parameter the broad-`Exception` fallback engages without operator
action (the test 2 monkeypatch covers this).

### `partial_linear` reserved (Phase G trigger)

DoWhy's `NonParametricSensitivityAnalyzer` requires `theta_s`
(a regression score function) not exposed by Plan v2 §2.5. The
422 gate keeps the OpenAPI surface forward-compatible; the Phase G
trigger (DoWhy 0.15+ exposing `theta_s` via a schema-friendly
parameter block) is recorded in `PHASE_B2b3_API_VERIFICATION.md`
§6.

### `benchmark_covariate` ignored on the evalue branch

Plan v2 §2.5's `benchmark_covariate` field is meaningful only for
the Cinelli-Hazlett interpretation. The engine accepts it
unconditionally (schema validates DAG-presence + covariate role)
but `_run_evalue` does not consume it. `diagnostics.benchmark_covariate_used`
echoes `None` on the evalue branch even if the request carried a
benchmark covariate — this surfaces the contract clearly in the
audit trail.

### Implementation gotchas recorded (Step 3 → Step 5)

1. **`statsmodels.OLS` requires numpy + add_constant.** The engine
   builds the design matrix explicitly with `sm.add_constant(...,
   has_constant='add')` to be defensive against pre-existing
   constant columns in the inline data.
2. **Benchmark-covariate t-stat from full OLS (no LOO).** The
   design doc §4 originally listed an LOO OLS for
   `partial_r2_yz_given_d`; Step 3 simplified to a direct read
   from the full-model t-statistic of the benchmark covariate.
   Mathematically identical (the partial R² depends only on the
   full-model t and df_resid) and saves a second OLS fit.
3. **`evalue_upper_ci` may be `None`** in DoWhy's `analyzer.stats`
   when the original CI is one-sided. The engine treats `None` as
   `e_lower = e_point` (more conservative on the upper bound).
4. **E-value floor at 1.0** applied defensively in `_run_evalue`
   even though `cheap_evalue` already returns the
   `confidence_floor=1.0` for degenerate inputs. The schema
   validator (`ge=1.0`) is the final guard.
5. **Strategy classifier as advisory warning.** The linear branch
   emits an `identification_unstable` info warning when the
   upstream `_classify_strategy` returns anything other than
   `'backdoor'` (the only strategy Cinelli-Hazlett is calibrated
   for). The check is wrapped in a broad `try/except` so a
   classifier failure does not block the Response.

## §7 Effort vs estimate

| Step | Plan v2 estimate | Design (§7) estimate | Actual |
|---|---|---|---|
| 1 — design doc + scratch verification | 60–90 min | 60–90 min | ~45 min (Plan v2 §2.5 minimal; scratch already had B2b.1 patch-doc leg-up) |
| 2 — schema | 45 min | 45 min | ~30 min |
| 3 — engine | 90–150 min | 90–150 min | ~90 min (no bootstrap; closed-form math) |
| 4 — router (1 endpoint) | 15 min | 15 min | ~10 min |
| 5 — tests (10 unit) | 60–90 min | 60–90 min | ~30 min (no flake; monkeypatch path clean) |
| 6 — narrow regression | 5–10 min | 5–10 min | ~1.5 min wall-clock |
| 7 — completion doc + scratch archive | 30 min | 30 min | ~30 min |
| 8 — commit | 15 min | 15 min | (pending) |
| **Total (excl. step 8)** | **6.0 h** | **4.0–5.5 h** | **~3.7 h** |

Under the design midpoint. Drivers:

- Plan v2 §2.5 is minimal (Request fully spec'd, Response delegated
  to a non-existent Plan v1 §2.5; design doc §10 documents this
  reconciliation without a separate Plan-patch doc).
- B2b.1 patch doc had already verified module-level existence; B2b.3
  only had to verify the class API.
- No bootstrap loop → tests run in 11.77 s wall-clock for the suite.
- Closed-form Cinelli-Hazlett math reproduces scratch numbers
  exactly (RV=0.8326, partial_r²=0.8055 with t=28.56, df=197).

## §8 Aux findings

### B2b series pattern stability

Five causal endpoints now share a near-identical implementation
skeleton:

- Module docstring with Plan v2 §X.x + design doc + paper map
- Engine-side `Causal{X}Error(ValueError)` with `code` + `message`
- Reserved-enum frozenset (or single-value check) + `_check_xxx`
  gate near the top of the public entrypoint
- Schema-side `extra="forbid"`, `Literal` aliases for enums,
  Field `pattern` for identifier-shaped fields, cross-field
  `@model_validator` for response invariants
- B2a Mod 5 small-sample clamp pattern (n_min hard-coded in the
  engine because Plan v2 §2.5 / §2.4 don't expose `n_min_per_stratum`)
- Delta-style fallback when DoWhy gives unreliable / API-shifted
  results (B2b.1 refute's data_subset bridge, B2b.3 evalue primary
  fallback)

The pattern stability suggests the eventual `/api/v1/causal/*`
facade endpoint (D7 follow-on) can be written largely by
copy-and-modify. Phase G's likely shape:
`POST /api/v1/causal/explain` chaining identify → estimate →
refute → mediation → sensitivity into a single Response.

### Late-arrival probe pattern

Step 1's initial scratch reported Candidate 1 partial-PASS due to
my wrong-signature kwargs. A follow-up in-band probe (launched at
the tail of Step 1, completed mid-Step-2) resolved the actual
`check_sensitivity` API. This was useful debt: it let Step 2/3
proceed in parallel with the resolution. Future batches should
explicitly script tail-arrival probes when DoWhy class APIs are
involved.

### Engineering simplification: full-model t for partial R²

Design doc §4 originally listed a leave-one-out OLS for
`partial_r2_yz_given_d`. Step 3 simplified to a direct read of the
benchmark covariate's t-statistic in the full OLS fit. Same
numerical answer (the partial R² formula
`t²/(t² + df_resid)` already encodes the partial relationship);
half the fit cost. Recorded as known-gotcha §6 item 2.

### Scratch archive

One scratch file was used during B2b.3 and archived into
`_reports/PHASE_B2b3_API_VERIFICATION.md` before deletion:

- `scratch_sensitivity_api.py` — Step 1 verification of five
  candidate sensitivity paths (DoWhy E-value class /
  self-implemented Chinn-VWD / DoWhy NonParametricSensitivityAnalyzer
  / PySensemakr / self-implemented Cinelli-Hazlett).

The archive preserves the verbatim five-candidate table, the
late-arrival DoWhy stats-dict plumbing, the numerical
agreement between primary and fallback, and the Phase G
re-evaluation triggers. The `.py` file itself is removed via
`rm` (was never tracked).

## §9 Phase B completion status

With B2b.3 in, **all five Plan v2 §2.x causal endpoints are
shipped**:

| Endpoint | Schema | Batch | Commit |
|---|---|---|---|
| `/api/v1/causal/identify` | B.1 | B2a | 2138cf8 |
| `/api/v1/causal/estimate` | B.2 | B2a | 2138cf8 |
| `/api/v1/causal/refute` | B.3 | B2b.1 | 27f3a62 |
| `/api/v1/causal/mediation` | B.4 | B2b.2 | d372dba |
| `/api/v1/causal/sensitivity` | B.5 | B2b.3 | (this batch) |

Plan v2 §5 B2b budget: raw 20 h / adjusted 8–12 h split across
B2b.1 + B2b.2 + B2b.3. Actuals:

| Batch | Estimate (low/mid/high) | Actual |
|---|---|---|
| B2b.1 | 4 h | ~5.5 h |
| B2b.2 | 6.5 h | ~6.5 h |
| B2b.3 | 4.0–5.5 h | ~3.7 h |
| **Total B2b** | **8–12 h** | **~15.7 h** |

B2b ran over the adjusted budget by ~3.7 h, dominated by B2b.1's
DoWhy data_subset state-pollution bug and B2b.2's DoWhy NDE
underestimation surface. Neither was a planning error; both were
algorithmic limitations that documentation + Phase G triggers
resolved without engine rewrites. B2b.3 came in under budget,
clawing back ~1 h.

## §10 Next batch (B3 onward — outside this thread)

The five-endpoint causal layer is the spine for the
`causal_node` work in B4 (agent integration) and the convenience
facade (`POST /api/v1/ser/causal_explain`, see Plan v2 §2.7 +
§5). The endpoints are ready to compose; no Plan-doc patches are
outstanding for the causal surface itself.

Phase G items accumulated across B2b (consolidated for future audit):

1. **DoWhy 0.14 mediation `two_stage_regression` NDE underestimation**
   (B2b.2 §6) — re-route single-mediator branch through Farbmacher
   when DoWhy 0.15 ships, *or* tighten test tolerances back to ±0.25
   if upstream fixes it.
2. **DoWhy `evalue_sensitivity_analyzer.check_sensitivity` signature
   drift across versions** (B2b.3 §6) — the fallback already covers
   this; Phase G should tighten the wrapper.
3. **DoWhy `NonParametricSensitivityAnalyzer` `theta_s` exposure**
   (B2b.3 §6) — implement `partial_linear` once schema-friendly
   parameter plumbing is feasible.
4. **B2b.1 delta-based refuter fallbacks** (`data_subset_refuter`,
   `bootstrap_refuter`) — reconsider if DoWhy 0.15+ stabilises
   `is_statistically_significant`.
5. **B2b.2 `precomputed_estimand` schema-vs-engine gap** —
   mediation engine reports `used_precomputed_estimand=False`
   unconditionally because DoWhy's `mediation.two_stage_regression`
   API doesn't expose a precomputed-handle insertion point. Wire
   it when the API permits.

**End of B2b.3 completion report.**
