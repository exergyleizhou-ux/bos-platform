# Phase B B2b.3 — `/api/v1/causal/sensitivity` design outline

> Step 1 design doc; NOT a completion report. Schema / engine /
> router / tests are scoped here but not yet implemented.
>
> Predecessor: B2b.2 (`/mediation`) committed at `d372dba`.
> Reference: Plan v2 §2.5 (verbatim Request shape; Response design
> deferred here because Plan v2 §2.5 says "Same shape as Plan v1
> §2.5; no further changes" but no Plan v1 doc exists). Also picks
> up the deferred work from
> `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md` (the E-value standalone
> class verification deferred from B2b.1).

## §1 Sensitivity method selection (mini-verify driven)

Five candidate paths were probed via
`backend/scratch_sensitivity_api.py` on a B2a-style backdoor bench
(T -> Y with confounder Z, n=200, seed=42, true ATE=2.0,
`backdoor.linear_regression` -> estimate.value = 2.0308). Results:

| # | Candidate | Outcome |
|---|---|---|
| 1 | DoWhy `EValueSensitivityAnalyzer` standalone class | **PASS.** Module `dowhy.causal_refuters.evalue_sensitivity_analyzer`; class `EValueSensitivityAnalyzer`. Correct `__init__` kwargs: `estimate, estimand, data, treatment_name, outcome_name`; methods `check_sensitivity(data=df)`, `get_evalue()`, `benchmark(...)`, `plot(...)`; attributes `stats`, `benchmarking_results`, `sd_outcome`. B2b.1 patch doc said it exists but isn't dispatched by `model.refute_estimate(...)`; this Step 1 confirmed standalone instantiation works. |
| 2 | Self-implemented E-value (B2a `cheap_evalue` extended with CI-bound robust variant) | **PASS** as a fallback. On the same bench: beta=2.0308, CI95%=[1.8906, 2.1710], std(Y)=2.6473. Point E-value = 3.4346; lower-CI-bound robust E-value = 3.2394. Both >1.5 threshold; both numerically consistent with B2a `cheap_evalue` formula. |
| 3 | DoWhy `NonParametricSensitivityAnalyzer` | **PARTIAL.** Module + class exist; `__init__(*args, theta_s, plugin_reisz=False, **kwargs)` requires a keyword-only `theta_s` (a regression score function) not exposed by Plan v2 §2.5's `method='partial_linear'` field. Instantiation without `theta_s` raises `TypeError: missing 1 required keyword-only argument`. Reserve at engine layer (D9-style). |
| 4 | PySensemakr (Cinelli-Hazlett 2020 official Python lib) | **NOT INSTALLED** (correctly per B1 deps lock). Rejected. |
| 5 | Self-implemented Cinelli-Hazlett (partial f^2 + robustness value from a single OLS fit) | **PASS.** On the same bench: t=28.56, df_resid=197, partial f^2 = 4.14, RV(q=1) = 0.8326, RV_alpha(q=1, alpha=0.05) = 0.8180, partial R^2(Y, T \| Z) = 0.8055. Closed form from Cinelli-Hazlett 2020 Eq. 4; no extra deps. |

### Selected path — three methods, three branches

The Plan v2 §2.5 `method` enum is
`Literal["evalue", "linear", "partial_linear"]`. Branch dispatch:

```
if method == "evalue":
    primary  = DoWhy EValueSensitivityAnalyzer  (Candidate 1)
    fallback = self-implemented Chinn-VWD       (Candidate 2)
elif method == "linear":
    primary  = self-implemented Cinelli-Hazlett (Candidate 5)
    no fallback needed (closed form, single OLS)
elif method == "partial_linear":
    422 code='method_reserved'                   (Candidate 3 reserve)
```

Why Candidate 2 fallback for `evalue`: DoWhy 0.14's
`check_sensitivity` calls `statsmodels` internally with the
`benchmark_covariate` slot left blank when no benchmark is given.
B2a's `cheap_evalue` is one-line cheap and the schema already
returns it in `/estimate.e_value_cheap`. If the DoWhy primary fails
(numerical or API), engine falls back to a self-computed
Chinn/VWD E-value and emits a `method_fallback` warning. This is
the same "primary + always-available fallback" pattern B2b.1 used
for `add_unobserved_common_cause` delta-based decisions.

Why Candidate 5 over PySensemakr for `linear`: B1 deps are locked;
adding `sensemakr` would require a Plan-doc patch and a Phase B/G
deps re-audit. The Cinelli-Hazlett 2020 robustness-value formula
is a single OLS + one closed-form expression — engineering cost is
~20 lines, no numerical risk for D9=alpha MVP.

### Phase G re-evaluation triggers

- DoWhy 0.15+ exposes `theta_s` from a schema-friendly parameter
  block (e.g. nuisance method names) -> drop the `partial_linear`
  422 gate, route to `NonParametricSensitivityAnalyzer`.
- BSF deps policy relaxes -> evaluate PySensemakr swap-in for the
  `linear` branch; numerical equivalence to Candidate 5 is the
  acceptance gate.
- If `check_sensitivity()` returns benchmark-covariate-dependent
  outputs we want to surface, expand the `benchmark_covariate`
  request field to a List and the response accordingly.

## §2 Schema — `app/schemas/causal/sensitivity.py` (B.5)

Plan v2 §2.5 spells out the **Request** verbatim and delegates the
**Response** to a non-existent Plan v1 §2.5. The Response shape
below is designed in this Step 1 to mirror B2b.1 refute / B2b.2
mediation conventions.

### Request (Plan v2 §2.5 verbatim + 1 augmentation)

```python
class CausalSensitivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate_handle: EstimateHandle
    method: Literal["evalue", "linear", "partial_linear"] = "evalue"
    benchmark_covariate: Optional[str] = Field(
        default=None, max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
        description=(
            "Optional adjustment-set covariate name to use as the "
            "benchmarking strength for the Cinelli-Hazlett RV "
            "interpretation. When supplied, must be in "
            "estimate_handle.dag.nodes with node_kind='covariate'."
        ),
    )
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    mode: Literal["sync", "async_job"] = "sync"
```

Augmentation rationale: Plan v2 §2.5 doesn't expose `assumptions_acknowledged`
(unlike B2b.2 mediation's Mod 8). For sensitivity, the assumptions
are *already* the sensitivity bounds themselves, so a separate
acknowledgement field is redundant. Keep the surface minimal.

### Response (designed here for Plan v1 §2.5's stale "same shape" delegation)

```python
class SensitivityEvalueDetail(BaseModel):
    """E-value branch payload."""
    model_config = ConfigDict(extra="forbid")
    e_value_point: float = Field(..., ge=1.0)
    e_value_lower_ci: float = Field(..., ge=1.0)
    source: Literal["dowhy_class", "self_chinn_vwd"]
    # source records which Candidate (1 primary or 2 fallback) ran.

class SensitivityLinearDetail(BaseModel):
    """Cinelli-Hazlett branch payload."""
    model_config = ConfigDict(extra="forbid")
    robustness_value: float = Field(..., ge=0.0, le=1.0)
    robustness_value_alpha: float = Field(..., ge=0.0, le=1.0)
    partial_r2_yd: float = Field(..., ge=0.0, le=1.0)
    partial_r2_yz_given_d: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # partial_r2_yz_given_d only present when benchmark_covariate provided.

class SensitivityDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["evalue", "linear"]
    n_samples: int = Field(..., ge=0)
    fit_time_ms: float = Field(..., ge=0.0)
    benchmark_covariate_used: Optional[str] = None

class CausalSensitivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Literal["evalue", "linear"]
    evalue_detail: Optional[SensitivityEvalueDetail] = None
    linear_detail: Optional[SensitivityLinearDetail] = None
    overall_robust: bool = Field(
        ...,
        description=(
            "evalue branch: e_value_lower_ci > 1.5. linear branch: "
            "robustness_value_alpha > 0.10 (Cinelli-Hazlett 2020 "
            "conventional 'highly robust' threshold)."
        ),
    )
    evidence_level: EvidenceLevel
    diagnostics: SensitivityDiagnostics
    warnings: List[CausalWarning] = Field(default_factory=list, max_length=20)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_detail_present(self) -> "CausalSensitivityResponse":
        if self.method == "evalue":
            if self.evalue_detail is None:
                raise ValueError("evalue_detail required when method='evalue'")
            if self.linear_detail is not None:
                raise ValueError("linear_detail must be None when method='evalue'")
        elif self.method == "linear":
            if self.linear_detail is None:
                raise ValueError("linear_detail required when method='linear'")
            if self.evalue_detail is not None:
                raise ValueError("evalue_detail must be None when method='linear'")
        return self
```

`partial_linear` is accepted at the Request schema (Literal enum)
but **engine 422-rejects** with `code='method_reserved'`. Same
D9-style reserved-enum pattern as B2a estimate's
`method_family_reserved`, B2b.1 refute's `refuter_reserved`, and
B2b.2 mediation's `decomposition_reserved`.

## §3 Paper alignment (V14 sensitivity refs)

Plan v2 §2.5 paper map: *"Operationalises the paper's
'Γ-bound ≥ 1.5' falsification gate (paper line 101). The cheap
E-value is already returned in-line by `/estimate` (Mod 9); this
endpoint exists for the expensive `partial_linear` /
non-parametric analysis the operator might want for a high-stakes
claim."*

**Interpretation for B2b.3.**

1. The "Γ-bound ≥ 1.5" gate is operationalised as the
   `overall_robust` field on the Response. For `method='evalue'`
   the gate uses `e_value_lower_ci > 1.5`; for `method='linear'`
   it uses `robustness_value_alpha > 0.10` (the Cinelli-Hazlett
   conventional threshold; not the same number as 1.5 because E-value
   and RV are on different scales — RV is a fraction in [0, 1]).
2. The paper's "10 000-iteration nonparametric bootstrap"
   (V14 line 153) is **not** a sensitivity bound — it's a CI
   construction method for the *mediation* analysis (B2b.2 §3
   already covered this). Sensitivity and refutation are
   orthogonal: refutation perturbs the estimate via Monte-Carlo
   sampling (B2b.1's territory); sensitivity bounds the bias from
   omitted variables (Γ-bound and partial-R^2 frameworks).
3. The paper uses sensitivity primarily as a robustness check on
   the headline ATE (not on mediation NDE/NIE). B2b.3's
   `evidence_level` rule promotes results to `validated` only when
   `overall_robust=True` AND the upstream `/estimate` already
   classified as `supported`.

## §4 Engine function signatures

### Public entrypoint

```python
def run_sensitivity(
    request: CausalSensitivityRequest,
) -> CausalSensitivityResponse:
    """Top-level dispatch.

    1. _check_method (reserved-enum gate; partial_linear -> 422).
    2. Realise df from request.estimate_handle.data.
    3. Validate benchmark_covariate (if provided) lives in
       handle.dag.nodes with node_kind='covariate'.
    4. Branch:
       - method == 'evalue'   -> _run_evalue
       - method == 'linear'   -> _run_cinelli_hazlett
    5. Assemble response (evidence_level + overall_robust + warnings).
    """
```

### E-value branch (Candidate 1 primary + Candidate 2 fallback)

```python
def _run_evalue(
    request: CausalSensitivityRequest, df: pd.DataFrame,
) -> Tuple[SensitivityEvalueDetail, SensitivityDiagnostics, List[CausalWarning]]:
    """Try DoWhy EValueSensitivityAnalyzer first; on any exception,
    fall back to self-implemented Chinn-VWD E-value and emit a
    method_fallback warning.

    Primary path (DoWhy API verified via Step 1 scratch tail-arrive
    probe; results recorded in PHASE_B2b3_API_VERIFICATION.md):
      1. Rebuild CausalModel from handle.dag + handle.data.
      2. identify_effect(proceed_when_unidentifiable=True).
      3. estimate_effect(method_name based on handle.method_family).
      4. EValueSensitivityAnalyzer(estimate=..., estimand=...,
         data=df, treatment_name=..., outcome_name=...).
      5. analyzer.check_sensitivity(data=df, plot=False) returns
         None but populates ``analyzer.stats`` dict with keys:
         ``converted_estimate``, ``converted_lower_ci``,
         ``converted_upper_ci``, ``evalue_estimate``,
         ``evalue_lower_ci``, ``evalue_upper_ci`` (the last is
         ``None`` on the n=200 backdoor bench).
      6. e_value_point = float(stats['evalue_estimate']); 
         e_value_lower_ci = float(stats['evalue_lower_ci']).
      7. NOTE: ``analyzer.get_evalue(coef_est, coef_se)`` is a
         static-style helper that takes coefficients directly; it
         is NOT the convenience method to call here. The
         post-check_sensitivity ``.stats`` dict is the canonical
         result surface.
      8. source='dowhy_class'.

    Fallback path (any primary exception):
      1. statsmodels OLS on Y ~ T + adjustment_set; beta + 95% CI.
      2. std(Y) from df.
      3. e_value_point = chinn_vwd(beta, std_y).
      4. e_value_lower_ci = chinn_vwd(
             bound_closer_to_null=min(|ci_lo|, |ci_hi|), std_y).
      5. source='self_chinn_vwd'; warning method_fallback with
         primary-exception type recorded.
    """
```

### Linear branch (Candidate 5, self-implemented Cinelli-Hazlett)

```python
def _run_cinelli_hazlett(
    request: CausalSensitivityRequest, df: pd.DataFrame,
) -> Tuple[SensitivityLinearDetail, SensitivityDiagnostics, List[CausalWarning]]:
    """Closed-form RV + partial R^2 from a single OLS fit.

    1. Build adjustment set from handle.dag covariates (excluding
       treatment / outcome / benchmark_covariate).
    2. OLS Y ~ T + adjustment_set. Extract beta, se, df_resid.
    3. t = beta / se; f^2 = t^2 / df_resid.
    4. RV(q=1) = 0.5 * (sqrt(f^4 + 4*f^2) - f^2).
    5. t_crit at alpha=0.05 from scipy.stats.t.ppf(0.95, df_resid).
    6. RV_alpha = 0.5 * (sqrt(F^4 + 4*F^2) - F^2) where
       F = |t - t_crit| / sqrt(df_resid).
    7. partial_r2_yd = f^2 / (1 + f^2).
    8. If benchmark_covariate:
         partial_r2_yz_given_d = compute the same from
         leave-one-out OLS where benchmark_covariate is dropped.
       Else: None.
    """
```

### Reserved-enum gate

```python
def _check_method(method: str) -> None:
    """partial_linear -> 422 code='method_reserved'."""
    if method == "partial_linear":
        raise CausalSensitivityError(
            code="method_reserved",
            message=(
                "method='partial_linear' is reserved for a future "
                "Phase B / Phase G release. B2b.3 MVP implements "
                "'evalue' and 'linear' only."
            ),
        )
```

### Custom exception

```python
class CausalSensitivityError(ValueError):
    """Router -> HTTP 422 with structured code + message.
    Mirrors CausalRefuteError / CausalEstimateError / CausalMediationError."""
    def __init__(self, code: str, message: str): ...
```

**Predicted engine LoC**: 400-550. Estimate breakdown:
- ~140 LoC: `_run_evalue` (primary DoWhy path + fallback OLS path)
- ~120 LoC: `_run_cinelli_hazlett` (OLS + RV/partial R^2 + LOO when
  benchmark)
- ~60 LoC: `_check_method`, custom exception, constants,
  `_classify_strategy` reuse
- ~80 LoC: `run_sensitivity` top-level orchestration + evidence_level
  rule + benchmark_covariate validation

Substantially smaller than B2b.2 mediation's 879 LoC because there
is no bootstrap loop (R1 mitigation not needed; sensitivity is
closed-form for the linear branch and a single class call for the
DoWhy E-value).

## §5 Tests — `tests/unit/test_causal_sensitivity_engine.py`

**10 unit tests** mirroring B2b.1 / B2b.2 patterns. Each test
independent; no FastAPI / TestClient; warnings suppressed.

| # | Test | Behaviour |
|---|---|---|
| 1 | `test_sensitivity_evalue_primary_path` | method='evalue' on B2a backdoor bench; expect `evalue_detail.source='dowhy_class'`, e_value_point > 1.5 |
| 2 | `test_sensitivity_evalue_fallback_on_dowhy_failure` | Force primary to fail (e.g. degenerate DAG) and confirm fallback fires; `source='self_chinn_vwd'`, warning emitted |
| 3 | `test_sensitivity_evalue_matches_cheap_evalue` | self-fallback e_value_point equals B2a `cheap_evalue` to 1e-6 |
| 4 | `test_sensitivity_linear_recovers_rv` | method='linear' on backdoor bench; RV(q=1) ≈ 0.83 (±0.05 tolerance) per Step 1 scratch number |
| 5 | `test_sensitivity_linear_partial_r2_field` | partial_r2_yd populated; ∈ [0, 1] |
| 6 | `test_sensitivity_benchmark_covariate_present` | benchmark_covariate provided; `partial_r2_yz_given_d` not None; `diagnostics.benchmark_covariate_used` echoes the input |
| 7 | `test_sensitivity_partial_linear_raises_422` | method='partial_linear' -> CausalSensitivityError(code='method_reserved') |
| 8 | `test_sensitivity_benchmark_covariate_not_in_dag_raises_422` | benchmark_covariate='unknown' -> CausalSensitivityError(code='benchmark_covariate_unknown') |
| 9 | `test_sensitivity_overall_robust_field` | When e_value_lower_ci > 1.5 -> `overall_robust=True`; verify the flag flips on a weak-effect bench |
| 10 | `test_sensitivity_response_validator_method_detail_consistency` | Construct Response with `method='evalue'` + `linear_detail` set -> ValidationError ("linear_detail must be None when method='evalue'") |

Expected wall-clock: ~30-60 s total. No bootstrap, no per-iteration
DoWhy work; each test ≈ one fit.

## §6 Reuse vs new

### Reused from B2a / B2b.1 / B2b.2 (no changes)

| Module | Symbol | Why |
|---|---|---|
| `app.schemas.causal_common` | `EstimateHandle` | Request payload (Plan v2 §2.5 verbatim) |
| `app.schemas.causal_common` | `CausalWarning`, `EvidenceLevel`, `CAUSAL_ENGINE_VERSION` | Response shell |
| `app.engine.extended.causal_utils` | `causal_data_to_dataframe` | Realise df from handle.data |
| `app.engine.extended.causal_utils` | `dag_to_gml` | Build DoWhy CausalModel for primary E-value path |
| `app.engine.extended.causal_utils` | `cheap_evalue` | Fallback E-value (Candidate 2 self-implementation) |
| `app.engine.extended.causal_utils` | `split_covariates` | Adjustment set inside Cinelli-Hazlett OLS |
| `app.engine.extended.causal_identify_engine` | `_classify_strategy` | Strategy echo for diagnostics + benchmark_covariate validation |

### New (B2b.3)

| Path | Purpose |
|---|---|
| `app/schemas/causal/sensitivity.py` | `SCHEMA_VERSION = "B.5"`; CausalSensitivityRequest + SensitivityEvalueDetail + SensitivityLinearDetail + SensitivityDiagnostics + CausalSensitivityResponse + 1 Response-level method/detail-consistency validator |
| `app/engine/extended/causal_sensitivity_engine.py` | run_sensitivity + _run_evalue (primary + fallback) + _run_cinelli_hazlett + _check_method + _validate_benchmark_covariate + CausalSensitivityError |
| `app/routers/causal.py` (modify) | `@router.post("/sensitivity")` block (~30 LoC after `/mediation`) |
| `tests/unit/test_causal_sensitivity_engine.py` | 10 unit tests |

## §7 Effort estimate

| Step | Estimate |
|---|---|
| 1 — design doc + scratch verification | 60-90 min (this batch; in progress now) |
| 2 — schema (sensitivity.py) | 45 min (B.5 fields dense but only 1 cross-field validator) |
| 3 — engine | 90-150 min (no bootstrap loop; closed-form linear branch; DoWhy class call for evalue primary) |
| 4 — router (1 endpoint) | 15 min |
| 5 — tests (10 unit) | 60-90 min |
| 6 — narrow regression | 5-10 min |
| 7 — completion doc + scratch archive | 30 min |
| 8 — commit | 15 min |
| **Total** | **4.0-5.5 h** (vs Plan v2 raw 6 h; tracks 2x efficiency target since B2b.2 ate ~6.5 h) |

The shorter range vs B2b.2 is driven by (a) no bootstrap surface,
(b) closed-form math on the linear branch, (c) DoWhy class is a
single call with no per-iteration state pollution risk.

## §8 Risks

- **R1 — DoWhy `EValueSensitivityAnalyzer.check_sensitivity` signature
  shift across versions.** Step 1 verified the DoWhy 0.14 signature
  (`data=df`) but a 0.15 upgrade may change the kwarg name. **Mitigation**:
  primary path is wrapped in try/except (broad `Exception`); fallback
  to Candidate 2 fires automatically with `method_fallback` warning.
  Same delta-based pattern B2b.1 used for `data_subset_refuter`.

- **R2 — Cinelli-Hazlett 2020 formula transcription errors.** The
  partial f^2 / RV expressions are algebraically simple but easy to
  mis-implement (sign of f_alpha, df_resid usage). **Mitigation**:
  Step 5 test 4 asserts RV ≈ 0.83 on the Step 1 scratch bench (n=200,
  seed=42, beta=2.0308 from OLS). The number is a captured baseline.
  Test 5 cross-checks partial_r2_yd = f^2 / (1 + f^2) by direct
  computation.

- **R3 — `benchmark_covariate` field semantic ambiguity.** Plan v2
  §2.5 declares the field but does not say what to *do* with it.
  Cinelli-Hazlett uses it as the strength reference (the LOO OLS
  pattern in §4); for E-value it's not meaningful. **Mitigation**:
  Engine ignores `benchmark_covariate` on the evalue branch and
  validates DAG-presence + node_kind='covariate' regardless.
  Response `diagnostics.benchmark_covariate_used` echoes only when
  the linear branch actually used it.

- **R4 — `partial_linear` reserved with `theta_s` ambiguity.**
  Plan v2 §2.5 lists `partial_linear` in the method enum but Plan
  v2 §2.5 does not expose a `theta_s` parameter. The Phase G
  trigger is documented; B2b.3 422-rejects to keep the OpenAPI
  surface forward-compatible. **Mitigation**: D9-style reserved
  pattern + Step 7 completion doc records the deferral.

- **R5 — overall_robust threshold split between branches.** E-value
  uses 1.5 (paper's Γ-bound); RV uses 0.10 (Cinelli-Hazlett 2020
  convention). The two numbers are on incompatible scales and a
  single threshold field on the schema would be misleading.
  **Mitigation**: threshold lives in engine constants
  (`_EVALUE_ROBUST_THRESHOLD = 1.5`, `_RV_ROBUST_THRESHOLD = 0.10`);
  Response surfaces only the boolean. Step 7 completion doc records
  the rationale for future audit.

## §9 Phase G re-evaluation triggers

Documented inline above; consolidated here:

1. **DoWhy 0.15+ exposes `theta_s` from a schema-friendly param block**
   -> drop `partial_linear` 422 gate; route through
   `NonParametricSensitivityAnalyzer` (Candidate 3 from Step 1).
2. **`check_sensitivity()` API change in DoWhy 0.15+** -> revisit
   the kwarg-name plumbing; the broad-`Exception` fallback handles
   this gracefully but a Phase G clean-up should tighten.
3. **Deps lock loosens** -> evaluate PySensemakr (Candidate 4)
   numerical-equivalence swap for the `linear` branch.
4. **BSF real data exhibits sensitivity-bound divergence between**
   the cheap (`/estimate.e_value_cheap`) and expensive
   (`/sensitivity`) E-value computations -> add a numerical-divergence
   warning when the two values differ by more than 10%.

## §10 Step 1 Plan v2 §2.5 reconciliation notes

Two Plan v2 §2.5 gaps surfaced during Step 1 and are documented
here (not as a separate Plan patch — neither requires changing
PLAN.md):

1. **Response shape delegated to non-existent Plan v1 §2.5.** Designed
   above in §2; no Plan-doc patch needed.
2. **`partial_linear` method listed without specifying the underlying
   estimator / `theta_s`.** Resolved by reserved-enum 422 (§4); Phase
   G trigger documented (§9 item 1).
