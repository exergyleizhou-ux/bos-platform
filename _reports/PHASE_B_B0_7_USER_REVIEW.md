# Phase B / B0.7 — DAG library user-review summary

> 3 candidate DAGs ready for user approval. After approval the DAG
> library locks in for B2 fixture use. Generated 2026-05-17.

## Files

```
_reports/PHASE_B_DAGS/
├── dag_001_ser_baseline.json                       (9 nodes, 12 edges)
├── dag_002_mediation_signal_kappa_ser.json         (8 nodes, 10 edges)
└── dag_003_relay_three_stage.json                  (10 nodes, 13 edges)
```

Plus validation: `_reports/PHASE_B_B0_7_DAG_VALIDATION.md`.

---

## DAG 001 — SER baseline causal chain

- **Question it answers.** *"Given an operator-set substrate-mass and nitrogen-mass policy, what is the average causal effect on SER, with D′ and G′ as the natural mediators? When D′ rises by 0.1, what is the implied SER lift along Eq. 3?"*
- **Paper grounding.** Direct operationalisation of Eq. 1–3 (paper lines 36, 39, 43). Every edge is either a paper equation or a standard species/feedstock confounder.
- **Nodes (9).** `dm_in`, `n_in`, `species_code`, `feedstock_code`, `dm_out`, `n_rec`, `d_prime`, `g_prime`, `ser_point`.
- **Edges (12).** 7 paper Eq-ref + 4 domain-confounding + 1 mechanical (`n_in → n_rec`).
- **Recommended estimator.** LinearDML.
- **Identifiability.** Back-door adjustment on `{species_code, feedstock_code}`.
- **Risk.** None worth blocking on. The `n_in → n_rec` edge is tautological (N conservation) and may be removed if you want a tighter DAG; keeping it is more faithful to Eq. 2.

✅ **Recommendation: accept as starter DAG for B2 fixtures.**

---

## DAG 002 — Mediation chain: Signal-API → κ → SER

- **Question it answers.** *"Of the total Signal-API effect on SER, how much is mediated through Kernel compilation efficiency κ vs. how much is the direct effect (ADE)? Paper's pre-registered claim: ~70% mediated."*
- **Paper grounding.** Load-bearing paper claim (lines 11, 49–50, 101, 153). Pearl–Rubin counterfactual framework. ACME + ADE decomposition. EconML DML mediation per D14 = γ.
- **Nodes (8).** `signal_activity_au`, `tau_m2_h`, `k_decay_point`, `cea_post_m2`, `kappa`, `d_prime`, `g_prime`, `ser_point`.
- **Edges (10).** 1 verbatim + 5 paper-Eq-ref + 4 implicit (kappa → outcomes, ADE direct).
- **Recommended estimator.** EconML DML mediation (D14 = γ). For the marginal ATE the same data supports LinearDML.

### ⚠️ Risk — Phase A schema gap

Two of the nodes do **not** exist in Phase A V5 schemas:

| Node | Status | B2b implication |
|---|---|---|
| `cea_post_m2` | NOT IN PHASE A | The `/api/v1/causal/mediation` endpoint must accept this as an inline data column in `CausalData`. |
| `kappa` | Computed quantity (Eq. 4) | Either inline-provided or server-side derived from `cea_post_m2 / signal_activity_au`. |

This is **the** load-bearing decision for B2b — the schema gap is real and the user should be aware before B1 finalises the requirements.

### Decision point — direct ADE edge

The DAG includes an explicit `signal_activity_au → d_prime` direct edge (the ADE channel; ~30% of total effect per paper line 11). Two options:

- **Default (recommended)**: keep the direct edge. ACME = ~70%, ADE = ~30%, total = 100%.
- **Pure full-mediation**: delete the direct edge. Forces ACME = 100%; suitable if you believe the paper's claim is *only* through κ.

❓ **User decision: keep direct ADE edge, or remove for pure full-mediation?**

---

## DAG 003 — Relay simulation causal chain (M1 → M2 → M3)

- **Question it answers.** *"What is the average causal effect of M2 residence time τ_m2_h on final_SER, controlling for k_decay and species? When τ_m2_h approaches τ_max_h, how sharply does relay_health flip from 'nominal' to 'failed'?"*
- **Paper grounding.** Eq. 5–6 (`S(τ) = S₀·exp(−k_decay·τ)`, `τ_M2 ≤ ln(S₀/S_min)/k_decay`). Paper §4.1 mechanistic-basis discussion.
- **Nodes (10).** `tau_m2_h`, `s0`, `k_decay_point`, `tau_max_h`, `signal_activity_au_terminal`, `biomass_kg_m3`, `substrate_kg_m3`, `species_code`, `final_ser`, `relay_health_status`.
- **Edges (13).** 1 verbatim + 5 paper-Eq-ref + 4 domain + 3 implicit.
- **Recommended estimator.** LinearDML for main effect. **Regression Discontinuity** at `τ_max_h` is a candidate for Phase-B-2 (deferred; DoWhy `regression_discontinuity_estimator`).

