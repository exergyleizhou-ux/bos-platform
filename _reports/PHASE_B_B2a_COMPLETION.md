# Phase B / B2a — Causal identify + estimate

> **Batch.** B2a — Plan v2 §5 / §2.1 + §2.2 implementation.
> **HEAD at start.** `84fe8f2` (post pytest.ini -x removal).
> **HEAD at end.** *uncommitted* — Step 8 follows on user say-so.
> **Date.** 2026-05-18.
> **Implements.** Plan v2 D6 = α (numpy 2.x landed in B1), D7 = α
> (new `/api/v1/causal/*` group), D8 = γ + DAG library (B0.7 fixtures
> ready), D9 = α (single LinearDML MVP), D10 = δ axis 1 (seeded
> smoke tests), D14 = γ (DML mediation framework — refute / mediation
> endpoints land in B2b).

## §1 Scope (delivered)

Two endpoints + their typed-strict schemas + engine wrappers + unit
tests:

- `POST /api/v1/causal/identify` — DoWhy `CausalModel.identify_effect`
  with deterministic strategy classification (backdoor / frontdoor /
  iv / mediation / trivial / unidentifiable). Returns
  `IdentifiedEstimandHandle` for forward use by `/estimate`.
- `POST /api/v1/causal/estimate` — three method families:
  `linear_regression` (statsmodels OLS), `propensity_score` (DoWhy
  IPW), `dml` (EconML LinearDML — D9 = α MVP). Reserved enum values
  `causal_forest_dml` / `x_learner` are accepted at the schema layer
  and 422-rejected by the engine, keeping the OpenAPI surface
  forward-compatible.

## §2 File inventory

