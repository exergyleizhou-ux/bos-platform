# Phase B Plan v1 — Adversarial Self-Review

> **Reviewer persona.** Senior staff engineer, 15 years, specialism
> in causal inference + distributed software architecture. Not the
> author of Plan v1. Goal: make Phase B not need a rewrite mid-flight.
> Bias: surface problems, not validate authorial vision.
>
> **Scope.** Reads `_reports/PHASE_B_PLAN.md` (987 lines, self-scored
> 92/100). Does not modify Plan v1. Does not write Plan v2.
>
> **Tone.** Counter-arguments first, then concede only if I can't break
> the recommendation under direct attack.

---

## Section-by-Section Critique

### Section 1 — Objective statement

**Potential issue 1.** The objective conflates *building causal
endpoints* with *building causal value*. Five typed endpoints can
exist with zero analyst-side value if the DAGs they're fed are
nonsense. The "Done" criterion in §7 reflects API shape and
refutation pass-rate — but a 100% refuter-pass rate on a
hand-picked synthetic bench is not the same as "Phase B works."
There is no acceptance item that says "at least one real BOS
question was answered."

**Potential issue 2.** "Honest evidence_level derived from
refutation pass/fail" is the strongest claim in §1, but Plan v1
doesn't operationalise it until D7 and §2.3, and the rule there
(`validated` = all mandatory refuters pass + back-door + lab-cited
DAG) is invented without justification. The objective makes a
promise the body of the plan hand-waves.

**Potential issue 3.** "No paper-rewrite" is correctly listed as
out of scope but is naive: if the paper revision changes the
headline mediation claim (R8), Phase B's golden-data fixtures
become stale. The objective should mention paper-version pinning,
not just exclusion.

**Verdict.** NEEDS REVISION — add (a) one "real question answered"
acceptance item, (b) move the evidence_level rule into §1's
"Done =" definition by reference, (c) pin to paper revision
`BOS_Paper1_JCP_FINAL.docx` SHA-256 explicitly.

---

### Section 2 — Five APIs

#### 2.1 `POST /api/v1/causal/identify`

**Schema gaps.**

- `DagSpec.source` is an enum (`hand | auto_causal_learn | hybrid`)
  but no `provenance_meta` field — for hybrid DAGs we cannot tell
  *which* edges came from which mechanism. This will bite during
  audit when a reviewer asks "why does X → Y exist in this DAG."
- `CausalIdentifyRequest` doesn't include `dataset_fingerprint`.
  Identification depends on the data's variable coverage; you
  cannot retroactively prove identification was sound without
  knowing what columns the data actually had.
- `assumptions: List[str]` is free-text. That makes it impossible
  to test or compare; should be an enum (`no_unobserved_confounders
  | positivity | consistency | sutva | …`).

**Edge cases unaddressed.**

- Empty DAG (only treatment + outcome, no edges) — `_check_dag_consistency`
  passes (acyclic) but `identify_effect` will return
  `IdentifiedEstimand(estimand_type=nonparametric-ate, none)`. The
  Pydantic response will fail because `strategy` enum has no "trivial"
  value — server-side 500.
- Cycle pre-validation triggers a `ValueError` at Pydantic time,
  which surfaces as HTTP 422. Good. But the error message says
  "DAG must be acyclic" — doesn't tell the operator *which edge*
  closes the cycle. Need to surface the smallest cycle in the
  validator error.
- Treatment ∉ DAG nodes: caught by referential integrity. But
  outcome ∉ DAG.nodes is *not* explicitly caught — `_check_dag_consistency`
  only checks edge endpoints. A treatment with no outgoing edges
  passes Plan v1's validators but is identification-meaningless.

**Paper alignment.** §2.1 maps identify to "paper §3.5 Mechanistic
Bounding and §4.1 mediation argument". That's loose. The paper's
§3.5 is empirical (BSF portability micro-assay), not identification.
The identify endpoint maps more naturally to §SI mediation-DAG
discussion if such a discussion exists. Need to grep again or
soften the claim.

