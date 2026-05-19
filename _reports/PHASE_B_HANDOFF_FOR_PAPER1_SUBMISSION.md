# Phase B handoff — Paper 1 submission ready

> Generated at the end of the multi-batch Phase B thread.
> Branch: `chat/bos-v9-stabilize-files`. Local-only repo (no
> `origin` remote configured at handoff time; configure + push
> when convenient).

## Current state

- **HEAD**: `34959b6 feat: Phase B B6 — frontend Mermaid causal panel + B4 design hand-off`
- **Tag**: `v0.9.0-paper1` -> `92a7a0f` (the B7 paper-pin commit; tag stays anchored there as the Paper 1 milestone)
- **Phase B batches shipped (8/9)**: B2a (identify + estimate), B2b.1 (refute), B2b.2 (mediation), B2b.3 (sensitivity), B7 (paper pin + reproduction map), B3 (OpenAPI snapshot + drift gate), B5 (E2E full chain), B6 (frontend Mermaid panel).
- **Not shipped (1/9)**: B4 (LangGraph causal agent). Design ships in `_reports/PHASE_B_B4_DESIGN.md` (commit `34959b6`); implementation = 0 lines.
- **Tests green**: 53 backend (43 causal engines + 1 paper gate + 4 OpenAPI drift + 5 E2E) + 32 frontend (`components/bos/`) = **85 PASS, 0 regression**.

## Paper 1 submission day checklist (do tomorrow morning)

Sequence matters — finish 1+2 before 3+4.

1. **`CITATION.cff` TODO fill** (~15 min). 10 placeholders to complete (search `<TODO` in the file):
   - author family / given name (the software credit)
   - author email + ORCID (uncomment + fill)
   - `license`: probably `MIT` to match README L482
   - `repository-code`: leave commented until/unless the repo goes public
   - `preferred-citation.title`: the final Paper 1 title
   - `preferred-citation.authors[0]`: first-author name (separate from software credit if different)
   - `preferred-citation.status`: bump from `in-preparation` to `submitted` once the manuscript is uploaded
2. **Paper V14 .docx Supplementary Information**. Add an "Implementation" section that cites:
   - the platform tag `v0.9.0-paper1`
   - the five `/api/v1/causal/*` endpoints + their `SCHEMA_VERSION` strings (B.1-B.5)
   - the Pearl/Rubin mediation engine (D14 = gamma) and the Gamma-bound 1.5 sensitivity gate
   - `_reports/PHASE_B_PLAN.md` §7 as the acceptance criteria record
3. **Cover letter**. Highlight: pre-registered Pearl/Rubin mediation on the Signal-API -> kappa -> SER pathway; ~70% proportion mediated; falsification gate operationalised via VanderWeele-Ding E-value + Cinelli-Hazlett robustness; full audit chain in `_reports/`.
4. **Submit to J Clean Prod Editorial Manager**. Update `CITATION.cff` `preferred-citation.status` to `submitted` in the same commit batch.

## Post-submission software work (slow burn, peer review window)

No urgency. Author can pick up these as the review process allows.

- **B4 — Agent causal_node** (Plan v2 §3, the only outstanding Phase B batch). Design fully scoped in `_reports/PHASE_B_B4_DESIGN.md`: 8 steps, 12 source + 8 test files, 6-10 h adjusted. The next thread starts from §9 of that doc; no re-recon needed.
- **Phase C** — Bayesian + conformal-prediction overlays on the causal layer. Not specified in Plan v2; will need its own plan.
- **Phase D-G** — long-horizon control / info-theory / PhyAgentOS work per the Plan v2 §1 "Out of scope" list.

## Audit trail anchors (for reviewers / co-authors)

If a reviewer asks "where is the evidence", point at:

- `_reports/PHASE_B_PLAN.md` (§1 paper SHA pin; §2 endpoint specs; §7 12-item acceptance gate)
- `_reports/PAPER_PINNING.md` (SHA pin history + Plan v3 review procedure)
- `_reports/PHASE_B_B2{a,b1,b2,b3,7}_COMPLETION.md` (per-batch completion reports)
- `_reports/PHASE_B_B7_AUDIT.md` (post-ship audit + drift fixes)
- `_reports/phase_b_openapi_snapshot.json` (API surface pinned, 5 paths + 28 schemas)
- `git log --oneline` for the full commit chain (9 Phase B commits + 1 pre-existing pytest config commit)

## Outstanding operational item

`git remote add origin <URL>` then `git push origin chat/bos-v9-stabilize-files --tags`. The repo is local-only at handoff time. Configure the remote when convenient — none of today's work depends on the push happening immediately.
