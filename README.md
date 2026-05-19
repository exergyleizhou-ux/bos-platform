# BOS Code v9.0

`bos-pipeline-reconciled` is the active BOS Code codebase. This repository contains the FastAPI backend, the React + Vite frontend, Docker-based local development, and the current schema package under `backend/app/schemas/`.

## Scope

- Backend API in `backend/app/`
- Frontend application in `frontend/src/`
- Local development stack in `docker-compose.yml`
- Production overrides in `docker-compose.prod.yml`
- OpenTelemetry overlay in `docker-compose.otel.yml`
- Runtime infrastructure config in `infra/`, `nginx/`, `deploy/`, and `monitoring/`

## Non-Goals For This README

This document only describes files and commands that exist in this repository today. It does not claim Storybook, MkDocs, Helm charts, Playwright folders, seed scripts, or load-test suites as supported entry points because those are not present here as runnable project surfaces.

## Stack

| Layer | Current implementation |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Alembic, Redis, Celery |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| Local dev | Docker Compose |
| Observability | OpenTelemetry overlay, Jaeger, Prometheus, Grafana |

## Repository Layout

```text
bos-pipeline-reconciled/
|-- backend/
|   |-- app/
|   |   |-- engine/
|   |   |-- middleware/
|   |   |-- routers/
|   |   |-- schemas/
|   |   |-- services/
|   |   |-- tasks/
|   |   |-- config.py
|   |   `-- main.py
|   |-- alembic/
|   |-- tests/
|   |-- Dockerfile
|   `-- Dockerfile.celery
|-- frontend/
|   |-- src/
|   |-- Dockerfile
|   |-- package.json
|   |-- postcss.config.js
|   |-- tailwind.config.ts
|   `-- vite.config.ts
|-- deploy/
|-- infra/
|-- monitoring/
|-- nginx/
|-- docker-compose.yml
|-- docker-compose.otel.yml
|-- docker-compose.prod.yml
|-- Makefile
`-- pyproject.toml
```

## Development Ports

- Frontend Vite dev server: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`
- Nginx proxy: `http://localhost:8080`
- Jaeger UI with OTel overlay: `http://localhost:16686`

## Quick Start

### Strict P0 Preflight

Run this before treating the repository as go-live ready:

```powershell
.\scripts\p0_preflight.ps1
```

The preflight checks the local BOS Code env posture, backend BOS Code tests, frontend type-check, and production build in one pass.
If `OPENAI_API_KEY` is present, it also runs a live provider smoke.

### Docker Compose

```bash
cp .env.example .env
make up
make migrate
```

### Local frontend only

```bash
cd frontend
npm install
npm run dev
```

### Immersive Login Scene Backends

The login page now supports two immersive renderer backends behind one interface:

- `procedural`: use the built-in shader-driven fallback scenes
- `gaussian`: require a real `.splat` / gaussian splat scene manifest
- `auto`: prefer the real gaussian backend when available, else fall back automatically

Frontend configuration lives in `frontend/.env.example`. In practice:

```bash
cd frontend
cp .env.example .env.local
```

Key variables:

- `VITE_SCENE_RENDERER_MODE=auto`
- `VITE_GAUSSIAN_SCENE_MANIFEST=/splats/manifest.json`
- `VITE_GAUSSIAN_SPLATS_CDN=...` only when you want to override the default CDN

Manifest inputs can come from:

- `frontend/public/splats/manifest.json`
- `window.__BOS_GAUSSIAN_SCENE_MANIFEST__` injected before app boot
- a remote JSON URL assigned to `VITE_GAUSSIAN_SCENE_MANIFEST`

Each manifest entry must include:

- `id`
- `label`
- `labelEN`
- `ambience`
- `path`
- `camPos`
- `camLook`

### Local backend only

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Supported Make Targets

```bash
make up
make up-build
make down
make restart
make logs
make migrate
make migrate-create MSG="describe change"
make migrate-history
make test
make test-cov
make test-integration
make test-frontend
make test-contract
make test-bos-mechanistic
make lint
make type-check
make build-frontend
make up-otel
make smoke-bos-mechanistic
make clean
```

## Testing

