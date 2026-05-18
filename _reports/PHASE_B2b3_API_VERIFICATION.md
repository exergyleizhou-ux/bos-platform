# Phase B B2b.3 — Sensitivity API verification archive

> Step 1 scratch verification archived at Step 7. The script
> ``backend/scratch_sensitivity_api.py`` is removed after archival;
> this file preserves the empirical evidence underpinning the
> three-branch design decision recorded in
> ``PHASE_B2b3_DESIGN.md`` §1, including the **late-arriving**
> probe outputs that resolved the DoWhy E-value API plumbing
> after the initial scratch run.

## §1 Scratch script purpose

``backend/scratch_sensitivity_api.py`` (336 lines, ASCII-only,
UTF-8 mode under Windows GBK) probed five candidate sensitivity
paths in our dep set (DoWhy 0.14 + EconML 0.16 + statsmodels +
sklearn; no PySensemakr per B1 deps lock). It also closed the
loop on a B2b.1 deferred item: the patch doc
``PHASE_B_PLAN_V2_PATCH_S2_3.md`` recorded that
``evalue_sensitivity_analyzer`` is not in DoWhy's
``model.refute_estimate(...)`` dispatch table but the standalone
class **module** exists. B2b.3 Step 1 verified the standalone
class API itself.

## §2 Five-candidate results

All probes run on a B2a-style backdoor bench (T -> Y with
confounder Z, n=200, seed=42, true ATE=2.0, OLS
`backdoor.linear_regression` estimate = 2.0308).

| # | Candidate | Outcome |
|---|---|---|
| 1 | DoWhy `EValueSensitivityAnalyzer` standalone class | **PASS.** Module `dowhy.causal_refuters.evalue_sensitivity_analyzer`. Class `EValueSensitivityAnalyzer`. Correct `__init__` kwargs: `estimate, estimand, data, treatment_name, outcome_name`. Methods: `check_sensitivity(data, plot=True)`, `get_evalue(coef_est, coef_se)`, `benchmark(data)`, `plot(...)`. Attrs after `check_sensitivity(data=df, plot=False)`: `stats={...}`, `benchmarking_results=...`, `sd_outcome`. |
| 2 | Self-implemented Chinn (2000) / VanderWeele-Ding 2017 E-value (via B2a `cheap_evalue`) | **PASS** as fallback. On the same bench: beta=2.0308, CI95%=[1.8906, 2.1710], std(Y)=2.6473. Point E-value = 3.4346; lower-CI-bound robust E-value = 3.2394. Both >1.5 threshold. |
| 3 | DoWhy `NonParametricSensitivityAnalyzer` | **PARTIAL.** Module + class exist; `__init__(*args, theta_s, plugin_reisz=False, **kwargs)` requires a keyword-only `theta_s` (a regression score function) not exposed by Plan v2 §2.5's `method='partial_linear'` field. Instantiation without `theta_s` raises `TypeError`. Reserved at engine layer (D9-style). |
| 4 | PySensemakr (Cinelli-Hazlett 2020 official Python lib) | **NOT INSTALLED** (correctly per B1 deps lock). Rejected. |
| 5 | Self-implemented Cinelli-Hazlett (closed-form RV + partial R^2 from a single OLS fit) | **PASS.** On the same bench: t=28.56, df_resid=197, partial f^2 = 4.14, RV(q=1) = 0.8326, RV_alpha(q=1, alpha=0.05) = 0.8180, partial R^2(Y, T \| Z) = 0.8055. Closed form from Cinelli-Hazlett 2020 Eq. 4. |

## §3 DoWhy E-value API verified plumbing (late-arrival probe)

The initial Step 1 scratch run reported Candidate 1 PASS at import
and class-instantiation, but the first set of method-introspection
probes raised on signature mismatches. A second probe run
(launched in-band, completed later) resolved the exact API:

```
check_sensitivity sig: (data: pandas.DataFrame, plot=True)
get_evalue sig:        (coef_est, coef_se)
benchmark sig:         (data: pandas.DataFrame)
```

After ``analyzer.check_sensitivity(data=df)``, ``analyzer.stats``
is populated with:

```python
{
    'converted_estimate':   2.0134,
    'converted_lower_ci':   1.9192,
    'converted_upper_ci':   2.1123,
    'evalue_estimate':      3.4419,   # <- E-value point
    'evalue_lower_ci':      3.2474,   # <- E-value robust (lower CI)
    'evalue_upper_ci':      None,     # one-sided here
}
```

**Two important plumbing facts** (codified in
`causal_sensitivity_engine.py::_run_evalue_primary_dowhy`):

1. `check_sensitivity` **returns `None`** and mutates the analyzer
   instance — the E-values live in `analyzer.stats` after the
   call, not in the return value.
2. `get_evalue(coef_est, coef_se)` is a static-style helper that
   takes coefficients directly; it is **not** the no-argument
   convenience method one might guess. The engine reads from
   `analyzer.stats['evalue_estimate']` and
   `analyzer.stats['evalue_lower_ci']` instead.

## §4 Numerical consistency: primary vs fallback

The two E-value implementations are numerically near-identical on
the strong-effect bench:

| Source | E-value point | E-value lower CI |
|---|---|---|
| DoWhy `EValueSensitivityAnalyzer` (Candidate 1) | 3.4419 | 3.2474 |
| Self-implemented Chinn-VWD (Candidate 2 / B2a `cheap_evalue`) | 3.4346 | 3.2394 |
| Δ | 0.0073 (0.21%) | 0.0080 (0.25%) |

Sub-1% agreement validates the delta-style fallback: when DoWhy
0.14 raises an exception on a future request, the engine falls
back without producing materially different bounds. The fallback
always emits a `method_fallback` warning so the audit trail is
preserved.

## §5 Cinelli-Hazlett closed-form sanity

The engine's `_robustness_value` and `_partial_r2_from_t` helpers
were unit-checked against the Step 1 scratch numbers and reproduce
them exactly:

```
_robustness_value(28.56, 197) = 0.8326   (scratch saw 0.8326) PASS
_partial_r2_from_t(28.56, 197) = 0.8055  (scratch saw 0.8055) PASS
```

This anchors the test-side baseline in
`test_sensitivity_linear_recovers_rv` (asserts within 0.05 of 0.8326).

## §6 Phase G re-evaluation triggers

Documented inline in design doc §9; reproduced here for archival
self-containment:

1. **DoWhy 0.15+ exposes `theta_s` from a schema-friendly param block**
   -> drop `partial_linear` 422 gate; route through
   `NonParametricSensitivityAnalyzer` (Candidate 3).
2. **`check_sensitivity()` API change in DoWhy 0.15+** -> revisit
   the kwarg-name plumbing; the broad-`Exception` fallback handles
   this gracefully but a Phase G clean-up should tighten.
3. **Deps lock loosens** -> evaluate PySensemakr (Candidate 4)
   numerical-equivalence swap for the `linear` branch.
4. **BSF real data exhibits sensitivity-bound divergence** between
   the cheap (`/estimate.e_value_cheap`) and expensive
   (`/sensitivity`) E-value computations beyond 10% -> add a
   numerical-divergence warning.

## §7 File disposition

- ``backend/scratch_sensitivity_api.py`` — **removed** at this step
  (was never tracked).
- Verbatim outputs above are sufficient for audit; the script is
  reconstructable from the design doc §1 table + this archive.
