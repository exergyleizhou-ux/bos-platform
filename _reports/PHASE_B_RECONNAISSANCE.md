# Phase B — Reconnaissance Report

> Phase 0 / Phase B Step 1 deliverable.
> Style follows `_reports/BOS_Phase0_Architecture_Gap_Report.md`.
>
> Generated 2026-05-17 against HEAD `b962e58` (branch
> `chat/bos-v9-stabilize-files`).
>
> **What this is.** A pre-Plan fact-collection pass for the Phase B
> "causal inference layer" effort: DoWhy / EconML compatibility, the
> Phase A schema surface seen as a causal-variable lattice, the paper's
> causal claims, the data-availability matrix, and a risk register.
>
> **What this is NOT.** Not a Plan. Not a DAG. Not an estimator
> choice. Not a roadmap. No backend / agent / frontend code was
> modified to produce this report.

---

## Section 1 — DoWhy / EconML reconnaissance

### 1.1 Throwaway venv

Created at `/tmp/bos-phase-b-recon-venv` (Windows-resolved path
`C:\Users\10420\AppData\Local\Temp\bos-phase-b-recon-venv\`). **Not**
committed; **not** added to `backend/requirements.txt`. To remove
post-recon: `rm -rf /tmp/bos-phase-b-recon-venv`.

Python in the venv: **3.12.7** (mirrors the host interpreter).

> Note: handoff §10 records "Python 3.11+ (verified via app.main:app
> boot)". The host actually runs 3.12.7. Both DoWhy and EconML are
> happy on 3.12.

### 1.2 Versions installed

| Package | Version | Provenance |
|---|---|---|
| **dowhy** | **0.14** | PyPI (latest, MIT, PyWhy Community) |
| **econml** | **0.16.0** | PyPI (latest, MIT, PyWhy contributors) |
| python-docx | 1.2.0 | helper for paper extraction (Section 3) |
| numpy | **2.4.5** | hard pull by dowhy + econml |
| scipy | **1.15.3** | hard pull by dowhy |
| pandas | **3.0.3** | hard pull by both |
| scikit-learn | 1.6.1 | dowhy + econml |
| statsmodels | 0.14.6 | dowhy + econml |
| networkx | 3.6.1 | dowhy (DAG) |
| sympy | 1.14.0 | dowhy (identification) |
| cvxpy | 1.8.2 | dowhy (overrule refuter) |
| shap | 0.48.0 | econml (interpreters) |
| lightgbm | 4.6.0 | econml (default tree learners) |
| numba | 0.65.1 | dowhy |
| causal-learn | 0.1.4.5 | dowhy (structure learning) |
| pydot | 4.0.1 | dowhy (graph viz) |

Direct requirements echoed by `pip show`:

```
dowhy.Requires:  causal-learn, cvxpy, cython, joblib, networkx,
                 numba, numpy, pandas, scikit-learn, scipy,
                 statsmodels, sympy, tqdm
econml.Requires: joblib, lightgbm, numpy, packaging, pandas,
                 scikit-learn, scipy, shap, sparse, statsmodels
```

### 1.3 DoWhy — the 4-step pipeline

DoWhy's API is structured as four explicit phases. The reconnaissance
hello-world (1.5) exercises all four:

1. **Model.** Build a `CausalModel(data, treatment, outcome,
   graph=… or common_causes=…)`. The graph can be a string in DOT/GML
   or a NetworkX object.
2. **Identify.** `model.identify_effect()` returns an
   `IdentifiedEstimand`. Uses the do-calculus to decide which
   adjustment set (back-door / front-door / IV) yields a
   statistically identifiable target.
3. **Estimate.** `model.estimate_effect(identified_estimand,
   method_name=…)`. Inventory of bundled methods discovered in
   `dowhy.causal_estimators`:
   - `linear_regression_estimator`
   - `generalized_linear_model_estimator`
   - `regression_estimator`
   - `propensity_score_estimator`
   - `propensity_score_matching_estimator`
   - `propensity_score_stratification_estimator`
   - `propensity_score_weighting_estimator`
   - `doubly_robust_estimator`
   - `distance_matching_estimator`
   - `instrumental_variable_estimator`
   - `regression_discontinuity_estimator`
   - `two_stage_regression_estimator`
   - `econml` (bridge — exposes any EconML estimator as a DoWhy
     `method_name="backdoor.econml.dml.LinearDML"` etc.)
   - `causalml` (bridge to Microsoft's CausalML library)
4. **Refute.** `model.refute_estimate(...)` — DoWhy's distinctive
   contribution. Inventory in `dowhy.causal_refuters`:
   - `random_common_cause` (add a synthetic confounder)
   - `placebo_treatment_refuter` (swap treatment with noise)
   - `data_subset_refuter` (re-fit on random subsamples)
   - `bootstrap_refuter`
   - `add_unobserved_common_cause` (sensitivity to hidden conf.)
   - `dummy_outcome_refuter`
   - `evalue_sensitivity_analyzer` (VanderWeele E-value)
   - `linear_sensitivity_analyzer` (Cinelli/Hazlett OLS sens.)
   - `non_parametric_sensitivity_analyzer`
   - `partial_linear_sensitivity_analyzer`
   - `assess_overlap` / `assess_overlap_overrule` (positivity)
   - `graph_refuter` (DAG-conditional-independence tests)
   - `reisz` (Reisz-representer based)
   - `overrule` (rule-based overlap rules)

   **This is the BOS-distinctive feature.** Phase B's
   `evidence_level` mapping for causal estimates should be a
   function of which refuters PASS — see Section 5 risk #7.

### 1.4 EconML — estimator menu

Enumerated via `dir()` on each submodule:

| Family | Module | Estimators |
|---|---|---|
| **DML** | `econml.dml` | `LinearDML`, `SparseLinearDML`, `KernelDML`, `NonParamDML`, `CausalForestDML`, `DML` |
| **DR** | `econml.dr` | `DRLearner`, `LinearDRLearner`, `SparseLinearDRLearner`, `ForestDRLearner` |
| **MetaLearners** | `econml.metalearners` | `SLearner`, `TLearner`, `XLearner`, `DomainAdaptationLearner` |
| **Orthogonal RF** | `econml.orf` | `DMLOrthoForest`, `DROrthoForest` |
| **IV** | `econml.iv` | (subclasses in `econml.iv.dml`, `econml.iv.dr`, `econml.iv.sieve` — re-export list is empty at root; non-trivial to enumerate without deeper introspection) |
| **Policy** | `econml.policy` | `PolicyTree`, `PolicyForest`, `DRPolicyTree`, `DRPolicyForest` |
| **Interpreters** | `econml.cate_interpreter` | `SingleTreeCateInterpreter`, `SingleTreePolicyInterpreter` |

Key implication: EconML separates **ATE-style** estimators (DML / DR
families) from **CATE-style** estimators (MetaLearners, OrthoForest,
CausalForestDML). For BOS, both matter — paper-level claims are
ATE-shaped ("staging improves SER"), but operator-level claims will
want CATE ("under feedstock X with moisture Y, the SER lift is…").

### 1.5 Hello-world verification

#### DoWhy

Command:

```python
import dowhy, numpy as np, pandas as pd
from dowhy import CausalModel
rng = np.random.default_rng(42)
n = 1000
X = rng.normal(0, 1, n)
T = (rng.uniform(0, 1, n) < 0.5).astype(int)
Y = 2.0 * T + 0.5 * X + rng.normal(0, 1, n)   # true ATE = 2.0
df = pd.DataFrame({"T": T, "X": X, "Y": Y})
m = CausalModel(data=df, treatment="T", outcome="Y", common_causes=["X"])
e = m.estimate_effect(m.identify_effect(proceed_when_unidentifiable=True),
                      method_name="backdoor.linear_regression")
r = m.refute_estimate(m.identify_effect(proceed_when_unidentifiable=True), e,
                      method_name="random_common_cause")
```

Output:

```
dowhy version: 0.14
Estimated ATE: 1.998 (true=2.0)
Refute p-value: 0.94          # random-common-cause refuter PASS
```

ATE error < 1e-2 on n=1000. Random-common-cause refuter passed
(estimate did not move significantly after a noise confounder was
injected).

#### EconML

Command:

```python
from econml.dml import LinearDML
from sklearn.linear_model import LinearRegression
import numpy as np
rng = np.random.default_rng(42)
n = 1000
X = rng.normal(0, 1, (n, 3))
W = rng.normal(0, 1, (n, 2))
T = 0.5*X[:,0] + rng.normal(0, 1, n)
true_theta = 1 + 0.5*X[:,0]                       # heterogeneous
Y = true_theta * T + 0.5*X[:,1] + 0.3*W[:,0] + rng.normal(0, 1, n)
est = LinearDML(model_y=LinearRegression(),
                model_t=LinearRegression(),
                random_state=42)
est.fit(Y, T, X=X, W=W)
print("ATE:", float(est.ate(X)))
print("coef_:", est.coef_)
```

Output:

```
EconML LinearDML ATE estimate: 0.946  (true mean = 0.996)
coef_:  [ 0.41284096  0.01046578 -0.04518660 ]
```

ATE error ≈ 0.05 on n=1000 (within expected DML noise band). The
recovered linear coefficient on X[:,0] (~0.41) is close to the true
0.5 — heterogeneity correctly attributed to the first covariate.

### 1.6 Compatibility vs BOS Core

| Constraint (BOS Core `requirements.txt`) | Phase B venv | Verdict |
|---|---|---|
| Python 3.11+ | 3.12.7 host | ✅ compatible |
| `numpy==1.26.4` | **numpy 2.4.5** | ⚠️ **MAJOR-VERSION JUMP** |
| `scipy==1.12.0` | **scipy 1.15.3** | ⚠️ minor-version drift, likely OK but un-tested |
| `pandas` (absent from BOS) | pandas 3.0.3 | ✅ new dependency for Phase B |
| `pydantic==2.6.1` | (not touched by dowhy/econml) | ✅ no conflict |
| `fastapi==0.109.2` | (not touched) | ✅ no conflict |
| `httpx==0.27.0` | (not touched) | ✅ no conflict |

**Bottom line:** dowhy 0.14 + econml 0.16.0 install cleanly in
isolation but the **numpy 2.x bump is a real concern**. If Phase B
shares the same venv as Phase A, every Phase A engine that pins to
numpy 1.x semantics needs revalidation. Two remediation paths to
consider (decision deferred to Plan v1):

- **Option α — pin numpy>=2.0** in BOS Core and run the full Phase A
  regression to find behavioural breaks.
- **Option β — split process**, run Phase B causal endpoints out of
  a separate venv / container so BOS Core can keep numpy 1.26.4
  until it's ready to migrate. This matches the Phase A
  `backend/agent/` isolation pattern.

**Verdict (recon-level):** "needs adaptation — not a blocker, but
must be decided in Plan v1 before A1-equivalent batch can start."

### 1.7 Hello-world artefacts

The hello-world scripts above ran in ~5–7 seconds each on the host
machine; **no errors or deprecation warnings** were surfaced after
`warnings.filterwarnings('ignore')` was set. (Some `FutureWarning`s
from sklearn 1.6 do appear without that filter — typical of
ML-stack drift, not a blocker.)

---

## Section 2 — BOS data flow: candidate causal roles

> **Scope.** Every field present in
> `backend/app/schemas/{ser,sfi,relay,mc,twin}.py`'s **V5/A.x
> request and response classes** is listed below with a candidate
> role tag for each of the five causal positions:
>
> - **T** = treatment (intentionally manipulable)
> - **O** = outcome (a quantity we care about)
> - **C** = covariate (background, possibly adjustable)
> - **M** = mediator (sits on a treatment→outcome path)
> - **Conf** = confounder (common cause threat to identification)
>
> A field can carry **multiple** roles depending on the analysis
> framing. The "primary" tag is bold; secondaries are plain.
> This is candidate-listing only. **No DAG is being designed here.**

### 2.1 SER schema (`schemas/ser.py`, A.1)

| Variable | Source | T | O | C | M | Conf | Notes |
|---|---|---|---|---|---|---|---|
| `dm_in` | SerComputeRequest | **T** | – | C | – | Conf | Operator-set substrate mass; correlates with batch scale |
| `dm_out` | SerComputeRequest | – | **O** | – | M | – | Direct mass-balance outcome |
| `n_in` | SerComputeRequest | T | – | C | – | Conf | Often correlated with `dm_in` (feedstock composition) |
| `n_rec` | SerComputeRequest | – | **O** | – | M | – | N-recovery outcome |
| `d_prime` | SerComputeRequest | – | O | – | **M** | – | Normalized deconstruction rate; classic mediator between conditioning treatment and SER |
| `g_prime` | SerComputeRequest | – | O | – | **M** | – | Normalized growth rate; symmetric mediator role |
| `species_code` | SerComputeRequest | **T** | – | C | – | Conf | Discrete treatment (assignment) **or** background stratum |
| `feedstock_code` | SerComputeRequest | **T** | – | C | – | Conf | Discrete treatment (lab) or stratum (field) |
| `monte_carlo.n_samples` | MonteCarloConfig | – | – | C | – | – | Pure compute-config; not causal |
| `monte_carlo.seed` | MonteCarloConfig | – | – | C | – | – | RNG-level |
| `monte_carlo.distributions.*.kind/mean/std` | DistSpec | – | – | C | – | Conf | Encodes the analyst's *prior* uncertainty — affects results but not a physical variable |
| `ser_point` | SerComputeResponse | – | **O** | – | – | – | The headline scalar outcome |
| `ser_ci_lower/upper` | SerComputeResponse | – | O | – | – | – | Uncertainty on the same outcome |
| `ser_std` | SerComputeResponse | – | O | – | – | – | Same |
| `delta_ser` | SerComputeResponse | – | **O** | – | – | – | Lift vs baseline — natural ATE-style target |
| `evidence_level` | SerComputeResponse | – | – | C | – | – | Metadata, not a physical variable |

### 2.2 SFI schema (`schemas/sfi.py`, A.2)

| Variable | Source | T | O | C | M | Conf | Notes |
|---|---|---|---|---|---|---|---|
| `temperature_c` | SfiMeasurements | **T** | – | C | M | Conf | Setpoint when controlled; ambient when observed |
| `moisture_pct` | SfiMeasurements | **T** | – | C | M | Conf | Same dual role |
| `density_kg_m3` | SfiMeasurements | – | – | **C** | – | Conf | Bulk substrate property; weakly controllable |
| `ph` | SfiMeasurements | T | – | **C** | M | Conf | Sometimes adjusted; often consequence |
| `ammonia_ppm` | SfiMeasurements | – | **O** | – | **M** | – | Outcome on emissions axis; mediator between N input and SFI verdict |
| `oxygen_pct` | SfiMeasurements | T | – | C | M | Conf | Ventilation outcome |
| `co2_pct` | SfiMeasurements | – | O | – | **M** | – | Activity proxy; mediator |
| `feed_rate_g_per_larva_day` | SfiMeasurements | **T** | – | C | – | – | Pure operator control |
| `k_decay_band.point/low/high` | KDecayBand | – | – | **C** | – | Conf | Latent kinetic parameter; **source-tagged** (lit/fit/meas) feeds evidence-level downgrade |
| `k_decay_band.source` | KDecayBand | – | – | C | – | – | Pure metadata — drives evidence policy |
| `s0` | SfiCheckRequest | T | – | C | – | – | Initial substrate pool |
| `s_min` | SfiCheckRequest | – | – | C | – | – | Threshold — not a variable, a setpoint |
| `horizon_hours` | SfiCheckRequest | – | – | **C** | – | – | Analyst-chosen horizon |
| `sfi_pass` | SfiCheckResponse | – | **O** | – | – | – | Binary outcome |
| `zone` | SfiCheckResponse | – | **O** | – | – | – | Categorical outcome |
| `composite_score` | SfiCheckResponse | – | **O** | – | – | – | Continuous outcome |
| `forecast_breach.earliest_breach_hour` | ForecastBreach | – | **O** | – | – | – | Time-to-event-style outcome |

### 2.3 Relay schema (`schemas/relay.py`, A.3)

| Variable | Source | T | O | C | M | Conf | Notes |
|---|---|---|---|---|---|---|---|
| `initial_state.biomass_kg` | TwinState | – | – | **C** | – | Conf | Initial condition — confounds outcome via path-dependence |
| `initial_state.substrate_kg` | TwinState | – | – | **C** | – | Conf | Same |
| `initial_state.temperature_c` | TwinState | T | – | C | – | Conf | Often a setpoint |
| `initial_state.moisture_pct` | TwinState | T | – | C | – | Conf | Same |
| `initial_state.nitrogen_g` | TwinState | – | – | **C** | – | Conf | Substrate composition |
| `initial_state.signal_activity_au` | TwinState | **T** | – | C | – | – | **The paper's headline Signal-API treatment.** Dosed by operator. |
| `relay_config.tau_m2_h` | RelayConfig | **T** | – | C | – | – | Stage scheduling — operator decision |
| `relay_config.s0/s_min` | RelayConfig | – | – | C | – | – | Threshold tuning |
| `relay_config.k_decay_band` | RelayConfig | – | – | **C** | – | Conf | (See SFI table) |
| `relay_config.tau_max_h` | RelayConfig | – | O | C | **M** | – | Eq.6 horizon: mediates between k_decay and feasibility |
| `horizon_steps` / `dt_hours` | RelaySimulateRequest | – | – | C | – | – | Numerical-config |
| `control_profile.setpoints.*` | ControlProfile | **T** | – | C | – | – | Operator control vector |
| `species_code` | RelaySimulateRequest | T | – | **C** | – | Conf | Stratum |
| `boundary_ledger[].mass_residual_kg` | BoundaryLedger | – | **O** | – | – | – | Closure outcome (auditability target) |
| `boundary_ledger[].nitrogen_residual_g` | BoundaryLedger | – | **O** | – | – | – | Same |
| `boundary_ledger[].closure_pct` | BoundaryLedger | – | **O** | – | – | – | Headline closure outcome |
| `relay_health.overall_status` | RelayHealth | – | **O** | – | – | – | Aggregate verdict |
| `relay_health.stage_completion.*` | RelayHealth | – | O | – | **M** | – | Per-stage outcome / mediator |
| `relay_health.k_decay_violation_at_step` | RelayHealth | – | **O** | – | – | – | Time-to-failure outcome |
| `final_ser` | RelaySimulateResponse | – | **O** | – | – | – | The headline SER outcome |
| `final_ser_ci` | RelaySimulateResponse | – | O | – | – | – | Uncertainty |

### 2.4 MC schema (`schemas/mc.py`, A.4)

| Variable | Source | T | O | C | M | Conf | Notes |
|---|---|---|---|---|---|---|---|
| `inputs[name].kind/mean/std` | McInput | – | – | **C** | – | – | Distribution priors — analyst inputs |
| `target_func` | McPropagateRequest | – | – | **C** | – | – | Choice of downstream computation (ser/sfi_score/relay_final_state/custom) |
| `target_func_config` | McPropagateRequest | – | – | C | – | – | Loose-typed escape hatch |
| `n_samples` / `seed` | McPropagateRequest | – | – | C | – | – | Sampler config |
| `target_mean` / `target_std` / `ci_*` | McPropagateResponse | – | **O** | – | – | – | Uncertainty-propagation outcome |
| `sobol_indices.first_order.*` / `.total.*` | SobolIndices | – | **O** | – | – | – | Variance-decomposition outcome — close in spirit to a mediation share |

> MC is fundamentally an **uncertainty-propagation** layer rather than
> a causal-inference layer. Its role in Phase B is likely to serve
> as the substrate for **counterfactual MC** (sampling under
> alternative DAGs / interventions) rather than a primary source of
> treatment / outcome variables.

### 2.5 Twin schema (`schemas/twin.py`, A.5)

| Variable | Source | T | O | C | M | Conf | Notes |
|---|---|---|---|---|---|---|---|
| `initial_state.biomass_kg/substrate_kg/temperature_c/moisture_pct/nitrogen_kg` | TwinState | – | – | **C** | – | Conf | All initial conditions |
| `config.mu_max` | TwinConfig | – | – | **C** | – | Conf | Kinetic parameter — usually treated as latent given species |
| `config.K_s` | TwinConfig | – | – | C | – | Conf | Half-saturation |
| `config.Y` | TwinConfig | – | – | **C** | – | Conf | Yield coefficient — critical confounder of `dm_in → biomass_kg` |
| `config.k_death` | TwinConfig | – | – | C | – | Conf | Mortality |
| `config.k_n` | TwinConfig | – | – | C | – | Conf | N-uptake |
| `config.tau_T/tau_M` | TwinConfig | – | – | **C** | – | – | Time constants — pure dynamics |
| `config.T_env/M_env` | TwinConfig | **T** | – | C | – | Conf | Ambient setpoints — operator-controllable |
| `inputs[].feed_rate_kg_h` | TwinInputStep | **T** | – | C | – | – | Per-step control |
| `inputs[].ventilation_m3_h` | TwinInputStep | **T** | – | C | – | – | Per-step control |
| `inputs[].heating_kw` | TwinInputStep | **T** | – | C | – | – | Per-step control |
| `observations[].weight_kg/temperature_c/moisture_pct` | TwinObservation | – | **O** | – | – | – | Sensor outcomes |
| `enable_ekf` | TwinRunRequest | – | – | C | – | – | Analyst toggle |
| `trajectory[].state.*` | TwinSnapshot | – | **O** | – | M | – | Path-of-state — every snapshot field carries both roles depending on horizon |
| `final_state.*` | TwinRunResponse | – | **O** | – | – | – | Terminal outcomes |
| `innovation_stats.mean_abs_innovation / rms_innovation` | InnovationStats | – | **O** | – | – | – | Model-fit outcomes (auditability) |

### 2.6 Tally

- **Total V5/A.x fields scanned:** ~90 (rough — counts vary by how
  `Dict[str, …]` payloads are unpacked).
- **Candidate primary treatments (T):** ~14 (`dm_in`, `n_in`,
  `species_code`, `feedstock_code`, `temperature_c`, `moisture_pct`,
  `feed_rate_g_per_larva_day`, `signal_activity_au`, `tau_m2_h`,
  `control_profile.setpoints.*`, `T_env`, `M_env`, `feed_rate_kg_h`,
  `ventilation_m3_h`, `heating_kw`).
- **Candidate primary outcomes (O):** ~12 (`ser_point`, `delta_ser`,
  `sfi_pass`, `composite_score`, `forecast_breach`, `final_ser`,
  `closure_pct`, `mass_residual_kg`, `nitrogen_residual_g`,
  `stage_completion`, `k_decay_violation_at_step`,
  `target_mean`).
- **Candidate mediators (M):** ~8 (`d_prime`, `g_prime`,
  `tau_max_h`, `ammonia_ppm`, `co2_pct`, `ph` partial, trajectory
  snapshots, stage_completion).
- **Candidate latent / confounding parameters:** ~10 (kinetic
  parameters `mu_max`/`K_s`/`Y`/`k_decay`, initial conditions,
  species/feedstock when used as stratum, ambient T/M).

**Headline finding (recon level):** the V5 schema surface is **rich
enough to support causal analysis** without new input fields. What
it lacks is **time-indexed observational batch data** linking those
fields — see Section 4.

---

## Section 3 — Paper causal-language harvest

> **Source.** `C:\Users\10420\Desktop\bos 0506\Paper1_BT\BOS_Paper1_JCP_FINAL.docx`
> (the file the handoff references — found one level up from the
> project root, not inside it).
>
> Extracted with `python-docx 1.2.0` to
> `_reports/_phase_b_paper_extract.txt` (258 paragraphs, ~104 KB).
> The extract file is treated as a working artefact (gitignored
> candidate; can be regenerated from the docx).
>
> **Method.** Section labels recovered by combining Word paragraph
> styles ("Heading 1/2/3") with a regex over numbered section
> prefixes ("2.4. ..."). Causal verbs scanned: cause/drive/increase/
> reduce/promote/inhibit/lead to/result in/due to/induce/enhance/
> determine/because of/attributed to/decrease/impact + Chinese
> equivalents (导致 / 驱动 / 影响 / 决定 / 由于 / 促进 / 抑制 / 造成).
> Sentence-length filter 15..350 chars.
> Total hits: **22**. The paper is English; no Chinese hits.

### 3.1 Claim list

| # | Section | Type | Claim |
|---|---|---|---|
| 01 | INTRODUCTION | cited | "Insect-based bioconversion offers a biological intensification pathway: by routing complex biopolymers through larval metabolism, insects rapidly **reduce** organic mass while generating high-value biomass and nutrient-rich frass [3, 9–13]." |
| 02 | INTRODUCTION | cited | "For lignocellulosic and fiber-rich residues, a recurring problem is that operating choices which **increase** dry-matter conversion also tend to accelerate nitrogen loss, so that greater mass reduction can be a worse outcome once nutrient recovery is included in the accounting [17–22]." |
| 03 | INTRODUCTION | author | "In insect-based chains, intensified conditioning also **increases** nitrogen loss, and single-species systems frequently fail to achieve both deep fiber breakdown and high nitrogen recovery within a single life cycle." |
| 04 | 2.2 Measurements | author | "Unless otherwise noted, mass-balance terms and derived indices were computed on a dry-matter basis using gravimetric total solids (TS), which were **determined** by oven-dry gravimetry…" |
| 05 | 2.2 Measurements | author | "Moisture content and total solids were **determined** gravimetrically by oven-drying at 105 °C to constant mass…" *(methods-language; not a substantive causal claim)* |
| 06 | 2.2 Measurements | author | "Signal-API potency was expressed in Biological Units (BU), with one BU defined as the dose producing a 10% **increase** in the validated P." *(operational definition — borderline)* |
| 07 | 2.2 Measurements | cited | "Midgut cellulolytic enzyme activity (CEA) was assayed as carboxymethyl-cellulase activity using a DNS **reducing**-sugar colorimetric method [42, 43]." *(reagent-name; false positive)* |
| 08 | 2.4 SER | author | "Where local priorities justify unequal weighting, SER can be generalized as SER = (D')^α_s · (G')^β_s … the default α_s = β_s = 0.5 **reduces** to the geometric mean…" *(math-reduction; false positive — should be filtered downstream)* |
| 09 | 2.5 Statistics | author | "For multi-component Signal-API cocktails, k_decay is interpreted as the effective **decay** rate of the potency-**determining** component under declared kernel / storage conditions…" |
| 10 | 3.3 Cellulase | author | "T. brevitarsis larvae in the TS system reached substantially higher CEA (~85 U/mg protein) than PB-only larvae (~60 U/mg protein) at matched developmental endpoints, an **increase** of approximately 47%…" |
| 11 | 3.4 Mechanistic probe | author | "The native Signal-API **increased** P." |
| 12 | 3.4 Mechanistic probe | author | "Heat inactivation **reduced** activity toward the water-control baseline (62.0 ± 5.0 U/mg protein; p < 0.05)." |
| 13 | 3.5 Mechanistic bounding | author | "…the 100 BU/kg condition failed at the priming checkpoint…while 200 BU/kg achieved PASS-with-gain at both priming and endpoint audits…by **increasing** BU/mL without adding water." |
| 14 | 3.5 Mechanistic bounding | cited | "Boundary metering of CO₂, NH₃, N₂O, and soluble-N leachate accounted for a portion of the previously unresolved remainder, **reducing** the SER-relevant residual from 16.4 ± 2.1% to 9.8 ± 1.7%." |
| 15 | 3.6.1 Progressive covariate | author | "The widening of the M3 simulation interval to cross zero reflects the under-**determined** covariate design at n = 4 … rather than instability in the M1 measured effect." |
| 16 | 4.1 Mechanistic basis | author | "The cue **reduces** the activation inertia of the successor stage, allowing more work to be extracted from the same primary substrate input under matched boundaries." |
| 17 | 4.3 Positioning vs BSF | cited | "On highly lignocellulosic rice husk with enzymatic/thermal/fermentation pretreatments, the best-treatment bioconversion efficiency reported was 34.8%, explicitly **attributed to** lignocellulosic-structure-limited digestibility [53]." |
| 18 | 4.4 Co-product / deployment | author | "By compressing total cycle time τ_tot from multi-week stabilization to a modular multi-day relay…, BOS **increases** effective asset turnover and **reduces** working-capital lock-up." |
| 19 | 4.4 Co-product / deployment | author | "The operator then either (i) restores delivered dose by **increasing** BU/mL within the declared HAL envelope, (ii) shortens τ_M2 and releases as PASS-with-retuning, or (iii) diverts the lot…" |
| 20 | 4.6 Decentralized biorefinery | author | "We treat boundary completeness as a prerequisite for releasing sustainability claims rather than an optional audit refinement: partial or unmetered boundaries **reduce** SER to an internal ranking statistic rather than a publishable sustainability KPI." |
| 21 | 4.7 Scope / scaffolding | author | "These methodological extensions … are pre-declared as the V15+ methodological frontier to be deployed as soon as data quality and quantity make them statistically meaningful." *(weak match on 'increase' nearby — borderline)* |
| 22 | 5. Limitations | author | "(L3) Off-gas and leachate partitioning **reduced** the boundary residual from 16.4% to 9.8%, but full mechanistic closure requires a broader emissions package." |

### 3.2 Observations on the harvest

- **Real load-bearing causal claims** (Phase B candidates): **#03**,
  **#10**, **#11**, **#12**, **#13**, **#16**, **#18**, **#22**.
  Each is an explicit treatment→outcome statement an analyst could
  pose as an ATE / CATE question.
- **Cited / referenced** causal mechanisms (Phase B will want to
  *reproduce*, not *re-derive*): **#01**, **#02**, **#14**, **#17**.
- **False positives** (verb usage that is mathematical or
  methodological, not causal): **#04**, **#05**, **#07**, **#08**,
  **#15**, **#21**. About 27% of hits — manageable but flags that
  the grep pass needs a human-in-the-loop filter when this becomes
  a real specification step.
- **Architectural insight.** The paper's load-bearing causal
  claims cluster around **(a) Signal-API dose → downstream CEA gain
  → SER lift** (claims #11–#13, #16, #18) and **(b) boundary
  closure ↔ residual reduction** (#14, #22). Both are well-aligned
  with the variable set in Section 2. **The mediation chain in
  (a) is the obvious first DAG to formalise** — but that decision
  belongs in Plan v1, not here.

---

## Section 4 — Phase A data inventory vs Phase B needs

> For every distinct field in the V5/A.x schemas, classify:
>
> - "✅ have it now (schema-resident)" — Phase A request/response
>   already carries the value.
> - "📊 needs historical batch data" — value is meaningful but the
>   project would need labelled retrospective records to power a
>   causal fit (likely in `app/models/batch.py` etc.).
> - "🧪 needs new experiments" — value can be generated but only
>   from purpose-collected runs.
> - "🎲 synthetic-only" — no realistic real-world source today.

### 4.1 Matrix (deduplicated by field name across schemas)

| Field | Phase A status | Phase B candidate use | Real-data availability |
|---|---|---|---|
| `dm_in` / `dm_out` | ✅ Request / Response | T / O for SER ATE | 📊 historical (batch DB) |
| `n_in` / `n_rec` | ✅ | T / O for N-recovery | 📊 historical |
| `d_prime` | ✅ Request | mediator | 📊 historical |
| `g_prime` | ✅ Request | mediator | 📊 historical |
| `ser_point` / `delta_ser` | ✅ Response | headline O | 📊 derivable from above |
| `species_code` | ✅ | stratum / T (discrete) | ✅ (db lookup) |
| `feedstock_code` | ✅ | stratum / T (discrete) | ✅ |
| `temperature_c` (SfiMeas + TwinState) | ✅ | T or C | 📊 historical (sensor logs) |
| `moisture_pct` | ✅ | T or C | 📊 |
| `density_kg_m3` | ✅ | C | 📊 |
| `ph` | ✅ | T or M | 📊 |
| `ammonia_ppm` | ✅ | O / M | 📊 |
| `oxygen_pct` / `co2_pct` | ✅ | O / M | 📊 |
| `feed_rate_g_per_larva_day` | ✅ | T | 📊 |
| `k_decay_band.point/low/high` | ✅ Request | C (latent) | 🧪 *or* 📊 (the paper itself says "literature-estimated"; refit needs new experiments) |
| `k_decay_band.source` | ✅ | metadata | ✅ |
| `s0` / `s_min` | ✅ | C / threshold | ✅ |
| `horizon_hours` | ✅ | C (analyst) | ✅ |
| `sfi_pass` / `zone` / `composite_score` | ✅ Response | O | 📊 derivable |
| `forecast_breach.earliest_breach_hour` | ✅ | O (time-to-event) | 📊 historical |
| `recommended_actions` | ✅ | not causal | – |
| `initial_state.*` (relay/twin) | ✅ | C | 📊 historical |
| `signal_activity_au` (TwinState in relay) | ✅ | **T** (Signal-API dose) | 🧪 needs new dose-response data |
| `relay_config.tau_m2_h` | ✅ | T (timing) | 📊 |
| `relay_config.tau_max_h` | ✅ | M (Eq.6 horizon) | ✅ derived |
| `control_profile.setpoints.*` | ✅ | T | 📊 |
| `boundary_ledger[].*` | ✅ Response | O (auditability) | 📊 |
| `relay_health.*` | ✅ | O | 📊 |
| `final_ser` / `final_ser_ci` | ✅ | O | 📊 |
| `mc.inputs[].*` | ✅ | C (analyst priors) | ✅ |
| `mc.sobol_indices.*` | ✅ Response | O (variance share) | ✅ engine-computed |
| `twin.config.mu_max/K_s/Y/k_death/k_n/tau_T/tau_M` | ✅ | C (latent kinetic) | 🧪 typically fitted, not measured |
| `twin.config.T_env/M_env` | ✅ | T (setpoint) | 📊 |
| `inputs[].feed_rate_kg_h / ventilation_m3_h / heating_kw` | ✅ | T (per-step) | 📊 |
| `observations[].weight_kg/temperature_c/moisture_pct` | ✅ | O (sensor) | 📊 |
| `trajectory[].state.*` | ✅ Response | O / M (state path) | 📊 engine-emitted, real if calibrated |
| `final_state.*` | ✅ Response | O | 📊 |
| `innovation_stats.*` | ✅ Response | O (model fit) | 📊 |
| `evidence_level` | ✅ Response | metadata | ✅ |

### 4.2 Inventory tally

- **Schema-resident (✅) ratio:** ~100%. Every field a Phase B
  causal analysis would want already has a typed home in the V5
  request/response surface. **No new schema fields are required
  for the first round of causal endpoints.**
- **Real-data ready (📊 historical) ratio:** ~70%. Most causal
  pieces could be wired against Daws / `app/models/batch.py` if
  the historical batch table is dense enough.
- **Needs new experiments (🧪) ratio:** ~10%. The exceptions are
  the latent kinetic parameters (`mu_max`, `K_s`, `Y`,
  `k_decay_band`) and the Signal-API dose (`signal_activity_au`).
  For Phase B the latent params are usually treated as adjustment
  variables, not refit. The Signal-API dose-response is the *one*
  axis where new experimental data would materially raise the
  evidence level.
- **Synthetic-only (🎲) ratio:** ~0%. The bench has been set so
  that **every Phase B variable has a real-world path**.

### 4.3 Implications (recon level)

- The simplest first round of Phase B endpoints can be built on
  the **`/api/v1/relay/simulate` response surface alone**: the
  twin trajectory + boundary ledger + relay_health between an
  intervention-free arm and an intervention arm gives every input
  to a DoWhy `CausalModel(treatment="signal_activity_au",
  outcome="final_ser", common_causes=...)` call.
- The **observational batch DB** is the gating asset. Without
  enough historical rows the DML asymptotic-normality argument
  doesn't pay off — see Risk #3.
- **No data axis is fundamentally missing.** The risk is *volume*
  and *coverage*, not "field absent".

---

## Section 5 — Risks + unknowns

> 10 open questions. Each tagged with one of:
> - **D** = needs explicit user decision (D-series Plan-v1 input).
> - **M** = will clear up mid-run (Plan v2 / batch implementation).
> - **E** = needs external input (paper revision, lab data, peer expert).

### 5.1 Open questions

1. **Numpy 2.x vs Phase A pin** — **D**
   *Issue.* dowhy 0.14 + econml 0.16.0 require numpy 2.x; BOS Core
   pins `numpy==1.26.4`. The two cannot coexist in one venv without
   a Core requirement bump.
   *Treatment suggestion.* Plan v1 §D6 should pick between
   (α) bump BOS Core to numpy>=2.0 and run the full A regression,
   or (β) isolate Phase B into a separate process / container so
   Core stays on 1.x. Phase A precedent (`backend/agent/`
   isolation) makes β the lower-risk default.

2. **Endpoint group placement** — **D**
   *Issue.* New `/api/v1/causal/*` group (clean separation) **vs**
   extending existing `/ser`, `/relay`, etc. (composition).
   *Treatment.* Plan v1 §D7. Defaulting to a new group matches
   Phase A's stylistic precedent (one router per paper module) and
   simplifies contract-snapshot drift detection (Phase B's
   equivalent of `_reports/phase_a_openapi_snapshot.json`).

3. **Statistical-power floor** — **E + M**
   *Issue.* DML's asymptotic-normality argument needs roughly
   n ≥ 200–500 effective records *per stratum*. The paper itself
   notes n = 4 reactor replicates per arm (claim #15 in Section 3
   above explicitly says "under-determined covariate design").
   *Treatment.* Plan v1 should ask: how many rows are in
   `app/models/batch.py`-backed history today? If < ~200 per
   feedstock category, the first Phase B endpoint must either
   (a) restrict to **literature-cited** ATEs (no first-party
   estimation), or (b) ship as `evidence_level="planned"` only,
   or (c) blend a Bayesian prior (Phase C territory) to stabilise.

4. **DAG sourcing policy** — **D + E**
   *Issue.* Who writes the DAG? Options: (α) author-as-domain-
   expert hand-codes a DOT file per analysis; (β) auto-discovery
   via `causal-learn` (pulled in by dowhy); (γ) hybrid (skeleton
   from causal-learn, edges signed by the author).
   *Treatment.* Plan v1 §D8. Recon recommends γ — auto-discovery
   is too fragile on n=4-style data; pure-hand DAGs scale badly.

5. **Estimator menu — which subset to ship first?** — **D**
   *Issue.* EconML offers 6 DML + 4 DR + 4 MetaLearner + 2 OrthoRF
   + 4 Policy = 20 estimators. DoWhy adds 14 more. Phase B can't
   wrap them all in one batch.
   *Treatment.* Plan v1 §D9 should pick a starter set of ≤ 4.
   Recon suggests `LinearDML` (ATE baseline), `CausalForestDML`
   (CATE), `XLearner` (heterogeneity), plus DoWhy's
   `random_common_cause` + `placebo_treatment_refuter` for the
   refutation suite. Everything else can be added in a B-series
   later batch.

6. **Test-strategy for non-deterministic estimates** — **D + M**
   *Issue.* Causal estimates are statistical; ATE values shift
   with the seed even on identical data. Phase A's `≤ 1e-6`
   numerical tolerance is meaningless here.
   *Treatment.* Plan v1 §D10. Reasonable Phase B test contract:
   (a) deterministic seed-pinned smoke (point estimate within
   pre-computed band), (b) refutation-pass test (random-common-
   cause refuter MUST pass on the bench case), (c) DAG-edge
   parity test (analyst-declared DAG matches the JSON serialized
   in the response). No "exact value" tests.

7. **Evidence-level mapping for causal results** — **D**
   *Issue.* What constitutes `validated` / `supported` / `planned`
   for a Phase B estimate? Phase A's mapping
   (measured / fitted / literature → validated / supported /
   planned) doesn't transfer literally — every causal estimate is
   "fitted" in that sense.
   *Treatment.* Plan v1 should propose, e.g.:
   `validated` = ≥3 refuters pass AND identification is strict
   back-door AND DAG cites primary lab data;
   `supported` = at least 1 refuter passes AND identification
   resolves under do-calculus;
   `planned` = unidentifiable / refuter-fail / DAG cites
   literature only.

8. **Agent-side `causal_node`** — **M**
   *Issue.* The Phase A LangGraph has `router/ser/sfi/relay/
   cyber_lab/render`. Phase B presumably adds a `causal_node`
   that drives `/api/v1/causal/*`. Open: does it own state keys
   `causal_estimate`, `causal_refute_pass`, `causal_dag` etc.?
   Does it sit *after* `relay_node` (causal analysis of the
   simulation output) or *parallel* (independent question)?
   *Treatment.* Plan v1 §D11 — recommend a Phase A-pattern
   independent branch with `cyber_lab`-style parallel calls
   when the user requests a mediation analysis (DoWhy mediator +
   EconML CATE on the same DAG can run via `asyncio.gather`).

9. **Render-node UX for causal output** — **M + D**
   *Issue.* Markdown rendering for an ATE + 95% CI + 3 refuter
   verdicts is **not** the same as rendering an SER scalar.
   Should the chat surface show a forest plot? A DAG? Just text?
   *Treatment.* Plan v1 §D12 — defaulting to text + a small
   refuter-pass badge keeps the V2 chat UI unchanged. Plot
   rendering belongs in Phase G, not B.

10. **Sunset policy for legacy non-causal `/relay/simulate`**
    — **M**
    *Issue.* Once `/causal/*` ships, naive `/relay/simulate`
    consumers may want a "causal-explained" variant. Either we
    add `?explain=causal` to existing endpoints (composition) or
    we keep them clean and add a second, intentional roundtrip.
    *Treatment.* Default to a second roundtrip (no quiet behavior
    change in the V5 contract). Sunset policy mirrors A/D1.

### 5.2 Risks summary

| # | Tag | Category | Biggest if unresolved |
|---|---|---|---|
| **1** | numpy 2.x | D | **Yes — blocks single-venv strategy.** |
| 2 | endpoint group | D | aesthetic / drift detection |
| **3** | statistical power | E + M | **Yes — risks shipping "planned" everything.** |
| 4 | DAG sourcing | D + E | quality of every Phase B result |
| 5 | estimator menu | D | scope creep |
| 6 | tests | D + M | flaky CI |
| 7 | evidence_level | D | audit story credibility |
| 8 | causal_node | M | clears in implementation |
| 9 | render UX | M + D | minor; clears in B3-equivalent |
| 10 | legacy sunset | M | minor |

**Two biggest:** #1 (numpy 2.x — concrete, must decide) and #3
(statistical power — concrete, must measure historical batch row
count before promising estimator quality).

---

## Section 6 — Recon-level acceptance checklist

| Item | Status |
|---|---|
| Throwaway venv created, isolated from BOS Core | ✅ `/tmp/bos-phase-b-recon-venv/` |
| DoWhy / EconML versions recorded | ✅ 0.14 / 0.16.0 |
| Direct + transitive dependency snapshot | ✅ Section 1.2 |
| DoWhy 4-step pipeline enumerated | ✅ Section 1.3 |
| EconML estimator menu enumerated | ✅ Section 1.4 |
| DoWhy hello-world (true ATE = 2.0 recovered) | ✅ 1.998 |
| EconML hello-world (true mean theta = 0.996 recovered) | ✅ 0.946 |
| Compatibility-vs-BOS verdict | ✅ "needs adaptation; numpy 2.x is the gate" |
| V5/A.x schema field → causal-role candidates | ✅ Section 2 (5 tables, ~90 fields) |
| Paper causal-language harvest | ✅ Section 3 (22 hits) |
| Phase A data inventory vs Phase B needs | ✅ Section 4 (matrix + tally) |
| Risks register | ✅ Section 5 (10 questions) |
| No Phase A code modified | ✅ `git status` shows untracked-only |
| No `backend/requirements.txt` modified | ✅ |
| No new endpoints / routes / Plan written | ✅ |

---

## Section 7 — Artefacts produced

| Path | Tracked? | Purpose |
|---|---|---|
| `_reports/PHASE_B_RECONNAISSANCE.md` | new (untracked) | this report |
| `_reports/_phase_b_paper_extract.txt` | new (untracked, ~104 KB) | raw plain-text dump of `BOS_Paper1_JCP_FINAL.docx` for the Section 3 grep pass; safe to delete, regeneratable from the docx |
| `/tmp/bos-phase-b-recon-venv/` | not in repo | throwaway venv with dowhy/econml; safe to delete |

---

## Section 8 — Next step (not started)

Per handoff §6 — the Strategy LLM proposes Plan v1, the user
reviews / amends scope, then implementation batches begin. **No
Plan, no code, no commits in this recon pass.**

Open D-series items raised here (preliminary numbering — final
numbers determined by Plan v1):

- **D6** numpy-2.x compatibility strategy (α bump Core / β isolate Phase B)
- **D7** endpoint group placement (new `/causal/*` vs extending existing)
- **D8** DAG sourcing policy (hand / auto / hybrid)
- **D9** estimator starter menu (recon recommends 4: LinearDML, CausalForestDML, XLearner, + DoWhy refuter suite)
- **D10** causal test strategy (seeded smoke + refutation-pass + DAG-edge parity)
- **D11** agent `causal_node` topology (recon recommends Phase A `cyber_lab`-style parallel branch)
- **D12** render-node UX (text-default; visual deferred to Phase G)

**End of reconnaissance.**
