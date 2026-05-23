# Phase C Plan v3 — Bayesian + Conformal Uncertainty Layer

> Plan v3 deliverable. Authorises Phase C engineering work that
> extends the Phase B causal layer with full uncertainty
> quantification (Bayesian posteriors + conformal prediction
> intervals + uncertainty propagation).
>
> **Selected strategy path**: v3' (parallel-friendly, Paper 2 to
> JOSS 2026-09 middle with arXiv preprint 2026-08-30, Paper 3
> methodology submit 2027-Q3).
>
> **Anchored at**: HEAD `085a583`, Paper 1 SHA `C7E4CE1B...3741C`
> (PINNED), Phase B 100% complete (10/10 batches), 53+51 tests
> PASS, tag `v0.9.1-paper-final`.
>
> **Approval gate**: this document supersedes Plan v2 §1 "Out of
> scope" for Bayesian + Conformal items. Plan v2 architectural
> constraints (paper-SHA gate, OpenAPI drift gate, audit chain
> §3 history, no method drift without re-pin) remain in force.

---

## §1 Scope

### §1.1 In scope (this Plan v3)

Phase C consists of **6 batches** delivering:
- 2 new `/api/v1/causal/*` endpoints (`bayesian_estimate`,
  `conformal_predict`)
- Bayesian variant of mediation analysis (extends existing
  `causal_mediation_engine.py` D14 implementation)
- End-to-end uncertainty propagation (Signal-API → κ → SER
  pipeline with full posterior credibility bands)
- Synthetic data validation suite (verifies posterior calibration
  + conformal coverage)
- Optional frontend uncertainty display (Mermaid + credibility
  bands)

### §1.2 Out of scope (deferred to Plan v4 / Phase D)

- Hierarchical Bayesian models for cross-substrate (Phase D
  multi-site)
- Real-time streaming inference (Phase E)
- LCA + economic modeling (Phase F)
- Cinelli-Hazlett extension to mediation (Phase D candidate)
- TMLE / AIPW doubly-robust estimators (Plan v4 V14+
  prerequisite)

### §1.3 Backward compatibility with Phase B

Phase C must preserve:
- All 53 Phase B contract / unit / e2e tests PASS
- All 51 LangGraph agent tests PASS
- `SCHEMA_VERSION` strings B.1 - B.5 unchanged
- Paper 1 (`v0.9.0-paper1` / `v0.9.1-paper-final`) anchoring
  unaffected
- Paper-SHA gate remains anchored at `C7E4CE1B...3741C`

Phase C adds:
- `SCHEMA_VERSION` C.1 (Bayesian) + C.2 (Conformal) + C.3
  (Bayesian mediation) + C.4 (uncertainty pipeline)

---

## §2 Batch breakdown (6 batches, 70-105 h)

### §2.1 Batch C1 — Bayesian baseline (10-15 h)

**Goal**: introduce PyMC-based posterior estimation as an
alternative / complement to LinearDML point estimates from
Phase B B2a.

**Deliverables**:
1. `backend/app/engine/extended/causal_bayesian_engine.py`
   - `BayesianEstimator` class wrapping PyMC4+ (or PyMC5)
   - Backdoor adjustment with weakly informative priors
   - Returns posterior samples (default 1000 draws × 2 chains)
   - Reports 95% Highest Density Interval (HDI) alongside
     posterior mean
   - Seed-locked at 42 (matches Paper 1 reproducibility)
2. `backend/app/schemas/causal/bayesian.py`
   - `BayesianEstimateRequest` / `BayesianEstimateResponse`
   - `SCHEMA_VERSION = "C.1"`
3. `backend/app/routers/causal.py` — add `POST
   /api/v1/causal/bayesian_estimate` endpoint
4. `backend/tests/unit/test_causal_bayesian_engine.py` (~8-10
   tests):
   - posterior recovery on synthetic data (true ATE = known)
   - HDI calibration (95% HDI contains true ATE ≥ 95% of runs)
   - prior sensitivity (informative vs weakly informative)
   - seed reproducibility
   - rejected method names (422 with `code='method_reserved'`,
     mirrors B2a pattern)
