# AGENTS.md
# BOS Protocol-First Development Charter for Codex

This file is adapted from `bos_codex_pack` and tuned for the current
`bos-pipeline-reconciled` repository.

## Identity of this repository
This repository is not just a biology repo and not just a generic SaaS app.
It is a protocol-first, audit-oriented BOS platform that combines:
- staged biology,
- explicit inter-stage interfaces,
- matched-boundary accounting,
- measurable control logic,
- operator-visible software surfaces,
- and exportable audit evidence.

Codex should optimize for:
- clarity,
- falsifiability,
- traceability,
- modularity,
- premium operator UX,
- and disciplined non-overclaiming.

## Mission
BOS (Biological Operating System) is a staged bioconversion architecture for
heterogeneous organic wastes.

Its job is to improve the conversion-versus-recovery trade-off by decoupling:
- upstream dissipative deconstruction of difficult substrates, and
- downstream anabolic nutrient recovery and product stabilization.

This repo should implement BOS as an auditable system with explicit interfaces,
release logic, and failure modes.

## Evidence boundary
All code, docs, UI copy, API responses, and comments must preserve the
difference between:

### Validated
Supported directly by the current BOS manuscript or the audited code surface.
Examples:
- protocol-first staged architecture,
- Module 1 / Kernel / Module 3 split,
- Signal-API / Control-API framing,
- matched-boundary accounting with D', G', SER,
- portability grammar: PASS / PASS_WITH_RETUNING / FAIL,
- BOS Pipeline v9 as an inspectable software reference surface.

### Supported but not closed
Partially bounded by evidence, but not identity-closed.
Examples:
- active window mainly localized to a heat-labile, protease-sensitive 3-10 kDa
  fraction,
- functional interface stronger than a phenomenological relay but weaker than
  molecule-level closure,
- portability as conditional compatibility rather than universality.

### Planned
Engineering roadmap, not already deployed fact.
Examples:
- wet-lab closed-loop Kalman supervision,
- universal hot-swappable executor substitution,
- full industrial mass / energy / carbon closure,
- manufactured Signal-API logistics at production grade,
- full MPC / digital-twin control in production.

Never silently upgrade Supported or Planned into Validated.

## Core architecture

### Module 1 - upstream deconstruction
Purpose:
- absorb feedstock heterogeneity,
- perform intensive conditioning and dissipative work,
- generate the upstream aqueous cue context.

### Module 2 - Kernel / signal compiler
Purpose:
- standardize moisture and oxygenation,
- rectify stochastic upstream output,
- compile the aqueous handover into a releasable Signal-API,
- enforce latency and fidelity constraints.

Kernel clock:
- `tau_M2` = kernel residence time
- `f = 1 / tau_M2`

### Module 3 - downstream executor / actuator
Purpose:
- receive released Signal-API under a Control-API,
- perform downstream conversion and nutrient recovery,
- produce stable, auditable outputs.

## BOS functional layers

### Biological process layer
BOS is a staged relay, not a monolithic black box.
Preserve explicit separation between:
- deconstruction,
- compilation,
- execution,
- recovery,
- audit.

### Interface layer
BOS lives or dies at the handover interface.

#### Signal-API
Treat Signal-API as:
- a transferable aqueous cue fraction,
- a functional handover object,
- a potency-qualified release object,
- a state-biasing input to downstream execution,
- not merely "extra nutrition".

#### Control-API
Control-API is the minimum auditable interface specification.
It must define:
- dose window,
- MTT (minimum triggering threshold),
- HAL (hydraulic loading),
- QC markers,
- dwell-time / stability envelope,
- release / reject / requalify logic,
- portability audit grammar.

### Accounting layer
All comparisons must remain matched-boundary and audit-ready.
Required primitives:
- `D'` - matched-boundary dry matter reduction,
- `G'` - matched-boundary nitrogen recovery,
- `SER` - composite system efficiency ratio,
- `DeltaDeltaSER` - staging advantage versus best single-stage baseline,
- `epsilon` - closure residual,
- QC pass/fail flags.

### Control layer
Treat instruction state as latent.
Preferred deployed abstraction:
- estimate `[C_signal, dC_signal/dt]`,
- use low-cost proxies,
- use persistence-gated zero-margin switching,
- keep logic auditable and causal.

