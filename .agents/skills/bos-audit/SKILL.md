# BOS Audit Skill
## Build an audit-ready, premium BOS control surface

This file is adapted from `bos_codex_pack` for the current
`bos-pipeline-reconciled` repository.

## Purpose
Use this skill when the repository needs to be upgraded toward a real BOS
platform rather than a loose mixture of manuscript ideas, scripts, and generic
dashboards.

This skill translates BOS into an implementation that is:
- protocol-first,
- interface-explicit,
- boundary-aware,
- release-gated,
- operator-visible,
- and visually premium.

This skill is especially appropriate when the user asks for:
- BOS hardening,
- BOS audit system design,
- Control-API formalization,
- Signal-API release workflow,
- premium dynamic UI,
- dashboard / digital twin / flight envelope surfaces,
- or Codex-ready BOS architecture work.

## When to use
Use this skill if one or more are true:
- the repo has BOS concepts but weak productization,
- the repo lacks typed release contracts,
- accounting and UI are disconnected,
- BOS terms exist only in prose and not in code,
- the system needs PASS / FAIL / REQUALIFY logic,
- the UI feels ordinary or static,
- the user wants a high-end dynamic operator cockpit,
- portability, locality, or flight-envelope logic is missing,
- or the repo needs a manuscript-faithful but product-grade BOS surface.

Do not use this skill for trivial copy edits or unrelated CRUD work.

## Core idea
Treat BOS as a five-surface system:
1. biological workflow,
2. interface contract,
3. accounting and evidence,
4. control and observability,
5. premium operator UI.

A good implementation does not merely "show BOS data." It makes BOS
inspectable, auditable, actionable, and elegant.

## Non-negotiable truth rules
This skill must preserve the difference between:
- validated,
- supported but not closed,
- planned.

Never silently turn any of these into product claims:
- unique instruction molecule identified,
- universal executor portability,
- fully deployed wet-lab closed-loop control,
- complete industrial closure,
- full production qualification.

If a feature is a premium product direction rather than a manuscript-validated
fact, label it clearly in code comments, docs, or UI copy.

## What this skill should build or improve

### A. Contract surfaces
Create or strengthen explicit objects and APIs for:
- `SignalBatch`
- `ControlAPIProfile`
- `MTTCalibration`
- `ReleaseDecision`
- `LocalityProfile`
- `PortabilityAudit`
- `BoundaryLedger`
- `FlightEnvelopeCheck`
- `AuditPacket`

### B. Decision logic
Add machine-readable logic for:
- release,
- reject,
- requalify,
- pass-with-gain,
- insufficient evidence,
- out-of-envelope conditions.

### C. Premium UI surfaces
Prefer rich, dynamic, high-end pages such as:
- executive overview dashboard,
- batch command center,
- signal lab / interface console,
- Control-API studio,
- locality sheet editor,
- portability matrix,
- flight envelope gate,
- digital twin / forecast surface,
- sustainability and ledger surface.

### D. Evidence plumbing
Make sure every important view can trace back to:
- persisted records,
- typed contracts,
- engine outputs,
- release logic,
- and audit artifacts.

## Desired user experience
The result should feel like a premium industrial biotech cockpit.

Target qualities:
- clean,
- fast,
- information-dense,
- executive-grade,
- highly interactive,
- motion-enhanced,
- but still rigorous.

### UI style bar
Aim for:
- strong layout hierarchy,
- large KPI sections,
- polished cards and panels,
- smooth route and page transitions,
- subtle micro-animations,
- rich but legible charts,
- precise status badges,
- evidence drawers and diff views,
- purposeful real-time feeling.

### Motion bar
Motion should help the operator understand:
- state change,
- release progression,
- trigger events,
- comparison deltas,
- background job progress,
- and drill-down navigation.

Never use motion that slows decisions or hides important numbers.

## Suggested implementation choices for this repo
This repository already uses the preferred stack:
- React + TypeScript,
- Tailwind,
- React Query,
- Zustand,
- Recharts,
- Framer Motion,
- FastAPI,
- explicit engine and router layers.

Extend the current stack instead of adding a parallel UI or API framework.

## Required chart mappings
Map BOS concepts to visuals intentionally:
- `SER / D' / G'` -> KPI tiles + trend charts + compare mode
- boundary ledger -> Sankey + waterfall + exact table
- release state -> stepper + decision badge rail
- Control-API -> envelope cards + threshold table + version diff
- portability -> heatmap matrix
- locality -> editable parameter grid + drift warnings
- uncertainty -> interval bands / histogram / violin where appropriate
- digital twin -> proxy trace + trigger marker + scenario overlay
- flight envelope -> radar / diamond / quadrant gate visualization
- async jobs -> streaming job cards / progress states

All charts should support hover values, empty states, and loading skeletons.

## Workflow

### Step 1 - Recon the repo
Inspect:
- architecture,
- framework choices,
- existing domain model,
- existing dashboards,
- API patterns,
- async stack,
- telemetry surface,
- and what BOS concepts are real versus decorative.