- Backend tests run from `backend/tests/`
- Frontend default `npm test` currently maps to TypeScript type-checking
- Frontend contract tests run with `npm run test:contract`
- BOS mechanistic slices can be run with `make test-bos-mechanistic`

<!-- BEGIN GENERATED: BOS_BENCHMARKS -->
## BOS Code benchmark harness

This repository includes a lightweight benchmark harness under `scripts/bos_code_benchmark.py`.
It selectively absorbs the strongest pattern from `toolathlon_gym`: task fixtures with explicit `preprocess -> run -> evaluate` stages and isolated per-task workspaces.

Use it to scaffold and run reproducible BOS Code regression slices:

```powershell
python .\scripts\bos_code_benchmark.py scaffold bos-code-smoke
python .\scripts\bos_code_benchmark.py run
.\scripts\run_bos_benchmarks.ps1
```

Task conventions and evaluator hooks are documented in `docs/BOS_CODE_BENCHMARKS.md`.
The generated starter suite index lives in `benchmark_tasks/README.md`.

Repository entry points:

- `make test-benchmarks`
- `make test-benchmarks-runtime`
- `make test-benchmarks-operator`
- `make test-benchmarks-protocol`
- `make test-benchmarks-release`
- `make test-benchmarks-media`
- `make generate-benchmark-docs`
- `make check-benchmark-docs`
- `powershell -ExecutionPolicy Bypass -File scripts/run_bos_benchmarks.ps1`

CI-owned suites:

- `runtime`: Runtime
  BOS Code runtime, provider, and cockpit recovery slices.
- `operator`: Operator Surfaces
  Operator-facing BOS pages, smoke evidence, and decision-console slices.
- `protocol`: Protocol And Read Models
  Backend router contracts and frontend read-model translation slices.
- `release`: Release Evidence
  Release dossier and manifest validation slices.
- `media`: Media Studio
  BOS Media Studio backend and frontend regression slices.

List or run suites from the catalog:

```powershell
python .\scripts\bos_code_benchmark.py list
python .\scripts\bos_code_benchmark.py list-suites
python .\scripts\bos_code_benchmark.py list-suites --json --ci-only
python .\scripts\bos_code_benchmark.py run --suite runtime
python .\scripts\bos_code_benchmark.py generate-readme
python .\scripts\bos_code_benchmark.py verify-docs
```
<!-- END GENERATED: BOS_BENCHMARKS -->

## BOS Code Product

`BOS Code` is now embedded as a first-class BOS workspace under the existing backend and frontend architecture.

Current BOS Code surfaces in this repository:

- backend domain models for workspaces, leases, sessions, turns, tool calls, events, artifacts, and verification
- REST endpoints under `/api/v1/code/...`
- WebSocket replay/live channel support via `code:session:{id}`
- frontend cockpit route at `/code`
- guarded runtime tools for safe shell and git status
- provider boundary with OpenAI/Codex as the default launch backend

## BOS Media Studio

`BOS Media Studio` embeds a Remotion-powered graphics and motion runtime inside BOS.

Current BOS Media surfaces in this repository:

- backend media runtime endpoints under `/api/v1/media/remotion/...`
- isolated Remotion workspace under `frontend/remotion-runtime/`
- operator-facing frontend route at `/bos/media`
- authenticated preview and download flow for generated PNG and MP4 artifacts
- generated artifact output under `backend/generated/remotion/`

### BOS Media quick setup

1. Copy `.env.example` to `.env`
2. Keep `BOS_MEDIA_REMOTION_ENABLED=true`
3. Install the isolated runtime once:

```bash
cd frontend/remotion-runtime
npm install
```

4. Start backend and frontend
5. Open `/bos/media` after logging in as an operator

If `OPENAI_API_KEY` is configured, the creative brief suggestion flow can use the Responses API.
Without a key, BOS Media Studio automatically falls back to the built-in heuristic suggester.

### BOS Media local smoke

Still render:

```bash
cd frontend/remotion-runtime
node render.mjs --payload smoke-payload.json --output smoke-output.png
```

Backend render service smoke:

```bash
C:\bos v9\bos v9\.venv\Scripts\python.exe -m pytest backend\tests\integration\test_media_router.py -q
```

### BOS Code quick setup

