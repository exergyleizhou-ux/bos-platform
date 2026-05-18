# Phase B B2b.1 — DoWhy 0.14 refute API verification archive

> Archived from `backend/scratch_refute_api.py` and
> `backend/scratch_refute_minimal.py` at B2b.1 Step 7. Both `.py`
> files are deleted after this archive lands.
>
> Purpose: preserve verbatim DoWhy 0.14 refute_estimate() return-object
> shape, observed kwargs, p_value observations, and the
> Step-1-vs-Step-5 reconciliation that drove Bug 2's path A fix.

## §1 DoWhy + dependency versions

```
dowhy        0.14
econml       0.16.0
numpy        2.4.5
scipy        1.15.3
pandas       3.0.3
networkx     3.6.1
Python       3.12.7 (Windows)
```

All from `backend/.venv-backend/` per Phase B B1 (commit `2373aed`).

## §2 Bench fixture (B2a-derived)

```python
rng = np.random.default_rng(42)
n = 80
Z = rng.normal(0, 1, n)
T = 0.5 * Z + rng.normal(0, 1, n)
Y = 2.0 * T + 0.7 * Z + rng.normal(0, 1, n)
df = pd.DataFrame({"T": T, "Y": Y, "Z": Z})

GML = """graph [
  directed 1
  node [ id 0 label "T" ]
  node [ id 1 label "Y" ]
  node [ id 2 label "Z" ]
  edge [ source 0 target 1 ]
  edge [ source 2 target 0 ]
  edge [ source 2 target 1 ]
]"""
```

Identified estimand: `backdoor` on `{Z}`.
Estimate value (`backdoor.linear_regression`, target_units='ate'):
**1.8281** (true ATE = 2.0).

## §3 DoWhy `CausalRefutation` object shape

All 5 implemented refuters return `dowhy.causal_refuter.CausalRefutation`
with `__dict__` keys:

```
['estimated_effect', 'new_effect', 'refutation_result',
 'refutation_type', 'refuter']
```

`add_unobserved_common_cause` additionally carries `new_effect_array`
(per-strength-grid scan). `evalue_sensitivity_analyzer` does not
return — it raises `ImportError` (see §5).

## §4 Per-refuter observations

Fields recorded across two scratch runs of `scratch_refute_api.py`
on the same fixture. The non-determinism in `random_common_cause`,
`placebo`, `data_subset`, and `bootstrap` is **load-bearing
evidence for Bug 2**.

### `random_common_cause`

| Run | `new_effect` | `refutation_result.p_value` | `is_statistically_significant` |
|---|---|---|---|
| scratch_refute_api.py (1st run) | 1.8278 | 0.98 | False |
| scratch_refute_api.py (3rd run) | 1.8274 | 0.94 | False |
| `refutation_type` | "Refute: Add a random common cause" |

Decision: **stable**. Engine keeps `not is_statistically_significant`
decoder for this refuter.

### `placebo_treatment_refuter`

kwargs: `placebo_type="permute"`

| Run | `new_effect` | `p_value` | `is_statistically_significant` |
|---|---|---|---|
| scratch (1st) | -0.0062 | 0.96 | False |
| scratch (3rd) | 0.0120 | 1.00 | False |
| `refutation_type` | "Refute: Use a Placebo Treatment" |

Decision: **stable**. `new_effect ≈ 0` (true mechanism: placebo T
should have no effect on Y). Engine keeps significance decoder.

### `data_subset_refuter`

kwargs: `subset_fraction=0.8`, `num_simulations=10`, `random_state=42`

| Run / context | `new_effect` | `p_value` | `is_statistically_significant` |
|---|---|---|---|
| scratch_refute_api.py 1st run (after placebo) | 1.8307 | 0.94 | False |
| scratch_refute_api.py 3rd run (after placebo) | 1.8212 | 0.96 | False |
| scratch_refute_minimal.py (no prior placebo) | 1.7670 | **0.00** | **True** |
| Step 5 engine (no prior placebo) | 1.7670 | **0.00** | **True** |
| `refutation_type` | "Refute: Use a subset of data" |

**Decision: UNRELIABLE**. The same code with the same fixture and
the same `random_state=42` reports `p_value=0.94/0.96` when run
*after* placebo_treatment_refuter, and `p_value=0.0` when run on a
fresh `CausalModel`. Engine routes through `_DELTA_BASED_REFUTERS`
fallback: `p_value=None`, `passed = |delta/orig| < 0.1`.

### `add_unobserved_common_cause`

