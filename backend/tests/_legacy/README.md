# Legacy tests

This directory holds **deferred** and **sunset** tests that are kept in tree for audit history but **skipped** in the active CI signal.

## Why

Per **Phase B Plan v2 / D13 = γ**:

- Phase 0.5 / D5 deferred the Code Cockpit subsystem.
- Phase A / D1 sunset the V1 endpoint surface (sunset date: 2027-05-17).
- A handful of Phase 0 baseline ingestion / brain-runtime tests are not in Phase A or Phase B scope.

Rather than delete these test files, we apply a module-level `pytest.mark.skip` and `git mv` them into `_legacy/`. This:

1. preserves file history (`git log --follow`),
2. removes them from the active CI signal (no spurious red),
3. keeps the audit trail (every skip-reason cites the originating decision).

## Inventory

| File | Originating decision | Skip reason |
|---|---|---|
| `test_code_router.py`                          | 0.5 / D5 | Code Cockpit subsystem deferred |
| `test_code_provider.py`                        | 0.5 / D5 | Code Cockpit subsystem deferred |
| `test_code_runtime_services.py`                | 0.5 / D5 | Code Cockpit subsystem deferred |
| `test_bos_code_benchmark.py`                   | 0.5 / D5 | Code Cockpit subsystem deferred |
| `test_ser_router.py`                           | A / D1   | V1 SER router superseded by `/api/v1/ser/compute`; sunset 2027-05-17 |
| `test_full_workflow.py`                        | A / D1   | V1 e2e workflow superseded by V5 contract; sunset 2027-05-17 |
| `test_dashboard_router.py`                     | A / D1   | V1 dashboard router; sunset 2027-05-17 |
| `test_users_router.py`                         | A / D1   | V1 users-router governance lane; not in Phase B scope |
| `test_wechat_router.py`                        | A / D1   | V1 wechat router; not in Phase B scope |
| `test_reviewed_external_candidate_service.py`  | Phase 0  | Baseline external-knowledge ingestion artefact |
| `test_external_sources_router.py`              | Phase 0  | Baseline external-sources router |
| `test_bos_router.py`                           | Phase 0  | Phase 0 brain-runtime document persistence |

Total: 12 files, 36 originally-failing tests.

## Restoring a legacy test

If a deferred subsystem is reactivated (e.g. Code Cockpit gets a real owner), the path is:

1. Remove the module-level `pytestmark = pytest.mark.skip(...)`.
2. `git mv` the file back to its original location under `tests/unit/`, `tests/integration/`, or `tests/e2e/`.
3. Fix what's broken; rebaseline.
4. Update this README to remove the entry.

## Not for

- Tests that are **flaky** — those belong in the active suite with
  proper `@pytest.mark.flaky` or a real fix.
- Tests that are **slow** — use `@pytest.mark.slow` and configure CI.
- Tests that are **WIP** — keep them at HEAD with `@pytest.mark.xfail`
  if the test exists but the feature is intentionally incomplete.