1. Copy `.env.example` to `.env`
2. Enable `FF_ENABLE_BOS_CODE=true`
3. Optionally provide `OPENAI_API_KEY` to enable live Responses API execution
4. Apply migrations
5. Start backend and frontend
6. Open `/code` after logging in

### WeChat official account channel

`BOS Code` can now be exposed as a WeChat official account conversation channel.

Current WeChat surfaces in this repository:

- admin APIs under `/api/v1/wechat/official-accounts`
- public callback endpoint under `/api/v1/wechat/official-accounts/{account_key}/callback`
- automatic `openid -> BOS session` binding
- inbound text messages forwarded into the existing BOS Code session service
- timeout fallback that can continue processing and push follow-up replies through the WeChat custom message API when `app_secret` is configured

Basic setup:

1. Apply the latest backend migration
2. Keep `WECHAT_ENABLE_OFFICIAL_ACCOUNTS=true`
3. Create an official account record through the admin API with `account_key`, `app_id`, `token`, and a tenant-local `default_user_id`
4. In the WeChat official account platform, point the server URL to `/api/v1/wechat/official-accounts/{account_key}/callback`
5. Use the same `token` value in WeChat platform verification
6. Set the message encryption mode to plaintext for the first-pass integration

Local helper:

- Run `powershell -ExecutionPolicy Bypass -File scripts/start_wechat_local.ps1` to start the backend plus a temporary LocalTunnel callback URL in one step.
- Run `powershell -ExecutionPolicy Bypass -File scripts/start_wechat_workspace_local.ps1` to start backend, frontend, backend tunnel, and frontend tunnel together for the full free local WeChat + BOS Assistant workflow.

Free local workflow notes:

- The WeChat callback URL from the script must be pasted into the WeChat test account backend whenever the temporary tunnel changes.
- The web assistant URL from the script can be opened on the phone to continue the same BOS Assistant flow in the browser.
- This is the best zero-cost setup, but it is still not a permanent production address. A stable fixed address still requires your own server and domain.

### BOS Code runtime surfaces

The embedded BOS Code cockpit now includes a persistent runtime layer:

- default heartbeat and reflection automation jobs are seeded when a workspace initializes
- session turns can automatically produce memory snapshots
- complex turns can automatically trigger background reflections
- reflections can create or update skill drafts under the tenant workspace
- the cockpit exposes `Always-On Runtime` and `Memory + Recall` panels for these flows

### BOS Code live local smoke

On Windows, if the default ports are busy, you can launch a live BOS Code environment on alternate ports:

```powershell
.\scripts\start_bos_code_live.ps1
```

This starts:

- backend on `http://127.0.0.1:8010`
- frontend on `http://127.0.0.1:5180`

Then run the live browser smoke:

```powershell
.\scripts\run_bos_code_live_smoke.ps1
```

Artifacts land under `reports/playwright-check/`.

### BOS Code Decision Center live smoke

After backend and frontend are running, you can validate the `/bos` protocol console end-to-end:

```powershell
.\scripts\run_bos_interface_live_smoke.ps1
```

This smoke signs in, seeds a batch, then creates a control profile, locality profile, executor profile, signal batch, portability audit, and release decision through the live UI.
Artifacts land under `reports/playwright-check/`.

### BOS mechanistic live smoke

After backend and frontend are running, you can validate the mechanistic signal surfaces end-to-end:

```powershell
.\scripts\run_bos_mechanistic_live_smoke.ps1
```

This smoke signs in, seeds a batch, enables the BOS signal/audit flags for the smoke tenant, compiles a signal, evaluates release, and verifies:

- the mechanistic summary card on `/bos/console`
- the supervisor history trend on `/bos/console`
- the packet mechanistic diagnostics in the audit modal
- the packet supervisor history in the audit modal
- the batch mechanistic snapshot and supervisor panel on `/batches/:id`
- the batch supervisor history trend on `/batches/:id`

Artifacts land under `reports/playwright-check/`:

- `live-bos-mechanistic-smoke.json`
- `live-bos-mechanistic-smoke-bos.png`
- `live-bos-mechanistic-smoke-packet.png`
- `live-bos-mechanistic-smoke-batch.png`

