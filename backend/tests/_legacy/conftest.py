"""Legacy test isolation.

Tests in this directory are deferred / sunset per:

- **Phase 0.5 / D5** — Code Cockpit subsystem deferred. Source files:
  ``test_code_router.py``, ``test_code_provider.py``,
  ``test_code_runtime_services.py``, ``test_bos_code_benchmark.py``.

- **Phase A / D1** — V1 endpoint sunset 2027-05-17. Source files:
  ``test_ser_router.py``, ``test_full_workflow.py``,
  ``test_dashboard_router.py``, ``test_users_router.py``,
  ``test_wechat_router.py``.

- **Phase 0 baseline ingestion artefact** — not in Phase A/B scope.
  Source files: ``test_reviewed_external_candidate_service.py``,
  ``test_external_sources_router.py``, ``test_bos_router.py``.

All tests in this directory are decorated with
``pytestmark = pytest.mark.skip(...)`` at module level. They are
kept in tree (via ``git mv``) for audit history but are excluded
from the active CI signal.

The originating decision is **Phase B Plan v2 / D13 = γ** (skip +
relocate). See ``_reports/PHASE_B_PLAN.md`` for the full rationale.
"""
