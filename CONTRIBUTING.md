# Contributing to BOS Platform

Thank you for your interest in contributing. BOS Platform is
the scientific software underlying Paper 1 ("Staged
bioconversion via a protocol-first Biological Operating System
…", *J Clean Prod*, in preparation). Contributions are
welcome, with the following caveats specific to a
publication-backing repository.

## Before you contribute

1. Read `README.md` for an architectural overview.
2. Read `_reports/PAPER_PINNING.md` for the audit-chain
   contract between the manuscript and the engines.
3. Read `_reports/PHASE_B_PLAN.md` §1–§7 for the methodological
   scope of Phase B (the causal layer that backs the paper).
4. If your contribution touches any of the five
   `/api/v1/causal/*` endpoints, their schemas, or the paper-
   SHA pin: open a discussion issue before opening a pull
   request.

## What we accept

| Class | Examples | Path |
|---|---|---|
| Bug fixes | Off-by-one errors, type-narrowing fixes, deps pinning fixes | Direct PR, link the failing test |
| Documentation | README clarifications, audit-chain doc improvements, additional examples | Direct PR |
| Tests | Additional unit / contract / e2e coverage | Direct PR — do not modify existing pinned values |
| Feature additions (within Plan v2 scope) | New refuter, new estimator family in the reserved enum, additional `evidence_level` rules | Discussion issue first |
| Feature additions (outside Plan v2 scope) | Bayesian / Conformal / TMLE branches, Phase C+ work | Open a Plan v3 review document first (see PAPER_PINNING.md §5 branch B) |

## What we cannot accept without a re-pin

The following changes require the paper-SHA gate to be
re-evaluated (see `PAPER_PINNING.md` §4):

- Modifying any engine's behaviour on the matched-boundary
  fixture in a way that changes the headline numbers
  (ΔΔSER = 0.15, 70% proportion mediated, Γ-bound ≥ 1.5).
- Changing any `SCHEMA_VERSION` constant (`B.1` … `B.5`).
- Adding or removing an endpoint from the public surface
  (`/api/v1/causal/*`).
- Modifying the OpenAPI snapshot at
  `_reports/phase_b_openapi_snapshot.json` without a paired
  drift-gate test update.

If your contribution falls into any of these categories,
expect a longer review cycle. The audit chain is load-bearing
for the manuscript's evidence-level claims.

## Development setup

```bash
# Clone
git clone https://github.com/exergyleizhou-ux/bos-platform.git
cd bos-platform/backend

# Python 3.12.7, venv
python -m venv .venv-backend
.venv-backend/Scripts/activate   # Windows
# or: source .venv-backend/bin/activate

pip install -r requirements.txt

# Run the contract / unit / e2e gates that back the paper
python -m pytest tests/contract/test_paper_version_pinned.py \
                tests/contract/test_phase_b_openapi.py \
                tests/unit/test_causal_identify_engine.py \
                tests/unit/test_causal_estimate_engine.py \
                tests/unit/test_causal_refute_engine.py \
                tests/unit/test_causal_mediation_engine.py \
                tests/unit/test_causal_sensitivity_engine.py \
                tests/e2e/test_phase_b_e2e.py -v
```

Expected: **53 PASSED**.

## Pull-request checklist

Before opening a PR:

- [ ] All 53 contract / unit / e2e tests pass locally.
- [ ] If you touched any engine: the paper-SHA gate still
      passes (see `tests/contract/test_paper_version_pinned.py`).
- [ ] If you touched any schema: the OpenAPI snapshot is
      regenerated and the four drift gates still pass.
- [ ] Documentation updated in lockstep with code (`README.md`,
      relevant `_reports/PHASE_B_B*` design / completion doc).
- [ ] Commit messages reference the relevant Plan v2 section,
      Design doc, or Audit doc.
- [ ] No fabricated data, no silent dependency updates, no
      auto-formatter sweeps mixed into substantive changes.

## Coding standards

- Type-hint every public function. Run `mypy` if you touch
  schema-adjacent code.
- Pydantic 2.x is the contract layer; do not introduce
  competing serialisation paths.
- DoWhy 0.14 / EconML 0.15.x is the methodological substrate;
  if you need a different version, open a discussion first.
- Random seed must be 42 for any test that produces numeric
  output the paper depends on.
- Pytest only; no test-runner zoo.

## Communication

- Discussion: open a GitHub Discussion (preferred for
  questions, design proposals, V14+ ideas).
- Bug reports: open a GitHub Issue with a minimal reproducer.
- Sensitive matters (security, integrity concerns, IP
  questions): email exergyleizhou@gmail.com.

## Code of Conduct

By participating in this project you agree to abide by the
[Code of Conduct](CODE_OF_CONDUCT.md).
