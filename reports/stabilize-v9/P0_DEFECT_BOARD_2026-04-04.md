# BOS P0 Defect Board (2026-04-04)

> Baseline source logs:
> - `reports/stabilize-v9/baseline_pytest.log`
> - `reports/stabilize-v9/baseline_frontend_typecheck.log`
> - `reports/stabilize-v9/baseline_frontend_lint.log`
> - `reports/stabilize-v9/baseline_frontend_build.log`

## Current Failure Summary
- Backend pytest: **69 failed + 9 errors + 209 passed**
- Frontend type-check: **69 errors**
- Frontend lint: **91 errors + 22 warnings**
- Frontend build: **pass**
- Migration chain: **single head achieved** (`004_digital_twins`)

## Board
| ID | Priority | Item | Current State | Owner | Deadline | Notes |
|---|---|---|---|---|---|---|
| DB-001 | P0 | Alembic multi-head convergence | Done | BE Platform (TBD) | 2026-04-04 | `alembic heads` now single head |
| DB-002 | P0 | Empty PostgreSQL DB migrate drill | Blocked | DevOps (TBD) | 2026-04-06 | Docker daemon unavailable in current session |
| BE-001 | P0 | Core flow API contract fixes (auth/batch/ser/dashboard) | Open | BE API (TBD) | 2026-04-07 | Validation mismatches cause 4xx/5xx test failures |
| BE-002 | P0 | Core flow backend tests green | Open | BE QA (TBD) | 2026-04-08 | Detailed failing cases in `backend_failed_tests.txt` |
| FE-001 | P0 | Type contract alignment with backend | Open | FE API/Types (TBD) | 2026-04-08 | 69 TS errors |
| FE-002 | P0 | ESLint error cleanup (main flow first) | Open | FE Core (TBD) | 2026-04-09 | 91 lint errors |
| CI-001 | P0 | CI script mismatch (`npm run test`) | Done | DevEx (TBD) | 2026-04-04 | Added `test` script + CI chain fix |
| CI-002 | P0 | CI full green (all gates passing) | Open | DevEx + BE + FE (TBD) | 2026-04-10 | Workflow logic fixed, code quality still red |
| CD-001 | P0 | CD real deploy action for staging | Open | DevOps (TBD) | 2026-04-10 | `cd.yml` still uses echo/commented deploy |
| OPS-001 | P0 | Production config hardening (secret required, no sqlite fallback) | Open | SRE/Security (TBD) | 2026-04-11 | Needed before go-live |

## Detailed Backend Failure List
- File: `reports/stabilize-v9/backend_failed_tests.txt`
- Entries: **78** (69 failed + 9 errors)
