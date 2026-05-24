# Phase C — Batch C2 Design: Conformal Prediction Engine

> Detail-level design for **Plan v3 Batch C2** (distribution-free
> conformal prediction intervals). Authorises engineering work to
> ship `causal_conformal_engine.py` + endpoint + tests + drift gate.
>
> **Scope reference**: `_reports/PHASE_C_PLAN.md` §2.2.
>
> **Anchor**: HEAD `98031ee` (Phase C C1 just shipped at tag
> `v0.10.0-phase-c-c1`); 53+4+4+1 contract/unit gates PASS;
> paper-pin SHA `C7E4CE1B...3741C`.
>
> **Estimated effort**: 10-15 hours (per Plan v3 §3).
> **Calendar target**: ship by 2026-08 early (per v3' schedule).

---

## §1 Purpose

C2 introduces distribution-free conformal prediction intervals
as a **complement to** the Bayesian HDI from C1 and the
frequentist CI from B2a. Conformal prediction gives
**finite-sample marginal coverage guarantees** (P(Y ∈ Ĉ(X)) ≥
1 - α) without distributional assumptions, which is critical
for the Paper 3 methodology paper's "distribution-free" claim.

The C2 engine handles:
1. Point predictions on new observations (e.g., projected SER)
2. Prediction interval at any α level (default 0.05)
3. Mondrian variant: stratifies conformal residuals by substrate
   class, giving conditional coverage guarantees within each
   substrate (handles cross-substrate heterogeneity reported in
   Paper 1 §3.5.1)

---

## §2 Method selection: Split-conformal + Mondrian

### §2.1 Split-conformal baseline (Lei & Wasserman 2014)

Given a regression model μ̂ (fit on training data) and a
calibration set (X_cal, Y_cal) **independent of training**:

1. Compute residuals on calibration set:
   `R_i = |Y_cal_i - μ̂(X_cal_i)|`
2. Compute the (1-α) quantile of residuals: `q_{1-α}(R)`
3. For new x, prediction interval is:
   `Ĉ(x) = [μ̂(x) - q_{1-α}, μ̂(x) + q_{1-α}]`

**Guarantee**: P(Y_new ∈ Ĉ(X_new)) ≥ 1 - α (marginal, finite-sample)

### §2.2 Mondrian variant (stratified conformal)

Same split-conformal procedure but residuals stratified by a
discrete stratum variable (e.g., substrate class):

1. For each stratum s, compute residuals on cal-set rows in s
2. q_{1-α}(R_s) = (1-α) quantile within stratum s
3. For new x with stratum s, prediction interval uses q_{1-α}(R_s)

**Guarantee**: P(Y_new ∈ Ĉ(X_new) | stratum=s) ≥ 1 - α
(conditional coverage within each stratum)

### §2.3 Why Mondrian matters for BOS

Paper 1 §3.5.1 + §4.3 shows substrate-class heterogeneity:
distillers' grains (D' = 68%), tobacco straw (85%), TCM
residue (70-80%), sludge (15% - outside envelope).

A marginal conformal interval averages across all substrates,
giving 95% marginal coverage. Mondrian gives 95% **per
substrate** — much more useful for the operator deciding "what
range of SER should I expect on tobacco straw specifically?"

### §2.4 Custom implementation, not mapie/crepes

The split-conformal algorithm is ~30 lines of code. Mondrian
adds ~20 more. Adding `mapie` or `crepes` Python packages
brings ~50-100MB of dependencies. We implement in-house.

### §2.5 Underlying regressor

The C2 engine **requires a pre-fit regressor** from upstream
(typically from `/estimate` Phase B endpoint or `/bayesian_estimate`
C1 endpoint). The conformal layer **wraps** the regressor, it
does not refit.

To keep the C2 endpoint self-contained for testing, we also
support **internal fit-and-conformalize**: if no upstream
regressor is provided, the engine fits a simple OLS on the
training split internally before conformalizing on the
calibration split.

---

## §3 API contract

### §3.1 Endpoint