### Software layer
The software layer is part of the evidentiary surface.
It must expose:
- boot and configuration,
- persisted state and tenant boundaries,
- typed service contracts,
- scientific engines,
- background compute,
- operator-facing UI,
- runtime observability,
- exportable audit packets.

## Current repository reality
This repo already contains meaningful BOS surfaces that Codex should extend
rather than duplicate:

- Backend stack: FastAPI, SQLAlchemy, async sessions, Celery tasks, engine
  modules under `backend/app/engine/`, typed routers under
  `backend/app/routers/`, schemas in both `backend/app/schemas.py` and
  `backend/app/schemas/`.
- Frontend stack: React, TypeScript, Vite, Tailwind, React Query, Zustand,
  Recharts, Framer Motion under `frontend/src/`.
- Existing operator surfaces: dashboard, batches, SER, simulation, forecast,
  digital twin, sustainability, admin, audit routes, and flight logic.

Codex should prefer extending these surfaces over introducing parallel
frameworks, duplicate route trees, or shadow domain models.

## Primary product goals
Every meaningful change should strengthen one or more of the following:

1. decouple deconstruction from recovery,
2. standardize handover through Signal-API,
3. formalize release logic through Control-API,
4. harden matched-boundary accounting,
5. make portability auditable rather than narrative,
6. surface failure modes early,
7. support locality-aware requalification,
8. bind biology, control, accounting, and software into one operator-visible
   system,
9. raise UI/UX quality without hiding uncertainty,
10. generate reusable audit artifacts rather than one-off outputs.

## Development priorities
Prioritize in this order unless the task explicitly says otherwise:

1. truth-preserving domain model,
2. typed contracts and persistence,
3. accounting integrity,
4. release / reject / requalify workflow,
5. operator visibility,
6. async and observability hardening,
7. premium UX and motion polish,
8. advanced modeling and speculative control.

Pretty UI never outranks audit correctness.

## Non-negotiable invariants

### Interface invariants
- HAL is first-class and never hidden.
- MTT must be explicit wherever release logic exists.
- Signal-API and Control-API versions must be persisted.
- Portability must allow FAIL.
- Local tuning must not mutate global truth silently.

### Accounting invariants
- No SER without explicit D' and G'.
- No cross-condition comparison on mismatched boundaries.
- Closure residuals must remain visible.
- Missing metering must block overconfident sustainability claims.

### Product invariants
- No false precision.
- No universal portability language.
- No "AI magic" copy.
- No hidden spreadsheet logic.
- No backend-only truth that operators cannot inspect.

## Preferred domain objects
Codex should prefer explicit versioned entities such as:
- `Batch`
- `FeedstockLot`
- `SignalBatch`
- `SignalPotencyMeasurement`
- `ControlAPIProfile`
- `LocalityProfile`
- `ExecutorProfile`
- `MTTCalibration`
- `ReleaseDecision`
- `PortabilityAudit`
- `BoundaryLedger`
- `ClosureRecord`
- `FlightEnvelopeCheck`
- `ThermalAudit`
- `ShelfLifeStudy`
- `DigitalTwinState`
- `ExportJob`
- `AuditPacket`
- `OperatorNote`
- `EvidenceLevelTag`

All entities should be traceable, versioned, and diffable where appropriate.

## Repository shape Codex should prefer
When the existing repo does not force another structure, prefer:
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/schemas/`
- `backend/app/routers/`
- `backend/app/services/`
- `backend/app/engine/`
- `backend/app/tasks/`
- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/hooks/`
- `frontend/src/store/`
- `frontend/src/lib/`
- `.agents/skills/`

Prefer feature modules over giant catch-all files.

## Backend standards

### Typed contracts
Every externally meaningful input/output should have explicit schemas.
Minimum contract surfaces:
- batch creation and update,
- signal potency report,
- Control-API definition,
- release decision,
- locality requalification,
- portability audit,
- boundary ledger export,
- flight-envelope status,
- digital-twin status.

### Engine layer
Scientific logic should live in named modules rather than routers.
Likely modules include:
- `ser_engine`
- `monte_carlo_engine`
- `mass_balance`
- `ghg_engine`
- `water_engine`
- `energy_engine`
- `tea_engine`
- `lca_engine`
- `risk_engine`
- `flight_envelope`
- `controller_engine`
- `digital_twin_engine`
- `kinetics_engine`
- `stability_engine`
- `portability_engine`

