# Phase B handoff — Paper 1 submission readiness (refreshed)

> This document supersedes the earlier handoff snapshot taken at
> HEAD `34959b6` (pre-B4-v2). Refreshed to the post-B4-v2 +
> CITATION.cff-fully-populated state. Author-side manual steps for
> JCP submission are externalised to
> `Paper1_BT/_drafts/INSTRUCTIONS_FOR_OPERATOR.md`; this document
> covers the software-side handoff only.

## §1 Current software state

- **Branch**: `chat/bos-v9-stabilize-files`
- **GitHub**: `https://github.com/exergyleizhou-ux/bos-platform`
  (private during peer review; will be public upon acceptance)
- **Working tree**: clean
- **Default branch on GitHub**: `chat/bos-v9-stabilize-files`
  (Phase G item: rename to `main` after acceptance and history
  rewrite)

### §1.1 Tags and anchors

- `v0.9.0-paper1` → commit `92a7a0f` — the B7 paper-pin commit.
  Anchored at the moment Plan v2 §1 R8 mitigation went live
  (paper-SHA gate + reproduction map shipped together).
- **`v0.9.1-paper-final` → commit `23ecac1`** — the post-patch
  final-submission anchor. Twelve manuscript patches landed
  (Author block / Corresponding author / GitHub URL / commit hash
  / Zenodo DOI ×2 / OSF DOI / CRediT / Acknowledgments / Funding
  section / LCA scoping); paper SHA re-pinned from
  `2FD4...3118D` (74,662 bytes) to `E64EAB...6D9A` (75,633 bytes,
  +971 bytes). Audit chain entry in `PAPER_PINNING.md` §3
  classifies as bibliographic + metadata + scoping (no method
  drift; no Plan v3 review triggered).

### §1.2 Phase B batches shipped (10/10, including B4 v2)

| Batch | What | Commit anchor |
|---|---|---|
| B1 | Deps landing + numpy 2.x migration | `2373aed` |
| B2a | Causal identify + estimate (D6/D7/D8/D9/D10/D14) | `2138cf8` |
| B2b.1 | Causal refute (4 mandatory + bootstrap) | `27f3a62` |
| B2b.2 | Causal mediation (Pearl/Rubin NDE/NIE) | `d372dba` |
| B2b.3 | Causal sensitivity (E-value + Cinelli-Hazlett) | `83c3c83` |
| B7 | Paper version pinning + reproduction map | `92a7a0f` (tagged) |
| B3 + B5 | OpenAPI drift gate + E2E full chain | `c4cb86e` |
| B6 | Frontend Mermaid causal panel | `34959b6` |
| B4 v2 | LangGraph causal subgraph (14 nodes, 51 tests) | `6966f3e` |

### §1.3 Test baseline

**104 tests PASS, 0 regression** (most recent full run on
HEAD `3faee19+` prior to this handoff commit):

- 43 causal unit tests: identify (6) + estimate (7) + refute (8)
  + mediation (12) + sensitivity (10)
- 1 paper-SHA pin gate
- 4 OpenAPI drift gates
- 5 end-to-end full-chain
- 51 LangGraph agent tests (isolation 2 + parity 38 + graph boot
  11)

### §1.4 Paper pin status

- **Paper file**: `Paper1_BT/BOS_Paper1_JCP_FINAL.docx`
  (75,633 bytes, ~260 paragraphs after Funding-section insertion,
  ~14,000 words after LCA append; latest in-place rewrite
  2026-05-20 via `scratch_y1_patch.py` applying 12 final-
  submission patches)
- **SHA-256 pinned in test**:
  `E64EAB068BC3DD58A7DF331201F42F14C581D33178F623EE38427CB052F36D9A`
  (uppercase form — `_sha256_of_file` calls `.upper()`)
- **Gate test**: `backend/tests/contract/test_paper_version_pinned.py`
- **Re-pin history + procedure**: `_reports/PAPER_PINNING.md` (§3
  contains B7 entry from 2026-05-18 + v0.9.1-paper-final entry
  from 2026-05-20)