5. `backend/agent/nodes/causal_bayesian.py` — new agent node
6. `backend/tests/contract/test_phase_c_openapi.py` — new
   OpenAPI drift gate (C-layer extension of B3)

**Dependencies**:
- PyMC ≥ 5.0 in requirements.txt (currently NOT installed)
- aesara / pytensor backend (numpy 2.x compatibility check
  needed)

**Risks**:
- PyMC sampler chains can be slow (10-30 seconds per request) →
  may need to expose `n_samples` / `n_chains` request parameters
  for fast vs accurate trade-off
- numpy 2.x compatibility: PyMC 5.x supports numpy 2.x; verify
  on `backend/.venv-backend`

**SCHEMA_VERSION**: `C.1`

---

### §2.2 Batch C2 — Conformal prediction (10-15 h)

**Goal**: introduce distribution-free conformal prediction
intervals as a complement to the frequentist CIs from Phase B
B2a/B2b and the Bayesian HDI from C1.

**Deliverables**:
1. `backend/app/engine/extended/causal_conformal_engine.py`
   - `ConformalEstimator` class
   - Split-conformal baseline (Lei & Wasserman 2014 style)
   - Mondrian variant: stratifies conformal residuals by
     substrate class (handles substrate-class heterogeneity per
     Plan v3 §3 design)
   - Returns prediction intervals at any α level (default 0.05)
2. `backend/app/schemas/causal/conformal.py`
   - `ConformalPredictRequest` / `ConformalPredictResponse`
   - `SCHEMA_VERSION = "C.2"`
3. `backend/app/routers/causal.py` — add `POST
   /api/v1/causal/conformal_predict` endpoint
4. `backend/tests/unit/test_causal_conformal_engine.py` (~8-10
   tests):
   - marginal coverage validation on synthetic data (split
     conformal: ≥ (1-α) coverage)
   - Mondrian conditional coverage (per-substrate ≥ (1-α))
   - calibration set sizing (sensitivity to n_cal)
   - edge case: empty calibration set raises clear error
5. `backend/agent/nodes/causal_conformal.py` — new agent node
6. Extend OpenAPI drift gate from C1

**Dependencies**:
- `mapie` or `crepes` Python package (Mondrian conformal
  prediction libraries), OR custom implementation if libraries
  too heavyweight
- recommended: custom implementation (~150-200 LOC), avoids
  dependency bloat

**Risks**:
- Mondrian groups need enough samples per stratum (typically
  ≥ 30); on small Paper 1 datasets, may have to fall back to
  marginal conformal with documented limitation

**SCHEMA_VERSION**: `C.2`

---

### §2.3 Batch C3 — Bayesian mediation (15-20 h)

**Goal**: extend `causal_mediation_engine.py` (Phase B B2b.2,
SCHEMA_VERSION B.4) with a Bayesian variant for NDE / NIE
posterior estimation. Complements the existing DoWhy two-stage
+ bootstrap variant.

**Deliverables**:
1. `backend/app/engine/extended/causal_mediation_engine.py`
   - Add `_run_bayesian_mediation` function alongside existing
     `_run_dowhy_mediation` and `_run_farbmacher_mediation`
   - Uses PyMC to estimate NDE / NIE posteriors jointly with the
     mediator equation
   - Returns posterior samples + HDI on `proportion_mediated`
     (replaces existing bootstrap CI when `request.method =
     "bayesian"`)
2. `backend/app/schemas/causal/mediation.py`
   - Extend `MediationRequest.method` enum to include `"bayesian"`
   - `SCHEMA_VERSION` bump from `B.4` → `C.3` (this is a
     **schema bump**, audit chain entry required in
     PAPER_PINNING.md §3)