### Step 2 - Build an evidence map
Classify what already exists into:
- validated BOS-aligned surface,
- partial / under-modeled surface,
- missing surface,
- speculative surface.

### Step 3 - Identify the next high-value vertical slice
Good slices include:
- Control-API typed workflow,
- release decision engine,
- audit packet generation,
- batch command center UI,
- locality sheet editor,
- portability matrix,
- flight envelope gate,
- signal lab with potency / MTT / HAL / stability panels.

Choose a slice that strengthens both truthfulness and operator usefulness.

### Step 4 - Model the domain first
Before polishing UI, create or harden:
- schema objects,
- persistence model,
- decision grammar,
- evidence tags,
- engine entry points.

### Step 5 - Implement the operator surface
Build a premium UI that makes the new domain surface obvious.
Do not dump raw tables and call it done.

### Step 6 - Add async / telemetry if required
If the slice requires recomputation or heavy export:
- add background job handling,
- add progress and result states,
- expose health and failure.

### Step 7 - Test and package the evidence
Add:
- unit tests for release logic,
- integration tests for routes,
- UI loading / error / empty states,
- clear summary of validated versus premium-aspirational behavior.

## Mandatory deliverables
A strong run of this skill should usually produce:

1. Domain upgrade
   - new or improved models and schemas for BOS concepts.

2. Decision upgrade
   - explicit PASS / FAIL / REQUALIFY / PASS_WITH_GAIN logic.

3. UI upgrade
   - at least one premium, dynamic operator-facing page.

4. Audit upgrade
   - visible trace from displayed value to stored record or engine output.

5. Narrative upgrade
   - concise explanation of what is validated, what is inferred, what remains
     future-facing.

## Minimum feature set for a premium BOS page
A page is not complete unless it includes most of the following:
- meaningful hero KPIs,
- current status badges,
- chart or visual summary,
- exact values on demand,
- loading state,
- empty state,
- error state,
- drill-down section,
- provenance / audit section,
- responsive layout,
- polished transitions.

## Preferred page blueprints

### 1. Batch Command Center
Must feel like a mission console.
Include:
- batch header,
- feedstock summary,
- SignalBatch card,
- Control-API card,
- release decision rail,
- event timeline,
- evidence tabs,
- operator note pane.

### 2. Signal Lab
Should feel like a premium assay plus release console.
Include:
- potency panel,
- MTT marker,
- HAL value and warning state,
- dwell-time / shelf-life chart,
- active-window summary,
- QC panel,
- release recommendation.

### 3. Flight Envelope
Should feel like a go/no-go mission gate.
Include:
- 4-axis envelope status,
- blockers list,
- mitigating actions,
- recent drift history,
- release recommendation,
- downloadable audit packet.

### 4. Portability Matrix
Should feel like an engineering compatibility board.
Include:
- executor rows,
- condition columns,
- PASS / PASS_WITH_RETUNING / FAIL heat cells,
- click-through rationale,
- notes on retuning and incompatibility.

## Interaction patterns to prefer
- drill-down drawers instead of navigation dead ends,
- compare mode for Control-API versions,
- sticky status rail for critical state,
- optimistic UI only when safe,
- streaming or progressive updates for background tasks,
- timeline scrubbers for batch lifecycle,
- animated delta badges for metric change,
- evidence popovers for any nontrivial KPI.

## Language rules for UI copy
Prefer language like:
- `Validated`
- `Supported, not identity-closed`
- `Planned`
- `Out of envelope`
- `Requalification required`
- `Insufficient evidence`

Avoid language like:
- `Solved`
- `Guaranteed`
- `Universal`
- `Fully autonomous`
- `Closed-loop proven` unless actually true.

## Failure handling
If the data or repo cannot support a claim, the skill must:
- degrade gracefully,
- label uncertainty clearly,
- keep the surface useful,
- and suggest the smallest missing piece.

Examples:
- no MTT data -> show `MTT not yet calibrated`
- no metering -> block sustainability release
- no locality sheet -> show `local requalification required`
- no executor evidence -> mark portability `unknown`

## What "done" looks like
This skill succeeds when the repo is more BOS-like in both substance and feel:
- more explicit contracts,
- better decision grammar,
- stronger operator surfaces,
- richer evidence plumbing,
- more premium UI,
- and fewer black boxes.

The best output is not merely "feature-rich." It should feel like a serious,
high-end, dynamic control system for a protocol-first biological platform.

## Output format for Codex after using this skill
When you finish, report in this structure:

### What I changed
List the main backend, frontend, and domain changes.

### BOS surfaces strengthened
State whether the work improved:
- interface,
- accounting,
- control,
- audit,
- UI,
- or observability.

### Evidence boundary
Explicitly separate:
- validated,
- supported,
- planned.

### UI upgrade summary
Describe the premium and dynamic surfaces added or improved.

### Remaining gaps
List the next highest-value missing BOS surfaces.

### Validation
State tests run, checks added, and any unverified assumptions.
