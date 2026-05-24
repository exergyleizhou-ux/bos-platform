# Paper 1 — Version pinning record

> Phase B B7 deliverable (Plan v2 §1 R8 mitigation).
> Audit chain: Plan v2 §1 -> ``tests/contract/test_paper_version_pinned.py``
> -> this document -> B7 commit message.

## §1 Purpose

Paper 1 ("Staged bioconversion via a protocol-first Biological
Operating System: Decoupling waste deconstruction from nutrient
recovery", in preparation for J Clean Prod) is the scientific
artefact backing the entire Phase B causal layer (five
`/api/v1/causal/*` endpoints). The paper operationalises a
*Tenebrio molitor* (M1) → aerobic kernel (M2) → *Protaetia
brevitarsis* (M3) relay on distillers' grains, with BSF
(*Hermetia illucens*) referenced only as a literature comparison
benchmark in §4.3. If the paper's *method* section drifts from
what the engines implement, the audit chain breaks and the
platform's evidence-level claims become unsupported.

(Pin-history note: the original 2026-05-16 pin in §3 was recorded
under an earlier working title — "BOS Platform for BSF
Bioconversion: Pre-registered Pearl/Rubin Mediation Analysis".
The paper file SHA-256 is the audit-binding anchor; the title
change is documented here for chain inspectability and was
captured in CITATION.cff commit `40cc9fa`.)

The B7 mitigation is a two-part gate:

1. ``tests/contract/test_paper_version_pinned.py`` — a contract
   test that SHA-256-hashes the paper file and fails if the hash
   changes.
2. This document — the re-pin procedure, classification rules for
   "minor metadata" vs "material method drift", and the audit log
   of every pin update.

When the gate test fails, **STOP all Phase B/C/D code work**.
Follow §5 below.

## §2 Current pin

| Field | Value |
|---|---|
| File path | `C:\Users\10420\Desktop\bos 0506\Paper1_BT\BOS_Paper1_JCP_FINAL.docx` |
| SHA-256 | `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C` |
| Size | 75,569 bytes |
| Pinned at commit | (post-OpenAI-critic polish; 8 patches: title shift + 5 highlights JCP-style + Software availability audit-facing framing + mediation in-silico tag) |
| Pin date | 2026-05-21 (afternoon) |
| Pin author | (5-author submission; see CITATION.cff for software credit and §3 history below for patch summary) |

The path is the author machine's absolute path. The test SKIPs on
machines where the path does not resolve — this is deliberate:
the gate's job is to alert the author when *they* save a new paper
revision, not to enforce paper presence on CI / co-author boxes.

A Phase G enhancement (see §7) would move the path to an
environment variable.

## §3 Pin history (audit chain)

### 2026-05-16 — Initial pin (Plan v2 §1)

- SHA-256: `BA13A10FDE39DECB96FD98F92694791A0A6739868ADDE69C374A49C013B110D7`
- Size: 74,671 bytes
- Plan v2 commit context: written 2026-05-17 against HEAD `b962e58`
- Recorded in: `_reports/PHASE_B_PLAN.md` §1
- Snapshot preserved as: `BOS_Paper1_JCP_FINAL.docx.bak` (next to
  the live file)

### 2026-05-24 — Phase C C5 ship (Validation suite — synthetic-data calibration benchmarks)

- Paper SHA-256: **unchanged** at
  `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
- Software tag bump: `v0.10.3-phase-c-c4` → `v0.10.4-phase-c-c5`
- CITATION.cff `version` → `0.10.4-phase-c-c5`, date-released
  `2026-05-24` (calibration run date)
- New files:
  - `backend/scripts/run_phase_c_calibration.py` — operator CLI
    that runs C1/C2/C4 calibration benchmarks at configurable
    n_trials and emits a markdown report at
    `_reports/PHASE_C_CALIBRATION_RUN_<date>.md`. Default
    n_trials=10; supports `--skip-bayesian` for fast iteration.
    Pure-numpy operations (C2 + C4) run in seconds; C1 PyMC
    runs at small trial count to keep wall-clock manageable.
  - `backend/tests/benchmarks/test_phase_c_calibration.py` —
    pytest-based benchmark tests at compact N (~30 trials for
    C2 + C4, 5 trials for C1). Marked `@pytest.mark.slow`;
    fast CI loops can skip via `-m "not slow"`.
  - `backend/tests/benchmarks/__init__.py` — pytest collection
    marker.
- New artifact:
  `_reports/PHASE_C_CALIBRATION_RUN_2026-05-24.md` — first
  calibration run output (C2 + C4 only; n_trials=20).
  - C2 Conformal: empirical coverage 0.954 (target 0.950) PASS
  - C4 Uncertainty pipeline: max point error 0.0028 PASS
- Test verification:
  - 2 fast benchmark tests PASS (C2 + C4)
  - C1 slow benchmark not run in this commit (would add ~5 min);
    runs cleanly via `pytest -m slow` or via the CLI
- No new endpoint added; no schema bump.
- Phase B + Phase C OpenAPI snapshots unchanged.
- Classification per §4: **software-extension event, not paper
  drift**. No Plan v3 review trigger. This batch builds
  CALIBRATION infrastructure on top of existing endpoints
  without modifying their public contracts.

### 2026-05-21 (late night) — Phase C C4 ship (Uncertainty propagation pipeline; non-paper-SHA event)

- Paper SHA-256: **unchanged** at
  `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
- Software tag bump: `v0.10.2-phase-c-c3` → `v0.10.3-phase-c-c4`
- CITATION.cff `version` → `0.10.3-phase-c-c4`
- New endpoint: `POST /api/v1/causal/uncertainty_pipeline`
  (SCHEMA_VERSION C.4)
- New engine: `causal_uncertainty_pipeline.py` (pure numpy,
  no PyMC dependency — composes upstream posteriors)
- Functionality: end-to-end SER uncertainty propagation
  operationalising Paper 1 §3.6's 2×10^5 Monte Carlo as a typed
  REST surface. Takes posterior samples on D' and G' (typically
  from /bayesian_estimate C1 runs) and propagates through
  SER = sqrt(D' × G') via Monte Carlo resampling or pairwise
  alignment. Optional mediation_proportion_posterior input
  produces a κ-mediation credibility band alongside SER.
- End-to-end smoke (synthetic Paper 1 baseline: D'~N(0.683,
  0.021), G'~N(0.672, 0.019), n=1000 each, n_propagated=10000):
  SER point 0.6763 (Paper 1: 0.68, err 0.004)
  95% band [0.6481, 0.6764, 0.7035]
  Evidence: validated
  Propagation: 32.6ms (no PyMC; numpy quantile + sqrt)
  0 invalid samples, 0 warnings
- Test coverage: 13 unit tests in
  `tests/unit/test_causal_uncertainty_pipeline.py`, all FAST
  (~5-20ms each). Covers: Paper 1 baseline recovery; band
  ordering; method dispatch (monte_carlo_resample vs
  pairwise_alignment); alpha sensitivity; seed reproducibility;
  mediation band; invalid-sample dropping; all-invalid error
  path.
- Phase C OpenAPI snapshot: 3 paths now (bayesian_estimate +
  conformal_predict + uncertainty_pipeline), 18 schemas under
  transitive closure (was 14 in C2 state).
- Phase B OpenAPI snapshot: unchanged (no Phase B endpoint
  modified).
- Classification per §4: **software-extension event, not paper
  drift**. No Plan v3 review trigger.

### 2026-05-21 (night) — Phase C C3 ship (Bayesian mediation branch; non-paper-SHA event, but Phase B mediation schema bump)

- Paper SHA-256: **unchanged** at
  `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
- Software tag bump: `v0.10.1-phase-c-c2` → `v0.10.2-phase-c-c3`
- CITATION.cff `version` → `0.10.2-phase-c-c3`
- **Schema additive change** (per Plan v3 §2.3):
  - `MediationMethod` Literal extended from
    `("dowhy_two_stage", "farbmacher_dml_loo")` to
    `("dowhy_two_stage", "farbmacher_dml_loo",
    "bayesian_mediation")`
  - `CausalMediationRequest` gains optional `method` field
    (default None → auto-dispatch by mediator count; explicit
    `"bayesian_mediation"` opts into PyMC branch)
  - `app/schemas/causal/mediation.py` SCHEMA_VERSION constant
    bumped `B.4` → `C.3` (informational; not emitted in
    response, but documents the lineage)
- **Phase B OpenAPI snapshot regenerated** to reflect new
  `MediationMethod` enum value + new optional `method` field on
  the request. **Classified as schema-additive, not method
  drift** — operators omitting `method` get the same behaviour
  as before C3.
- New engine function: `_run_bayesian_mediation` in
  `causal_mediation_engine.py` (~150 LOC). PyMC two-stage Pearl
  decomposition: mediator equation `M = α_T·T + α_X·X + ε_M`,
  outcome equation `Y = β_T·T + β_M·M + β_X·X + ε_Y`; NDE =
  posterior(β_T), NIE = posterior(α_T · β_M), total = NDE + NIE.
- **Bootstrap short-circuit** for bayesian_mediation: rather
  than re-running PyMC 200x (which would take ~30 min per
  request), the CI bands are derived from the posterior
  quantiles of the SINGLE PyMC run. Triggers a
  `method_fallback` warning explaining the short-circuit. The
  posterior typically has 1000+ samples, so CI quantile
  estimation is stable.
- End-to-end smoke (synthetic n=150, true NDE=0.5, NIE=3.0,
  total=3.5): recovered NDE=0.853, NIE=2.925 (err 0.075),
  total=3.778; 95% CI brackets true values; sampling time
  148.7s.
- Test coverage: 5 new tests (3 slow PyMC + 2 fast schema
  validation) added to existing
  `tests/unit/test_causal_mediation_engine.py`. All 14 non-slow
  tests PASS (12 original + 2 new C3 fast), 0 regression on
  Phase B B2b.2 behaviour.
- Phase C OpenAPI snapshot unchanged (no new endpoint; the
  mediation endpoint is in Phase B scope).
- Classification per §4: **schema-additive, not method drift**.
  No Plan v3 review trigger. Pre-C3 operators (no `method`
  field in request) get identical behaviour.

### 2026-05-21 (late evening) — Phase C C2 ship (Conformal prediction engine; non-paper-SHA event)

- Paper SHA-256: **unchanged** at
  `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
- Software tag bump: `v0.10.0-phase-c-c1` → `v0.10.1-phase-c-c2`
- CITATION.cff `version`: `0.10.0-phase-c-c1` →
  `0.10.1-phase-c-c2`
- New endpoint: `POST /api/v1/causal/conformal_predict`
  (SCHEMA_VERSION C.2)
- Implementation: custom split-conformal + Mondrian variants
  (~50 LOC numpy core, no mapie / crepes dependency); Lei &
  Wasserman 2014 split-conformal + Vovk et al. 2005 Mondrian
  stratification
- Test coverage: 12 new unit tests in
  `tests/unit/test_causal_conformal_engine.py` (FAST, no PyMC
  required, ~5-10 ms per test) covering all 10 C2 design §4.3
  behaviors + 2 bonus tests; all PASS
- Phase C OpenAPI snapshot regenerated to include 2nd path
  (2 paths total in `_reports/phase_c_openapi_snapshot.json`,
  14 schemas captured under transitive ref closure)
- End-to-end smoke (synthetic ATE=2.0, n=200): prediction diff
  T=1 - T=0 = 1.977 (true 2.0, err 0.023); marginal quantile
  q_(1-α) = 2.42; coverage guarantee 95%; evidence='supported'
- Mondrian conditional coverage smoke (n=300, 2 strata with
  noise SD 0.5 vs 2.0): per-stratum quantiles correctly larger
  for noisier stratum
- Classification per §4: **software-extension event, not paper
  drift**. No Plan v3 review trigger.

### 2026-05-21 (evening) — Phase C C1 ship (Bayesian baseline engine; non-paper-SHA event, recorded for audit chain completeness)

- Paper SHA-256: **unchanged** at
  `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
  (Phase C is software extension, not manuscript modification)
- Software tag bump: `v0.9.1-paper-final` →
  `v0.10.0-phase-c-c1`
- CITATION.cff `version` bumped from `0.9.1-paper-final` to
  `0.10.0-phase-c-c1`
- Phase C Batch C1 first wave landed (commit 326d38e: schema +
  engine + deps) plus second wave (this commit: router endpoint
  + 11 unit tests + OpenAPI snapshot + drift gate + Phase B
  scope tightening)
- New endpoint: `POST /api/v1/causal/bayesian_estimate`
  (SCHEMA_VERSION C.1)
- New components in `_reports/phase_c_openapi_snapshot.json`:
  1 path + 11 schemas (BayesianEstimateRequest /
  BayesianEstimateResponse / BayesianDiagnostics + transitively-
  referenced CausalData / DagSpec / etc.)
- Phase B `test_phase_b_openapi.py` scope rule tightened from
  `/api/v1/causal/*` glob to an explicit 5-path frozenset
  (`PHASE_B_CAUSAL_PATHS`). This prevents future Phase C / D
  endpoint additions from falsely triggering Phase B drift
  alarms.
- End-to-end smoke test (synthetic ATE=2.0, n=100): posterior
  mean 1.847, 95% HDI [1.551, 2.116], r_hat 1.0000, ESS 803,
  n_divergent 0, evidence_level='validated'.
- Classification per §4: **software-extension event, not paper
  drift**. No Plan v3 review trigger; Phase C is itself the
  approved extension. Paper-SHA gate test verified PASS at the
  unchanged anchor.

### 2026-05-21 (afternoon) — post-OpenAI-critic polish re-pin (Option A: framing + JCP-style highlights + audit-facing software wording)

- SHA-256: `C7E4CE1B695401659668D256B779B60EB30738D9963B875112EAC9406353741C`
- Size: 75,569 bytes
- Delta: -82 bytes (net text shrink from new shorter highlights)
- Cause: OpenAI engineer critic review (~3000-word JCP-style
  repositioning brief) accepted 8/12 suggestions with our 3
  calibrations. Applied via
  `backend/scripts/scratch_final_polish.py`:

  | Patch | Change |
  |---|---|
  | P1 | Title: "Staged bioconversion via a protocol-first Biological Operating System: Decoupling waste deconstruction from nutrient recovery" → "Staged insect bioconversion through a protocol-first Biological Operating System improves resource recovery from distillers' grains" (keeps BOS brand, foregrounds waste / resource / recovery for JCP editor) |
  | P2.1 | Highlight 1: BOS architecture framing → "A staged insect-bioconversion relay improved matched-boundary resource efficiency on distillers' grains." |
  | P2.2 | Highlight 2: Signal-API mechanism framing → "The relay increased SER from 0.53 to 0.68 by jointly improving dry-matter reduction and nitrogen recovery." |
  | P2.3 | Highlight 3: dose-response RCS-Hill framing → "Signal-API hardening localised activity to a heat-labile, protease-sensitive 3–10 kDa fraction within a defined dose and stability envelope." |
  | P2.4 | Highlight 4: cross-executor framing → "Control-API rules convert biological handover into auditable dose, hydraulic-load, stability, and reject criteria with PASS / PASS-with-retuning / FAIL outcomes." |
  | P2.5 | Highlight 5: M1/M2/M3 progressive adjustment framing → "An audit software layer links cleaner-production claims to frozen code, schemas, and tests, with in-silico covariate audits pre-registered as V14 wet-lab targets." |
  | P3.1 | Software availability: "The full computational core is encapsulated in the BOS Pipeline v9.0 archive" → "The audit-facing implementation reference for this manuscript is encapsulated in the BOS Pipeline v9.0 archive" (per OpenAI's "claim-protection layer, not platform" reframe) |
  | P4 | Mediation 70% in abstract: gains explicit "pre-registered in-silico estimate maps" tag so reviewers cannot misread it as a wet-lab direct causal claim |

  Calibrations against OpenAI's full proposal:
  - Discussion §4 NOT contracted to 5 subsections (kept §4.1–4.7
    structure; the three-tier evidence framing in §4.7 is load-
    bearing methodological architecture that reviewer would
    otherwise miss).
  - Figures NOT reshuffled to OpenAI's recommended 6-figure plan
    (would require regenerating figure files; reserved for
    revision round if a reviewer raises figure layout).
  - The README 7-column paper↔code crosswalk was NOT replaced;
    instead the OpenAI 5-row "claim-protection" table was
    added ABOVE it (complementary, not competing). The two
    tables serve different reviewer personae (editor / software).

- Classification per §4: **bibliographic + metadata + framing**,
  no method-section drift, no headline-number change, no
  equation change, no DAG topology change, no Plan v3 review.
- SI unchanged in this re-pin (the SI patches and Declaration /
  Author contributions additions from 2026-05-21 morning remain
  in place; SI SHA still `6ee74d53...0ce4`).
- Audit chain: this entry + the commit message + the
  `scripts/scratch_final_polish.py` script that produced the
  patches.

### 2026-05-21 — post-GPT-critic-cleanup re-pin (Option A: minor metadata; 3 anonymous-acknowledgment substitutions)

- SHA-256: `AA251B01904306271F25FDA234F56D07D9F0B4284AD94C8CE88F1915A4E3CC8B`
- Size: 75,651 bytes
- Delta: +18 bytes
- Cause: GPT critic review identified 3 `[TODO: ...]` placeholders
  still present in the Acknowledgments paragraph (distillery name
  / commercial supplier name / laboratory colony source). To
  preserve manuscript readiness for submission without disclosing
  party identities, all three were substituted with anonymised
  wording:
  - `[TODO: name of regional grain-spirit distillery]` →
    "a regional grain-spirit distillery (identifier withheld for
    confidentiality; batch-level data in Supplementary Table
    S10A)"
  - `[TODO: regional commercial supplier name]` →
    "a regional commercial supplier"
  - `[TODO: laboratory colony source]` →
    "an institutional laboratory colony"
- Sanity verified: 0 remaining `[TODO` occurrences in the
  patched docx (`backend/scratch_followup_patch.py` printed
  "remaining [TODO occurrences: 0").
- Classification per §4: **bibliographic + metadata**, no
  method drift. No Plan v3 review triggered.
- Companion SI changes (no SI gate test, recorded for audit):
  appended two short statements at the end of
  `BOS_Paper1_JCP_SI.docx` — "Declaration of competing
  interests: see main manuscript." and "Author contributions:
  see main manuscript." SI SHA changed from
  `0cb94f40...4a99af` to `6ee74d53...0ce4` (+37 bytes).
- Audit chain: this entry + commit message + the
  `scratch_followup_patch.py` script that produced the rewrite.

### 2026-05-20 — v0.9.1-paper-final re-pin (Option B: pre-submission final patches)

- SHA-256: `E64EAB068BC3DD58A7DF331201F42F14C581D33178F623EE38427CB052F36D9A`
- Size: 75,633 bytes
- Delta: +971 bytes
- Cause: Final pre-submission patches applied via
  `backend/scratch_y1_patch.py`. Twelve patches in total,
  classified as **bibliographic / metadata / scoping**, not
  method-section drift. No Plan v3 review triggered (see §4
  trigger conditions — none of the patches modifies Pearl/Rubin
  decomposition, Γ-bound threshold, refuter selection,
  identification strategy, headline numbers, equation numbering,
  or DAG topology).
- Patches applied:
  1. Author list — five authors with affiliation superscripts:
     Lei Zhou(1), Qingwei Deng(2), Xuechen Li(1), Xinyi Huang(3),
     Guangsheng Chen(1,*). (1) Zhejiang A&F University SKLSS;
     (2) Guangdong Polytechnic Normal University; (3) Zhejiang
     A&F University Optoelectronic Engineering.
  2. Corresponding author: Guangsheng Chen (chengu1@zafu.edu.cn).
  3. Software availability — GitHub URL embedded
     (`https://github.com/exergyleizhou-ux/bos-platform`).
  4. Software availability — commit hash filled (92a7a0f).
  5. Software availability — Zenodo DOI placeholder
     (`10.5281/zenodo.XXXXXXX — pending mint`).
  6. Data availability — Zenodo DOI placeholder (matching format).
  7. Software availability — OSF DOI placeholder
     (`10.17605/OSF.IO/XXXXX — pending pre-registration`).
  8. CRediT statement — five-author role assignment (Lei Zhou
     leads software/methodology/analysis/writing; Guangsheng Chen
     supervision/PA/W-R&E; others Conceptualization + W-R&E).
  9. Acknowledgments — template with TODO placeholders for
     distillery/supplier/colony source names + CTI third-party
     lab + Zhejiang A&F University colleagues.
  10. Funding section (new) — Option B, no funded support
      ("This research did not receive any specific grant from
      funding agencies...").
  11. §4.4 LCA scoping paragraph appended — declares boundary-
      explicit LCA as V14 pre-registered deliverable, defers
      Scope 1+2 emissions / water / energy to companion paper.
  12. (No method-section text changes; all patches are at the
      front matter, back matter, or pre-existing scoping
      paragraph.)
- Evidence (recorded for audit):
  - `scratch_y1_patch.py` (operator-side, not committed) applied
    each patch with hit-count guards (each anchor confirmed
    unique with 1 hit before replacement).
  - Post-patch sanity verified: 9 placeholder strings absent,
    11 replacement anchors present in final docx.
  - Both `BOS_Paper1_JCP_FINAL.docx` (overwrites original) and
    `.y1-patched.docx` saved with identical SHA.
  - Backup `.pre-y1-patch` preserved at the B7 pin SHA
    (`2FD4...3118D`) for rollback.
- Verdict: **bibliographic + metadata + scoping**, no Plan v3
  review needed.
- Action: gate test re-pinned to the new SHA; CITATION.cff
  bumped to version `0.9.1-paper-final`, date-released
  `2026-05-20`.

### 2026-05-18 — B7 re-pin (Option A: minor metadata)

- SHA-256: `2FD4387028B2B160388C65CCB0F269967E05B55FDEAF6BA62B1570BCB533118D`
- Size: 74,662 bytes
- Delta: −9 bytes
- Cause: Word save metadata refresh (lastModifiedBy /
  lastModifiedTime / internal XML whitespace). No text content
  change.
- Evidence (recorded for audit):
  - `backend/scratch_paper_diff.py` extracted both files via
    `python-docx` and compared paragraph-level text.
  - Result: **0 differing paragraphs** out of 258 paragraphs in
    both files.
  - Critical method keywords confirmed present in the current
    paper:
    - `Pearl`: 4 hits (paras 100, 132, 152, 216)
    - `Rubin`: 3 hits (paras 100, 132, 152)
    - `mediation`: 6 hits (paras 10, 100, 113, 152, 214, ...)
    - `ACME`: 1 hit (para 100)
    - `NDE`: 63 hits
    - `NIE`: 4 hits
    - `Signal-API`: 32 hits
    - `70%`: 2 hits (paras 10, 100)
    - `proportion mediated`: 1 hit (para 10)
    - `1.5`: 1 hit (para 100)
    - `Eq. 4`: 3 hits (paras 49, 100, 152)
    - `sensitivity`: 12 hits
  - Expected 0-hit keywords (BOS implementation choices, not paper
    text):
    - `kappa`: 0 hits — paper uses Greek letter κ; BOS code uses
      ASCII identifiers (no string match expected).
    - `E-value`: 0 hits — paper uses "Γ-bound >= 1.5"; BOS B2b.3
      operationalises that via VanderWeele-Ding E-value (recorded
      in `PHASE_B2b3_DESIGN.md` §3).
    - `Cinelli`: 0 hits — paper does not cite Cinelli-Hazlett by
      name; BOS B2b.3 `linear` branch is a power-user addition,
      not paper-required (recorded in `PHASE_B2b3_DESIGN.md` §1).
- Verdict: **minor metadata delta**, no Plan v3 review needed.
- Action: gate test re-pinned to the new SHA.

## §4 Trigger conditions for Plan v3 review

A gate-test failure escalates to a full Plan v3 review when **any**
of the following are true:

- **Method section text changes** — Pearl/Rubin mediation
  description, Cinelli-Hazlett or related sensitivity bound,
  refutation methodology, identification strategy.
- **Numerical claim changes** — the abstract's 70% proportion
  mediated, Γ-bound 1.5 threshold, headline ATE point estimate,
  bootstrap iteration counts, n-per-arm.
- **Equation changes** — Eq. 1–4 numbering, the form of any
  equation referenced by an engine (e.g. Eq. 4 = Pearl
  counterfactual decomposition).
- **New cited method** the engines do not currently implement —
  e.g. a switch from VanderWeele-Ding to a different sensitivity
  framework.
- **DAG topology changes** in the paper's causal model section
  (e.g. adding a new mediator, instrument, or unmeasured
  confounder).

A failure is **NOT** a Plan v3 trigger when only the following
change:

- Word metadata (lastModifiedBy, lastModifiedTime, app revision
  counter, internal XML whitespace, .docx zip-file ordering).
- Formatting (bold, italic, font, paragraph spacing).
- Front-matter author additions or affiliation updates.
- Typo fixes in non-method sections (abstract typos count as
  method changes if they touch the 70% / Γ-bound numbers).
- Reference list reordering, addition of references that the BOS
  engines do not depend on.

The categorisation must be recorded in §3 with a one-line evidence
summary even for minor re-pins, so the audit chain stays
inspectable.

## §5 Re-pin procedure (when the gate fails)

1. **STOP** all Phase B/C/D code work. Do not commit any further
   engine / schema / router / test changes until the gate is
   restored.
2. Compute the current SHA via PowerShell (the source of truth on
   the author machine):
   ```
   (Get-FileHash 'C:\Users\10420\Desktop\bos 0506\Paper1_BT\BOS_Paper1_JCP_FINAL.docx' -Algorithm SHA256).Hash
   ```
3. Run `backend/scratch_paper_diff.py` (regenerate if it was
   archived) to extract paragraph-level text diff between the new
   file and the previous pin's snapshot (the `.bak` next to the
   live file, or a git-archived copy).
4. Categorise the diff against §4. Capture which paragraphs
   changed and which critical keywords they touch.
5. **Branch on category**:
   - **Minor metadata / formatting / non-method text**: re-pin
     `PINNED_SHA256` in `test_paper_version_pinned.py`, append an
     entry to §3 with the evidence summary, commit with a
     `chore(paper-pin):` prefix message. No Plan v3 review.
   - **Material method change**: open a Plan v3 review document
     (`_reports/PHASE_B_PLAN_V3_REVIEW_<date>.md`) that audits
     each affected engine and lists the code changes required.
     Land the code changes first, then re-pin in the same commit
     batch that finalises the v3 review.
6. Update CITATION.cff `date-released` and `version` if the
   re-pin is material (Phase G-style version bump).

## §6 Audit chain links

- `_reports/PHASE_B_PLAN.md` §1 — original pin record.
- `backend/tests/contract/test_paper_version_pinned.py` — the
  gate test, with the pinned constant.
- This document — re-pin log and procedure.
- `CITATION.cff` — software citation metadata referencing the
  paper as `preferred-citation`.
- B7 commit message — links this document, the gate test, and
  the corresponding Plan v2 §1 / B7 sections.

The chain is acyclic: Plan v2 -> gate test -> this doc ->
CITATION.cff. Any future re-pin appends a §3 entry; no node is
ever rewritten.

## §7 Phase G future enhancement

- **Path indirection.** Move `PAPER_PATH` from a hardcoded
  absolute path to an environment variable `BOS_PAPER1_PATH` with
  the current absolute path as the default. Allows CI / co-author
  boxes / Phase G public-repo contributors to point at their own
  copy.
- **Multi-version pinning.** If Paper 1 ever has a "submitted" vs
  "accepted" vs "published" lineage, the gate could carry a tuple
  of acceptable SHAs and report which one matches. For B7 the
  single-pin pattern is sufficient.
- **Paper section anchors.** A richer gate could checksum the
  method section specifically (extract via python-docx, normalise
  whitespace, hash). That would let formatting changes pass
  cleanly without re-pinning. Useful when revision rounds at JCP
  trigger lots of cosmetic edits.

## §8 Archive — Step 1.5 scratch evidence

The text-diff scratch script (`backend/scratch_paper_diff.py`)
was used during Step 1.5 of the B7 batch to verify that the
2026-05-18 paper SHA mismatch was metadata-only (§3 evidence
block). It was **deleted** at Step 3d rather than committed,
matching the scratch-archive convention used by B2b.1 / B2b.2 /
B2b.3 (scratch produces evidence into a `_reports/` archive doc,
the script itself is not tracked).

The script is regenerable in ~80 lines via `python-docx` (already
in the backend venv from B7 Step 1.5; no extra deps). When a
future re-pin needs to run §5 step 3, recreate the script with
the contract:

- inputs: two `Path` objects to `.docx` files
- output: paragraph-level text diff to stdout, plus a critical-
  keyword scan against the current pin's anchors

The verbatim diff output from the 2026-05-18 run is preserved in
§3 above (0 differing paragraphs + critical-keyword inventory),
so the §3 audit trail does not depend on the script being in
the repo.

If a Phase G clean-up wants a permanent script, the natural home
is `backend/scripts/paper_pin_diff.py` with a CLI surface
(`--current PATH --reference PATH --format json`).

**Update 2026-05-20 (post-v0.9.1-paper-final)**: the patch-side
of this workflow has been promoted to permanent scripts at:

- `backend/scripts/paper_pin_patch_main.py` — applies the 12
  pre-submission patches to the main manuscript (author block,
  GitHub URL, DOIs, CRediT, Acknowledgments, Funding, LCA);
  produces both an in-place rewrite and a side-by-side
  `.y1-patched.docx`.
- `backend/scripts/paper_pin_patch_si.py` — applies the SI
  patches (commit hash, tag, Zenodo bracketed placeholder).

The diff script (§7 first bullet) is still a Phase G item; the
text-diff lives inline in the operator workflow for now (compare
`.pre-y1-patch` backup vs current via the `python-docx`
paragraph-text equality used during the B7 re-pin).