3. `backend/tests/unit/test_causal_mediation_engine.py` — add
   ~5-7 tests for the Bayesian branch:
   - Pearl identity: NDE + NIE = ATE on synthetic data with
     known truth (within HDI tolerance)
   - HDI coverage on `proportion_mediated`
   - comparison: Bayesian posterior mean vs DoWhy point estimate
     should agree within tolerance on the same fixture
4. Update Phase B B4 v2 agent node `causal_mediation.py` to
   dispatch on the new `method = "bayesian"` parameter

**Critical audit-chain note**:
- This batch **modifies a Phase B schema** (`causal/mediation.py`)
  → triggers OpenAPI drift gate FAILURE if not paired with
  snapshot regeneration
- Procedure (per Plan v2 §1 R8 + PAPER_PINNING.md §4):
  1. Add new enum value to `MediationRequest.method`
  2. Re-run `backend/scripts/freeze_phase_a_openapi.py` (or
     equivalent for Phase B) to regenerate snapshot
  3. Update `_reports/phase_b_openapi_snapshot.json`
  4. Append PAPER_PINNING.md §3 entry: "schema additive change,
     not method drift" classification
  5. Paper 1 SHA gate UNCHANGED (this is a software-side schema
     extension, not a manuscript change)

**Dependencies**: Batch C1 must ship first (PyMC infrastructure).

**Risks**: Bayesian mediation is methodologically subtler than
LinearDML. Need to consult Hoyer et al. 2008 / Daniel et al.
2015 for prior specification. Plan v3 review session 2 should
include 1 h on prior choice.

**SCHEMA_VERSION**: `C.3` (mediation upgraded from B.4)

---

### §2.4 Batch C4 — Uncertainty propagation (15-20 h)

**Goal**: end-to-end uncertainty band from Signal-API → κ → SER.
Currently the Phase B engines report point + CI/HDI **per
endpoint**; C4 propagates uncertainty across endpoints so the
final SER claim carries the combined uncertainty.

**Deliverables**:
1. `backend/app/engine/extended/causal_uncertainty_pipeline.py`
   - New engine wrapping the 5 Phase B endpoints with explicit
     uncertainty propagation
   - Monte Carlo sampling of input uncertainty (Signal-API BU/kg
     dose, k_decay, kappa) → propagates to SER posterior
   - Reports a single `final_ser_credibility_band` (low / median
     / high) from the joint posterior
2. `backend/app/schemas/causal/uncertainty.py`
   - `UncertaintyPipelineRequest` / `UncertaintyPipelineResponse`
   - `SCHEMA_VERSION = "C.4"`
3. `backend/app/routers/causal.py` — add `POST
   /api/v1/causal/uncertainty_pipeline` endpoint
4. `backend/tests/unit/test_causal_uncertainty_pipeline.py`
   (~5-8 tests)
5. `backend/agent/nodes/causal_uncertainty.py` — agent node

**Dependencies**: C1 + C2 + C3 all shipped.

**Risks**:
- Monte Carlo over 5 endpoints is slow (~30-60 seconds per
  request) → expose progressive sampling parameter
- Cross-endpoint dependencies (e.g. mediation depends on
  identify) — need to be careful not to double-count
  uncertainty

**SCHEMA_VERSION**: `C.4`

---

### §2.5 Batch C5 — Validation suite (10-15 h)

**Goal**: synthetic-data benchmarks proving the Bayesian + Conformal
engines are well-calibrated, and that uncertainty propagation
in C4 doesn't drift.

**Deliverables**:
1. `backend/tests/benchmarks/test_phase_c_calibration.py` — NOT
   in regular `tests/unit/` because takes longer (~5-10 min);
   runs nightly or on PR-only
   - Generate synthetic causal datasets with known truth (ATE,
     ACME, NDE, NIE)
   - Sweep over n (10, 50, 100, 500) × noise (low, medium, high)
     × confounding strength
   - Assert: HDI coverage ≥ (1-α) within statistical tolerance
   - Assert: Conformal coverage ≥ (1-α) within tolerance
   - Output: calibration plots (PNG) for Paper 3 figures
