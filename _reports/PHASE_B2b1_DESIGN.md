# Phase B B2b.1 — `/api/v1/causal/refute` design outline

> Step 1 design doc; NOT a completion report. Schema / engine / router
> / tests are scoped here but not yet implemented.
>
> Predecessor: B2a (`/identify` + `/estimate`) committed at `2138cf8`.
> Reference: Plan v2 §2.3 (with patch noted in
> `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md`).

## §1 Revision overview

Plan v2 §2.3 listed five mandatory refuters. The DoWhy 0.14 API
verification (`backend/scratch_refute_api.py`, kept for B2b.1
implementation reference until commit) confirmed that
**`evalue_sensitivity_analyzer` is not dispatched by
`model.refute_estimate(method_name=...)`** — it surfaces as
`ImportError: evalue_sensitivity_analyzer is not an existing causal
refuter`. E-value is a sensitivity-analysis class (Cinelli-Hazlett
family), not a Monte-Carlo refuter.

**Resolution**: E-value moves to `/api/v1/causal/sensitivity` (B2b.3).
The `/refute` endpoint reduces to **4 mandatory + 1 optional
implemented + 1 optional reserved**. See
[`PHASE_B_PLAN_V2_PATCH_S2_3.md`](./PHASE_B_PLAN_V2_PATCH_S2_3.md)
for the Plan v2 patch record.

## §2 Refuter enum + reserved pattern (mirrors B2a D9=α)

```python
RefuterName = Literal[
    # Mandatory — Phase B B2b.1 implements all 4
    "random_common_cause",
    "placebo_treatment_refuter",
    "data_subset_refuter",
    "add_unobserved_common_cause",
    # Optional — implemented
    "bootstrap_refuter",
    # Optional — reserved (engine raises HTTP 422 code='refuter_reserved')
    "non_parametric_sensitivity_analyzer",
]
```

Six enum values; engine implements 5; one reserved.

## §3 `CausalRefuteRequest` (full fields)

```python
class CausalRefuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estimate_handle: EstimateHandle          # reused from B2a
    refuters: List[RefuterName] = Field(..., min_length=1, max_length=6)
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    significance_alpha: float = Field(default=0.05, ge=0.001, le=0.5)
    mode: Literal["sync", "async_job"] = "sync"   # B2b.1 sync only
    original_e_value: Optional[float] = Field(    # see §10
        default=None, ge=1.0,
        description=(
            "Echo of e_value_cheap from the preceding /estimate "
            "response. When present, used in the evidence_level rule "
            "verbatim. When absent, the engine recomputes via a "
            "lightweight LR estimate (one extra pass; ~20% engine "
            "cost). Strongly recommended to pass it through to "
            "preserve the audit trail."
        ),
    )
```

## §4 `RefuterResult` sub-model

```python
class RefuterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refuter: RefuterName
    passed: bool
    p_value: Optional[float] = Field(default=None, ge=0, le=1)
    delta_estimate: float          # new_effect - estimated_effect
    diagnostic: str = Field(..., max_length=512)
```

`p_value` is **Optional** because `add_unobserved_common_cause` does
not perform a significance test (see §7).

## §5 `CausalRefuteResponse` (full fields)

```python
class CausalRefuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refute_results: List[RefuterResult] = Field(..., min_length=1)
    overall_robust: bool                # all mandatory refuters passed
    evidence_level: EvidenceLevel       # validated / supported / planned
    e_value_used: float = Field(..., ge=1.0,
        description="Echo of the e_value the rule consumed.")
    warnings: List[CausalWarning] = Field(default_factory=list, max_length=20)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
```

## §6 Refuter ↔ DoWhy field map (verified)

Empirically established via `scratch_refute_api.py` on the B2a
backdoor bench (T / Y / Z, n=80, seed=42).

| Refuter | DoWhy method_name | `refutation_result` shape | `passed` derivation |
|---|---|---|---|
| `random_common_cause` | `"random_common_cause"` | `{p_value, is_statistically_significant}` | `not is_statistically_significant` |
| `placebo_treatment_refuter` | `"placebo_treatment_refuter"` (+ `placebo_type="permute"`) | same | same |
| `data_subset_refuter` | `"data_subset_refuter"` (+ `subset_fraction=0.8`) | same | same |
| `add_unobserved_common_cause` | `"add_unobserved_common_cause"` (+ effect-strength kwargs) | **`None`** (no significance test) | `abs(delta_estimate / original_estimate) < 0.1` |
| `bootstrap_refuter` | `"bootstrap_refuter"` | `{p_value, is_statistically_significant}` | same as random_common_cause |

