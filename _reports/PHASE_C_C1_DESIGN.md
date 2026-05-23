# Phase C — Batch C1 Design: Bayesian Baseline Engine

> Detail-level design for **Plan v3 Batch C1** (Bayesian
> baseline ATE estimation via PyMC). Authorises engineering
> work to ship `causal_bayesian_engine.py` + endpoint + tests.
>
> **Scope reference**: `_reports/PHASE_C_PLAN.md` §2.1 (Plan v3
> shipped at commit 5aa359c).
>
> **Anchor**: HEAD `5aa359c`, Phase B 100% complete, 53+51
> tests PASS, paper-pin SHA `C7E4CE1B...3741C`.
>
> **Estimated effort**: 10-15 hours (per Plan v3 §3).
> **Calendar target**: ship by 2026-07 end (per v3' schedule).

---

## §1 Purpose

C1 introduces Bayesian posterior estimation of the ATE as an
**alternative to** Phase B B2a's LinearDML point estimate. It
does **not replace** LinearDML; the two approaches are reported
side-by-side, satisfying the methodology paper (Paper 3)'s
"dual Bayesian–frequentist reporting" claim.

The PyMC backend handles model fitting + posterior sampling.
Output is a posterior distribution over the ATE, summarised as:
- Posterior mean
- 95% Highest Density Interval (HDI)
- Posterior samples (default 1000 × 2 chains = 2000 draws)
- Diagnostic statistics (R-hat, effective sample size, divergent
  transitions)

---

## §2 Method selection: Bayesian backdoor regression

### §2.1 Model specification

For a binary or continuous treatment `T`, outcome `Y`, and
backdoor adjustment set `X`:

```
β_T ~ Normal(μ_prior, σ_prior²)        # treatment coefficient
β_X ~ Normal(0, σ_X²)                  # covariate coefficients
σ_y ~ HalfNormal(σ_y_prior)            # noise scale
Y | T, X, β ~ Normal(β_T·T + β_X·X, σ_y²)
```

The posterior `p(β_T | data, X, T, Y)` is interpreted as the
ATE posterior.

### §2.2 Prior choice (Plan v3 review Session 2 decision)

**Weakly informative priors (default)**:
- `μ_prior = 0`, `σ_prior = 1` (assumes treatment effect is on
  unit scale; data should be standardised or this assumption
  documented in response)
- `σ_X = 5` (wide prior on covariates)
- `σ_y_prior = 1` (HalfNormal scale)

**Informative prior (optional, when domain knowledge available)**:
- Operator may pass `prior_treatment_mean` and
  `prior_treatment_sd` in request
- Defaults to 0, 1 if not provided

**Rationale**: weakly informative priors per Gelman et al.
(2008) recommendation; allows the data to dominate the posterior
while preventing impossible-magnitude estimates from sampling
noise on small-n datasets.

### §2.3 Sampler choice

- **Default**: PyMC NUTS sampler (`pm.sample(target_accept=0.95)`)
- **Chains**: 2 (default) or operator-configurable
- **Draws**: 1000 per chain (default) or operator-configurable
- **Tune**: 1000 (default)
- **Seed**: 42 (locked, matches Paper 1 reproducibility convention)

Total wall-clock: ~10-30 seconds per request on the default
fixture size. Slower than DoWhy's LinearDML (sub-second), but
that is the price for full posterior characterisation.

---

## §3 API contract

### §3.1 Endpoint

```
POST /api/v1/causal/bayesian_estimate
Content-Type: application/json
```

### §3.2 Request schema (`BayesianEstimateRequest`)

```python
class BayesianEstimateRequest(BaseModel):
    """Phase C Batch C1 — Bayesian backdoor estimation."""

    SCHEMA_VERSION: str = "C.1"

    # Data — same shape as Phase B causal endpoints
    causal_data: CausalData  # treatment, outcome, covariates

    # DAG — same shape as Phase B
    dag: CausalDAG

    # Identification — reuse Phase B identify endpoint output
    identification: IdentifyResult | None = None

    # Bayesian-specific parameters
    method: Literal["bayesian_backdoor"] = "bayesian_backdoor"
    n_chains: int = Field(default=2, ge=2, le=8)
    n_draws: int = Field(default=1000, ge=500, le=5000)
    n_tune: int = Field(default=1000, ge=500, le=5000)
    target_accept: float = Field(default=0.95, ge=0.8, le=0.99)

    # Prior specification (optional)
    prior_treatment_mean: float = 0.0
    prior_treatment_sd: float = Field(default=1.0, gt=0)
    prior_covariate_sd: float = Field(default=5.0, gt=0)
    prior_noise_sd: float = Field(default=1.0, gt=0)

    # Seed
    random_seed: int = 42
```

### §3.3 Response schema (`BayesianEstimateResponse`)

```python
class BayesianEstimateResponse(BaseModel):
    """Phase C Batch C1 response."""

    SCHEMA_VERSION: str = "C.1"

    # Point estimate (posterior mean for backward compat with
    # Phase B B.2 frequentist response)
    ate_point: float
    ate_posterior_mean: float

    # Uncertainty
    ate_hdi_95: tuple[float, float]  # (low, high) of 95% HDI
    ate_posterior_sd: float

    # Posterior samples (for downstream propagation in C4)
    ate_posterior_samples: list[float]  # length = n_chains * n_draws

    # Diagnostics
    r_hat: float                  # < 1.01 desired
    effective_sample_size: float  # > 400 desired
    n_divergent: int              # should be 0
    warnings: list[str]

    # Evidence level (mirrors B.2 frequentist response)
    evidence_level: Literal[
        "validated", "supported", "planned"
    ]

    # Metadata
    method: Literal["bayesian_backdoor"] = "bayesian_backdoor"
    n_chains: int
    n_draws: int
    random_seed: int
    runtime_seconds: float
```

### §3.4 Evidence-level rules for Bayesian

Mirror Phase B B.2 rules but on posterior-based criteria:

- `validated`:
  - `r_hat < 1.01` AND
  - `effective_sample_size > 400` AND
  - `n_divergent == 0` AND
  - HDI excludes zero AND
  - identification.strategy == "backdoor"
- `supported`:
  - `r_hat < 1.05` AND
  - `effective_sample_size > 100` AND
  - HDI excludes zero
- `planned`: otherwise

---

## §4 Engine implementation: `causal_bayesian_engine.py`

### §4.1 Module structure

```python
# backend/app/engine/extended/causal_bayesian_engine.py
"""Phase C C1 — Bayesian backdoor ATE engine.

Wraps PyMC 5.x NUTS sampler to compute posterior over the
treatment-effect coefficient under backdoor adjustment.

Reference: PHASE_C_PLAN.md §2.1 + PHASE_C_C1_DESIGN.md.
"""

import time
import warnings as warnings_module
from typing import Tuple, List

import numpy as np
import pandas as pd
import pymc as pm
import arviz as az

from app.engine.extended.causal_utils import (
    causal_data_to_dataframe,
    select_backdoor_variables,
)
from app.schemas.causal.bayesian import (
    BayesianEstimateRequest,
    BayesianEstimateResponse,
)
from app.engine.extended.causal_identify_engine import (
    _classify_strategy,
)


def estimate_ate_bayesian(
    request: BayesianEstimateRequest,
) -> Tuple[BayesianEstimateResponse, List[str]]:
    """Estimate ATE posterior via PyMC backdoor regression."""
    start_time = time.time()
    warnings_list = []

    # 1. Convert causal_data to DataFrame (reuse Phase B util)
    df = causal_data_to_dataframe(request.causal_data)

    # 2. Identify backdoor adjustment set from DAG
    backdoor_vars = select_backdoor_variables(
        request.dag,
        treatment="treatment",
        outcome="outcome",
    )

    # 3. Prepare design matrices
    T = df["treatment"].values
    Y = df["outcome"].values
    if backdoor_vars:
        X = df[backdoor_vars].values
    else:
        X = np.zeros((len(df), 0))

    # 4. Build PyMC model
    with pm.Model() as model:
        # Treatment coefficient (the parameter of interest)
        beta_T = pm.Normal(
            "beta_T",
            mu=request.prior_treatment_mean,
            sigma=request.prior_treatment_sd,
        )

        # Covariate coefficients
        if X.shape[1] > 0:
            beta_X = pm.Normal(
                "beta_X",
                mu=0,
                sigma=request.prior_covariate_sd,
                shape=X.shape[1],
            )
        else:
            beta_X = pm.Deterministic(
                "beta_X", pm.math.constant(np.zeros(0))
            )

        # Noise
        sigma_y = pm.HalfNormal(
            "sigma_y",
            sigma=request.prior_noise_sd,
        )

        # Mean
        mu = beta_T * T
        if X.shape[1] > 0:
            mu = mu + pm.math.dot(X, beta_X)

        # Likelihood
        pm.Normal("Y_obs", mu=mu, sigma=sigma_y, observed=Y)

        # Sample
        with warnings_module.catch_warnings():
            warnings_module.simplefilter("ignore")
            idata = pm.sample(
                draws=request.n_draws,
                tune=request.n_tune,
                chains=request.n_chains,
                target_accept=request.target_accept,
                random_seed=request.random_seed,
                progressbar=False,
            )

    # 5. Extract posterior samples
    posterior_samples = idata.posterior["beta_T"].values.flatten()
    posterior_mean = float(np.mean(posterior_samples))
    posterior_sd = float(np.std(posterior_samples))

    # 6. Compute HDI (Highest Density Interval)
    hdi = az.hdi(posterior_samples, hdi_prob=0.95)
    hdi_low = float(hdi[0])
    hdi_high = float(hdi[1])

    # 7. Diagnostics
    summary = az.summary(idata, var_names=["beta_T"])
    r_hat = float(summary["r_hat"].iloc[0])
    ess = float(summary["ess_bulk"].iloc[0])
    n_divergent = int(
        idata.sample_stats["diverging"].sum().item()
    )

    # 8. Evidence level
    hdi_excludes_zero = (hdi_low > 0) or (hdi_high < 0)
    strategy = _classify_strategy(request.identification)

    if (r_hat < 1.01 and ess > 400 and n_divergent == 0
            and hdi_excludes_zero and strategy == "backdoor"):
        evidence_level = "validated"
    elif r_hat < 1.05 and ess > 100 and hdi_excludes_zero:
        evidence_level = "supported"
    else:
        evidence_level = "planned"

    # 9. Build response
    response = BayesianEstimateResponse(
        ate_point=posterior_mean,
        ate_posterior_mean=posterior_mean,
        ate_hdi_95=(hdi_low, hdi_high),
        ate_posterior_sd=posterior_sd,
        ate_posterior_samples=posterior_samples.tolist(),
        r_hat=r_hat,
        effective_sample_size=ess,
        n_divergent=n_divergent,
        warnings=warnings_list,
        evidence_level=evidence_level,
        n_chains=request.n_chains,
        n_draws=request.n_draws,
        random_seed=request.random_seed,
        runtime_seconds=time.time() - start_time,
    )

    return response, warnings_list
```

---

## §5 Schema module: `app/schemas/causal/bayesian.py`

Standard Pydantic schema (similar pattern to `app/schemas/causal/estimate.py`).

Frozen `SCHEMA_VERSION = "C.1"` constant.

Validates:
- `n_chains` ∈ [2, 8]
- `n_draws` ∈ [500, 5000]
- `n_tune` ∈ [500, 5000]
- `target_accept` ∈ [0.8, 0.99]
- prior SDs > 0

---

## §6 Router integration: `app/routers/causal.py`

Add new endpoint following the pattern of existing 5:

```python
@router.post(
    "/bayesian_estimate",
    response_model=BayesianEstimateResponse,
    summary="Bayesian backdoor ATE estimation (Phase C C1)",
)
async def causal_bayesian_estimate(
    request: BayesianEstimateRequest,
) -> BayesianEstimateResponse:
    response, warnings_list = estimate_ate_bayesian(request)
    # Add warnings to response if needed
    return response
```

Reuse Phase B exception-handling pattern (HTTP 422 for invalid
methods, 500 for unexpected errors with traceback in logs).

---

## §7 Test plan: `tests/unit/test_causal_bayesian_engine.py`

### §7.1 Test list (~10 tests)

1. **test_bayesian_recovery_synthetic_known_ate** — generate
   synthetic data with known ATE = 2.0; assert posterior mean
   within 0.3 of 2.0 (3-sigma envelope on n=200 data)
2. **test_bayesian_hdi_calibration** — 100 synthetic datasets,
   each with random known ATE; HDI captures true ATE in ≥ 95%
   of cases (within statistical tolerance)
3. **test_bayesian_prior_sensitivity_weakly_informative** — same
   data, weakly vs uniformly informative; results should agree
   within 5%
4. **test_bayesian_prior_sensitivity_informative** — same data,
   informative prior centered at true value; should reduce
   posterior SD
5. **test_bayesian_seed_reproducibility** — same input, same
   seed → identical posterior samples
6. **test_bayesian_seed_different** — same input, different
   seeds → different samples but same posterior mean within 5%
7. **test_bayesian_diagnostic_r_hat** — well-mixed chains
   should yield r_hat < 1.01 on standard test fixture
8. **test_bayesian_diagnostic_ess** — ESS > 400 on standard
   fixture
9. **test_bayesian_n_divergent_zero** — no divergent
   transitions on standard fixture
10. **test_bayesian_reserved_method_422** — request with
    `method = "bayesian_dml"` (reserved enum value) → 422

### §7.2 Synthetic data generator

```python
def generate_synthetic_causal_data(
    n: int = 200,
    true_ate: float = 2.0,
    confounding_strength: float = 0.5,
    noise_sd: float = 1.0,
    seed: int = 42,
):
    """Generate causal data with known truth."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, n)  # confounder
    T = rng.binomial(1, 1 / (1 + np.exp(-confounding_strength * X)))
    Y = true_ate * T + 0.5 * X + rng.normal(0, noise_sd, n)
    return pd.DataFrame({"treatment": T, "outcome": Y, "X": X})
```

### §7.3 Test runtime budget

~6-8 minutes for full Bayesian test suite (~30s per Bayesian
test × 10-12 tests). Acceptable for unit tests; marker as
`@pytest.mark.slow` to allow optional skip in fast CI loops.

---

## §8 Agent node: `backend/agent/nodes/causal_bayesian.py`

Follow B4 v2 pattern from `causal_estimate.py`:

```python
"""Phase C C1 — Bayesian estimate node.

Wraps /api/v1/causal/bayesian_estimate as a LangGraph node.
"""

from typing import Any, Dict

from agent.state import BOSState
from agent.tools import call_bayesian_estimate  # new tool

async def bayesian_estimate_node(state: BOSState) -> Dict[str, Any]:
    """Run Bayesian ATE estimation on the current causal claim."""
    request = build_bayesian_request_from_state(state)
    response = await call_bayesian_estimate(request)
    return {
        "causal": {
            **state.causal,
            "bayesian": response.model_dump(),
        }
    }
```

Add to LangGraph in `backend/agent/graph.py`. Edge: dispatched
from `router_node` when `intent = "causal.bayesian"`.

---

## §9 OpenAPI drift gate extension

Create `tests/contract/test_phase_c_openapi.py` mirroring B3:

```python
def test_phase_c_openapi_paths_match_snapshot():
    """New C-layer endpoints must be in the snapshot."""
    snapshot = load_phase_c_snapshot()
    actual = get_current_openapi_paths()
    assert "/api/v1/causal/bayesian_estimate" in actual
    # ... etc
```

Snapshot file: `_reports/phase_c_openapi_snapshot.json` (new).

---

## §10 Dependencies: `requirements.txt` additions

```
pymc>=5.10,<6.0
arviz>=0.16,<1.0
```

Compatibility check needed:
- PyMC 5.x supports numpy 2.x ✓ (confirmed in upstream changelog)
- ArviZ 0.16+ supports PyMC 5.x ✓
- pytensor (PyMC backend) numpy 2.x compatible ✓

Concern: PyMC adds ~150 MB to the venv. Acceptable.

---

## §11 Risk register (C1 specific)

| Risk | Mitigation |
|---|---|
| PyMC numpy 2.x incompat surfaces at install | Test install on `backend/.venv-backend` FIRST; if fails, use PyMC 4.x or pin numpy 1.26 |
| Sampler hangs / divergent transitions on edge cases | Implement timeout (30s default); on divergent, escalate to operator with `code='sampler_divergent'` warning |
| Test runtime 6-8 min slows CI | Mark slow tests `@pytest.mark.slow`; fast CI runs only the synthetic-recovery test |
| Prior misspecification (too narrow / too wide) | Default to weakly informative; document deviation as warning |
| PyMC version drift breaks reproducibility | Pin PyMC to specific minor version (≥5.10,<6.0); upgrade only via Plan v3 amendment |

---

## §12 Implementation order (estimated hours)

| Step | Action | Hours |
|---|---|---|
| 1 | Install PyMC + ArviZ in venv; verify numpy 2.x compat | 0.5-1 |
| 2 | Implement `app/schemas/causal/bayesian.py` schema | 1-2 |
| 3 | Implement `app/engine/extended/causal_bayesian_engine.py` engine | 3-4 |
| 4 | Implement `app/routers/causal.py` endpoint addition | 0.5 |
| 5 | Write 10 unit tests | 3-4 |
| 6 | Implement `backend/agent/nodes/causal_bayesian.py` agent node | 1-1.5 |
| 7 | Implement `tests/contract/test_phase_c_openapi.py` drift gate | 1-1.5 |
| 8 | Update OpenAPI snapshot + audit chain entry | 0.5 |
| **Total** | | **10.5-15 hours** |

Matches Plan v3 §3 C1 budget (10-15 hours).

---

## §13 Acceptance criteria for C1 ship

C1 is "shipped" when ALL of the following pass:

- [ ] PyMC + ArviZ installed in `backend/.venv-backend`
- [ ] `causal_bayesian_engine.py` exists and imports cleanly
- [ ] `app/schemas/causal/bayesian.py` exists with
      `SCHEMA_VERSION = "C.1"`
- [ ] `POST /api/v1/causal/bayesian_estimate` endpoint added to
      router
- [ ] 10 unit tests written and all PASS
- [ ] OpenAPI snapshot regenerated with new endpoint
- [ ] OpenAPI drift gate `test_phase_c_openapi.py` PASSES
- [ ] Agent node `causal_bayesian.py` added to LangGraph
- [ ] Agent tests still 51 PASS, 0 regression
- [ ] 53 Phase B tests still PASS (no regression on existing
      causal layer)
- [ ] PAPER_PINNING.md §3 appended with C1 entry (classified
      "Phase C extension, no method drift, no paper-SHA change")
- [ ] CITATION.cff `version` bumped to `0.10.0-phase-c-c1`
- [ ] Tag `v0.10.0-phase-c-c1` created
- [ ] Commit + push to GitHub
- [ ] Paper 1 SHA gate STILL PASSES (`C7E4CE1B...3741C`
      unchanged)

---

## §14 Sign-off

Plan v3 review Session 2 deliverable complete. Authorises C1
engineering work to start.

**Next steps**:
- Operator: confirm C1 design (this document)
- Then: install PyMC + ArviZ in venv
- Then: C1 engineering kickoff (Step 1 of §12 above)
- C1 expected ship date: 2026-07 end (per v3' schedule), ~3-4
  weeks at 3-5 h/week

---

End of PHASE_C_C1_DESIGN.md (Plan v3 Session 2 deliverable).