2. Standalone CLI: `backend/scripts/run_phase_c_calibration.py`
   - Operator can run benchmarks ad-hoc
   - Generates `_reports/PHASE_C_CALIBRATION_RUN_<date>.md` with
     plots embedded
3. CI integration: `paper1-gate.yml` extension to run
   benchmarks weekly (not on every commit)

**Dependencies**: C1-C4 all shipped.

**Risks**: synthetic-data benchmarks can be tuned to pass —
need to follow established statistical conventions (e.g. Lei et
al. 2018 conformal coverage simulations) and document any
deviations.

**Output**: Paper 3 §"Validation" section has ready-made figures
and tables.

---

### §2.6 Batch C6 — Frontend uncertainty display (10-20 h, optional)

**Goal**: extend `frontend/src/components/bos/CausalMermaidPanel.tsx`
to render uncertainty bands alongside the existing DAG visualization.

**Deliverables**:
1. `frontend/src/components/bos/UncertaintyBandPanel.tsx` — new
   React component
2. Visualizes posterior densities (kernel density estimate
   overlay) + conformal prediction intervals + HDI bars
3. Integrates with the existing Mermaid DAG (clickable nodes →
   show node uncertainty distribution)
4. Frontend tests: extend existing `frontend/src/components/bos/`
   test suite (~8-10 new tests)

**Dependencies**: C4 shipped. Optional — can be deferred.

**Why optional**: Paper 3 + Paper 2 (JOSS) cite the engines, not
the UI. UI improvement is operator UX, not paper-critical.

**Risks**: low. UI work is independent of the audit chain.

---

## §3 Plan v3 hour budget total

| Batch | Hours | Cumulative |
|---|---|---|
| C1 Bayesian baseline | 10-15 | 10-15 |
| C2 Conformal prediction | 10-15 | 20-30 |
| C3 Bayesian mediation | 15-20 | 35-50 |
| C4 Uncertainty propagation | 15-20 | 50-70 |
| C5 Validation suite | 10-15 | 60-85 |
| C6 Frontend (optional) | 10-20 | 70-105 |
| **Plan v3 documentation overhead** | 5-10 | **75-115** |

**At 3-5 h/week sustainable pace**: ~6 months calendar time
(2026-07 → 2027-01).

**Critical milestones**:
- C1 + C2 ship by **2026-12**: Paper 2 (JOSS) can cite Bayesian
  + Conformal as "supported endpoints"
- C3 + C4 ship by **2027-02**: Paper 3 §3 Results section
  unblocked
- C5 ship by **2027-03**: Paper 3 §"Validation" figures ready
- C6 optional: 2027-04 or deferred

---

## §4 v3' parallelism specification

### §4.1 What runs in parallel with Phase C

Per `_drafts/STRATEGIC_ROADMAP_v3_PARALLEL.md` §5 schedule:

| Month | Phase C work | Paper-side work | Total weekly |
|---|---|---|---|
| 2026-07 | C1 (10-15 h) | (none, prep only) | 3-4 h |
| 2026-08 | C1 finish + C2 partial (~10 h) | Paper 2 drafting (20 h) | 7-8 h ⚠ (controlled 1-month spike) |
| 2026-09 | C2 finish (~5-10 h) | Paper 2 submit + arXiv preprint + NSFC | 5-6 h |
| 2026-10 | C3 partial (~10 h) | Paper 3 lit review (~5 h) | 5-6 h |
| 2026-11 | C3 finish (~5 h) | Paper 3 lit review (~5 h) + housekeeping | 4 h |
| 2026-12 | C4 (~15-20 h) | Paper 3 §1+§2 outline (~5 h) | 5-6 h |
| 2027-01-02 | C5 (~10-15 h) | Paper 3 §2 method draft (~10 h) | 5-6 h |
| 2027-03-06 | C6 (optional) | Paper 3 §3+§4 drafting | ~4 h |
| 2027-07 | (Phase D scoping?) | Paper 3 submit | ~3 h |