### Async work
Use background execution for:
- Monte Carlo,
- exports,
- heavy recomputation,
- webhook delivery,
- long-running audit packet generation.

Async jobs should declare:
- task name,
- retry policy,
- timeout,
- idempotency expectations,
- audit-visible status.

### Observability
Support:
- health/readiness,
- structured logs,
- request IDs,
- timing telemetry,
- explicit failure surfaces,
- optional Prometheus / Grafana wiring.

## Frontend standards
The repository should feel like a premium industrial biotech control surface,
not a generic CRUD panel.

### Design intent
Target aesthetic:
- clean,
- high-trust,
- executive-grade,
- scientific,
- theme-capable,
- motion-rich but disciplined.

### UX principles
- put state, uncertainty, and release status in the foreground,
- keep the operator oriented at all times,
- support drill-down from KPI to evidence,
- animate transitions to clarify state change, not for decoration,
- preserve accessibility and performance.

### Visual language
Prefer:
- strong information hierarchy,
- large KPI cards with secondary evidence,
- subtle depth where appropriate,
- smooth micro-interactions,
- responsive layout,
- compact but readable dense-data surfaces,
- color semantics tied to PASS / WARN / FAIL / PLANNED.

### Motion rules
Motion is useful for:
- card entrance,
- metric deltas,
- tab and route transitions,
- timeline scrubbers,
- drill-down panels,
- streaming or polling refresh,
- comparison toggles.

Motion must never:
- obscure values,
- delay critical actions,
- create uncertainty about the current decision state.

### Frontend stack rule
This repo already uses React + TypeScript + Tailwind + React Query + Zustand +
Framer Motion + Recharts. Extend that stack instead of replacing it.

## Required premium operator surfaces
The system should be able to support pages such as:

1. Executive Overview Dashboard
   - SER trend
   - release pass rate
   - active batches
   - current alarms
   - portability status
   - sustainability flags
   - recent audit packets

2. Batch Command Center
   - batch metadata
   - feedstock state
   - Signal-API version and potency
   - Control-API envelope
   - release state
   - event timeline
   - evidence drawer
   - operator notes

3. Signal Lab / Interface Console
   - potency curves
   - MTT localization
   - HAL
   - stability retention
   - active-window summary
   - identity / QC markers
   - release or reprocess recommendation

4. Control-API Studio
   - dose window
   - HAL envelope
   - MTT
   - QC thresholds
   - storage bounds
   - version diff
   - local override warnings

5. Locality Sheet Editor
   - waste-state vector `w`
   - local calibration history
   - pretreatment flags
   - requalification triggers
   - site and season comparisons

6. Portability Matrix
   - executor classes
   - PASS / PASS_WITH_RETUNING / FAIL outcomes
   - retuning notes
   - compatibility bands
   - cross-site audit history

7. Flight Envelope / Release Gate
   - observability axis
   - dynamics axis
   - thermal/energy axis
   - closure/accounting axis
   - release decision
   - blocking issues
   - recommended mitigation

8. Digital Twin / Forecast Surface
   - latent state estimates
   - proxy traces
   - expected handover timing
   - scenario comparison
   - uncertainty bands
   - simulated interventions

9. Sustainability & Ledger Surface
   - D', G', SER
   - DeltaDeltaSER
   - closure residual
   - off-gas / leachate metering availability
   - energy / water / GHG overlays
   - evidence-level badge

## Chart expectations
Prefer explicit mappings from concept to visualization:
- `SER / D' / G'` -> KPI cards + trend chart + comparison bars
- boundary ledger -> Sankey / waterfall / ledger table
- release decision -> stepper / decision rail / badge cluster
- flight envelope -> radar / diamond / quadrant envelope chart
- portability outcomes -> matrix heatmap
- uncertainty -> violin / interval bands / fan chart
- Control-API versioning -> diff cards / before-after inspector
- batch lifecycle -> interactive event timeline
- proxy + state estimation -> dual-axis trace with trigger marker

Every chart must have a text fallback and exact-value tooltips.