```
POST /api/v1/causal/conformal_predict
Content-Type: application/json
```

### §3.2 Request schema (`ConformalPredictRequest`)

```python
class ConformalPredictRequest(BaseModel):
    SCHEMA_VERSION: str = "C.2"

    # Data and DAG (same shape as Phase B causal endpoints)
    data: CausalData
    dag: DagSpec
    treatment: str
    outcome: str

    # Conformal-specific
    method: Literal["split_conformal", "mondrian_conformal"] = "split_conformal"
    alpha: float = Field(default=0.05, gt=0, lt=1)  # 1-alpha coverage
    calibration_fraction: float = Field(default=0.3, gt=0, lt=1)
    stratum_variable: str | None = None  # required for Mondrian

    # Optional new observations to predict
    new_observations: list[dict[str, float]] | None = None

    # Reproducibility
    random_seed: int = 42
```

### §3.3 Response schema (`ConformalPredictResponse`)

```python
class ConformalPredictResponse(BaseModel):
    SCHEMA_VERSION: str = "C.2"

    # Per-observation predictions (one entry per new_obs row)
    predictions: list[ConformalPrediction]  # point + interval per row

    # Calibration set statistics
    coverage_guarantee: float  # 1 - alpha
    n_calibration_samples: int
    n_training_samples: int

    # Marginal interval width on calibration set (sanity)
    median_interval_width: float

    # Mondrian-specific
    strata_used: dict[str, int] | None  # stratum_value -> n_cal_in_stratum
    per_stratum_quantiles: dict[str, float] | None  # stratum -> q_{1-alpha}

    # Method + diagnostics
    method: Literal["split_conformal", "mondrian_conformal"]
    alpha: float
    random_seed: int
    evidence_level: EvidenceLevel
    warnings: list[CausalWarning]


class ConformalPrediction(BaseModel):
    point: float                  # μ̂(x)
    interval_low: float           # μ̂(x) - q_{1-α}
    interval_high: float          # μ̂(x) + q_{1-α}
    stratum: str | None = None    # which stratum (Mondrian only)
```

### §3.4 Evidence-level rules

- `validated`:
  - Calibration n ≥ 30 (general rule of thumb for stable quantile)
  - For Mondrian: each stratum has n ≥ 20 cal samples
  - Median interval width < 50% of outcome std (informative)
- `supported`:
  - Calibration n ≥ 10 (any stratum)
  - Interval reported but width not necessarily informative
- `planned`: otherwise

---

## §4 Engine implementation

### §4.1 Module structure

```python
# backend/app/engine/extended/causal_conformal_engine.py
"""Phase C C2 — split-conformal + Mondrian prediction intervals.

Custom implementation (no mapie/crepes dependency). Wraps an
internal OLS fit on training split, then computes residuals on
calibration split to derive distribution-free prediction
intervals at the requested α level.
"""

# Public API
def predict_conformal(request: ConformalPredictRequest) -> Tuple[
    ConformalPredictResponse, list[CausalWarning]
]: ...

# Exception
class CausalConformalError(Exception): ...

# Private helpers
def _split_conformal(...)
def _mondrian_conformal(...)
def _fit_internal_ols(X, Y)
def _compute_quantile(residuals, alpha)
```

### §4.2 Algorithm