### New files (11)

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/schemas/causal_common.py` | 345 | DagSpec / DagNode / DagEdge / CausalData / IdentifiedEstimandHandle / EstimateHandle / MethodParams / DmlParams / CausalWarning + shared Literal types |
| `backend/app/schemas/causal/__init__.py` | 12 | package marker + docstring on the B.1–B.5 split |
| `backend/app/schemas/causal/identify.py` | 166 | `SCHEMA_VERSION = "B.1"` — Identify request/response + 4 model-level validators |
| `backend/app/schemas/causal/estimate.py` | 276 | `SCHEMA_VERSION = "B.2"` — Estimate request/response + 4 model-level validators (sync size gate, method_params alignment, precomputed_estimand fingerprint match, treatment/outcome in DAG) |
| `backend/app/engine/extended/causal_utils.py` | 230 | DAG → GML / NetworkX adapters; dataset fingerprint; per-stratum count; cheap E-value (VanderWeele-Ding 2017 with Chinn 2000 RR approximation); covariate split + DML pre-condition |
| `backend/app/engine/extended/causal_identify_engine.py` | 266 | DoWhy identify_effect wrapper + strategy classifier + assumptions-to-strategy mapping + evidence-level rule |
| `backend/app/engine/extended/causal_estimate_engine.py` | 545 | DoWhy / EconML estimate dispatch; precomputed-estimand re-use; n_min_per_stratum clamp; cheap E-value inline computation |
| `backend/app/routers/causal.py` | 134 | `/api/v1/causal/{identify,estimate}` FastAPI router + 422 mapping for `CausalEstimateError(code=...)` |
| `backend/tests/unit/test_causal_identify_engine.py` | 157 | 6 unit tests (trivial / backdoor / mediation / fingerprint echo / assumptions × 2) |
| `backend/tests/unit/test_causal_estimate_engine.py` | 244 | 7 unit tests (LR ATE recovery / DML ATE recovery / DML no-continuous-covariate guard / reserved-method 422 / small-n clamp / precomputed estimand re-use / handle round-trip) |
| **TOTAL** | **~2 375** | |

### Modified files (1)

| Path | Δ | Purpose |
|---|---|---|
| `backend/app/routers/__init__.py` | +2 | Register `causal.router` under prefix `/causal` with tag `Causal (Phase B)` |

### Total diff

`~2 377` lines added; `0` lines removed. No Phase A or V9 baseline file modified.

## §3 Test results

### B2a unit suite (Step 5 outcome)

```
13 passed in 19.45s
```

| # | Test | Result |
|---|---|---|
| 1 | `test_identify_trivial_dag` | ✅ |
| 2 | `test_identify_backdoor_with_confounder` | ✅ |
| 3 | `test_identify_mediation_when_mediator_tagged_on_path` | ✅ |
| 4 | `test_identify_estimand_handle_carries_fingerprint` | ✅ |
| 5 | `test_identify_assumptions_match_strategy_backdoor` | ✅ |
| 6 | `test_identify_assumptions_match_strategy_mediation` | ✅ |
| 7 | `test_estimate_linear_regression_recovers_ate` | ✅ ATE within 0.25 of true=2.0 on n=200 |
| 8 | `test_estimate_dml_recovers_ate` | ✅ ATE within 0.5 of true=2.0 on n=80 |
| 9 | `test_estimate_dml_requires_continuous_covariate` | ✅ |
| 10 | `test_estimate_reserved_method_raises_422` | ✅ `method_family_reserved` |
| 11 | `test_estimate_small_n_clamps_to_planned` | ✅ planned + `small_sample` warning |
| 12 | `test_estimate_uses_precomputed_estimand` | ✅ `used_precomputed_estimand=True` |
| 13 | `test_estimate_handle_roundtrips_request` | ✅ |

### Narrow regression (Step 6 outcome)

```
555 passed in 62.25s (1:02)
```

Coverage:

- `tests/unit/` — all 47 active files (B2a's 2 + V9 baseline 28 + Phase A 5 schemas + reference / external-source / vision / risk / sensitivity / mass-balance / ser / flight-envelope / kinetics / digital-twin / etc.)
- `tests/integration/test_phase_a_{mc,relay,ser,sfi,twin}_endpoint.py` — Phase A V5 endpoint contract preserved

Explicitly skipped (D13 / hang-risk):

- `tests/_legacy/` (170 skipped at the source) — D13 already applied
- `tests/integration/test_bos_assistant_evidence_kernels.py` (175 KB; suspected of historic 9-min hang)
- `tests/integration/test_bos_router_live.py` / `test_simulation_lab_router.py` / `test_external_knowledge_matrix.py` / `test_twin_router.py` — V1 heavy paths not in B2a's modification path

## §4 Regression vs B1 baseline

| Metric | B1 (post-B0.7) | B2a Step 6 narrow | Δ |
|---|---|---|---|
| Phase A subset (`-k phase_a`) | 217 PASS | 217 PASS (folded in 555) | **0** ✓ |
| BOS V9 baseline unit | ~325 PASS | ~325 PASS (folded in 555) | **0** ✓ |
| B2a new tests | n/a | **13 PASS** | +13 ✓ |
| FAIL | 0 | **0** | **0** ✓ |
| Narrow-regression wall-clock | (not measured) | 62.25 s | — |

Full backend regression (`pytest tests/ agent/tests/`) was **not** run
in B2a per the task brief (`-k` wildcards caused a 9-minute hang
historically; the narrow Tier-1 + Tier-2 path proved sufficient for
this batch). The full regression will be exercised in B5 with the
same scope-limiting flags.

## §5 Architecture decisions verified

| Decision | Mechanism in B2a | Verified by |
|---|---|---|
| D6 = α numpy 2.x | All deps live in `.venv-backend`; DoWhy + EconML run on numpy 2.4.5 | All 13 tests + 555 narrow regression |
| D7 = α + facade | `/api/v1/causal/*` group registered; facade `/api/v1/ser/causal_explain` reserved for B2b | Router OpenAPI dump (Step 4 ACK) |
| D8 = γ + DAG library | `_reports/PHASE_B_DAGS/*.json` already committed; DagSpec.source enum includes `"library"` value | DagSpec validator + schema |
| D9 = α LinearDML MVP | Reserved enum values `causal_forest_dml` / `x_learner` 422-rejected at engine layer | `test_estimate_reserved_method_raises_422` ✅ |
| D10 = δ axis 1 | Seeded smoke tests (np.random.default_rng(42)) for ATE recovery | `test_estimate_linear_regression_recovers_ate` / `test_estimate_dml_recovers_ate` ✅ |
| D14 = γ DML mediation | Mediation strategy detected in identify; full mediation endpoint lands in B2b | `test_identify_mediation_when_mediator_tagged_on_path` ✅ |
| Mod 3 (DAG cycle reporting) | Schema validator surfaces smallest cycle | Smoke test during Step 2 |
| Mod 4 (precomputed estimand) | `CausalEstimateRequest.precomputed_estimand` skips re-identification | `test_estimate_uses_precomputed_estimand` ✅ |
| Mod 5 (n_min_per_stratum) | n < threshold → `evidence_level="planned"` + `small_sample` warning | `test_estimate_small_n_clamps_to_planned` ✅ |
| Mod 6 (sync gate) | Inline > 10 000 rows + mode="sync" → 422 | Smoke test during Step 2 |
| `e_value_cheap` (Mod 9) | Computed inline during /estimate using Chinn 2000 approximation | Returned in `CausalEstimateResponse.e_value_cheap` |

## §6 Bugs found and fixed during B2a

Two engine-layer bugs were surfaced by the 13-test suite and fixed
under user supervision:

### Bug 1 — `dag_to_gml()` missing `directed 1`

- **Symptom.** 8 of 13 tests failed with
  `networkx.exception.NetworkXError: graph should be directed acyclic`
  inside `dowhy.graph.check_valid_backdoor_set`.
- **Root cause.** NetworkX's `parse_gml()` defaults to `Graph`
  (undirected) unless `directed 1` is explicitly declared in the
  GML payload. DoWhy's d-separation check downstream of the
  back-door verification then sees an undirected graph and raises.
- **Fix.** 1-line change to `causal_utils.dag_to_gml()`:
  ```diff
  - lines = ["graph ["]
  + lines = ["graph [", "  directed 1"]
  ```
- **Validation.** 4 PASS → 12 PASS after the fix. The originally-
  passing 4 stayed green; 8 new ones recovered.

### Bug 2 — `split_covariates` dtype check was dead code

- **Symptom.** `test_estimate_dml_requires_continuous_covariate`
  expected `CausalEstimateError(code="no_continuous_covariate")` but
  no error was raised; DML happily fit on a binary-encoded Z.
- **Root cause.** `CausalData.inline: List[Dict[str, float]]` forces
  pandas to promote *all* columns to `float64` when the DataFrame is
  built. The earlier `split_covariates` heuristic required
  `is_integer_dtype(s) or is_object_dtype(s) or is_bool_dtype(s)`
  for a column to be classified as discrete — which is **always
  False** under the inline-float protocol. The dtype check was
  effectively dead code, and any low-cardinality numerical column
  (e.g. species_code, feedstock_code) was misclassified as
  continuous.
- **Fix.** Simplified the heuristic to pure cardinality: `if
  n_unique < discrete_threshold: discrete.append(col)`. Updated the
  docstring to explain why dtype is no longer consulted.
- **Validation.** 12 PASS → 13 PASS after the fix.

Both bugs were caught *because* the seeded-smoke axis 1 tests were
written for B2a — the engine code was wrong, but the test suite
worked exactly as intended. No further engine changes were made
once 13/13 went green.

## §7 Effort vs estimate

| Step | Plan v2 estimate | Actual |
|---|---|---|
| 1 — re-read Plan v2 §2.1+§2.2+§2.6 | 30 min | ~15 min |
| 2 — schemas (4 files) | 1.5–2 h | ~45 min |
| 3 — engines (3 files) | 3–4 h | ~1.5 h (incl. 2 bug fixes surfaced during Step 5) |
| 4 — routers + main.py register | 1 h | ~20 min (smoke verified via OpenAPI dump, no pytest needed) |
| 5 — unit tests (13 tests, 2 files) | 2–3 h | ~1.5 h (incl. diagnostic + 2 bug reruns) |
| 6 — narrow regression | 15–30 min | ~3 min (62 s test + 2 min reading) |
| 7 — completion doc | 30 min | ~20 min |
| **Total** | **~10–14 h (Plan v2 2× efficiency)** | **~5 h** |

Came in well under estimate because: (a) Plan v2's spec was clear enough
that schemas almost wrote themselves, (b) DoWhy + EconML hello-world
work in B0.5 / reconnaissance had pre-validated the library APIs, (c)
the 2 bugs were surgical 1–2 line fixes once diagnosed.

## §8 Aux findings

### `_legacy/test_causal_*` filename clash protection

The `_legacy/` directory does not contain any `causal_*` files
(they are all V1 / V0.5 era artifacts). The new
`tests/unit/test_causal_{identify,estimate}_engine.py` files are
unambiguous additions.

### `requirements.txt.B1-backup` already cleaned

Confirmed deleted in Task 1 of the current chat session; verified
absent in the inventory grep.

### `pytest-timeout` plugin not installed

The B2a brief suggested `--timeout=30`, but `pytest-timeout` was
not in `requirements.txt`. We relied on the Bash tool's outer
timeout (180 000 ms) instead. No test exceeded ~5 s individually;
DML fit on n=80 was the slowest at ~3 s.

## §9 Next batch

**B2b** (refute + mediation + sensitivity endpoints) is unblocked:

- `app/schemas/causal/refute.py` (`SCHEMA_VERSION = "B.3"`)
- `app/schemas/causal/mediation.py` (`SCHEMA_VERSION = "B.4"`)
- `app/schemas/causal/sensitivity.py` (`SCHEMA_VERSION = "B.5"`)
- Engines: `causal_refute_engine.py`, `causal_mediation_engine.py`,
  `causal_sensitivity_engine.py`
- Async-job protocol completion (Mod 6) — sync mode shipped in B2a;
  B2b adds `mode="async_job"` flow + `/api/v1/causal/jobs/{job_id}`
  status endpoint
- Five mandatory refuters (D7 / Mod 7): `random_common_cause`,
  `placebo_treatment_refuter`, `data_subset_refuter`,
  `add_unobserved_common_cause`, `evalue_sensitivity_analyzer`
- Evidence-level promotion rule (refute pass-rate + E-value > 1.5
  → `validated`)
- DAG library `dag_002` becomes the canonical mediation fixture
  (Signal-API → κ → SER; ACME / ADE decomposition under sequential
  ignorability)

**Plan v2 §5 B2b estimate**: raw 20 h → adjusted 8–12 h at 2×
efficiency.

**End of B2a completion report.**