### §4.2 Why this passes sustainability check

- August spike (7-8 h/week) is **1 month only**, then drops back
- September-February average is **5-6 h/week**, sustainable
- All months stay below 10 h/week ceiling

### §4.3 Conditional fallbacks

If at any month the actual load exceeds 7 h/week sustained:
- **Fallback 1**: defer C6 (frontend) — saves 10-20 h
- **Fallback 2**: delay Paper 3 submit from 2027-07 → 2027-Q4
- **Fallback 3**: revert to v2 conservative (Paper 2 = 2026-12)
- **Last resort**: pause Phase C C4+ until 2027 Q2

---

## §5 Paper 2 (JOSS) outline — embedded here (Step C deliverable)

### §5.1 Title

"BOS Platform: A protocol-first audit-grade software stack for
staged-bioconversion cleaner-production claims"

### §5.2 Target

**JOSS** (Journal of Open Source Software, IF n/a — software
venue, no traditional impact factor; community-respected).
SoftwareX as fallback.

### §5.3 Section outline (~2000 words for JOSS)

| § | Section | Word target | Content |
|---|---|---|---|
| 1 | Summary | 200 | BOS Platform = audit-grade software stack backing JCP Paper 1 mediation framework; bridges cleaner-production research's reproducibility gap |
| 2 | Statement of need | 300 | Cleaner-production research has reproducibility gap; existing tools (DoWhy, EconML) lack paper-software linkage; BOS introduces SHA-gated audit chain |
| 3 | Architecture | 500 | 5 REST endpoints with Pydantic schemas + frozen SCHEMA_VERSION; 14-node LangGraph agent; React+Mermaid frontend; 53+51=104 tests PASS; paper-SHA gate; OpenAPI drift gate |
| 4 | Case study | 500 | Cite Paper 1 (JCP); show how 70% κ-mediation maps to `causal_mediation_engine.py` Pearl-Rubin NDE/NIE |
| 5 | Comparison with existing tools | 200 | DoWhy/EconML (general causal, no paper linkage); KNIME/Galaxy (workflow but not paper-bound); BOS combines |
| 6 | Availability + reproducibility | 300 | GitHub URL, Zenodo DOI, tag chain, audit chain, MIT, CI workflow |

### §5.4 Writing schedule (v3')

- **2026-06**: outline confirmed (this document)
- **2026-08 first half**: §1 + §2 + §3 draft (15 h)
- **2026-08 second half**: §4 + §5 + §6 draft (10 h)
- **2026-08-30**: draft complete; post arXiv preprint (cs.SE)
- **2026-09-02**: submit to JOSS, citing preprint DOI

### §5.5 Risks

- **JOSS rejection** (~15%): redirect to SoftwareX (1-2 months
  delay)
- **Preprint policy conflict**: JOSS explicitly allows; SoftwareX
  partially restrictive — withdraw preprint if needed
- **JCP-JOSS dual-submission concern**: zero risk; different
  contribution types (causal claim vs software artifact)

### §5.6 Strategic value (NSFC angle)

NSFC Youth application 2026-09-30 cites: "Lead author of BOS
Platform software paper (preprint DOI 10.XXXX/zenodo.YYYY,
under review at Journal of Open Source Software)". Strong
preliminary-work signal vs. vague "in preparation".

---

## §6 Paper 3 (methodology) preliminary outline

### §6.1 Title (draft)

"Bayesian–frequentist dual reporting and distribution-free
conformal prediction for boundary-matched bioconversion claims"

### §6.2 Target

- Primary: **Methods in Ecology and Evolution** (IF ~7) — broad
  reach, methodology-friendly
- Backup: **Statistics in Medicine** (IF ~2, pure stats venue)
  or **Journal of Causal Inference** (open-access, IF ~1.5)

### §6.3 Section skeleton (~6000-8000 words)