**Estimate compatibility.** `CausalIdentifyResponse.adjustment_set`
is `List[str]` but `CausalEstimateRequest` doesn't accept it as
input — the estimate endpoint takes `dag + treatment + outcome`
and re-identifies internally. That's a round-trip waste *and*
creates a divergence risk (identify says backdoor on {X,Z}, estimate
re-runs and picks {X} only). Need either: (a) estimate accepts
optional `precomputed_estimand`, or (b) reorder so identify is
an *internal* step of estimate and never independently called.

#### 2.2 `POST /api/v1/causal/estimate`

**method_family enum explosion.** Plan v1 lists 5 values:
`linear_regression | propensity_score | dml | causal_forest_dml |
x_learner`. But:

- DoWhy provides 14 native estimators (recon §1.3); EconML provides
  ~20. Picking 5 *names* doesn't pick 5 *behaviours* — `dml` and
  `causal_forest_dml` both go through `econml.dml.*` with different
  classes. A user wanting `DR` (doubly robust) is out of luck.
- `method_params: Dict[str, Any]` is the escape hatch but it loses
  schema discipline — `model_y` and `model_t` parameters for DML
  must be sklearn estimator *instances*, which aren't JSON-serialisable.
  Plan v1 implicitly demands string-name → factory mapping that
  isn't specified.

**Small-sample behaviour.** Plan v1 §6 lists "R2 power floor" as
high severity but the endpoint itself silently accepts any
`data.inline` with no `n >= n_min` check. The paper has n=4
arms; an honest estimate endpoint must refuse to fit on n < 30
*per stratum* (or whatever the threshold is) — or return
`evidence_level=planned` automatically. Plan v1 doesn't enforce
either.

**Compute cost / sync vs async.** `CausalForestDML` on 50k rows
with the default `n_estimators=100` is a 30–120 s call. The
endpoint is implicit-synchronous (`POST` returns the result body).
At 30s+ the agent's `httpx.AsyncClient` will time out on default
settings (5s read timeout). Either bump timeouts in agent (need
to specify) or expose an async-job pattern (job_id → poll). Plan
v1 doesn't pick.

**MC reuse.** `mc_propagate` (Phase A `/api/v1/mc/propagate`)
already does uncertainty propagation. `CausalEstimateResponse.ci_*`
is *another* MC-style uncertainty layer. Plan v1 does not say how
they relate — bootstrap inside estimate, MC outside estimate, or
both. The agent will end up calling MC on top of estimate, getting
nested uncertainty that double-counts. Need an explicit "estimate
ci is computed *how*" rule.

#### 2.3 `POST /api/v1/causal/refute`

**Refuter shortlist defended weakly.** Plan v1 says "starter
refuter menu" with random_common_cause / placebo / data_subset
mandatory. The remaining four are listed as "optional" with no
rationale. Strongest case for each *omitted* refuter:

