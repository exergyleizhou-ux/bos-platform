# Phase A — V5 API Freeze

> **Frozen 2026-05-17.** This document records the Phase A API
> contract baseline and the drift-detection workflow that protects it.

## What is frozen

Five V5 endpoints under `/api/v1/*`, all `POST`, all stateless:

| Endpoint | Paper map | Schema version |
|---|---|---|
| `/api/v1/ser/compute` | Eq. 1–3, 7 | `A.1` (in `schemas/ser.py`) |
| `/api/v1/sfi/check` | Eq. 5–6 | `A.2` (in `schemas/sfi.py`) |
| `/api/v1/relay/simulate` | M1→M2→M3 relay | `A.3` (in `schemas/relay.py`) |
| `/api/v1/mc/propagate` | Eq. 7 (generic) | `A.4` (in `schemas/mc.py`) |
| `/api/v1/twin/run` | Stateless EKF run | `A.5` (in `schemas/twin.py`) |

Plus three **D1 sunset** legacy endpoints (kept callable until 2027-05-17):

- `POST /api/v1/twin/{twin_id}/predict` &nbsp;`deprecated=True`
- `POST /api/v1/twin/{twin_id}/update` &nbsp;`deprecated=True`
- `POST /api/v1/twin/{twin_id}/simulate` &nbsp;`deprecated=True`

## Artefacts

| Path | Role |
|---|---|
| `_reports/phase_a_openapi_snapshot.json` | Deterministic JSON dump of the frozen surface (8 paths + 40 transitive schemas; ~82 KB) |
| `backend/scripts/freeze_phase_a_openapi.py` | Helper that regenerates the snapshot from the live app |
| `backend/tests/contract/test_phase_a_openapi.py` | Contract + drift tests (17) that gate the snapshot |

## Frozen surface guarantees

The contract tests enforce all of the following on every `pytest`:

1. **Path existence** — all 5 V5 paths + 3 D1 sunset paths exist as `POST`.
2. **Required-field floor** — every request schema retains the paper-mandated fields:
   - `/ser/compute`: `dm_in`, `dm_out`, `n_in`, `n_rec`, `d_prime`, `g_prime`, `species_code`
   - `/sfi/check`: `species_code`, `measurements`
   - `/relay/simulate`: `initial_state`, `relay_config`, `horizon_steps`, `dt_hours`, `species_code`
   - `/mc/propagate`: `inputs`, `target_func`, `target_func_config`
   - `/twin/run`: `initial_state`, `inputs`
3. **Response-field floor** — every response schema retains the audit fields (e.g. `engine_version`, `evidence_level`, …).
4. **Paper-strict numeric ranges** preserved in OpenAPI:
   - `d_prime ∈ [0, 1]` (Eq. 3)
   - `ser_point ∈ [0, 1]` (Eq. 1)
5. **Literal sets** preserved:
   - SFI `zone ∈ {safe, caution, danger, out_of_envelope}`
   - MC `target_func ∈ {ser, sfi_score, relay_final_state, custom}`
   - Relay `BoundaryLedger.stage ∈ {M1, M2, M3}`
6. **D1 sunset** — all 3 legacy twin compute endpoints carry `deprecated=True` in OpenAPI.
7. **Drift detection** — per-endpoint request/response property keys + `required` lists are diffed against the snapshot. Any addition or removal trips the test with a precise message.

## Drift workflow

When you change a Phase A schema or route:

1. Make the code change.
2. Run `pytest backend/tests/contract/test_phase_a_openapi.py` from the repo root.
3. **If the diff is intentional**:
   - Re-run `python backend/scripts/freeze_phase_a_openapi.py` to regenerate the snapshot.
   - Commit the schema change and the regenerated snapshot together.
   - Update this freeze doc's "What is frozen" table if a schema version bumped.
4. **If the diff is unintentional**:
   - Read the test failure (it names the added/removed field, the path, the schema).
   - Fix the underlying schema/router code.
   - Re-run tests — they should be green without touching the snapshot.

Never regenerate the snapshot to "make the tests pass" without also reviewing what changed.

## Coverage stats (at freeze time, 2026-05-17)

| Layer | Count |
|---|---|
| Schemas in `schemas/{ser,sfi,relay,mc,twin}.py` | 35+ Pydantic classes, ~2 200 LoC |
| Engine code in `engine/core/{sfi,relay,monte_carlo}_engine.py` (Phase A additions) | ~1 300 LoC (orchestration only; no physics rewrites) |
| Phase A unit + integration tests | 190 (full regression in 47.83 s) |
| Phase A contract tests | 17 (full regression in 19.14 s) |

## Decisions referenced

| Plan v2 decision | How it shows up in the freeze |
|---|---|
| **D1** Coexist + sunset | 3 legacy twin endpoints `deprecated=True`; other 4 V5 paths are new and coexist with V9 routes that keep their own URLs |
| **D2** Strict schemas | `ge / le / gt / lt / pattern / examples` survive in OpenAPI (verified by `test_ser_request_d_prime_bounded_unit_interval` etc.) |
| **D3** In-memory state | Out of scope for the API freeze (Phase A state lives in the agent, not Core) |
| **D4** HTTP REST + async | The freeze captures the REST surface; async is a Core implementation detail and not part of the wire contract |
| **D5** SER→SFI→Relay→MC→Twin order | Honoured: snapshot contains exactly those 5 endpoints, schema versions A.1 → A.5 in implementation order |

## Next step

Phase A2 (this batch) is **closed**. The freeze is the precondition
for Phase A3 (Agent skeleton implementation), which will consume the
frozen OpenAPI snapshot to seed `backend/agent/schemas/*` mirror
files (per Plan v2 §3.4 schema-parity rule).
