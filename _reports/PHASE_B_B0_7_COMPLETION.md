# Phase B / B0.7 — Completion report

> **Batch.** B0.7 — DAG library generation (Plan v2 / D8 = γ implementation).
> **HEAD at start.** `4568ad7` (post B0.5).
> **HEAD at end.** to be committed with this report.
> **Date.** 2026-05-17.

## Summary

3 candidate DAGs generated from the paper (`BOS_Paper1_JCP_FINAL.docx`, SHA-256 `ba13a10f…`) and the Phase A V5 schemas. All three pass structural validation (no cycles, unique IDs, ≥1 treatment + ≥1 outcome). User ratified the 5 default decisions during review; small post-review edits applied to DAG 002 + DAG 003 land the user's choices in the JSON. DAG library is locked in for B2 fixture use.

## Files

```
_reports/PHASE_B_DAGS/
├── dag_001_ser_baseline.json                       (9 nodes, 12 edges)
├── dag_002_mediation_signal_kappa_ser.json         (8 nodes, 10 edges)
└── dag_003_relay_three_stage.json                  (10 nodes, 13 edges, 5 bos_field_ref + node_id_convention)

_reports/PHASE_B_B0_7_DAG_VALIDATION.md             (110 lines, auto-check report)
_reports/PHASE_B_B0_7_USER_REVIEW.md                (154 lines, user-review summary + Q1–Q5)
_reports/PHASE_B_B0_7_COMPLETION.md                 (this file)
```

## User decisions (Q1–Q5)

All five answered with the recommended default. Rationale captured below for the audit trail.

### Q1 — DAG 001 acceptance

**Decision.** Accept as-is (9 nodes, 12 edges; keep `n_in → n_rec` mass-conservation edge).

**Rationale.** DAG 001 is the strongest paper-anchored of the three; every edge is either an explicit Eq. 1–3 reference or a standard species/feedstock confounder. The `n_in → n_rec` edge is tautological in the limit (N is conserved on a matched boundary) but is also exactly what Eq. 2 states, so removing it would create a small inconsistency between DAG and paper. Faithfulness wins.

### Q2 — DAG 002 direct ADE edge

**Decision.** Keep the `signal_activity_au → d_prime` direct edge.

**Rationale.** Paper line 11 explicitly reports "~70% proportion mediated through κ", which implies a residual ~30% direct effect (ADE). A pure full-mediation DAG (ACME = 100%) would over-commit to the V14 in-silico claim. Keeping ADE preserves the decomposition the paper actually wrote down.

### Q3 — DAG 002 `cea_post_m2` schema strategy

**Decision.** Inline column (no Phase A schema change).

**Rationale.** Adding `cea_post_m2` to Phase A V5 schemas would bump SCHEMA_VERSION on `SerComputeRequest` and trigger an OpenAPI contract drift on Phase A's frozen snapshot. The inline-column path lets B2b's `/api/v1/causal/mediation` accept the value via `CausalData.inline` without touching Phase A's contract.

**JSON updates landed:**

```json
"cea_post_m2": {
  ...
  "source_schema": "(INLINE_COLUMN — provided via CausalData.inline ...)",
  "inline_column_name": "cea_post_m2",
  "unit": "U / mg protein",
  "expected_range": [0.0, 100.0]
}

"kappa": {
  ...
  "source_schema": "(COMPUTED — derived as cea_post_m2 / signal_activity_au ...)",
  "computation": "cea_post_m2 / signal_activity_au",
  "fallback": "inline_column 'kappa' if pre-computed"
}
```

### Q4 — DAG 003 naming convention (Option B = `bos_field_ref`)

**Decision.** Add `bos_field_ref` mapping to each synthetic-id node; document the time-indexed DSL at DAG top level.

**Rationale.** Causal-DAG IDs are graph-semantic ("biomass at M3 start"); schema fields are typed data carriers (`relay.TwinState.biomass_kg`). Option B keeps the DAG human-readable while preserving the mapping that B2a's `DagSpec` validator will use.

**JSON updates landed (5 nodes + 1 top-level convention):**

| Node | `bos_field_ref` |
|---|---|
| `k_decay_point` | `sfi.KDecayBand.point` |
| `signal_activity_au_terminal` | `relay.TwinSnapshot.state.signal_activity_au@step_at_m2_end` |
| `biomass_kg_m3` | `relay.TwinState.biomass_kg@step_at_m3_boundary` |
| `substrate_kg_m3` | `relay.TwinState.substrate_kg@step_at_m3_boundary` |
| `relay_health_status` | `relay.RelayHealth.overall_status` |

Plus top-level:

```json
"node_id_convention": "Causal-semantic IDs; see bos_field_ref for schema field mapping. Time-indexed via @step_at_<phase>_<position> DSL (e.g. @step_at_m3_boundary)."
```