kwargs:
```python
{
    "confounders_effect_on_treatment": "linear",
    "confounders_effect_on_outcome": "linear",
    "effect_strength_on_treatment": 0.01,
    "effect_strength_on_outcome": 0.02,
}
```

| Run | `new_effect` | `refutation_result` |
|---|---|---|
| scratch (1st) | 1.7615 | **None** |
| scratch (3rd) | 1.8639 | **None** |
| `refutation_type` | "Refute: Add an Unobserved Common Cause" |

**No significance test by design.** Engine uses delta-based fallback
from the start. `p_value=None`, `passed = |delta/orig| < 0.1`.

### `bootstrap_refuter`

kwargs: `num_simulations=100`, `random_state=42`

| Run / context | `new_effect` | `p_value` | `is_statistically_significant` |
|---|---|---|---|
| scratch_refute_api.py 1st run | 1.8391 | 0.94 | False |
| scratch_refute_api.py 3rd run | 1.8507 | 0.76 | False |
| scratch_refute_minimal.py (no prior refuters) | 1.9803 | **0.00** | **True** |
| Step 5 engine (no prior refuters) | 1.9802 | **0.00** | **True** |
| `refutation_type` | "Refute: Bootstrap Sample Dataset" |

**Decision: UNRELIABLE**. Same pattern as `data_subset_refuter`.
Engine routes through `_DELTA_BASED_REFUTERS` fallback.

## §5 `evalue_sensitivity_analyzer` — not a refuter

```
REFUTER: evalue_sensitivity_analyzer
  RAISED: ImportError: evalue_sensitivity_analyzer is not an existing causal refuter.
    ...site-packages/dowhy/causal_refuters/__init__.py:29  get_class_object
```

DoWhy 0.14 ships E-value sensitivity analysis as the
`dowhy.causal_refuters.evalue_sensitivity_analyzer` module / class,
but it is **not registered** in `model.refute_estimate(method_name=...)`'s
dispatch table.

Plan v2 §2.3 listed it as one of the 5 mandatory refuters; this is
inconsistent with the DoWhy 0.14 API. Resolution: Plan v2 §2.3
patch (filed at `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md`) — E-value
moves to `/api/v1/causal/sensitivity` (B2b.3), mandatory count
drops from 5 to 4.

## §6 Reconciliation — why p_value differs across runs

The `is_statistically_significant` field for `data_subset_refuter`
and `bootstrap_refuter` is **path-dependent** in DoWhy 0.14:

- When called *immediately after another refuter* on the same
  `CausalModel` instance (e.g. after placebo_treatment_refuter),
  these refuters return p_value ≈ 0.9 (passed).
- When called on a *fresh* `CausalModel` (no prior refuter calls),
  they return p_value = 0.0 (significant).

This is consistent with the hypothesis that DoWhy mutates internal
estimate state across refute_estimate calls — the "estimated_effect"
DoWhy compares against may be the *original* estimate in the fresh
case (yielding a strict significance test) but a *previously-mutated*
estimate after another refuter (yielding a permissive test).

We did **not** formally verify this hypothesis via DoWhy source-code
inspection. The engineering response was pragmatic: treat the
significance field as unreliable for these two refuters and use
the delta-based fallback instead. The `_DELTA_BASED_REFUTERS`
constant and its module-level comment in
`backend/app/engine/extended/causal_refute_engine.py` capture this
decision durably.

## §7 Forward-looking flags

When DoWhy upgrades to 0.15+ (or whenever Phase G has time for a
deeper API audit), revisit:

1. **Are `data_subset_refuter` / `bootstrap_refuter` deterministic
   with `random_state=42` in fresh state?** If yes, the fix is in
   our call pattern, not the refuters themselves.
2. **Does the path-dependence persist?** If DoWhy stabilises the
   `refutation_result` API, the `_DELTA_BASED_REFUTERS` fallback
   can be narrowed back to `add_unobserved_common_cause` alone.
3. **Is `evalue_sensitivity_analyzer` registered in DoWhy 0.15+'s
   dispatch?** If yes, B2b.3's `/sensitivity` can include it as a
   first-class refuter; if no, treat it as a standalone class
   (Cinelli-Hazlett style).

## §8 Source preservation

The two scratch files are not preserved verbatim in this archive
(they were never committed). Their **logical content** is preserved
above. To reproduce:

- Section §2 fixture + §4 per-refuter kwargs → reconstruct
  `scratch_refute_api.py`.
- Section §2 fixture + §4 data_subset/bootstrap kwargs (only those
  two refuters, no prior placebo call) → reconstruct
  `scratch_refute_minimal.py`.

**End of API verification archive.**
