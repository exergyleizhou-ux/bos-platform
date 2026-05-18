# Phase B B2b.2 — `/api/v1/causal/mediation` design outline

> Step 1 design doc; NOT a completion report. Schema / engine /
> router / tests are scoped here but not yet implemented.
>
> Predecessor: B2b.1 (`/refute`) committed at `27f3a62`.
> Reference: Plan v2 §2.4 (verbatim, with the verifications recorded
> below).

## §1 Mediation method selection (mini-verify driven)

Five candidate paths were probed via
`backend/scratch_mediation_api.py` (UTF-8 mode required for the
DoWhy warning prints under Windows GBK). Results:

| # | Candidate | Outcome |
|---|---|---|
| 1 | EconML `mediation` submodule | **FAIL** — `ModuleNotFoundError: No module named 'econml.mediation'`. EconML 0.16's submodule list: `dml`, `dr`, `metalearners`, `orf`, `iv`, `policy`, `cate_interpreter`, `panel`, `validate`, … — none are mediation-specific. |
| 2 | DoWhy `nonparametric-nde` / `nonparametric-nie` estimand_type + `mediation.two_stage_regression` | **PASS for single mediator.** Pearl decomposition holds **exactly**: ATE=0.7971 = NDE 0.2925 + NIE 0.5045 on the n=200 bench (gap=0.0000). |
| 3 | `dowhy.gcm.mediation` | **FAIL** — module does not exist in DoWhy 0.14 (`dowhy.gcm` has `influence`, `causal_mechanisms`, `falsify`, etc., but no `mediation` submodule). |
| 4 | Self-implemented Farbmacher 2022 DML | **PASS as a fallback** — 3 sequential EconML LinearDML fits (total / T→M / direct) produce ACME=0.50 and proportion_mediated=0.63 on the same bench (vs true 0.42 / 0.51). The estimates are noisier than DoWhy's NDE/NIE on the same data but the *mechanism* is sound. |
| 5 | causalml | **NOT INSTALLED** (correctly per B1 deps policy). Rejected. |

### Mini-verify Gap 2 — multi-mediator

DoWhy 0.14's multi-mediator support is broken:

- `IdentifiedEstimand.get_mediator_variables()` returned `['M2']`
  for a DAG that explicitly declares `M` and `M2` as mediators
  (only the last-detected mediator).
- `model.estimate_effect(method_name="mediation.two_stage_regression")`
  on the multi-mediator DAG returned NIE=0.2288 vs the true
  Indirect=0.99 (0.7·1.2 from M-path + 0.3·0.5 from M2-path) —
  underestimates by ~77%, consistent with only computing one
  mediator's contribution.
- No `per_mediator_decomposition` attribute on the
  `CausalEstimate` object.
- Trying to "focus" the estimand on a specific mediator (via the
  same DAG) does nothing — DoWhy still picks `['M2']`.

### Selected path — **hybrid (single→DoWhy, multi→Farbmacher)**

```
if len(mediators) == 1:
    use candidate 2 (DoWhy NDE/NIE/ATE triple)
else:  # len(mediators) >= 2
    use candidate 4 (Farbmacher leave-one-out)
```

Both branches return the same `MediationDecomposition` +
`mediator_share` shape so callers don't need to know which path
ran.

### Phase G re-evaluation triggers

- DoWhy 0.15+ if `get_mediator_variables()` returns *all*
  declared mediators and `estimate_effect` for NIE includes
  per-mediator decomposition → drop candidate 4 fallback, use
  candidate 2 for both single and multi.
- Switch bootstrap CI to normal-approximation CI if engine
  wall-clock under K=5 mediators exceeds 30 s per request.

## §2 Schema — `app/schemas/causal/mediation.py` (B.4)

Strict adherence to Plan v2 §2.4 verbatim — no field renaming, no
field omission.

### Request

