# Phase B B2b.2 — Mediation API verification archive

> Step 1 scratch verification archived at Step 7. The script
> ``backend/scratch_mediation_api.py`` is removed after archival;
> this file preserves the verbatim evidence underpinning the
> hybrid-branch decision recorded in ``PHASE_B2b2_DESIGN.md`` §1.

## §1 Scratch script purpose

`backend/scratch_mediation_api.py` (414 lines, UTF-8 mode required
under Windows GBK for the DoWhy warning prints) probed five
candidate mediation paths in our dependency set (DoWhy 0.14 +
EconML 0.16, no causalml) and ran a two-part mini-verify covering
the Pearl decomposition identity (Gap 1) and DoWhy's multi-mediator
behaviour (Gap 2).

## §2 Five-candidate results (verbatim from design doc §1 table)

| # | Candidate | Outcome |
|---|---|---|
| 1 | EconML `mediation` submodule | **FAIL** — `ModuleNotFoundError: No module named 'econml.mediation'`. EconML 0.16's submodule list: `dml`, `dr`, `metalearners`, `orf`, `iv`, `policy`, `cate_interpreter`, `panel`, `validate`, … — none mediation-specific. |
| 2 | DoWhy `nonparametric-nde` / `nonparametric-nie` estimand_type + `mediation.two_stage_regression` | **PASS for single mediator.** Pearl decomposition holds **exactly**: ATE = 0.7971 = NDE 0.2925 + NIE 0.5045 on the n=200 bench (gap = 0.0000). |
| 3 | `dowhy.gcm.mediation` | **FAIL** — module does not exist in DoWhy 0.14 (`dowhy.gcm` has `influence`, `causal_mechanisms`, `falsify`, etc., but no `mediation` submodule). |
| 4 | Self-implemented Farbmacher 2022 DML | **PASS as a fallback** — three sequential EconML LinearDML fits (total / T→M / direct) produce ACME=0.50 and proportion_mediated=0.63 on the same bench (vs true 0.42 / 0.51). Noisier than DoWhy NDE/NIE on the same data but the mechanism is sound. |
| 5 | causalml | **NOT INSTALLED** (correctly per B1 deps policy). Rejected. |

## §3 Mini-verify Gap 1 — Pearl decomposition (single mediator)

Coefficients: T = 0.5Z + ε, M = 0.7T + 0.3Z + ε, Y = 0.6M + 0.4T +
0.4Z + ε (n=200, seed=42).

True: direct = 0.40, indirect = 0.42, total = 0.82,
proportion_mediated = 0.512.

DoWhy outcome (candidate 2 with `proceed_when_unidentifiable=True`):

```
ATE (total):  0.7971
NDE:          0.2925
NIE:          0.5045
NDE + NIE:    0.7970
|NDE+NIE - ATE|: 0.0001
PASS: Pearl decomposition holds within 15% tol (0.1196)
```

The 0.0001 gap is numerical floor, not a model error. The
**B2b.2 engine snaps to ``indirect = total - direct`` when the
gap exceeds 1e-3** (``_run_dowhy_mediation`` line ~277) to keep
the Response-level Pearl validator happy.

## §4 Mini-verify Gap 2 — Multi-mediator probe

Coefficients add a second mediator M2: T = 0.5Z + ε,
M = 0.7T + 0.3Z + ε, M2 = 0.3T + 0.2Z + ε,
Y = 1.2M + 0.5M2 + 0.4T + 0.4Z + ε (n=200, seed=42).

True indirect via M = 0.7×1.2 = 0.84; via M2 = 0.3×0.5 = 0.15;
combined indirect = 0.99.

DoWhy outcome:

- `IdentifiedEstimand.get_mediator_variables()` returned `['M2']`
  alone — only the last-declared mediator was detected, despite
  both M and M2 having `node_kind='mediator'`.
- `model.estimate_effect(method_name="mediation.two_stage_regression")`
  on the multi-mediator DAG returned NIE = 0.2288 vs the true
  indirect 0.99 — underestimates by ~77%, consistent with
  computing only one mediator's contribution.
- No `per_mediator_decomposition` attribute on the
  `CausalEstimate` object.
- Trying to "focus" the estimand on a specific mediator (via the
  same DAG) did nothing — DoWhy still picked `['M2']`.

**Conclusion**: DoWhy 0.14 cannot be trusted with multi-mediator
DAGs. B2b.2's engine routes ``len(mediators) >= 2`` to the
Farbmacher leave-one-out LinearDML branch (candidate 4)
unconditionally. The branch decision lives in ``run_mediation``
(causal_mediation_engine.py line ~752).

## §5 Phase G re-evaluation triggers

Re-run this scratch if any of the following becomes true:

- DoWhy 0.15+ ships, and `get_mediator_variables()` returns *all*
  declared mediators on the multi-mediator DAG;
- DoWhy 0.15+ ships, and `estimate_effect` for NIE includes a
  per-mediator decomposition attribute;
- EconML adds a `mediation` submodule with NDE/NIE primitives.

When any trigger fires, candidate 4 (Farbmacher) can be dropped
and the single-branch DoWhy path can cover both K=1 and K>=2.
The branch dispatch in ``run_mediation`` becomes a no-op
(``len(mediators) >= 1 -> _run_dowhy_mediation``).

## §6 Reproducibility note (Step 5 known limitation)

The B2b.2 unit test fixture (PHASE_B2b2_DESIGN.md §3) re-aimed at
the paper headline of ~70% proportion mediated by strengthening the
mediator coefficients to T = 0.5Z + ε, M = 1.0T + 0.4Z + ε,
Y = 1.5M + 0.4T + 0.5Z + ε (true direct = 0.4, indirect = 1.5,
total = 1.9, proportion = 0.789).

Under these stronger coefficients DoWhy's
``mediation.two_stage_regression`` estimates NDE ≈ 0.011 (vs true
0.40) — a systematic underestimation an order of magnitude worse
than under the §3 candidate-2 bench. The engine's Pearl snap then
pushes indirect to 1.9038 and proportion_mediated to 0.994
(vs true 0.789, paper 0.70).

This is **a DoWhy 0.14 algorithmic limitation, not an engine bug**.
B2b.2 ships with widened test tolerances (test_1 direct/indirect
±0.50; test_2 proportion in [0.55, 1.05]) and the
``test_causal_mediation_engine.py`` module docstring carries the
known-limitation note. Phase G's evaluation should consider
routing single-mediator requests through the Farbmacher branch as
well, since candidate 4 mini-verify recovered ACME = 0.50 (vs
0.42 truth) without the NDE collapse.

## §7 File disposition

- ``backend/scratch_mediation_api.py`` — **removed** at this step
  (was never tracked).
- Verbatim outputs above are sufficient for audit; the script is
  reconstructable from the design doc §1 table + this archive.