- **Status**: PASS at this handoff. Two further re-pins remain
  during operator workflow (Step 2 Zenodo DOI substitution + Step
  3 OSF DOI substitution); after those land, the paper SHA
  stabilises until peer review feedback arrives.

### §1.5 CITATION.cff status

- **Fully populated**: author (Zhou Lei, exergyleizhou@gmail.com,
  ORCID 0009-0000-9073-1349), repository, license (MIT), abstract,
  14 keywords aligned to the paper (Tenebrio molitor / Protaetia
  brevitarsis / Signal-API / Control-API / distillers-grains /
  Pearl-Rubin / etc.), preferred-citation title + first author +
  status (in-preparation).
- **Version**: `0.9.1-paper-final` (bumped from `0.9.0-paper1`
  in commit `23ecac1` to match the post-patch paper anchor).
- **Date-released**: `2026-05-20`.
- **Identifiers field**: Zenodo DOI placeholder ready (operator
  fills after Step 2 Zenodo mint).
- **Lifecycle field**: `preferred-citation.status` will bump
  through `in-preparation` → `submitted` (Step 6 same-day commit)
  → `accepted` → `in-press` → `published` (Step 7 each milestone).

### §1.6 README status

- 606 lines, 7 status badges (License / Paper / Tag / Tests /
  Phase / Zenodo pending / OSF pending).
- §"Paper 1 Reproduction" includes a 7-column paper-method ↔ BOS
  endpoint crosswalk (paper section / Eq. → claim → endpoint →
  schema (with SCHEMA_VERSION) → engine → test file → DAG ref)
  plus a supporting-infrastructure table (paper SHA pin / OpenAPI
  snapshot / E2E / Agent / Mermaid / audit-chain anchors).

### §1.7 Community files

- `CODE_OF_CONDUCT.md` (Contributor Covenant 1.4 + scientific
  integrity)
- `CONTRIBUTING.md` (accept / cannot-accept-without-re-pin lists,
  dev setup, PR checklist)
- `SECURITY.md` (scope, private vulnerability reporting,
  disclosure timeline, audit-chain integrity priority)

### §1.8 CI status

- `.github/workflows/ci.yml` — pre-existing repo-wide CI (lint,
  docs-consistency, frontend-compile, benchmark-suite,
  test-backend with coverage, test-frontend, release-packet-ingest,
  Docker build, Trivy security scan). Triggers on `main` / `develop`
  pushes and PRs to `main` — currently does NOT trigger on the
  Phase B working branch.
- `.github/workflows/paper1-gate.yml` (new at this handoff) —
  independent workflow that runs the 53-test Phase B contract /
  unit / e2e gate + the 51-test LangGraph agent gate on every
  push to `main` or `chat/bos-v9-stabilize-files` and every PR
  targeting either. Paper-pin gate SKIPs gracefully on CI by
  design (documented in PAPER_PINNING.md §2 and asserted by the
  workflow itself).

## §2 Operator-side manual work remaining

The author-facing checklist is fully externalised to
`Paper1_BT/_drafts/INSTRUCTIONS_FOR_OPERATOR.md`. The seven steps
are summarised here for completeness:

| Step | Action | Time |
|---|---|---|
| 1 | Apply 6 paper patches (Word) + re-pin SHA | ~30 min |
| 2 | Zenodo DOI mint via GitHub Release | ~30 min |
| 3 | OSF V14 pre-registration | ~1–2 h |
| 4 | GitHub release publish (if separate from Step 2) | ~5 min |
| 5 | Cover letter finalize | ~30 min |
| 6 | J Clean Prod Editorial Manager submission | ~1–2 h |
| 7 | (Post-acceptance) repo public switch | ~10 min |
| **TOTAL pre-submission** | | **~3.5–5.5 h** |