```python
class CausalMediationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dag: DagSpec
    treatment: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    outcome: str = Field(
        ..., min_length=1, max_length=64,
        pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$",
    )
    mediators: List[str] = Field(..., min_length=1, max_length=8)
    data: CausalData
    decomposition: Literal[
        "natural", "controlled", "interventional"
    ] = "natural"   # B2b.2 MVP implements 'natural' only;
                    # 'controlled'/'interventional' reserved
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    n_bootstrap: int = Field(default=200, ge=100, le=10_000)
                    # Plan v2 default is 1000; we drop to 200 for
                    # the MVP wall-clock budget (~30 s under K=5
                    # mediators). Phase G can raise to 1000.
    assumptions_acknowledged: List[Literal[
        "sequential_ignorability",
        "no_treatment_mediator_interaction",
        "consistency",
        "positivity",
    ]] = Field(..., min_length=1)
    precomputed_estimand: Optional[IdentifiedEstimandHandle] = Field(
        default=None,
        description=(
            "Optional echo of an /identify response's estimand_handle "
            "for the parent ATE; saves one identification re-run. "
            "Same audit-trail rationale as B2a's Mod 4."
        ),
    )
    mode: Literal["sync", "async_job"] = "sync"

    @model_validator(mode="after")
    def _check_treatment_outcome_in_dag(self) -> "CausalMediationRequest":
        names = {n.name for n in self.dag.nodes}
        if self.treatment not in names or self.outcome not in names:
            raise ValueError("treatment/outcome must be in dag.nodes")
        if self.treatment == self.outcome:
            raise ValueError("treatment and outcome must differ")
        return self

    @model_validator(mode="after")
    def _check_mediators_in_dag(self) -> "CausalMediationRequest":
        names_by_kind = {
            n.name: n.node_kind for n in self.dag.nodes
        }
        for m in self.mediators:
            if m not in names_by_kind:
                raise ValueError(
                    f"mediator {m!r} not declared in dag.nodes"
                )
            if names_by_kind[m] != "mediator":
                raise ValueError(
                    f"mediator {m!r} must have node_kind='mediator' "
                    f"in the DAG (got {names_by_kind[m]!r})"
                )
        if len(set(self.mediators)) != len(self.mediators):
            raise ValueError("duplicate mediator names not allowed")
        return self

    @model_validator(mode="after")
    def _check_sync_size_gate(self) -> "CausalMediationRequest":
        if (self.mode == "sync"
            and self.data.inline is not None
            and len(self.data.inline) > 10_000):
            raise ValueError(
                f"sync mode + inline rows {len(self.data.inline)} > 10000; "
                f"use mode='async_job' (B2b.3 will implement)."
            )
        return self

    @model_validator(mode="after")
    def _check_async_not_implemented(self) -> "CausalMediationRequest":
        if self.mode != "sync":
            raise ValueError(
                "mode='async_job' reserved for a later batch; "
                "B2b.2 sync only."
            )
        return self
```

### Sub-models

```python
class MediationDecomposition(BaseModel):
    """Plan v2 §2.4: total = direct + indirect (Pearl identity).

    Used three times in the response: once for point estimates,
    once for the lower CI band, once for the upper CI band.
    """
    model_config = ConfigDict(extra="forbid")
    total_effect: float
    direct_effect: float
    indirect_effect: float
    mediator_share: Dict[str, float] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_share_sum(self) -> "MediationDecomposition":
        s = sum(self.mediator_share.values())
        if not (0.7 <= s <= 1.3):  # Mod 8 slack
            raise ValueError(
                f"mediator_share values sum to {s:.3f}; must be in "
                f"[0.7, 1.3] under nonparametric mediation."
            )
        return self


class MediationDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["dowhy_two_stage", "farbmacher_dml_loo"]
    n_samples: int = Field(..., ge=0)
    n_bootstrap_used: int = Field(..., ge=0)
    n_mediators: int = Field(..., ge=1)
    fit_time_ms: float = Field(..., ge=0.0)
    used_precomputed_estimand: bool = Field(default=False)
```

### Response

