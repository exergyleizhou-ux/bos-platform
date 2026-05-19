# ⚠️ Quarantined: B4 v1 root `agent/` directory

This directory was created as part of Phase B Batch B4 v1
(commit `ddcbc24`, Phase B Steps 1-2/8) under the incorrect
assumption that the BOS Agent service was net-new in the
repository.

**The actual BOS Agent service is at `backend/agent/`**
(Phase A A.3 ship, 2089 LoC, FastAPI on port 8001, LangGraph
StateGraph with 6 nodes wired: `router`, `ser`, `sfi`, `relay`,
`cyber_lab`, `render`). B4 v2 extends *that* service in-place
instead of duplicating it here.

## Status

- **Quarantined**: do not extend, do not run.
- **Tests**: the 48 tests under `agent/tests/` (isolation +
  schema parity) still pass, but they validate the duplicate
  surface, not anything that ships to production.
- **Files**: 14 `.py` modules / ~1474 LoC of Phase B causal
  schemas + a minimal FastAPI stub — all duplicates of code that
  already exists or will exist under `backend/agent/`.

## Why kept (not deleted or reverted)

The `ddcbc24` commit is preserved as an audit trail of the
"Phase A precedent missed" mistake. A `git revert` would add a
destructive marker to the chain; leaving `ddcbc24` plus this
README is the more honest record.

Phase G may `git rm` this directory once B4 v2 is well-established
in `backend/agent/`. Until then, this stands as historical
reference.

## Authoritative B4 work

- Design: `_reports/PHASE_B_B4_v2_DESIGN.md`
- Implementation: in-place extensions to `backend/agent/`
  (Steps 1-4 per the v2 design, ~3-5 h adjusted)
- v1 design (frozen, do not extend):
  `_reports/PHASE_B_B4_DESIGN_v1_VOID.md`

## DO NOT

- Add new files to this directory.
- Reference this directory from B4 v2 code or tests.
- Treat `agent/main.py` here as the agent service entry point —
  the real entry is `backend/agent/main.py` (FastAPI app), run
  via `python -m agent.main` from inside `backend/`.