The four boilerplate drafts that feed Steps 5 and patches 5–6 are
prepared and shipped:

- `Paper1_BT/_drafts/cover_letter_draft.md`
- `Paper1_BT/_drafts/credit_statement_draft.md`
- `Paper1_BT/_drafts/acknowledgments_draft.md`
- `Paper1_BT/_drafts/lca_scoping_note_draft.md`
- `Paper1_BT/_drafts/JCP_FINAL_PATCH_INSTRUCTIONS.md` (Word
  Find-and-Replace recipes for the 6 patches)
- `Paper1_BT/_drafts/INSTRUCTIONS_FOR_OPERATOR.md` (end-to-end
  checklist)
- `Paper1_BT/_drafts/RELEASE_NOTE_v0.9.0-paper1.md` (GitHub
  Release body)

## §3 Audit chain anchors (for reviewers / co-authors)

If a reviewer asks "where is the evidence?", point at:

- `_reports/PHASE_B_PLAN.md` (Plan v2 — §1 paper SHA pin, §2
  endpoint specs, §7 12-item acceptance gate)
- `_reports/PHASE_B_PLAN_V2_PATCH_S2_3.md` (Plan v2 §2.3 patch —
  `evalue_sensitivity_analyzer` moved to `/sensitivity`)
- `_reports/PAPER_PINNING.md` (SHA pin history + Plan v3
  trigger conditions + §5 re-pin procedure)
- `_reports/PHASE_B_B2{a,b1,b2,b3,7}_COMPLETION.md` — per-batch
  completion reports
- `_reports/PHASE_B_B4_v2_COMPLETION.md` — Phase B closure (10/10)
- `_reports/PHASE_B_B7_AUDIT.md` — post-ship audit + drift fixes
- `_reports/phase_b_openapi_snapshot.json` — API surface pinned
  (5 paths + 28 schemas)
- `git log --oneline` — full commit chain (15+ Phase B commits +
  3 paper-side audit commits + this handoff)

## §4 Post-submission software work (slow burn, peer-review window)

No urgency. The author can pick these up as the review process
allows, in roughly this order:

- **Phase G housekeeping** — repository visibility switch
  (private → public), default branch rename (`chat/bos-v9-stabilize-files`
  → `main`), repository history slimming (~275 MB →
  ~50 MB target), GitHub Actions CI consolidation.
- **Reviewer feedback application** — track each reviewer comment
  against the audit-chain anchors above; for any comment that
  affects the methodology (Pearl-Rubin decomposition, Γ-bound
  threshold, refuter selection, etc.), open a Plan v3 review per
  `_reports/PAPER_PINNING.md` §4–5.
- **Phase C — Bayesian + Conformal overlays** on the causal
  layer. Not in Plan v2 scope; needs its own Plan v3 document.
  Pre-registered in the paper's §4.7 as V15+ methodological
  frontier.
- **Phase D–G** — long-horizon control / info-theory / PhyAgentOS
  work per the Plan v2 §1 "Out of scope" list.

## §5 What this handoff supersedes

- The May 18 version of this same document at HEAD `859e37e` (in
  the commit history under `docs: Phase B handoff — Paper 1
  submission ready, B4 pending`). That version was accurate at
  the time but became stale once B4 v2 shipped, CITATION.cff was
  fully populated, the GitHub remote was configured, and the
  Phase G community files + paper-gate CI landed.

## §6 What this handoff does NOT cover

- The wet-lab V14 campaign protocol — pre-registered at OSF (DOI
  to be issued by the operator in Step 3 of
  `INSTRUCTIONS_FOR_OPERATOR.md`).
- The frozen analysis archive at Zenodo — DOI to be minted by the
  operator in Step 2.
- The cover letter and graphical abstract — operator-driven,
  draft scaffolding is in `Paper1_BT/_drafts/`.

---

End of handoff. The next time this document needs to update is
when reviewer feedback returns or when Phase G work begins.