### ⚠️ Naming-convention gap

Five nodes use *synthetic time-indexed IDs* that don't match Phase A schema field names literally:

| DAG node ID | Real schema location |
|---|---|
| `k_decay_point` | `sfi.KDecayBand.point` |
| `signal_activity_au_terminal` | `relay.TwinSnapshot.state.signal_activity_au` (final step) |
| `biomass_kg_m3` | `relay.TwinState.biomass_kg` (at M3 boundary) |
| `substrate_kg_m3` | `relay.TwinState.substrate_kg` (at M3 boundary) |
| `relay_health_status` | `relay.RelayHealth.overall_status` |

❓ **User decision: pick a naming convention.**

- **Option A** — rename DAG nodes to schema-literal (e.g. `k_decay_point` → `kdecayband_point`). Less readable in causal-DAG context.
- **Option B (recommended)** — add `bos_field_ref` lookup field on each `DagNode` (already exists in Plan v2 §2.6's `DagNode` Pydantic schema). E.g. `bos_field_ref: "relay.TwinState.biomass_kg@step_at_m3_boundary"`. Time-indexed refs would need a tiny DSL definition.

---

## Cross-DAG decision points (user action)

For each, tick one:

### Q1. DAG 001 acceptance

- [ ] Accept DAG 001 as-is (9 nodes, 12 edges).
- [ ] Accept with edits: remove `n_in → n_rec` tautological edge (8 nodes / 11 edges).
- [ ] Reject — redesign needed (specify direction).

### Q2. DAG 002 acceptance + direct-ADE-edge

- [ ] Accept DAG 002 as-is, **keep** direct ADE edge (ACME ≈70%, ADE ≈30%).
- [ ] Accept DAG 002, **remove** direct ADE edge (pure full-mediation model).
- [ ] Reject — redesign needed.

### Q3. DAG 002 schema gap acknowledgement

DAG 002 requires `cea_post_m2` data plumbing that doesn't exist in Phase A schemas. B2b's `/api/v1/causal/mediation` endpoint must accept it as an inline column.

- [ ] Acknowledge — B2b will plumb the data inline (no Phase A schema change).
- [ ] Acknowledge — B2b will add new Phase A V5 fields (`SerComputeRequest.cea_post_m2`, etc.). Adds Phase A schema-version bump.
- [ ] Block until paper provides wet-lab `cea_post_m2` data.

### Q4. DAG 003 acceptance + naming convention

- [ ] Accept DAG 003 as-is, use **Option B** (`bos_field_ref` mapping; recommended).
- [ ] Accept DAG 003, use **Option A** (rename node IDs to schema-literal).
- [ ] Reject — redesign needed.

### Q5. Regression Discontinuity at τ_max (DAG 003)

The discontinuity at `τ_max_h` is a Regression Discontinuity candidate.

- [ ] Defer to Phase-B-2 (Plan v2 default; D9 = α LinearDML only).
- [ ] Bring forward to Phase B core (add RDD estimator to D9 menu).

---

## Cross-cutting concerns

### Small-sample warnings (apply to all 3)

Paper experiment has n=4 / arm. Per Plan v2 §6 R2 branched mitigation: **the auto-clamp rule `n < n_min_per_stratum (default 30) → evidence_level="planned"` applies to all 3 DAGs**.

DAG 001 is the only one likely to reach `evidence_level="validated"` with a moderately-sized historical batch corpus (because dm_in / n_in / species / feedstock have many real observations). DAG 002 stays at `"planned"` until wet-lab `cea_post_m2` data lands. DAG 003 reaches `"supported"` if multiple `tau_m2_h` values exist in the relay-simulation training corpus.

### Estimator alignment with D9 = α

All three DAGs default to **LinearDML**. CausalForestDML / XLearner remain reserved per Plan v2.

### Refutation suite (D7 mandatory five)

All three DAGs are compatible with the 5-refuter mandatory suite (random_common_cause / placebo / data_subset / add_unobserved / evalue). E-value > 1.5 + p > 0.10 on all 5 → `evidence_level="validated"`.

---

## Next action after user approval

1. **User answers Q1–Q5 above.**
2. **Claude Code applies any user-requested edits** (e.g. remove direct ADE edge in DAG 002 if Q2 chooses pure full-mediation).
3. **B0.7 closes** with a final commit covering the DAG files + validation + this review doc.
4. **B1 starts**: `backend/requirements.txt` updated per B0.5's findings F1–F5.

**End of user-review summary.**