| § | Section | When achievable | Notes |
|---|---|---|---|
| 1 | Introduction | 2026-10 (lit review parallel with Phase C C3) | Frame the small-n + heterogeneity problem in cleaner production |
| 2 | Methods (math) | 2026-12 → 2027-02 (after Plan v3 method choices locked + Phase C C5 ship) | Bayesian formulation + Mondrian conformal + uncertainty propagation; cite BOS Platform Paper 2 |
| 3 | Results | 2027-03-06 (after C5 ship) | Re-analyze Paper 1 BSF data + 1-2 additional public datasets (kitchen waste / livestock manure) |
| 4 | Discussion | 2027-04-06 | Compare with frequentist baseline; coverage validation; calibration plots |
| 5 | Validation | 2027-05 | Synthetic data benchmarks from C5 |
| 6 | Conclusions | 2027-06 | Future work pointers |

### §6.4 Acceptance probability

Realistic: ~30-40% major-rev first round (methodology venues
are demanding). Total accepted after revision: ~50-60%.

---

## §7 NSFC Youth 2026 application skeleton (Step D deliverable)

### §7.1 Application title (draft, ~25 字)

"基于审计级软件层的循环生物经济多阶段昆虫转化系统效率评估方法研究"
("Audit-grade software-layer-based methodology for staged
insect-bioconversion system-efficiency evaluation in
circular bioeconomy")

### §7.2 Funding amount

¥200-300K, 3 years

### §7.3 Section skeleton

**§1 立项依据 (Background)** (~3000 字):
- 国内外现状 (insect bioconversion + circular economy
  reproducibility crisis)
- BOS Platform 现有工作 (Paper 1 JCP + Paper 2 JOSS preprint)
- 拟解决科学问题 (Bayesian + Conformal applied to BSF +
  multi-substrate)

**§2 研究目标与内容 (Goals + Content)** (~2000 字):
- Phase C 6 batches as engineering deliverables
- Paper 3 methodology paper as scientific output
- V14 wet-lab as longer-term deliverable (signaled but not
  budget-loaded)

**§3 研究方法与技术路线 (Methods)** (~2000 字):
- Detailed batch breakdown
- Software audit chain methodology
- Pre-registration discipline

**§4 创新性 (Novelty)** (~800 字):
- 软件 + 论文一体化审计模式 (audit-chain-preserved software-paper
  linkage)
- Bayesian + Conformal applied to cleaner-production claims
- Mondrian variant for substrate-class heterogeneity

**§5 研究基础 (Preliminary work)** (~1500 字):
- Paper 1 (JCP, under review, submitted 2026-05-22)
- Paper 2 (JOSS, preprint published 2026-08-30, under review)
- BOS Platform v0.9.1-paper-final + Zenodo DOI
- 104 tests PASS + audit chain
- CN118988941A patent

**§6 工作条件 (Resources)** (~500 字):
- Zhejiang A&F SKLSS lab access
- Existing Phase B software stack (immediate productivity)

**§7 经费预算 (Budget)** (~500 字):
- 实验材料费: ¥50K (V14 prep materials)
- 设备费: ¥30K (sensors for Phase E preparation)
- 差旅费: ¥30K (collaboration trips + conference)
- 出版费: ¥40K (open-access Paper 2 + Paper 3 APCs)
- 劳务费: ¥50K (1-2 part-time MSc students for Phase C
  engineering assistance)

### §7.4 Submission timing

- Drafting: 2026-09 (after Paper 2 submitted to JOSS)
- Internal review: 2026-09-20 to 2026-09-28 (group PI +
  collaborators)
- Submission: **2026-09-30 deadline**

---

## §8 Industry partner identification (Step F's industry deliverable)

### §8.1 Target distilleries (Zhejiang region)

Identify 3-5 candidates by 2026 Q4 through Guangsheng Chen's
local network:

| Type | Why fit |
|---|---|
| Baijiu distillery (白酒酒厂) — large scale | Distillers' grains volume aligns with Paper 1 substrate |
| Rice wine distillery (黄酒酒厂) | Different fermentation residue chemistry, multi-substrate angle for Phase D |
| Beer brewery (啤酒厂) | Brewer's grains as backup substrate, BSF benchmark literature precedent |

### §8.2 Conversation script outline (for Lei Zhou / Guangsheng Chen)

**Pitch (3 minutes)**:
1. "We've developed an insect-bioconversion process that turns
   distillers' grains into valuable larval biomass + frass
   fertilizer with measured 68% system efficiency."
2. "Our process is published-pending in J Clean Prod (top
   cleaner-production journal) and software-open in GitHub +
   Zenodo."