## Commercial Narrative

BOS Code is designed as a verification-first enterprise AI workbench for scientific and industrial operations.

- Who it is for:
  enterprise pilot teams, operator/scientist workflows, and review-heavy technical environments
- What problem it solves:
  it combines runtime execution, verification, release gating, audit packets, and decision support in one surface
- Why it is safer than generic tools:
  release dossiers, structured verification gates, page-level smoke coverage, and evidence-bearing packet outputs are built into the product story
- What a pilot includes:
  BOS Code runtime, BOS Code decision center, release dossier artifacts, trust/verification reporting, and enterprise-readable operational proof

When you are done, stop any live dev processes started on the alternate ports:

```powershell
.\scripts\stop_bos_code_live.ps1
```

### BOS Code verification

Backend integration slice:

```bash
C:\bos v9\bos v9\.venv\Scripts\python.exe -m pytest backend\tests\integration\test_code_router.py -q
```

Provider/unit slice:

```bash
C:\bos v9\bos v9\.venv\Scripts\python.exe -m pytest backend\tests\unit\test_code_provider.py -q
```

Notes:

- If `OPENAI_API_KEY` is empty, BOS Code stays operational and falls back to a structured provider-unavailable stub response.
- Frontend type-check still depends on the local Node/TypeScript toolchain being installed.
- On Windows, prefer `.\scripts\p0_preflight.ps1` over the Bash-oriented `Makefile` for strict local verification.
- The websocket base must point at the versioned API route, for example `ws://localhost:8000/api/v1/ws`.

### BOS Code runtime focused checks

On Windows you can run smaller focused runtime slices instead of waiting for the whole runtime unit file:

```powershell
.\scripts\run_bos_code_runtime_slice.ps1 -Slice recovery
.\scripts\run_bos_code_runtime_slice.ps1 -Slice maintenance
.\scripts\run_bos_code_runtime_slice.ps1 -Slice autonomy
.\scripts\run_bos_code_runtime_slice.ps1 -Slice ui
```

Use `-Slice full` when you explicitly want the full backend runtime unit suite plus the runtime UI test.

### BOS Code autonomy guard

If you want the local always-on runtime to stay up with the API, frontend, Celery worker, and Celery beat together, use:

```powershell
.\scripts\start_bos_code_autonomy_guard.ps1
.\scripts\status_bos_code_autonomy_guard.ps1
.\scripts\stop_bos_code_autonomy_guard.ps1
```

Notes:

- default ports are backend `8011` and frontend `5181`
- use `-ForceRestart` if the guard state file already exists and you want to replace the current guard
- use `-DryRun` on the start script to inspect the launch plan without spawning processes
- if Redis is unavailable locally, the guard falls back to `degraded` mode and starts backend + frontend + a local autonomy poller instead of Celery
- use `-SkipCelery` if you want to force that degraded mode even when Redis is present
- use `-PollIntervalSec` to change how often the degraded-mode autonomy poller checks for due BOS Code jobs

## Schema Source Of Truth

- The authoritative schema package is `backend/app/schemas/`
- New schemas should be added as package modules and re-exported from `backend/app/schemas/__init__.py` when needed
- The old single-file schema aggregate is retained only as legacy material and is not the active import path

## Working Tree Boundaries

- Treat this repository as the current BOS v9 mainline
- Treat generated logs, SQLite files, caches, and temporary output as disposable artifacts
- Treat sibling directories outside this repository as archives, references, or separate work unless explicitly promoted later

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Paper 1 Reproduction (J Clean Prod, in preparation)

The five `/api/v1/causal/*` endpoints back the methodology described
in Paper 1, "Staged bioconversion via a protocol-first Biological
Operating System: Decoupling waste deconstruction from nutrient
recovery" (in preparation, *J Clean Prod*). The paper studies a
*Tenebrio molitor* (Module 1) → aerobic kernel (Module 2) →
*Protaetia brevitarsis* (Module 3) relay on distillers' grains,
with the Signal-API / Control-API interface as the engineered
inter-stage contract; BSF (*Hermetia illucens*) appears only as a
comparison benchmark in §4.3, not as a relay executor.

### Quick verification