```python
class CausalMediationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decomposition: MediationDecomposition         # point estimates
    ci_lower: MediationDecomposition              # lower bootstrap band
    ci_upper: MediationDecomposition              # upper bootstrap band
    assumptions_echo: List[Literal[
        "sequential_ignorability",
        "no_treatment_mediator_interaction",
        "consistency",
        "positivity",
    ]] = Field(..., min_length=1)
    proportion_mediated: float = Field(..., ge=-1.0, le=2.0)
        # bounded -1..2 because nonparametric mediation can be
        # negative (Direction reversal) or super-additive
    proportion_mediated_ci: Tuple[float, float]
    evidence_level: EvidenceLevel
    diagnostics: MediationDiagnostics
    warnings: List[CausalWarning] = Field(default_factory=list, max_length=20)
    engine_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")

    @model_validator(mode="after")
    def _check_pearl_invariant(self) -> "CausalMediationResponse":
        d = self.decomposition
        # |direct + indirect - total| < 1e-3 (Plan v2 §2.4)
        gap = abs(d.direct_effect + d.indirect_effect - d.total_effect)
        if gap > 1e-3:
            raise ValueError(
                f"Pearl identity violated: |direct+indirect-total|="
                f"{gap:.4e} > 1e-3. Engine should always satisfy this."
            )
        return self
```

## §3 Paper alignment (V14 lines 11 + 153)

**Line 11 (abstract)** — verbatim quote:

> *"...and a pre-registered in-silico mediation analysis located
> the Signal-API → SER effect proximally through Kernel
> compilation efficiency κ (**~70% proportion mediated**)."*

**Line 153 (methods)** — verbatim quote:

> *"All analyses reported in this manuscript are fully reproducible
> from primary data via the analysis pipeline (Python 3.11; scipy
> 1.x; statsmodels 0.14.x; numpy; pandas), including the Hill
> 4-parameter fit (Eq. 8), restricted cubic spline regression at
> 3-, 4-, and 5-knot configurations, Welch's t-tests with Hedges'
> g effect size, 10,000-iteration nonparametric bootstrap,
> 1000-iteration Monte Carlo simulations for M2 / M3 progressive
> adjustment and VIF audit, and **the Pearl / Rubin counterfactual
> mediation analysis on the Signal-API → κ → SER pathway (Eq. 4)**.
> All random seeds are fixed at 42."*

### Interpretation for B2b.2

1. **Treatment = Signal-API (potency)**, **mediator = κ (Kernel
   compilation efficiency)**, **outcome = SER**. Single mediator in
   the paper's main analysis — so the DoWhy NDE/NIE branch covers
   this case.