DoWhy returns `CausalRefutation` for all five. `__dict__` carries
`estimated_effect`, `new_effect`, `refutation_result`,
`refutation_type`, `refuter`. We expose:

```python
delta_estimate = float(refute.new_effect - refute.estimated_effect)
diagnostic     = refute.refutation_type   # e.g. "Refute: Add a random common cause"
```

## §7 `add_unobserved_common_cause` special case

This refuter does not perform a hypothesis test. It returns:

- `new_effect_array` — scan over confounder-strength grid
- `new_effect` — single value (typically the midpoint of the grid)
- `refutation_result = None`

The current Plan v2 schema declares `p_value: Optional[float]`
specifically to accommodate this. The engine maps:

```python
delta = float(refute.new_effect - refute.estimated_effect)
orig  = float(refute.estimated_effect)
rel_delta = abs(delta / orig) if orig != 0 else float("inf")
passed = rel_delta < 0.1   # default threshold; configurable
```

No `p_value` in the response object for this refuter. The
`diagnostic` string records the absolute / relative delta so the
operator sees why `passed` was True or False.

## §8 Engine function signatures (target)

```python
class CausalRefuteError(ValueError):
    """Raised on /refute pre-condition failure. Router → HTTP 422."""
    def __init__(self, code: str, message: str): ...

_RESERVED_REFUTERS = frozenset({"non_parametric_sensitivity_analyzer"})

def _check_refuter(name: RefuterName) -> None:
    """Reject reserved refuters early with code='refuter_reserved'."""

def _refute_single(
    model: "CausalModel",
    identified_estimand,
    estimate,
    refuter_name: RefuterName,
    *,
    seed: Optional[int],
    alpha: float,
    delta_threshold: float = 0.1,
) -> RefuterResult:
    """Dispatch to model.refute_estimate(...) and normalise the result.
    Handles add_unobserved_common_cause's no-p_value case."""

def _aggregate(
    results: List[RefuterResult],
    identify_strategy: str,
    e_value: float,
    alpha: float,
) -> Tuple[bool, EvidenceLevel]:
    """Returns (overall_robust, evidence_level) per Plan v2 §2.3 rule."""

def run_refute(request: CausalRefuteRequest) -> CausalRefuteResponse:
    """Top-level entrypoint. Builds DoWhy model from EstimateHandle,
    iterates refuters, aggregates, returns the response. ~250-350 LoC
    including the e_value fallback path."""
```

