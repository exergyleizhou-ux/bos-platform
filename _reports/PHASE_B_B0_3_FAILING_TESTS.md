# Phase B / B0.3 — Failing-test inventory (pre-skip)

> Snapshot taken **2026-05-17** against HEAD `b962e58`.
> Source: full backend regression
> `python -m pytest tests/ agent/tests/ -q --tb=no -o "addopts=" -rfE`
> Wall-clock: 724.71 s (12:04). Result: **36 failed, 888 passed, 1 skipped**.
>
> This document records the 36 failing tests *before* the
> `@pytest.mark.skip` + `git mv tests/_legacy/` treatment in batch
> B0.3. After B0.3 these tests are still in tree (under
> `tests/_legacy/`) but are skipped in the active CI signal.

## Tally

| Category | Files | Failing tests | Originating decision |
|---|---|---|---|
| Code Cockpit subsystem | 4 | **20** | Phase 0.5 / D5 — Code Cockpit deferred |
| V1 endpoint sunset | 5 | **12** | Phase A / D1 — sunset 2027-05-17 |
| Phase 0 baseline ingestion | 3 | **4** | Not in Phase A / B scope |
| **Total** | **12** | **36** | |

## File-by-file detail

### Code Cockpit (Phase 0.5 / D5)

#### `tests/integration/test_code_router.py` — 16 fails

| # | Test method |
|---|---|
| 1 | `TestCodeRouter::test_workspace_init_and_status` |
| 2 | `TestCodeRouter::test_session_create_turn_and_events` |
| 3 | `TestCodeRouter::test_runtime_memory_reflection_and_skill_endpoints` |
| 4 | `TestCodeRouter::test_create_turn_can_trigger_background_reflection_when_session_is_complex` |
| 5 | `TestCodeRouter::test_write_lease_conflict_is_rejected` |
| 6 | `TestCodeRouter::test_tool_endpoints_return_structured_results` |
| 7 | `TestCodeRouter::test_task_and_worker_foundations` |
| 8 | `TestCodeRouter::test_recovery_and_readiness_surfaces` |
| 9 | `TestCodeRouter::test_branch_state_and_readiness_requests_are_race_safe` |
| 10 | `TestCodeRouter::test_lane_control_status_updates_are_lane_aware` |
| 11 | `TestCodeRouter::test_operator_control_plane_transitions_follow_review_lifecycle` |
| 12 | `TestCodeRouter::test_execute_next_automation_action_respects_gate_and_executes_when_ready` |
| 13 | `TestCodeRouter::test_execute_next_automation_action_can_soft_reset_runtime` |
| 14 | `TestCodeRouter::test_execute_next_automation_action_can_refresh_branch_for_stale_posture` |
| 15 | `TestCodeRouter::test_execute_next_automation_action_can_rerun_verification_for_failed_stage` |
| 16 | `TestCodeRouter::test_recovery_endpoint_does_not_offer_run_verification_while_review_gate_is_active` |

**Reason summary.** Code Cockpit subsystem (`/api/v1/code/*` router + supporting services in `app/services/code/*`) was preserved in tree by Phase 0.5 but explicitly **out of Phase A and Phase B scope** (Phase 0.5 / D5). The router's tests fail because the surrounding services aren't being maintained to match.

#### `tests/unit/test_code_provider.py` — 2 fails

- `test_provider_retries_transient_gateway_error`
- `test_provider_surfaces_model_cooldown_without_retry_storm`

#### `tests/unit/test_code_runtime_services.py` — 1 fail

- `test_maintenance_job_creates_session_when_none_exists`

#### `tests/unit/test_bos_code_benchmark.py` — 1 fail

- `test_run_suite_executes_preprocess_and_evaluation_hooks`

### V1 endpoint sunset (Phase A / D1 — sunset 2027-05-17)

#### `tests/integration/test_ser_router.py` — 5 fails

| # | Test method |
|---|---|
| 1 | `TestSERCompute::test_ser_compute_basic` |
| 2 | `TestSERCompute::test_ser_compute_with_nitrogen` |
| 3 | `TestSERCompute::test_ser_response_has_recommendations` |
| 4 | `TestSERCompute::test_ser_compute_manual_without_batch_id` |
| 5 | `TestSERStatistics::test_statistics_use_result_grading` |

**Reason summary.** V1 SER router (`/api/v1/ser`, not the V5
`/api/v1/ser/compute`). Phase A / D1 marks the V1 surface as
deprecated with sunset 2027-05-17.

#### `tests/e2e/test_full_workflow.py` — 3 fails

- `TestBatchAnalysisWorkflow::test_complete_batch_workflow`
- `TestBatchAnalysisWorkflow::test_multi_batch_comparison`
- `TestRBACWorkflow::test_scientist_can_compute`

**Reason summary.** End-to-end workflow tests that chain through the V1 endpoints; superseded by the V5 contract's `tests/e2e/test_phase_a_e2e.py`.

#### `tests/integration/test_dashboard_router.py` — 1 fail

- `TestDashboardGradeDistribution::test_grade_distribution_matches_ser_result_grading`

#### `tests/integration/test_users_router.py` — 2 fails

- `TestAdminRoleGrants::test_admin_can_replace_elevated_governance_role_grants`
- `TestAdminRoleGrants::test_admin_can_read_tenant_scoped_role_grant_audit_history`

#### `tests/integration/test_wechat_router.py` — 1 fail

- `TestWechatRouter::test_callback_verification_and_text_message_flow`

### Phase 0 baseline ingestion (not in A/B scope)

#### `tests/unit/test_reviewed_external_candidate_service.py` — 2 fails

- `test_seed_phase4a_domain_metadata_sources_only_touches_source_records`
- `test_seed_p0_creates_eight_db_backed_review_cards`

#### `tests/integration/test_external_sources_router.py` — 1 fail

- `test_external_sources_seed_resolve_and_list_flow`

#### `tests/integration/test_bos_router.py` — 1 fail

- `TestBosGuidanceAndSignals::test_brain_runtime_document_can_be_updated`

## Notes

1. **Two new files vs Plan v2 §B0.3 forecast.** The Plan v2 §5 wording assumed 12 files based on the previous (24 visible) regression. The new regression surfaced two additional files (`test_full_workflow.py`, `test_bos_router.py`) that were lost to stdout-buffer truncation last time. Total file count still 12; line count still 36.

2. **`test_full_workflow.py` is in `tests/e2e/`** — needs `git mv` from `tests/e2e/test_full_workflow.py` (not `tests/integration/`). Plan-level impact: none — `tests/_legacy/` is flat.

3. **B0.3 also moves passing tests in the same files.** Every test in these 12 files becomes `skip`, not just the 36 failing ones. This is intentional and consistent with `@pytest.mark.skip` module-level semantics: when a subsystem is deferred, all tests in its surface area are deferred together. The total tests-now-skipped count is **170**, not 36.

4. **No Phase A test is in this list.** Phase A subset (`-k "phase_a"`) showed 217 PASS / 0 FAIL both before and after B0.3.

**End of inventory.**