2. Expected `proportion_mediated ≈ 0.70` (paper's headline number).
   The B2b.2 fixture must be parameterised so the engine recovers
   this within bootstrap noise to be a meaningful regression test.
3. Pearl/Rubin counterfactual framework — exactly what
   `mediation.two_stage_regression` computes. **D14 = γ confirmed.**
4. seeds fixed at 42 — tests use `np.random.default_rng(42)` to
   match.

### Test fixture re-design

Current mini-verify bench has `proportion_mediated ≈ 0.51` (too far
from paper's 0.70). The B2b.2 unit-test fixture must use these
coefficients:

```python
# proportion_mediated target = 0.70 ± bootstrap noise
T = 0.5 * Z + noise           # treatment
M = 1.0 * T + 0.4 * Z + noise # mediator (strengthened T → M)
Y = 1.5 * M + 0.4 * T + 0.5 * Z + noise  # weakened direct T → Y

# True direct = 0.4
# True indirect = 1.0 × 1.5 = 1.5
# True total = 1.9
# True proportion mediated = 1.5 / 1.9 = 0.789  ← close to paper 0.70
```

Tests will assert recovery within ±0.10 of 0.789 under n=200, seed=42.

## §4 Engine function signatures

### Public entrypoint

```python
def run_mediation(request: CausalMediationRequest) -> CausalMediationResponse:
    """Top-level dispatch.

    1. Pre-condition checks (single sync mode for B2b.2).
    2. Build data + DAG.
    3. Branch on len(request.mediators):
       - 1 → _run_dowhy_mediation (DoWhy NDE/NIE/ATE triple)
       - >= 2 → _run_farbmacher_mediation (leave-one-out DML loop)
    4. Apply n_min_per_stratum clamp (returns evidence_level=
       'planned' + small_sample warning, same as B2a's Mod 5).
    5. Bootstrap CI on the chosen branch (~n_bootstrap iterations).
    6. Validate Pearl invariant + mediator_share sum slack.
    """
```

### Single-mediator branch (candidate 2)

```python
def _run_dowhy_mediation(
    request: CausalMediationRequest, df: pd.DataFrame,
) -> Tuple[MediationDecomposition, MediationDiagnostics, str]:
    """Wraps DoWhy NDE/NIE/ATE triple.

    1. Build CausalModel(graph=dag_to_gml(dag)).
    2. identify_effect 3 times: ATE, NDE, NIE.
    3. estimate_effect with method_name='backdoor.linear_regression'
       for ATE, 'mediation.two_stage_regression' for NDE/NIE.
    4. Pack into MediationDecomposition:
        total = ATE.value
        direct = NDE.value
        indirect = NIE.value
        mediator_share = {request.mediators[0]: 1.0}
    Returns (decomposition_point, diagnostics_no_ci, identify_strategy).
    Bootstrap CI is done by the outer caller.
    """
```

### Multi-mediator branch (candidate 4 — Farbmacher leave-one-out)

```python
def _run_farbmacher_mediation(
    request: CausalMediationRequest, df: pd.DataFrame,
) -> Tuple[MediationDecomposition, MediationDiagnostics, str]:
    """Leave-one-out DML mediation.

    1. Identify covariates (DAG covariate nodes, excluding mediators).
    2. Baseline: LinearDML(Y ~ T | X=covariates) → total_effect.
    3. Full-adjust: LinearDML(Y ~ T | X=covariates + all_mediators)
       → direct_effect. Total indirect = total - direct.
    4. Leave-one-out per mediator m:
        LinearDML(Y ~ T | X=covariates + mediators_without_m)
        → effect_without_m
        per_mediator_indirect[m] = effect_without_m - direct
    5. Normalize: mediator_share[m] = |per_med[m]| / Σ|per_med|.
       (Absolute-value normalisation handles sign-reversal cases.)
    6. Pack into MediationDecomposition.
    Returns (decomposition_point, diagnostics_no_ci, "backdoor").
    """
```

### Bootstrap CI

```python
def _bootstrap_ci(
    request: CausalMediationRequest,
    df: pd.DataFrame,
    *,
    branch_fn,                     # callable: _run_dowhy or _run_farbmacher
    n_bootstrap: int,
    alpha: float,
    seed: Optional[int],
) -> Tuple[MediationDecomposition, MediationDecomposition]:
    """Returns (ci_lower, ci_upper) MediationDecomposition triples.

    For each of n_bootstrap iterations:
      - Resample df with replacement (n_total rows).
      - Run branch_fn on the bootstrap sample.
      - Collect per-bootstrap (total, direct, indirect, mediator_share).
    Then take percentile (alpha/2, 1-alpha/2) for each field.

    mediator_share CIs use the same per-row resampling but build
    a Dict[str, float] for both bounds (separately per mediator).
    """
```

### Assumption echo + reserved pattern

```python
class CausalMediationError(ValueError):
    """Raised on /mediation pre-condition failure. Router → HTTP 422."""
    def __init__(self, code: str, message: str): ...

_RESERVED_DECOMPOSITIONS = frozenset({"controlled", "interventional"})

def _check_decomposition(decomposition: str) -> None:
    """B2b.2 MVP implements 'natural' only.
    'controlled' / 'interventional' reserved with HTTP 422
    code='decomposition_reserved'."""
```

**Predicted engine LoC**: 550 – 700. Estimate breakdown:
- ~150 LoC: single-mediator DoWhy branch (3 identify+estimate calls)
- ~200 LoC: multi-mediator Farbmacher loop + per-mediator share
- ~150 LoC: bootstrap CI (resampling loop + percentile aggregator
  for MediationDecomposition + Dict[str,float] field)
- ~50 LoC: _check_decomposition, _validate_assumptions, custom
  exception, constants
- ~50 LoC: run_mediation top-level orchestration

## §5 Tests — `tests/unit/test_causal_mediation_engine.py`

**10 unit tests** mirroring B2b.1's structure. All use the
proportion-mediated-0.789 fixture (§3) with `np.random.default_rng(42)`,
n=200, no network / FastAPI imports.

| # | Test | Behavior |
|---|---|---|
| 1 | `test_mediation_single_dowhy_recovers_decomposition` | Single mediator, decomposition.total ≈ 1.9, .indirect ≈ 1.5, .direct ≈ 0.4 (±0.15) |
| 2 | `test_mediation_proportion_close_to_paper_value` | proportion_mediated within ±0.10 of 0.789 (paper headline 0.70) |
| 3 | `test_mediation_multi_farbmacher_leave_one_out` | Two mediators (M, M2). Loop branch fires; mediator_share keys = {M, M2}; share sum within [0.7, 1.3] |
| 4 | `test_mediation_pearl_invariant` | Engine response satisfies `|direct + indirect - total| < 1e-3` (validator) |
| 5 | `test_mediation_reserved_decomposition_raises_422` | `decomposition='controlled'` → CausalMediationError(code='decomposition_reserved') |
| 6 | `test_mediation_empty_assumptions_raises_422` | `assumptions_acknowledged=[]` → schema validator 422 |
| 7 | `test_mediation_mediator_not_in_dag_raises_422` | Request `mediators=['unknown']` → schema validator 422 |
| 8 | `test_mediation_mediator_share_sum_slack_validator` | Construct response with sum outside [0.7, 1.3] → schema validator 422 |
| 9 | `test_mediation_small_n_clamps_to_planned` | n=20 < n_min=30 → evidence_level='planned' + small_sample warning (B2a's Mod 5 pattern) |
| 10 | `test_mediation_bootstrap_ci_brackets_point_estimate` | For all 4 decomposition fields (total/direct/indirect + proportion), ci_lower ≤ point ≤ ci_upper |

Expected runtime: ~60-90 s total (5 of these involve bootstrap with
n_bootstrap=200 on n=200 data, each ~5-10 s; the schema-only ones
are < 1 s).

## §6 Reuse vs new

### Reused from B2a / B2b.1 (no changes)

| Module | Symbol | Why |
|---|---|---|
| `app.schemas.causal_common` | `DagSpec` | Request payload |
| `app.schemas.causal_common` | `CausalData` | Inline data |
| `app.schemas.causal_common` | `IdentifiedEstimandHandle` | precomputed_estimand reuse |
| `app.schemas.causal_common` | `CausalWarning`, `EvidenceLevel` | Response shape |
| `app.schemas.causal_common` | `CAUSAL_ENGINE_VERSION` | Response |
| `app.engine.extended.causal_utils` | `causal_data_to_dataframe` | Realise df from CausalData |
| `app.engine.extended.causal_utils` | `dag_to_gml` | Build DoWhy CausalModel |
| `app.engine.extended.causal_utils` | `split_covariates` | Adjust set for Farbmacher branch |
| `app.engine.extended.causal_utils` | `count_per_stratum` | n_min clamp |
| `app.engine.extended.causal_identify_engine` | `_classify_strategy` | Strategy echo to diagnostics |
| `app.engine.extended.causal_estimate_engine` | `_resolve_sklearn_model` | Nuisance model dispatch for Farbmacher DML |
| `app.engine.extended.causal_estimate_engine` | `_confidence_z` | (optional, only if normal-approx fallback added) |

### New (B2b.2)

| Path | Purpose |
|---|---|
| `app/schemas/causal/mediation.py` | `SCHEMA_VERSION = "B.4"`; Request + MediationDecomposition + MediationDiagnostics + Response + 5 model validators (assumptions / mediators / sync size / async-not-impl / Pearl invariant) |
| `app/engine/extended/causal_mediation_engine.py` | run_mediation + _run_dowhy_mediation + _run_farbmacher_mediation + _bootstrap_ci + _check_decomposition + CausalMediationError class |
| `app/routers/causal.py` (modify) | `@router.post("/mediation")` block (~25-35 LoC after estimate / refute) |
| `tests/unit/test_causal_mediation_engine.py` | 10 unit tests covering single + multi + boundary cases |

## §7 Effort estimate

| Step | Estimate |
|---|---|
| 2 — schema (mediation.py) | 60 min (Plan v2 §2.4 fields are dense; 5 validators) |
| 3 — engine | 180-240 min (single branch + multi branch + bootstrap CI) |
| 4 — router (1 endpoint) | 15 min |
| 5 — tests (10 unit) | 90-120 min (incl. fixture re-design + bootstrap-heavy tests) |
| 6 — narrow regression | 5 min |
| 7 — completion doc | 30 min |
| 8 — commit | 15 min |
| **Total** | **6.5-8 h** (vs Plan v2 raw 8h — 2× efficiency target) |

The wide range is driven by (a) the bootstrap CI's wall-clock for
tests and (b) potential surprises in DoWhy's `mediation.two_stage_regression`
under our exact request shape.

## §8 Risks

- **R1 — Bootstrap CI computational cost.** With n=200 rows,
  K=5 mediators, n_bootstrap=200, the Farbmacher branch does
  200×5=1000 LinearDML fits per request, plus the baseline + full.
  Worst case ~5-10 minutes per test. **Mitigation**: keep
  n_bootstrap=200 default for B2b.2 MVP (Plan v2 §2.4's 1000
  default is too slow); document the trade-off; Phase G can raise
  + add normal-approximation CI fallback. Default lowered to 200.
- **R2 — Per-mediator leave-one-out under interaction.** Farbmacher
  decomposition assumes mediators are non-interacting. Linear data
  satisfies this exactly; nonlinear cases would under-count
  interaction effects. **Mitigation**: document the assumption in
  Diagnostics + warning when interaction is suspected; production
  data is BSF batches which are predominantly linear by
  construction.
- **R3 — `mediator_share` sum slack [0.7, 1.3] under bootstrap
  noise.** With small n + many mediators, the bootstrap-resampled
  per-mediator effects may sum outside [0.7, 1.3] even on the
  point estimate. **Mitigation**: schema validator on the *point*
  decomposition only — the bootstrap CI bounds are not subject to
  the sum constraint (they record the percentile band; sum need
  not be exactly preserved). Add a `mediator_share_renormalized`
  warning when raw sum exceeds [0.7, 1.3] *before* normalisation.
- **R4 — DoWhy NDE/NIE for the single-mediator branch may have
  internal-state pollution like B2b.1's data_subset.** Currently
  not observed — Pearl identity held to 0.0000 in mini-verify — but
  if a future DoWhy upgrade introduces this, fall back to candidate
  4 even for single mediator.
- **R5 — Paper proportion_mediated 0.70 fixture validation.** The
  re-designed fixture (§3) targets 0.789. The 10% gap from
  paper's 0.70 is intentional (linear synthetic data is over-mediation-
  ized relative to BSF reality). Test asserts ±0.10 around 0.789
  rather than 0.70 — this is regression-test fidelity, not
  paper-replication fidelity. Phase G can add a more realistic
  fixture once real BSF data is available.
- **R6 — `controlled` / `interventional` decomposition reserved.**
  Plan v2 §2.4 lists 3 decomposition modes; B2b.2 MVP only ships
  'natural'. Reserved enum pattern with 422 code='decomposition_reserved'.
  Phase G adds 'controlled' (uses Pearl's mediation formula with
  fixed mediator level) and 'interventional' (uses
  interventional probability of mediator levels).

## §9 Phase G re-evaluation triggers

1. **DoWhy multi-mediator API**: if `get_mediator_variables()`
   returns all declared mediators and per-mediator decomposition
   is added → drop candidate 4 fallback, single code path for any
   K. Engine could shed ~200 LoC.
2. **Bootstrap CI performance**: if engine wall-clock under K=5
   mediators exceeds 30 s per request → add normal-approximation
   CI fallback (`_confidence_z` from B2a is already importable).
3. **Bootstrap parallelisation**: B2b.2 MVP is single-threaded.
   Phase G can use `joblib.Parallel(n_jobs=-1)` for 4-8x speedup.
4. **Controlled / interventional decomposition**: when paper
   versioning makes these modes useful, lift reserved-enum to
   implemented.
5. **Real BSF dataset**: replace the synthetic 0.789 fixture with
   a real BSF batch sample once the Daws pipeline is wired.

**End of design outline.**
