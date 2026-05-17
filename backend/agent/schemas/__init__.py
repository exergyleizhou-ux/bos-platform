"""BOS Agent - schema mirrors of the V5 contracts.

These files are hand-authored copies of the Phase A schemas defined in
``app/schemas/{ser,sfi,relay,mc,twin}.py``. They live here so the
agent process can validate Core requests/responses without importing
``app.*`` (Plan v2 paragraph 3.4 isolation rule).

Every mirror module carries a ``SCHEMA_VERSION = "A.N"`` constant that
MUST equal the Core-side version. A test in ``agent/tests`` reads both
constants via reflection and fails on drift.
"""