**DSL spec (for B2a implementers).** A `bos_field_ref` value has form `<module>.<Class>.<field>` optionally suffixed with `@step_at_<phase>_<position>`, where:

- `<module>` ∈ `{ser, sfi, relay, mc, twin}` matching `app/schemas/*.py`.
- `<Class>` is a Pydantic model name in that module.
- `<field>` is a dotted attribute path (e.g. `state.signal_activity_au` for a nested field).
- `<phase>` ∈ `{m1, m2, m3}` and `<position>` ∈ `{start, end, boundary}` — selects a time step in a trajectory-typed field.

Strict at parse time; resolved by an indexer the B2a engine will provide.

### Q5 — Regression Discontinuity at τ_max

**Decision.** Defer to Phase-B-2 (keep Plan v2 D9 = α LinearDML MVP).

**Rationale.** RDD is statistically tighter than DML *at the discontinuity*, but it answers a different question (local average treatment effect at the threshold, not global ATE). Plan v2 D9 commits to one estimator well-shipped; adding RDD now would scope-creep into the "ship 3 sketchily" path the Plan v1 review explicitly rejected. DoWhy's `regression_discontinuity_estimator` is enum-reserved for Phase-B-2.

## B2 fixture usage guide

When B2a starts wiring `/api/v1/causal/{identify,estimate}` test fixtures, the three DAGs serve different roles:

| DAG | Use case in B2 | Estimator | Expected `evidence_level` on golden bench |
|---|---|---|---|
| **dag_001** | ATE smoke test (D10 axis 1). Simplest paper-aligned causal question; pure schema-resident variables. | LinearDML | `validated` once n ≥ 30 per stratum |
| **dag_002** | Mediation smoke test for B2b `/causal/mediation`. Requires `cea_post_m2` inline data plumbing. | EconML DML mediation (Farbmacher 2022) | `planned` until V14 wet-lab data lands; auto-clamp by `n_min_per_stratum` |
| **dag_003** | Multi-confounder + time-indexed test fixture; exercises `bos_field_ref` DSL resolution. | LinearDML | `supported` with synthetic relay-simulation training corpus |

## Workspace state

| File | Status |
|---|---|
| `_reports/PHASE_B_DAGS/dag_001_ser_baseline.json` | untracked (new) |
| `_reports/PHASE_B_DAGS/dag_002_mediation_signal_kappa_ser.json` | untracked (new + edited per Q3) |
| `_reports/PHASE_B_DAGS/dag_003_relay_three_stage.json` | untracked (new + edited per Q4) |
| `_reports/PHASE_B_B0_7_DAG_VALIDATION.md` | untracked (new) |
| `_reports/PHASE_B_B0_7_USER_REVIEW.md` | untracked (new) |
| `_reports/PHASE_B_B0_7_COMPLETION.md` | untracked (new) |

No source code touched. No `backend/requirements.txt` change. No Phase A schema bump.

## Validation re-check after edits

```
dag_001_ser_baseline.json:                 VALID, 9 nodes, 12 edges
dag_002_mediation_signal_kappa_ser.json:   VALID, 8 nodes, 10 edges
                                           cea_post_m2: +inline_column_name, +unit, +expected_range
                                           kappa: +computation, +fallback
dag_003_relay_three_stage.json:            VALID, 10 nodes, 13 edges
                                           5/5 bos_field_ref present
                                           node_id_convention top-level: ✓
```

All three remain syntactically valid JSON and structurally valid DAGs.

## Effort vs estimate

| Step | Estimate (task brief) | Actual |
|---|---|---|
| 1 — read paper + schemas | 30 min | ~5 min (re-used recon §3 extract + schema reads from earlier turns) |
| 2 — write 3 DAG JSON | 60–90 min | ~25 min |
| 3 — consistency check | 20 min | ~10 min |
| 4 — user review doc | 15 min | ~15 min |
| Post-review edits (Q3 + Q4 landed) | 25 min | ~10 min |
| Completion doc | 15 min | ~15 min |
| **Total** | **~2–3 h** | **~1.3 h** |

Beat estimate because the paper extract and schema contents were already in conversation context from earlier batches (B0.5 + reconnaissance).

## Next batch

**B1 — dependencies + numpy migration landing.** Unblocked. Will:

- Update `backend/requirements.txt` per B0.5 findings F1–F5 (numpy 2.x, scipy ≥1.13, pyarrow ≥16, aiosqlite, pydantic >=2.6 <3.0).
- Inline or document the Phase A agent deps decision (F4).
- Add `dowhy==0.14` + `econml==0.16.0` for the causal layer.
- Run full 925-test regression on the new venv. Acceptance: same as B0.3 baseline (754 PASS / 171 SKIP / 0 FAIL).

**End of B0.7 completion report.**