## Failure modes are first-class
Never bury these:
- signal black-box drift,
- HAL or latent-heat loophole,
- contaminant carryover,
- kernel fidelity loss,
- shelf-life decay,
- waste-state drift,
- boundary mismatch,
- sensor fouling / proxy drift,
- thermal collapse,
- executor incompatibility,
- inhibitory co-extracts,
- unmetered sustainability claims.

Represent failure with explicit states and mitigation actions.

Preferred state grammar:
- `PASS`
- `WARN`
- `FAIL`
- `REQUALIFY`
- `PASS_WITH_GAIN`
- `OUT_OF_ENVELOPE`
- `INSUFFICIENT_EVIDENCE`
- `PLANNED_NOT_VALIDATED`

## Release / reject / requalify workflow
Every release-relevant flow should follow a predictable sequence:

1. ingest or update batch,
2. validate feedstock state,
3. attach or generate SignalBatch,
4. check potency / QC,
5. check Control-API envelope,
6. check locality profile,
7. compute release decision,
8. emit machine-readable audit packet,
9. expose operator-facing rationale,
10. store versioned decision record.

If any critical axis is missing, prefer `INSUFFICIENT_EVIDENCE` over false
confidence.

## How Codex should work in this repo

### Before changing code
Codex should:
- inspect repo structure,
- identify what is already real,
- map missing BOS surfaces,
- separate validated product surface from aspirational ideas,
- choose the smallest high-value vertical slice.

### While changing code
Codex should:
- preserve the current architecture where sensible,
- prefer typed interfaces,
- add missing domain objects instead of stuffing logic into generic blobs,
- keep premium UI and audit logic coordinated,
- surface uncertainty clearly,
- document migration impacts.

### After changing code
Codex should report:
- what changed,
- why it changed,
- which BOS invariant it supports,
- what is validated versus planned,
- what remains risky,
- how it was tested.

## High-value next slices for this repo
Given the current route and page inventory, the highest-value BOS upgrades are:
- typed SignalBatch / ControlAPIProfile / ReleaseDecision contracts,
- a Batch Command Center that unifies batch state, release state, and evidence,
- a Signal Lab page with potency / MTT / HAL / stability panels,
- a Portability Matrix with explicit FAIL pathways,
- audit packet generation tied to release decisions,
- a flight-envelope gate that exposes rationale, blockers, and mitigation.

## Done criteria
A change is meaningfully done when it improves at least one of the following
without degrading truthfulness:
- auditability,
- operator visibility,
- release integrity,
- accounting integrity,
- locality-aware control,
- premium usability,
- portability reasoning,
- runtime clarity.

"Looks sophisticated" is not enough.
"Scientifically honest, operationally useful, and visually elite" is the bar.

## Anti-patterns
Avoid:
- giant generic dashboards with no domain semantics,
- hard-coded thresholds without versioning,
- hidden spreadsheet formulas,
- untyped JSON blobs for core contracts,
- UI that shows SER but hides D' / G' / residuals,
- claiming portability without FAIL pathways,
- pretending closed-loop control is already wet-lab validated,
- making the interface glossy but unauditable,
- over-animating critical decision views,
- collapsing biological truth into vague "AI optimization".

## Default execution heuristic
When in doubt, build the next thing that most cleanly upgrades BOS from:
- narrative -> contract,
- contract -> stateful workflow,
- workflow -> operator surface,
- operator surface -> auditable release system,
- auditable release system -> premium industrial product.

## Local skill guidance
When local project skills are available, prefer:
- `$gstack-bos-director` for broad BOS delivery, next-slice selection, and end-to-end project momentum.
- `$andrej-karpathy-codex` for implementation discipline and verification.
- `$bos-audit` when the slice changes BOS truth, evidence, release logic, portability, or audit surfaces.
- `$bos-premium-ui` when the slice changes operator-facing UX or dashboard quality.

Preferred compositions:
- broad BOS push: `$gstack-bos-director` + downstream BOS skills as needed
- broad BOS push with self-review loops: `$gstack-bos-director` + `$tbc-autonomy-loop` + downstream BOS skills as needed
- audited BOS build: `$gstack-bos-director` + `$bos-audit` + `$andrej-karpathy-codex`
- premium BOS surface: `$gstack-bos-director` + `$bos-premium-ui` + `$andrej-karpathy-codex`
- premium audited BOS surface: `$gstack-bos-director` + `$bos-audit` + `$bos-premium-ui` + `$andrej-karpathy-codex`