- `add_unobserved_common_cause` — the *only* refuter that addresses
  the headline causal-inference worry ("what if there's a hidden
  confounder"). Dropping it to "optional" defeats the audit story.
- `bootstrap_refuter` — cheap (sub-second) and gives CI for the
  refute itself. No reason to make it optional.
- `evalue_sensitivity_analyzer` — VanderWeele E-value is the
  standard reporting unit in clinical causal lit; dropping it means
  Phase B can't speak the same language as the literature it cites.
- `non_parametric_sensitivity_analyzer` — Cinelli/Hazlett style;
  the *only* one of the menu that doesn't depend on linearity.

**Streaming.** Refutation on full DoWhy + EconML re-fit can take
2–5 min on big data. Plan v1 says the agent calls refute as part
of its `causal_node` chain. The chat user sees a 5-minute blank.
Plan v1 doesn't have a streaming or progress hook.

**80% pass-rate origin.** §7 acceptance #4 ("refutation pass-rate
≥ 80%") cites no source. The literature actually doesn't agree on
a threshold — most papers report all refuters individually. 80%
floor is invented. Either justify or replace with "each mandatory
refuter has its own pass criterion, all must pass."

#### 2.4 `POST /api/v1/causal/mediation`

**Untestable assumption.** Mediation analysis requires *sequential
ignorability* (no unobserved mediator-outcome confounding).
`CausalMediationRequest` does not surface this assumption — the
user can fire off a mediation analysis and get a number without
ever declaring the assumption they made. The schema should force
an `assumptions_acknowledged: List[Literal["sequential_ignorability",
"no_treatment_mediator_interaction", …]]` field, and refuse if
empty.

**Method choice.** Plan v1 doesn't say which mediation method:

- **Baron-Kenny** (1986): the textbook one, but biased under
  treatment-mediator interaction.
- **IORW** (inverse odds ratio weighting): handles interaction
  but needs propensity models for both treatment and mediator.
- **DML mediation** (Farbmacher 2022): the most modern; available
  as a research-grade pattern via EconML.

Each has different data requirements and different identification
assumptions. Plan v1 leaves this as a Plan v2 D-decision implicitly
— but D11 / D9 are also implicit. This is a real D14 that's
missing.

**Mediator share validator.** The `mediator_share` sum-to-1
validator (`[0.95, 1.05]` slack) is too tight for nonparametric
mediation — Pearl's decomposition can sum well outside [0.95, 1.05]
when interaction is present. Either widen to [0.7, 1.3] or split
into per-mediator effects without the sum constraint.

#### 2.5 `POST /api/v1/causal/sensitivity`

**Method choice undefined.** Plan v1 lists three methods (`linear`,
`evalue`, `partial_linear`) as enum values but doesn't say which is
default or how the agent picks. Each addresses different worries:

- **linear** (Cinelli-Hazlett, 2020): robustness value for OLS.
- **evalue** (VanderWeele-Ding, 2017): worst-case bias from
  unmeasured confounder.
- **partial_linear**: dowhy's generalisation; expensive.

For most BOS questions the right one is *evalue* because operators
want a single number ("how strong would a hidden confounder need
to be to overturn this?"). Plan v1 doesn't make this call.

**Independent vs embedded.** Plan v1 makes sensitivity an
independent endpoint (B.5) requiring `EstimateHandle` to re-fit.
Alternative: embed `sensitivity` as a field in
`CausalEstimateResponse` (compute it once during estimation).
Pros of independent: cleaner OpenAPI surface, refuter-style audit
trail. Cons: double the compute cost; the cheap E-value is *free*
during estimation. Plan v1 doesn't acknowledge the trade.

**Verdict for Section 2.** NEEDS REVISION on all five endpoints.
Top fixes: (1) `precomputed_estimand` plumbing identify→estimate;
(2) small-sample refusal rule; (3) sync/async strategy; (4)
mediation method picker (new D14); (5) sensitivity default method.

---

### Section 3 — Agent causal_node

**BOSState bloat.** Plan v1 adds 12 fields to `BOSState`. Phase A
had ~26 fields; this brings it to ~38. The TypedDict is becoming
a record without structure. Should be:

```python
class CausalSlice(TypedDict, total=False):
    dag: Optional[Dict[str, Any]]
    treatment: Optional[str]
    outcome: Optional[str]
    identified: Optional[bool]
    strategy: Optional[str]
    ate: Optional[float]
    ate_ci: Optional[Tuple[float, float]]
    mediation: Optional[Dict[str, Any]]
    refute_results: Optional[List[Dict[str, Any]]]
    refute_passed: Optional[bool]
    sensitivity: Optional[Dict[str, Any]]
    evidence_level: Optional[str]

class BOSState(TypedDict, total=False):
    # ... existing ...
    causal: Optional[CausalSlice]
```

Same applies retroactively to Phase A's SER/SFI/Relay state keys
but that's out of scope; for Phase B at least group new keys.

**Single-node serial chain.** Plan v1 picks D11=α (single node,
internal asyncio.gather only for refute+sensitivity). But the chain
is identify → estimate → (refute || sensitivity || mediation). That's
**three** independent post-estimate calls, not two. Plan v1
implicitly only parallelises two and forgets mediation.

**Partial-failure semantics.** Plan v1 §3.2 doesn't say what happens
if refute fails but estimate succeeded. Options:

- Return estimate with `evidence_level=planned` + a warning.
- Return error.
- Return estimate with `refute_results=None`.

Each has merits. The plan needs a position.

**Router LLM prompt.** Plan v1 lists keyword patterns. The actual
LLM intent classification is left as "see Phase A code". A real
prompt for the causal intent:

```
You are routing an operator question to the right BOS module.
Causal intent: the operator wants to know WHY a result happened,
WHAT WOULD HAPPEN under intervention, or HOW MUCH of an effect a
specific factor caused. Examples:
  - "为什么 SER 在用这种 feedstock 时下降？"
  - "If I raise temperature by 5°C, what happens to ammonia?"
  - "How much of the SER lift came from D' vs G'?"
Non-causal intent (NOT this branch):
  - "What is the current SER?" → ser
  - "Is the system safe?"      → sfi
```

Plan v1 doesn't ship this prompt. It needs to.

**Render numerical convention.** Plan v1 §3.4 shows `{ate:.3f}` but
doesn't specify CI bracket. `[low, high]` vs `(low, high)` is a
real audit-style choice; pick now or expect drift across rendering
calls.

**Verdict.** NEEDS REVISION — group BOSState fields; specify
parallel branches; specify partial-failure semantics; ship the
LLM prompt; lock CI bracket convention.

---

### Section 4 — D6–D13 decisions

#### D6 — numpy 2.x

**Strongest counter.**

- Isolation = +1 service = monitoring complexity. Phase A already
  has Core + Agent. Causal Service = 3 services. Healthchecks ×3,
  log aggregation ×3, deployment artefact ×3.
- "dowhy forces numpy 2.x" → that train has already left the
  station. Every package downstream of dowhy is following. Pinning
  Core to numpy 1.26.4 *forever* is itself a debt — eventually
  scipy / sklearn / pandas will drop 1.x support and Core breaks
  anyway.
- numpy 2.0 release notes (June 2024): the *binary* compat break
  is the C-API ABI, not the Python-level API for most users. BOS
  Core's numpy usage is shallow (numerical kernels in
  `engine/core/`) — a one-day audit + run of all 925 tests likely
  shows zero or few breaks.
- Phase A 4.5× efficiency means a numpy migration *measured* at
  6 h could land in 1.5 h. That's cheaper than the lifetime cost
  of running a 3rd service for the rest of the project.

**Reality check.** If we assume the migration is ≤ 8h and
isolation is +20h lifetime overhead (deployment + monitoring +
inter-service auth), α (migrate) wins on a 6-month horizon.

**Reviewer recommendation.** **Flip to α (migrate Core to numpy
2.x)** unless an inspection of the actual numpy usage in
`engine/core/` finds non-trivial breakage. Add a B0.5 batch:
"numpy 2.x readiness audit" (2–4 h).

#### D7 — `/api/v1/causal/*` placement

**Strongest counter.** Industrial users don't ask "give me an ATE
of dm_in on ser_point." They ask "why did this batch fail?" or
"what should I change?" That's a *workflow* question, not a
*method* question. A `/causal/*` group puts the method first. An
embedded design (e.g. `POST /api/v1/relay/simulate?explain=causal`
returning the same body plus a `causal_explanation` block) puts
the workflow first.

**But.** OpenAPI freeze + drift detection (Phase A precedent A2)
works much better on a contained router. Embedding doubles the
schema surface of every Phase A endpoint. The agent's
`causal_node` becomes more complex because each call must know
which "host" endpoint it's piggybacking on.

**Reviewer recommendation.** Keep **α** (new group) **but add**
a thin `/api/v1/ser/causal_explain` convenience shortcut that
proxies to `/causal/estimate` with a pre-baked DAG for the SER
question. Document it as "convenience facade, not source of truth."

#### D8 — DAG sourcing

**Strongest counter.** Hybrid γ ("hand skeleton + auto-validate")
assumes someone hand-writes the skeleton. Who? Plan v1 doesn't
name an owner. Options:

- **Paper author.** Phase B presumes the paper author (the user)
  will participate. But the paper is being submitted to JCP; the
  author has zero time-budget for DAG curation during Phase B.
- **Claude Code.** That's just α (auto-discovery) with extra
  steps; "hand" means "the LLM authored it without a domain
  expert in the loop."
- **Pre-recorded.** Author pre-commits a DAG library
  (`_reports/PHASE_B_DAGS/*.json`) up front; Phase B reads from
  it. Sustainable.

**Reviewer recommendation.** **Keep γ** but require Plan v2 to
name the DAG-author role explicitly *and* commit to a
pre-recorded DAG library of ≥ 3 starter DAGs before B2 ships.
Without a real DAG, every causal endpoint is theoretical.

#### D9 — Estimator menu

**Strongest counter.** Plan v1 says "3 estimators" — LinearDML,
CausalForestDML, XLearner. But:

- Where is the *selection rule*? When does the agent pick
  LinearDML vs CausalForestDML? Plan v1 punts to "method_family
  is a request param." Operators don't know which to pick.
- XLearner overlaps significantly with CausalForestDML on
  heterogeneous-effect questions. Reviewer's hand-up: defend the
  XLearner choice independently of CausalForestDML.
- 3 estimators implies 3 hyperparameter spaces × 3 default
  presets the agent must reasonably set. That's 9 implicit
  decisions Plan v1 doesn't document.

**Reviewer recommendation.** **Downgrade to D9=α (one estimator,
LinearDML)** for B2 MVP. Add CausalForestDML and XLearner in a
follow-up Phase-B-2 batch only after the MVP runs against real
data. Ship 1 well > 3 sketchily.

#### D10 — Test strategy

**Strongest counter.** Three test axes × 5 endpoints × ~10 cases
per axis = ~150 new tests for B2 + B5 alone. Phase A's 217 Phase A
tests took A1 batch ~6 h adjusted; Phase B's 150 tests at the same
rate is ~4 h *just for the test suite*. That's a quarter of the
total Phase B budget. The matrix is real.

**But.** Stochastic estimators absolutely require redundant
checks; a single seed-pinned test is one bug-fix away from masked
regression.

**Reviewer recommendation.** **Stagger.** B2 ships axis 1 only
(seeded smoke). B3 (OpenAPI contract) adds axis 3 (schema parity)
naturally. B5 adds axis 2 (refutation pass) for the e2e suite
only — not per-endpoint. That gives full coverage at three test
suites, not three axes × five endpoints. Tag this as D10 = "δ
staggered."

#### D11 — Agent causal_node topology

**Strongest counter.** Single node hides three failure modes
behind one error frame:

- "Identify failed" → operator sees "causal_node failed."
- "Estimate failed but identify succeeded" → same.
- "Refute failed but estimate succeeded" → same.

The agent's render layer can't distinguish, so the operator can't
either. Multi-node (γ) topology with explicit edge labels gives
the user surgical error messages.

**Reviewer recommendation.** **Flip to D11=γ (5 nodes)**. The
"+4 edges" cost Plan v1 cites is overstated; LangGraph edges are
cheap. The "+4 state-transitions" cost is real but small.
Multi-node also enables Phase G's streaming rendering without a
rewrite.

#### D12 — Render UX

**Strongest counter.** A causal result rendered as text alone is
not actionable for non-statistician operators. The recon §3.2
explicit value claim is the *mediation chain* — without a visual
of "Signal-API → CEA → SER" the chain is just three sentences in
markdown.

**However.** Markdown supports inline Mermaid in many renderers
(GitHub, Notion, modern Slack). Adding a single
`render_dag_as_mermaid(dag) -> str` helper and embedding it in
the response markdown is ~30 lines of code. *Not* β (matplotlib
PNG round-trip) but a cheap visual upgrade.

**Reviewer recommendation.** **Flip to D12=β-lite (Mermaid DAG
in markdown)**. Forest plot can wait for Phase G. Add ~30 LoC to
the render path.

#### D13 — Baseline 36-fail

**Strongest counter.** A red CI is a feature only if everyone
knows which reds are "approved." Plan v1 records the 36 fails in
a doc; nobody reading `pytest tests/` sees that doc. Six months
in, a new developer (or a future Claude session) sees 36 reds
and concludes the codebase has rot.

**Reviewer recommendation.** **Flip to D13=γ (mark-skip + move
to `tests/_legacy/`)**. The cost (Plan v1 estimate: half-day)
is overpaid; for files we know are deferred (Code Cockpit, V1 SER
router), a `@pytest.mark.skip(reason="legacy-deferred per
0.5/D5 / A/D1 sunset")` decorator across the failing classes is
1–2 hours, not half a day. The *git blame* on those decorators
becomes the audit trail.

---

### Section 5 — Batch breakdown

**Strongest counter to Phase A 4.5× efficiency reuse.** Phase A
work was *mechanical* — typed schema + validator + router glue +
test cases following well-trodden FastAPI patterns. Phase B is
*scientific*:

- Picking the right DAG is research-grade.
- Choosing refuters that match the BOS context is research-grade.
- Validating refutation-pass behaviour on real n=4 data is
  research-grade.

Research-grade work historically runs **1×–2×** plan estimates,
not 4.5×. Plan v1's ~20.5h total at 4.5× efficiency should be
re-estimated at 2× efficiency: **~40–55h adjusted**.

**Missing batch.** No B0.5 for numpy audit (if D6 flips to α).
No B7 for paper-version pinning (R8 mitigation).

**B2 too big.** "Five endpoints + their schemas + their engines"
in one batch is 36h raw / 8h adjusted. That's the largest single
batch in the plan and the riskiest (most novel code). Should be
split into B2a (`identify` + `estimate`) and B2b (`refute` +
`mediation` + `sensitivity`).

**Verdict.** Re-estimate at 2× efficiency; split B2; add B0.5
conditional on D6=α; add B7 paper-pinning.

---

### Section 6 — Risks R1–R10

**Risks missing from Plan v1.**

- **R11 Paper-author availability.** D8=γ depends on a hand-authored
  DAG skeleton. The user is also the paper author and is in JCP
  submission cycle. Plan v1 assumes DAG-authoring bandwidth that
  may not exist.
- **R12 Anthropic API cost explosion.** Phase B adds an LLM-driven
  router that classifies on "causal" intent + a render layer that
  formats causal output. Both add LLM calls per agent run. At
  Phase A's cadence (1 LLM call per turn) plus Phase B's causal
  classification overhead, monthly API spend could 2-3×. Plan v1
  doesn't budget LLM cost.
- **R13 DoWhy 0.14 → 0.15 API drift.** DoWhy releases roughly
  quarterly; the project is in active development. A 6-month
  Phase B horizon overlaps at least one minor release. Plan v1
  pins to 0.14 in B1's requirements but doesn't say what
  triggers a re-pin.
- **R14 CausalForest training time unboundedness.** On n > 20k with
  CausalForestDML default settings, training can exceed 10 minutes.
  Plan v1's sync-only API contract (R6 in plan) is incompatible.
- **R15 Refutation false-positive risk.** Random-common-cause
  refuter passes ~95% of the time even on bad estimates because
  it's testing a weak null. Operator sees "refutation passed" and
  trusts the estimate. The acceptance #4 ≥ 80% pass-rate is
  trivially achievable; the *honest* gate is something like
  "refutation passes AND identification is strict AND sensitivity
  E-value > 1.5."

**Risks Plan v1 lists but understates.**

- **R2 (statistical power).** Plan v1 says "Plan v2 should audit
  DB row count" but does not specify what happens if the count is
  < 200/stratum. The honest answer is: "Phase B becomes a
  *demonstrator* on synthetic data, not a production analytics
  surface." That demotion is a real Plan v2 decision.

---

### Section 7 — Acceptance criteria

**Issue 1.** Acceptance #4: "Refutation pass-rate ≥ 80% on
golden-data bench (≥ 90% target, 80% floor)." Source: invented.
Suggest: replace with "On the golden bench, all *mandatory*
refuters (random-common-cause, placebo, data-subset) pass with
p > 0.10, and the E-value robustness check returns E-value > 1.2."
That's testable and literature-grounded.

**Issue 2.** Acceptance #8: "Phase A `217 phase_a tests` PASS
unchanged." The reconnaissance reconciliation found 217 Phase A
tests by `-k phase_a` (216 + 1 agent isolation). Acceptance #8
should pin to 217 explicitly *and* require a new
`tests/contract/test_phase_a_freeze.py` that snapshots this
count so future Phase B work can't quietly drop tests.

**Issue 3.** Acceptance #9: "Baseline 36-fail floor un-worsened
(no new fails added)." If D13 flips to γ (mark-skip), this number
changes — needs re-stating.

**Issue 4.** Missing acceptance: "At least one real (not synthetic)
BOS question was answered end-to-end via the Phase B stack." This
is the §1-objective gap from earlier.

---

## D6–D13 Final Recommendations (after self-critique)

| Decision | Plan v1 Rec | After Critique | Reason |
|---|---|---|---|
| **D6** numpy | β isolate | **α migrate** | Lifetime overhead of a 3rd service > one-time numpy 2.x migration cost. Add B0.5 audit. |
| **D7** placement | α new group | **α + facade** | Keep new group (OpenAPI drift hygiene) but add a thin `/api/v1/<paper-module>/causal_explain` convenience layer. |
| **D8** DAG | γ hybrid | **γ + DAG library** | Keep hybrid but commit to a pre-recorded DAG library (≥ 3 starter DAGs) *before* B2. |
| **D9** estimators | β 3 + refuters | **α 1 + refuters** | Ship LinearDML well in B2 MVP. CausalForestDML + XLearner deferred to Phase-B-2. |
| **D10** tests | δ three-axis | **δ staggered** | B2 = axis 1 only. B3 picks up axis 3 by virtue of schema-parity tests. B5 adds axis 2 in e2e only. |
| **D11** topology | α single node | **γ 5 nodes** | Multi-node enables surgical error messages and Phase G streaming. Edge cost is overstated. |
| **D12** render | α text only | **β-lite mermaid** | Mermaid DAG in markdown is ~30 LoC and a major UX win. Forest plot can wait. |
| **D13** baseline | α record-only | **γ skip + _legacy/** | A red CI without skip-marker discipline is a future-developer trap. 1–2h cost. |

**6 of 8 decisions flipped under adversarial review.** D6, D9, D11,
D12, D13 each see a clean recommendation change; D7 and D8 are
hardened with explicit additions. D10 keeps the option letter but
materially changes the staggering interpretation.

This is a *high* flip rate — Plan v1 was over-indexed on
"keep options open." Plan v2 should explicitly close on these.

---

## Plan modifications required

1. **§1.** Add an "at least one real BOS question answered"
   acceptance criterion. Add paper-revision pinning.
2. **§2 (new D14).** Add D14: mediation-method choice (Baron-Kenny
   vs IORW vs DML-mediation). Default proposal: DML-mediation.
3. **§2.1.** `_check_dag_consistency` must report the offending
   cycle edges, not just "not acyclic." Add outcome-in-DAG check.
4. **§2.1 + §2.2.** Add `precomputed_estimand` plumbing so
   `identify` → `estimate` can pass the estimand without re-fit.
5. **§2.2.** Add `n_min_per_stratum` request param (default 30);
   sub-threshold → `evidence_level=planned` automatic downgrade.
6. **§2.2 + §2.3 + §2.4.** Add a sync/async toggle. Default sync
   for n ≤ 10 000; async-job pattern for larger.
7. **§2.3.** Promote `add_unobserved_common_cause` and
   `evalue_sensitivity_analyzer` from "optional" to mandatory.
8. **§2.4.** Add `assumptions_acknowledged` required field.
   Widen `mediator_share` sum-to-1 slack to [0.7, 1.3].
9. **§2.5.** Embed cheap E-value in `CausalEstimateResponse` as
   a free side-effect; keep the dedicated endpoint for the
   expensive `partial_linear` method.
10. **§3.** Group new `BOSState` fields under a `causal:
    CausalSlice` sub-TypedDict. Specify partial-failure semantics.
    Ship the LLM router prompt verbatim.
11. **§3.4.** Lock CI rendering convention as `[low, high]`.
12. **§5.** Re-estimate at 2× efficiency (~40–55h adjusted). Split
    B2 into B2a + B2b. Add B0.5 (numpy audit, conditional on D6).
    Add B7 (paper-version pinning, ~1h).
13. **§6.** Add R11–R15 (paper-author availability, LLM cost,
    DoWhy version drift, CausalForest unbounded train, refutation
    false-positive). Tighten R2 with concrete branching (≥200/stratum
    → analytics surface; < 200 → demonstrator).
14. **§7.** Replace acceptance #4 wording with literature-grounded
    refuter-pass rule (p > 0.10 mandatory refuters + E-value > 1.2).
    Pin acceptance #8 to 217 phase_a tests via new contract test.
    Re-state acceptance #9 conditional on D13=γ. Add acceptance
    #11 ("one real BOS question answered").

**14 modifications.** This is a substantial v1→v2 delta. Plan v2
self-score should target 96/100 like Phase A's v2; Plan v1 deserves
a more honest 86/100 after this review (not the 92 the author
claimed). The 6-point gap is exactly the flipped-decisions tax.

---

**End of adversarial self-review.**