3. "We're looking for industrial partners interested in a
   1-3 ton/day pilot, with the partner contributing waste stream
   + facility space; we contribute IP + technical execution."

**Ask**: in-kind contribution (waste stream + space) for 6-12
month pilot; ¥200-500K to cover process engineering + monitoring
equipment.

### §8.3 Timeline

- 2026-Q4: introductory conversations (Guangsheng Chen's network)
- 2027-Q1: NDA + preliminary proposal sharing
- 2027-Q2: formal pilot proposal
- 2027-Q3+: pilot execution (if accepted)

---

## §9 D1 patent filing decision (Step F's IP deliverable)

### §9.1 D1 subject matter

**"Composition and dosing envelope of Signal-API peptide
fraction for staged insect bioconversion"**

Specific claims:
- 3-10 kDa heat-labile, protease-sensitive peptide class
- Dose envelope (BU/kg range derived from RCS / Hill fits)
- Stability formulation (k_decay rate, temperature / pH /
  freeze-thaw stability windows)
- Production method: kernel reactor τ_M2 = 120 min, aerobic
  conditions, derivation from Tenebrio molitor M1 effluent

### §9.2 Why file before V14 wet-lab paper

V14 wet-lab paper (Paper 3 or later) will disclose more precise
peptide identification or alternative compositional information.
**Filing the broad composition claim before V14 publishes
preserves novelty**.

### §9.3 Timeline

- **2026-09-30**: Internal IP discussion with Zhejiang A&F tech
  transfer office (post NSFC submission)
- **2026-11-30**: Patent claims drafted
- **2026-12-15**: D1 patent filed (China primary, US/EU optional
  later)
- **2026-12-31**: Filing confirmation; patent application number
  recorded in `_reports/IP_LEDGER.md`

### §9.4 Cost

- Domestic patent agent fee: ¥5-15K
- USPTO/EPO if extended: $5-15K USD additional
- Recommended: file China only initially; extend after Paper 3
  acceptance

### §9.5 Dependencies

- Confirm CN118988941A claim scope to avoid overlap (need to
  read the existing patent specification before D1 drafting)
- Coordinate with Guangsheng Chen / Zhejiang A&F tech transfer
  office

---

## §10 Phase G mini-batch housekeeping (Step E deliverable)

### §10.1 What can be done now (1-2 h each, distributed)

| Item | Time | Trigger |
|---|---|---|
| Default branch rename to `main` | 5 min (GitHub web UI) + 10 min local sync | After Paper 1 acceptance (post-public switch); not urgent now |
| .git history slim 275 MB → ~50 MB | 1-2 h (`git filter-repo`) | After Paper 1 acceptance |
| Repo visibility private → public | 30 sec (GitHub web UI) | After Paper 1 acceptance |
| Sphinx documentation site | 2-3 h | Anytime; nice-to-have for Paper 2 JOSS submission |
| CI consolidation (merge `ci.yml` + `paper1-gate.yml`) | 1 h | After Phase C C5 ships |
| Update `_reports/PHASE_B_HANDOFF` to reflect Phase C kickoff | 30 min | After Plan v3 confirmed |
| Archive obsolete _reports/ docs | 1-2 h | Quarterly maintenance |

### §10.2 What requires Paper 1 acceptance first

- Public switch (Paper 1 must be accepted, not just submitted —
  avoid leaking pre-publication content)
- Default branch rename (cosmetic, but better signaled post-
  acceptance)
- History rewrite (irreversible, do after final paper-SHA stable)

### §10.3 What can ship in this Plan v3 cycle

- **Sphinx documentation site** (~2-3 h): publish at
  `bos-platform.github.io` or similar. Strengthens Paper 2 JOSS
  submission by giving reviewers a polished entry point.
- **Update PHASE_B_HANDOFF** (~30 min): reflect that Phase B is
  closed and Plan v3 (Phase C) is starting.

---

## §11 Plan v3 review session sequence

**Session 1** (~2 hours, this batch): Plan v3 document ship.
This document.

**Session 2** (~1 hour, deferred): Phase C C1 design doc
(`PHASE_C_B1_DESIGN.md`). Prior choice for PyMC. Endpoint
specification. Test scope.

**Session 3** (~1 hour, deferred): NSFC Youth application
detailed drafting (after Paper 2 JOSS submitted).

**Session 4** (~1 hour, deferred): D1 patent claims drafting
(after Plan v3 internal alignment with Guangsheng Chen).

**Session 5+** (later batches): Phase C C2-C6 design docs, one
per batch, written in the week before each batch starts.

---

## §12 Audit chain implications

Phase C extensions to audit chain:
- New OpenAPI drift gate covering C.1-C.4 schemas
- New tests added to `tests/contract/test_phase_c_openapi.py`
- PAPER_PINNING.md §3 entries for each batch (schema additions
  classified as "non-method-drift")
- Tag chain: `v0.9.1-paper-final` (current) → `v0.10.0-phase-c-c1`
  → `v0.10.1-phase-c-c2` → … → `v0.10.5-phase-c-c5` →
  `v1.0.0-paper2-submit` (when Paper 2 ships)

---

## §13 Risk register (Plan v3 specific)

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| PyMC numpy 2.x incompatibility | 20% | High (Phase C blocked) | Test in C1 first batch; fall back to PyMC 4 if needed |
| Bayesian mediation prior misspecification | 30% | Medium (C3 results need re-running) | Plan v3 Session 2 explicit prior discussion |
| Conformal coverage failure on small-n Paper 1 data | 25% | Medium (Mondrian groups too small) | Document limitation; use marginal conformal as fallback |
| Phase C engineering time overrun | 40% | Medium (Paper 3 slips) | v3' has built-in 25% buffer (70-105 h range vs 50 h floor) |
| Paper 2 JOSS rejection | 15% | Low (redirect to SoftwareX) | Have SoftwareX as backup |
| Paper 1 first decision delays NSFC timing | 20% | Medium (NSFC narrative weaker) | Submit Paper 2 preprint regardless; rely on preprint DOI |
| D1 patent overlap with CN118988941A | 30% | Medium (claims need narrowing) | Tech transfer office review before filing |

---

## §14 Approval

This Plan v3 supersedes Plan v2's "Out of scope" §1 listing for
Bayesian + Conformal items. Approved-by-default upon write
(operator: Lei Zhou; corresponding author: Guangsheng Chen).
Any subsequent material methodological change to this plan
requires a new Plan v3 amendment document, not silent code
drift.

**Sign-off conditions**:
- Phase B 100% complete (✅ at 23ecac1)
- Paper 1 submitted (target: 2026-05-22)
- 53+51 tests PASS at `v0.9.1-paper-final` (✅)
- Audit chain at PAPER_PINNING.md §3 reflects current state (✅
  at 085a583)

---

End of Plan v3 (PHASE_C_PLAN.md). This document is the gate for
starting Phase C C1 engineering work.

**Next action after this ship**:
- Operator: confirm v3' path acceptance and approve Plan v3
- Then: Plan v3 Session 2 (C1 design doc) ~1 hour
- Then: C1 engineering kickoff (`scratch_phase_c_c1_design.md` →
  Bayesian engine implementation)
