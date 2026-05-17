# Phase B / B0.3 — Completion report

> **Batch.** B0.3 — Baseline test cleanup (Plan v2 / D13 = γ implementation).
> **HEAD at start.** `b962e58` (post Phase A6 / handoff).
> **HEAD at end.** `b962e58` — **uncommitted** (waits for user confirmation).
> **Date.** 2026-05-17.
> **Predecessor decision.** Plan v2 §4 D13 = γ skip + relocate.

## Goal

Stop the 36 baseline failures from polluting the active CI signal
*without* deleting code that may be reactivated later.

## Outcome

| Metric | Before B0.3 | After B0.3 | Δ |
|---|---|---|---|
| **Total tests collected** | 925 | 925 | 0 |
| **Passed** | 888 | 754 | -134 |
| **Failed** | 36 | **0** | **-36** ✓ |
| **Skipped** | 1 | 171 | +170 |
| Phase A subset (`-k phase_a`) | 217 PASS | 217 PASS | 0 ✓ |
| Wall-clock | 724.71 s | 369.63 s | -354.92 s (faster because skipped tests don't run) |

**Acceptance** (Plan v2 §7 #9 *"Baseline floor stable after D13"*): **PASS**.

## What changed

### New directory

```
backend/tests/_legacy/
├── __init__.py
├── README.md                  (12-row inventory + restore protocol)
├── conftest.py                (rationale + decision citations)
├── test_bos_code_benchmark.py
├── test_bos_router.py
├── test_code_provider.py
├── test_code_router.py
├── test_code_runtime_services.py
├── test_dashboard_router.py
├── test_external_sources_router.py
├── test_full_workflow.py
├── test_reviewed_external_candidate_service.py
├── test_ser_router.py
├── test_users_router.py
└── test_wechat_router.py
```

### File migrations (`git mv`)

All 12 fail-source files moved via `git mv` (rename detected by git — verified with `git status` showing `R` prefix on each line):

| Old path | New path |
|---|---|
| `backend/tests/unit/test_bos_code_benchmark.py` | `backend/tests/_legacy/test_bos_code_benchmark.py` |
| `backend/tests/integration/test_bos_router.py` | `backend/tests/_legacy/test_bos_router.py` |
| `backend/tests/unit/test_code_provider.py` | `backend/tests/_legacy/test_code_provider.py` |
| `backend/tests/integration/test_code_router.py` | `backend/tests/_legacy/test_code_router.py` |
| `backend/tests/unit/test_code_runtime_services.py` | `backend/tests/_legacy/test_code_runtime_services.py` |
| `backend/tests/integration/test_dashboard_router.py` | `backend/tests/_legacy/test_dashboard_router.py` |
| `backend/tests/integration/test_external_sources_router.py` | `backend/tests/_legacy/test_external_sources_router.py` |
| `backend/tests/e2e/test_full_workflow.py` | `backend/tests/_legacy/test_full_workflow.py` |
| `backend/tests/unit/test_reviewed_external_candidate_service.py` | `backend/tests/_legacy/test_reviewed_external_candidate_service.py` |
| `backend/tests/integration/test_ser_router.py` | `backend/tests/_legacy/test_ser_router.py` |
| `backend/tests/integration/test_users_router.py` | `backend/tests/_legacy/test_users_router.py` |
| `backend/tests/integration/test_wechat_router.py` | `backend/tests/_legacy/test_wechat_router.py` |

### Per-file edits

Each file got a module-level `pytestmark = pytest.mark.skip(reason=...)` block inserted right after its top-of-file imports. The reason cites the originating decision (0.5/D5, A/D1, or Phase 0 baseline). Three files required a fix-up: the initial insertion placed `pytestmark` *after* the first `class Foo:` line which Python parsed as an empty class body + a top-level statement (IndentationError). Fixed by moving `pytestmark` *before* the class definitions in `test_ser_router.py`, `test_full_workflow.py`, `test_dashboard_router.py`.

**Total content change**: 12 files × ~3 LoC inserted per file ≈ 36 net LoC added. No test method bodies were modified.

## Verification

### Per-suite check

| Suite | Command | Result |
|---|---|---|
| Legacy subset | `pytest tests/_legacy/ -q` | **170 skipped** in 0.61 s |
| Phase A subset | `pytest tests/ agent/tests/ -k "phase_a" -q` | **217 passed, 708 deselected** in 50.64 s |
| Full backend | `pytest tests/ agent/tests/ -q` | **754 passed, 171 skipped, 0 failed** in 369.63 s |

### Sanity counts

- 754 active passing tests + 170 legacy-skipped tests + 1 pre-existing skip = **925 total** ✓ (same as B0.3-start)
- 0 active failures ✓
- 217 Phase A tests untouched ✓ (validated independently via `-k phase_a`)
- 12 files renamed, git tracking preserved (`git log --follow backend/tests/_legacy/test_code_router.py` traces back to the Phase 0.5 baseline commit `9586586`)

## Impact analysis

- **No Phase A test moved.** Confirmed by Phase A subset PASS = 217.
- **No active feature broken.** None of the 754 still-active tests changed status.
- **134 passing tests now hidden behind module-level skip.** These belong to the same files as the 36 failures (e.g. `TestCodeRouter` has 6 passing methods alongside its 16 failing methods). When the parent subsystem reactivates, removing the module skip recovers them in one operation.
- **CI signal honesty.** A future reader of `pytest tests/` now sees `754 passed, 171 skipped, 0 failed` — the deferral state is auditable via the skip-reasons rather than hidden under a permanently-red bar.

## Workspace state

```
RM backend/tests/_legacy/test_bos_code_benchmark.py          (renamed + skip-marker added)
RM backend/tests/_legacy/test_bos_router.py                  (renamed + skip-marker added)
RM backend/tests/_legacy/test_code_provider.py               (renamed + skip-marker added)
RM backend/tests/_legacy/test_code_router.py                 (renamed + skip-marker added)
RM backend/tests/_legacy/test_code_runtime_services.py       (renamed + skip-marker added)
RM backend/tests/_legacy/test_dashboard_router.py            (renamed + skip-marker added)
RM backend/tests/_legacy/test_external_sources_router.py     (renamed + skip-marker added)
RM backend/tests/_legacy/test_full_workflow.py               (renamed + skip-marker added)
RM backend/tests/_legacy/test_reviewed_external_candidate_service.py
RM backend/tests/_legacy/test_ser_router.py                  (renamed + skip-marker added)
RM backend/tests/_legacy/test_users_router.py                (renamed + skip-marker added)
RM backend/tests/_legacy/test_wechat_router.py               (renamed + skip-marker added)
?? backend/tests/_legacy/__init__.py
?? backend/tests/_legacy/conftest.py
?? backend/tests/_legacy/README.md
?? _reports/PHASE_B_B0_3_FAILING_TESTS.md
?? _reports/PHASE_B_B0_3_COMPLETION.md
```

**No** changes outside `backend/tests/`. No Phase A backend code touched. No `backend/requirements.txt` touched. No frontend touched. No commit yet (per task brief: *"留给用户决定 commit 时机"*).

## Effort vs estimate

| Phase | Estimated | Actual | Notes |
|---|---|---|---|
| Step 1 — locate fails | 15 min | ~10 min | Re-ran full regression for definitive list; previous reconciliation showed only 24 due to stdout buffering — actual is 36 across 12 files (2 files were truncated last time) |
| Step 2 — create `_legacy/` | 5 min | ~5 min | + README.md (not in Plan v2 §B0.3 but adds audit trail) |
| Step 3 — git mv + marker | 1.5 h | ~25 min | Used a single Python loop to insert markers across all 12 files; 3 follow-up fix-ups for `pytestmark`-after-`class` IndentationError |
| Step 4 — verify | 15 min | ~10 min (incl. full-regression wait) | Phase A subset + legacy subset + full regression |
| Step 5 — docs | 15 min | ~15 min | Two reports |
| **Total** | **~2.5 h** | **~1 h** | Faster than estimate; Plan v2's 2× efficiency assumption proves conservative for this batch (mostly mechanical work) |

## Findings worth flagging

1. **Two failing files were invisible in the previous reconciliation.** `tests/e2e/test_full_workflow.py` (3 fails) and `tests/integration/test_bos_router.py` (1 fail) account for exactly the 12 "missing" failures from the earlier 24-vs-36 mismatch. Cause: pytest's `-q --tb=no` short summary output got truncated by Windows pipe buffering on the previous full-regression run.

2. **`pytest.ini` had `-x` in `addopts`** — exit on first failure. To get the full picture during reconciliation we had to override with `-o "addopts="`. The Plan v2 §B5 acceptance gates should call this out so future regressions don't get artificially short-circuited.

3. **`backend/.venv-backend-tests` venv is broken** on the current host — its `pyvenv.cfg` hard-codes a `home` path with mojibake (`���ĵİ�ľľ`) from a different user-dir encoding. The full regression runs under the host-level `C:/Users/10420/AppData/Local/Programs/Python/Python312/python.exe` instead, which has BOS deps installed globally. **Not a B0.3 blocker** but worth noting for B0.5 (numpy audit) — that batch will need a clean venv.

## Next steps

- User reviews this report.
- User decides commit-message + commit timing. Suggested:

```
feat: Phase B B0.3 — relocate 36 baseline failures to tests/_legacy/

12 fail-source files moved via `git mv` to backend/tests/_legacy/
and decorated with module-level `pytestmark = pytest.mark.skip(...)`
citing originating Phase 0.5/D5 (Code Cockpit, 4 files),
Phase A/D1 (V1 sunset, 5 files), and Phase 0 baseline (3 files).

Active CI signal: 754 PASS / 171 SKIP / 0 FAIL (was 888/1/36).
Phase A subset (-k phase_a) unchanged at 217 PASS / 0 FAIL.

Implements Phase B Plan v2 D13 = γ.
```

- After commit, user picks the next batch — **B0.5** (numpy audit) and **B0.7** (DAG library) are now both unblocked and can run in parallel.

**End of B0.3 completion report.**