Predicted engine file size: **250–350 LoC** (somewhere between
`causal_identify_engine.py` 266 LoC and `causal_estimate_engine.py`
545 LoC — refute is conceptually closer to identify's "wrap DoWhy +
classify" pattern).

## §9 Reuse vs new

**Reused from B2a (no changes)**

| Module | Symbol | Why |
|---|---|---|
| `app.schemas.causal_common` | `EstimateHandle` | Request payload |
| `app.schemas.causal_common` | `CausalWarning` | Response warnings |
| `app.schemas.causal_common` | `EvidenceLevel` | Response literal |
| `app.schemas.causal_common` | `CAUSAL_ENGINE_VERSION` | Response |
| `app.engine.extended.causal_utils` | `causal_data_to_dataframe` | Rebuild df from handle |
| `app.engine.extended.causal_utils` | `dag_to_gml` | Rebuild DoWhy CausalModel |
| `app.engine.extended.causal_utils` | `cheap_evalue` | E-value fallback (§10) |

**New (B2b.1)**

| Path | Purpose |
|---|---|
| `app/schemas/causal/refute.py` | `SCHEMA_VERSION = "B.3"`; Request + Response + RefuterResult |
| `app/engine/extended/causal_refute_engine.py` | DoWhy refute dispatch + aggregation |
| `app/routers/causal.py` (modify) | `@router.post("/refute")` block (~20 LoC) |
| `tests/unit/test_causal_refute_engine.py` | 8 unit tests (§11) |

No changes to identify / estimate paths.

## §10 `e_value` acquisition policy — **decision needed**

The Plan v2 §2.3 `validated` evidence-level rule requires
`e_value > 1.5`. The B2a `/estimate` endpoint already returns
`e_value_cheap` on its response, but `/refute`'s `EstimateHandle`
**does not carry that value** (handle was designed before E-value
was promoted into the rule).

Two options:

### Option (a) — `original_e_value: Optional[float]` request field + engine fallback (recommended)

- Request accepts optional `original_e_value`. When provided,
  engine uses it verbatim; the audit-trail is clean (front-end
  carried the value from `/estimate.e_value_cheap`).
- When omitted, engine recomputes via a lightweight LR estimate
  on the same data + DAG (re-realised from `EstimateHandle`). Cost:
  ~20% engine wall-clock on a typical n=200 bench.
- Response always echoes the value back via `e_value_used`.

**Pros**: stateless (no server-side cache), graceful degradation,
documents the audit chain, ~zero front-end work for happy path.

**Cons**: schema has a "shadow optional" field that some clients
will forget to pass, falling silently into the fallback path.
Mitigation: response `warnings` includes `e_value_recomputed` when
the fallback fired.

### Option (b) — Engine always recomputes

- No new request field. Engine always re-runs a lightweight LR
  estimate to obtain `e_value_cheap` regardless of what the client
  did.

**Pros**: no extra optional field; behaviour identical regardless
of front-end.

**Cons**: ~20% wall-clock penalty on every `/refute` call even
when the front-end has the value already. Loses the audit chain
("did the e_value in the rule match what /estimate originally
returned?").

### Recommendation

**Option (a) hybrid**. The "explicit-when-possible, fallback-when-not"
pattern preserves stateless semantics + audit traceability without
forcing the wall-clock hit. The new `original_e_value` field is
self-documenting and matches the precedent of
`precomputed_estimand` in `/estimate` (B2a's Mod 4).

## §11 Test design (8 unit tests)

All use the B2a `_synthetic_linear_bench` fixture verbatim
(n=80 / seed=42 / true ATE=2.0); no FastAPI / TestClient / network.

| # | Test | Behavior |
|---|---|---|
| 1 | `test_refute_random_common_cause_passes` | `passed=True`, `p_value > 0.10`, `delta_estimate` small |
| 2 | `test_refute_placebo_treatment_passes` | `new_effect ≈ 0`, `passed=True`, `p_value > 0.10` |
| 3 | `test_refute_data_subset_passes` | `passed=True`, `p_value > 0.10`, `delta_estimate` small |
| 4 | `test_refute_add_unobserved_no_pvalue` | `p_value is None`, `passed=True`, `delta_estimate` small enough |
| 5 | `test_refute_bootstrap_passes` | optional-implemented refuter works the same as random_common_cause |
| 6 | `test_refute_reserved_method_raises_422` | `non_parametric_sensitivity_analyzer` → `CausalRefuteError(code='refuter_reserved')` |
| 7 | `test_refute_evidence_level_validated_requires_high_evalue` | 4 mandatory all PASS + backdoor + `original_e_value=2.0` → `evidence_level='validated'` |
| 8 | `test_refute_evidence_level_planned_when_evalue_low` | 4 mandatory all PASS + backdoor + `original_e_value=1.1` → `evidence_level='supported'` (not validated) |

Expected runtime: ~30 s total (each refuter call ~3 s; identify
reuse via `EstimateHandle` saves the identify step).

## §12 Effort estimate

| Step | Estimated |
|---|---|
| 2 — schema (refute.py + RefuterName Literal) | 30 min |
| 3 — engine (causal_refute_engine.py) | 90 min (incl. add_unobserved adapter + e_value fallback path) |
| 4 — router (1 endpoint + register) | 15 min |
| 5 — tests (8 unit) | 60 min |
| 6 — narrow regression (`tests/unit/test_causal_*` only, 21 tests total) | 5 min |
| 7 — completion doc | 30 min |
| 8 — commit | 15 min |
| **Total** | **~4 h** (vs Plan v2 raw 8 h → 2× efficiency) |

## §13 Risks

- **`add_unobserved_common_cause` threshold default `0.1`** is
  ad-hoc. Plan v2 doesn't specify. Acceptable for B2b.1 MVP; could
  be re-tuned in Phase G when real-data benches exist.
- **DoWhy 0.14 sub-API stability**: the 4 mandatory refuters were
  verified to return the same `CausalRefutation` shape, but
  upgrade to DoWhy 0.15+ may break the `refutation_result` dict
  layout. The schema accepts `Optional[float]` for `p_value` so
  this is contained.
- **E-value fallback path**: Option (a) introduces a path that
  silently recomputes when client forgets to pass
  `original_e_value`. Mitigation already in §10 (response warning).
- **Reserved refuter naming**: `non_parametric_sensitivity_analyzer`
  is conceptually sensitivity (like e-value) and may also belong
  in `/sensitivity`. Leaving it as a reserved refuter for now
  preserves Plan v2 enum stability.

**End of design outline.**