```python
def predict_conformal(request):
    # 1. Load data
    df = causal_data_to_dataframe(request.data)

    # 2. Select features (backdoor adjustment set)
    backdoor_vars = _select_backdoor_variables(request)
    X_cols = backdoor_vars + [request.treatment]
    X_full = df[X_cols].values
    Y_full = df[request.outcome].values

    # 3. Split into train + calibration (random with seed)
    rng = np.random.default_rng(request.random_seed)
    n = len(df)
    indices = rng.permutation(n)
    n_cal = int(n * request.calibration_fraction)
    cal_idx = indices[:n_cal]
    train_idx = indices[n_cal:]

    X_train, Y_train = X_full[train_idx], Y_full[train_idx]
    X_cal, Y_cal = X_full[cal_idx], Y_full[cal_idx]

    # 4. Fit internal OLS on training split
    beta_hat = _fit_internal_ols(X_train, Y_train)

    # 5. Compute calibration residuals
    Y_cal_pred = X_cal @ beta_hat
    residuals = np.abs(Y_cal - Y_cal_pred)

    # 6. Dispatch by method
    if request.method == "split_conformal":
        q = np.quantile(residuals, 1 - request.alpha,
                        method='higher')  # finite-sample correction
        ...
    elif request.method == "mondrian_conformal":
        strata_col = df[request.stratum_variable].values[cal_idx]
        per_stratum_quantiles = {}
        for stratum in np.unique(strata_col):
            mask = strata_col == stratum
            if mask.sum() >= 1:
                per_stratum_quantiles[str(stratum)] = np.quantile(
                    residuals[mask], 1 - request.alpha,
                    method='higher',
                )
        ...

    # 7. Predict on new_observations
    predictions = []
    for obs in request.new_observations or []:
        x_new = np.array([obs[c] for c in X_cols])
        y_hat = float(x_new @ beta_hat)
        if request.method == "split_conformal":
            interval_low = y_hat - q
            interval_high = y_hat + q
        else:
            stratum = obs.get(request.stratum_variable, "default")
            q_s = per_stratum_quantiles.get(str(stratum), q)
            interval_low = y_hat - q_s
            interval_high = y_hat + q_s
        predictions.append(ConformalPrediction(
            point=y_hat,
            interval_low=interval_low,
            interval_high=interval_high,
            stratum=str(stratum) if request.method == "mondrian_conformal" else None,
        ))

    # 8. Evidence level + response
    ...
```

### §4.3 Test plan (~8-10 tests)

1. **test_split_conformal_recovers_truth**: synthetic linear DGP,
   marginal coverage ≥ 90% on holdout
2. **test_split_conformal_coverage_validation**: 100 Monte Carlo
   datasets; coverage ≥ (1-α) within statistical tolerance
3. **test_split_conformal_interval_width_decreases_with_n**: n=50
   vs n=500; wider for smaller n
4. **test_mondrian_conditional_coverage**: 2 strata, different
   noise levels; each stratum has ≥ (1-α) coverage
5. **test_mondrian_requires_stratum_variable**: missing
   stratum_variable → CausalConformalError(code='missing_stratum')
6. **test_mondrian_handles_empty_stratum**: stratum present in
   prediction but absent from calibration → falls back to marginal
7. **test_alpha_sensitivity**: α=0.05 vs α=0.10; 0.05 wider
8. **test_seed_reproducibility**: same seed → identical predictions
9. **test_calibration_fraction_sensitivity**: 0.2 vs 0.4 split;
   both work
10. **test_reserved_method_raises**: invalid method literal →
    ValidationError at pydantic layer

---

## §5 Acceptance criteria

- [ ] `app/schemas/causal/conformal.py` with SCHEMA_VERSION="C.2"
- [ ] `app/engine/extended/causal_conformal_engine.py` implements
      `predict_conformal()` + `CausalConformalError`
- [ ] `POST /api/v1/causal/conformal_predict` added to router
- [ ] 8-10 unit tests in `tests/unit/test_causal_conformal_engine.py`
      (FAST — no PyMC required, just numpy + scipy)
- [ ] `tests/contract/test_phase_c_openapi.py` PHASE_C_CAUSAL_PATHS
      extended to include `/api/v1/causal/conformal_predict`
- [ ] `_reports/phase_c_openapi_snapshot.json` regenerated
- [ ] All Phase B + C contract gates PASS (no regression)
- [ ] PAPER_PINNING.md §3 C2 entry appended
- [ ] CITATION.cff version → `0.10.1-phase-c-c2`
- [ ] Tag `v0.10.1-phase-c-c2` created and pushed
- [ ] Paper 1 SHA gate STILL PASSES (`C7E4CE1B...3741C` unchanged)

---

End of PHASE_C_C2_DESIGN.md.
