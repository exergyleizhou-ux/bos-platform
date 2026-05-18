# Plan v2 §2.3 — patch record

> Filed during B2b.1 Step 1 (design phase, no code).
> Trigger: DoWhy 0.14 API verification.

## §1 Background

Plan v2 §2.3 (the `/api/v1/causal/refute` spec) listed **five**
mandatory refuters:

1. `random_common_cause`
2. `placebo_treatment_refuter`
3. `data_subset_refuter`
4. `add_unobserved_common_cause`
5. **`evalue_sensitivity_analyzer`** ← problematic

`backend/scratch_refute_api.py` (kept in tree for B2b.1
implementation reference; deleted at B2b.1 commit) verified all
five against the B2a backdoor bench (T / Y / Z, n=80, seed=42).
Result for #5:

```
REFUTER: evalue_sensitivity_analyzer
  RAISED: ImportError: evalue_sensitivity_analyzer is not an existing causal refuter.
    ...site-packages/dowhy/causal_refuters/__init__.py:29  get_class_object
```

E-value sensitivity analysis exists in DoWhy 0.14 as a standalone
class (`dowhy.causal_refuters.evalue_sensitivity_analyzer`
module), but it is **not dispatched** by
`model.refute_estimate(method_name=...)`. The `causal_refuters`
package's dispatch table excludes it.

## §2 Revision

| Refuter | Plan v2 (before) | Plan v2 (after, this patch) |
|---|---|---|
| `random_common_cause` | mandatory | mandatory |
| `placebo_treatment_refuter` | mandatory | mandatory |
| `data_subset_refuter` | mandatory | mandatory |
| `add_unobserved_common_cause` | mandatory | mandatory |
| `evalue_sensitivity_analyzer` | mandatory | **moved to `/api/v1/causal/sensitivity` (B2b.3)** |
| `bootstrap_refuter` | optional | optional, **implemented** in B2b.1 (API verified equivalent) |
| `non_parametric_sensitivity_analyzer` | optional | optional, **reserved** in B2b.1 (schema enum accepts; engine raises HTTP 422 `code='refuter_reserved'`) |

Net: `/refute` mandatory count **5 → 4**.

## §3 Semantic rationale

E-value (VanderWeele-Ding 2017) is a **sensitivity analysis**: it
asks *"how strong would unmeasured confounding need to be to
overturn the estimate?"*. It does not perform a Monte-Carlo
counterfactual simulation. Folding it under `/refute` was a
categorisation error in Plan v2.

The natural endpoint for E-value is `/api/v1/causal/sensitivity`
(B2b.3), which will also host:

- Linear sensitivity (Cinelli-Hazlett OLS bound)
- `non_parametric_sensitivity_analyzer` (DoWhy's
  Reisz-representer-based bound; deferred from B2b.1's reserved
  list at Phase G if useful)

`/refute` becomes a clean **simulation-based** check; `/sensitivity`
becomes a clean **bound-based** check.

## §4 Evidence-level rule revision

Plan v2 §2.3's three-tier rule referenced **5 mandatory + backdoor
+ e_value > 1.5**. With the patch, the rule becomes:

```
validated:
    4 mandatory refuters all pass (p > 0.10)
    AND identify.strategy == "backdoor"
    AND estimate.e_value_cheap > 1.5

supported:
    >= 2/4 mandatory refuters pass (p > 0.05)
    AND identify.strategy in {"backdoor", "frontdoor", "mediation"}

planned:
    otherwise
```

`e_value_cheap` is sourced from the preceding `/estimate` response
(carried through to `/refute` via the optional
`original_e_value` request field — see
`PHASE_B2b1_DESIGN.md §10`).

## §5 Scope and impact

| Surface | Impact |
|---|---|
| Plan v2 §2.3 file | This patch document is referenced; the v2 PLAN.md is **not** edited in place. Audit trail: PLAN v2 → patch doc → B2b.1 design doc → implementation |
| B2b.1 implementation | Implements 4 mandatory + 1 optional (bootstrap), 1 reserved (non_parametric_sensitivity_analyzer). evalue removed from this batch |
| B2b.3 `/sensitivity` | Will host E-value + linear (Cinelli-Hazlett) + non-parametric. The reserved enum value moves at B2b.3 time |
| Phase B endpoint count | Unchanged — 5 endpoints (identify, estimate, refute, mediation, sensitivity) |
| Plan v2 §7 acceptance #4 | Refutation-honesty test must update: from "all 5 mandatory pass p > 0.10" to "all 4 mandatory pass p > 0.10". Will be reflected in B5 acceptance test |

## §6 Audit chain

- **Where this decision lives**: `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md` (this file)
- **Why**: empirical scratch verification (`backend/scratch_refute_api.py`)
- **Cross-references**: `PHASE_B2b1_DESIGN.md §1, §10, §13`; B2b.1 implementation commit message will cite this patch
- **Plan v2 itself stays as it was**: no in-place edits. Patches
  accumulate as separate audit-traceable docs.

**End of patch record.**