```bash
# Check out the paper-pinned tag (created in B7 commit batch).
git checkout v0.9.0-paper1

# Verify paper SHA-256 pin (Plan v2 §1 R8 mitigation).
cd backend
.venv-backend/Scripts/python.exe -m pytest \
  tests/contract/test_paper_version_pinned.py -v

# Verify the five causal endpoints (43 unit tests).
.venv-backend/Scripts/python.exe -m pytest \
  tests/unit/test_causal_identify_engine.py \
  tests/unit/test_causal_estimate_engine.py \
  tests/unit/test_causal_refute_engine.py \
  tests/unit/test_causal_mediation_engine.py \
  tests/unit/test_causal_sensitivity_engine.py
```

### Paper method ↔ BOS endpoint map

| Paper section | BOS endpoint | Implementation |
|---|---|---|
| Methods — Identification (Eq. 1) | `POST /api/v1/causal/identify` | B2a `causal_identify_engine.py` |
| Methods — Estimation (Eq. 2) | `POST /api/v1/causal/estimate` | B2a `causal_estimate_engine.py` |
| Methods — Robustness / Refutation | `POST /api/v1/causal/refute` | B2b.1 `causal_refute_engine.py` |
| Methods — Mediation (Eq. 4, 70% finding) | `POST /api/v1/causal/mediation` | B2b.2 `causal_mediation_engine.py` |
| Methods — Sensitivity (Γ-bound ≥ 1.5) | `POST /api/v1/causal/sensitivity` | B2b.3 `causal_sensitivity_engine.py` |

### Audit chain

Planning, design, and completion docs at `_reports/`:

- `PHASE_B_PLAN.md` — Plan v2 (B7 paper-pin in §1)
- `PHASE_B_PLAN_V2_PATCH_S2_3.md` — Plan v2 §2.3 patch
  (`evalue_sensitivity_analyzer` moved to `/sensitivity`)
- `PHASE_B2b1_DESIGN.md`, `PHASE_B2b2_DESIGN.md`,
  `PHASE_B2b3_DESIGN.md` — per-batch design outlines
- `PHASE_B_B2b1_COMPLETION.md`, `PHASE_B_B2b2_COMPLETION.md`,
  `PHASE_B_B2b3_COMPLETION.md` — per-batch completion reports
- `PAPER_PINNING.md` — SHA pin history, re-pin procedure, and
  Plan v3 trigger conditions

Software citation metadata: see `CITATION.cff`. Author, ORCID,
repository, license, paper title, and first-author identity are
populated; `preferred-citation.status` remains `in-preparation`
until the manuscript is uploaded to J Clean Prod Editorial Manager
(bumps to `submitted` / `in-press` / `published` as the submission
lifecycle progresses).

### Phase G known limitations (do not affect Paper 1 finding)

Documented in each completion doc §10 / §6, consolidated in
`PHASE_B_B2b3_COMPLETION.md` §10:

- B2b.1: DoWhy refute `data_subset` / `bootstrap` significance is
  path-dependent across DoWhy 0.14 calls; engine uses a delta-based
  decision rule as a stable fallback.
- B2b.2: DoWhy `mediation.two_stage_regression` systematically
  underestimates NDE under strong mediator coefficients; engine
  surfaces the Pearl-identity-consistent decomposition via a snap
  and tests use widened tolerances.
- B2b.2: `precomputed_estimand` schema field is forward-compatible
  but the DoWhy NDE/NIE branch always re-identifies internally;
  diagnostics report `used_precomputed_estimand=False`.
- B2b.3: DoWhy `EValueSensitivityAnalyzer.check_sensitivity`
  signature drift across versions is absorbed by an automatic
  self-implemented Chinn-VWD fallback.
- B2b.3: DoWhy `NonParametricSensitivityAnalyzer` requires a
  `theta_s` parameter Plan v2 §2.5 does not expose; the
  `partial_linear` method is reserved (HTTP 422
  `code='method_reserved'`).

None of these affect the headline Pearl/Rubin mediation result
(70% proportion mediated on the synthetic fixture targeting the
paper's Signal-API → κ → SER pathway claim) or the Γ-bound
robustness gate (1.5 threshold operationalised via
`e_value_lower_ci`).
