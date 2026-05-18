# Paper 1 — Version pinning record

> Phase B B7 deliverable (Plan v2 §1 R8 mitigation).
> Audit chain: Plan v2 §1 -> ``tests/contract/test_paper_version_pinned.py``
> -> this document -> B7 commit message.

## §1 Purpose

Paper 1 ("BOS Platform for BSF Bioconversion: Pre-registered
Pearl/Rubin Mediation Analysis", in preparation for J Clean Prod)
is the scientific artefact backing the entire Phase B causal layer
(five `/api/v1/causal/*` endpoints). If the paper's *method*
section drifts from what the engines implement, the audit chain
breaks and the platform's evidence-level claims become unsupported.

The B7 mitigation is a two-part gate:

1. ``tests/contract/test_paper_version_pinned.py`` — a contract
   test that SHA-256-hashes the paper file and fails if the hash
   changes.
2. This document — the re-pin procedure, classification rules for
   "minor metadata" vs "material method drift", and the audit log
   of every pin update.

When the gate test fails, **STOP all Phase B/C/D code work**.
Follow §5 below.

## §2 Current pin

| Field | Value |
|---|---|
| File path | `C:\Users\10420\Desktop\bos 0506\Paper1_BT\BOS_Paper1_JCP_FINAL.docx` |
| SHA-256 | `2FD4387028B2B160388C65CCB0F269967E05B55FDEAF6BA62B1570BCB533118D` |
| Size | 74,662 bytes |
| Pinned at commit | B7 commit (see `git log` for hash; tagged `v0.9.0-paper1`) |
| Pin date | 2026-05-18 |
| Pin author | (sole author env; see CITATION.cff for software credit) |

The path is the author machine's absolute path. The test SKIPs on
machines where the path does not resolve — this is deliberate:
the gate's job is to alert the author when *they* save a new paper
revision, not to enforce paper presence on CI / co-author boxes.

A Phase G enhancement (see §7) would move the path to an
environment variable.

## §3 Pin history (audit chain)

### 2026-05-16 — Initial pin (Plan v2 §1)

- SHA-256: `BA13A10FDE39DECB96FD98F92694791A0A6739868ADDE69C374A49C013B110D7`
- Size: 74,671 bytes
- Plan v2 commit context: written 2026-05-17 against HEAD `b962e58`
- Recorded in: `_reports/PHASE_B_PLAN.md` §1
- Snapshot preserved as: `BOS_Paper1_JCP_FINAL.docx.bak` (next to
  the live file)

### 2026-05-18 — B7 re-pin (Option A: minor metadata)

- SHA-256: `2FD4387028B2B160388C65CCB0F269967E05B55FDEAF6BA62B1570BCB533118D`
- Size: 74,662 bytes
- Delta: −9 bytes
- Cause: Word save metadata refresh (lastModifiedBy /
  lastModifiedTime / internal XML whitespace). No text content
  change.
- Evidence (recorded for audit):
  - `backend/scratch_paper_diff.py` extracted both files via
    `python-docx` and compared paragraph-level text.
  - Result: **0 differing paragraphs** out of 258 paragraphs in
    both files.
  - Critical method keywords confirmed present in the current
    paper:
    - `Pearl`: 4 hits (paras 100, 132, 152, 216)
    - `Rubin`: 3 hits (paras 100, 132, 152)
    - `mediation`: 6 hits (paras 10, 100, 113, 152, 214, ...)
    - `ACME`: 1 hit (para 100)
    - `NDE`: 63 hits
    - `NIE`: 4 hits
    - `Signal-API`: 32 hits
    - `70%`: 2 hits (paras 10, 100)
    - `proportion mediated`: 1 hit (para 10)
    - `1.5`: 1 hit (para 100)
    - `Eq. 4`: 3 hits (paras 49, 100, 152)
    - `sensitivity`: 12 hits
  - Expected 0-hit keywords (BOS implementation choices, not paper
    text):
    - `kappa`: 0 hits — paper uses Greek letter κ; BOS code uses
      ASCII identifiers (no string match expected).
    - `E-value`: 0 hits — paper uses "Γ-bound >= 1.5"; BOS B2b.3
      operationalises that via VanderWeele-Ding E-value (recorded
      in `PHASE_B2b3_DESIGN.md` §3).
    - `Cinelli`: 0 hits — paper does not cite Cinelli-Hazlett by
      name; BOS B2b.3 `linear` branch is a power-user addition,
      not paper-required (recorded in `PHASE_B2b3_DESIGN.md` §1).
- Verdict: **minor metadata delta**, no Plan v3 review needed.
- Action: gate test re-pinned to the new SHA.

## §4 Trigger conditions for Plan v3 review

A gate-test failure escalates to a full Plan v3 review when **any**
of the following are true:

- **Method section text changes** — Pearl/Rubin mediation
  description, Cinelli-Hazlett or related sensitivity bound,
  refutation methodology, identification strategy.
- **Numerical claim changes** — the abstract's 70% proportion
  mediated, Γ-bound 1.5 threshold, headline ATE point estimate,
  bootstrap iteration counts, n-per-arm.
- **Equation changes** — Eq. 1–4 numbering, the form of any
  equation referenced by an engine (e.g. Eq. 4 = Pearl
  counterfactual decomposition).
- **New cited method** the engines do not currently implement —
  e.g. a switch from VanderWeele-Ding to a different sensitivity
  framework.
- **DAG topology changes** in the paper's causal model section
  (e.g. adding a new mediator, instrument, or unmeasured
  confounder).

A failure is **NOT** a Plan v3 trigger when only the following
change:

- Word metadata (lastModifiedBy, lastModifiedTime, app revision
  counter, internal XML whitespace, .docx zip-file ordering).
- Formatting (bold, italic, font, paragraph spacing).
- Front-matter author additions or affiliation updates.
- Typo fixes in non-method sections (abstract typos count as
  method changes if they touch the 70% / Γ-bound numbers).
- Reference list reordering, addition of references that the BOS
  engines do not depend on.

The categorisation must be recorded in §3 with a one-line evidence
summary even for minor re-pins, so the audit chain stays
inspectable.

## §5 Re-pin procedure (when the gate fails)

1. **STOP** all Phase B/C/D code work. Do not commit any further
   engine / schema / router / test changes until the gate is
   restored.
2. Compute the current SHA via PowerShell (the source of truth on
   the author machine):
   ```
   (Get-FileHash 'C:\Users\10420\Desktop\bos 0506\Paper1_BT\BOS_Paper1_JCP_FINAL.docx' -Algorithm SHA256).Hash
   ```
3. Run `backend/scratch_paper_diff.py` (regenerate if it was
   archived) to extract paragraph-level text diff between the new
   file and the previous pin's snapshot (the `.bak` next to the
   live file, or a git-archived copy).
4. Categorise the diff against §4. Capture which paragraphs
   changed and which critical keywords they touch.
5. **Branch on category**:
   - **Minor metadata / formatting / non-method text**: re-pin
     `PINNED_SHA256` in `test_paper_version_pinned.py`, append an
     entry to §3 with the evidence summary, commit with a
     `chore(paper-pin):` prefix message. No Plan v3 review.
   - **Material method change**: open a Plan v3 review document
     (`_reports/PHASE_B_PLAN_V3_REVIEW_<date>.md`) that audits
     each affected engine and lists the code changes required.
     Land the code changes first, then re-pin in the same commit
     batch that finalises the v3 review.
6. Update CITATION.cff `date-released` and `version` if the
   re-pin is material (Phase G-style version bump).

## §6 Audit chain links

- `_reports/PHASE_B_PLAN.md` §1 — original pin record.
- `backend/tests/contract/test_paper_version_pinned.py` — the
  gate test, with the pinned constant.
- This document — re-pin log and procedure.
- `CITATION.cff` — software citation metadata referencing the
  paper as `preferred-citation`.
- B7 commit message — links this document, the gate test, and
  the corresponding Plan v2 §1 / B7 sections.

The chain is acyclic: Plan v2 -> gate test -> this doc ->
CITATION.cff. Any future re-pin appends a §3 entry; no node is
ever rewritten.

## §7 Phase G future enhancement

- **Path indirection.** Move `PAPER_PATH` from a hardcoded
  absolute path to an environment variable `BOS_PAPER1_PATH` with
  the current absolute path as the default. Allows CI / co-author
  boxes / Phase G public-repo contributors to point at their own
  copy.
- **Multi-version pinning.** If Paper 1 ever has a "submitted" vs
  "accepted" vs "published" lineage, the gate could carry a tuple
  of acceptable SHAs and report which one matches. For B7 the
  single-pin pattern is sufficient.
- **Paper section anchors.** A richer gate could checksum the
  method section specifically (extract via python-docx, normalise
  whitespace, hash). That would let formatting changes pass
  cleanly without re-pinning. Useful when revision rounds at JCP
  trigger lots of cosmetic edits.

## §8 Archive — Step 1.5 scratch evidence

The text-diff scratch script lives at
`backend/scratch_paper_diff.py`. It is **kept** in the B7 commit
rather than deleted because:

- It is the canonical implementation of §5 step 3.
- Future re-pins re-run it.
- It is a small, dependency-bounded script (python-docx already
  in the backend venv; no extra deps).

If a Phase G clean-up wants to promote it, the natural home is
`backend/scripts/paper_pin_diff.py` with a CLI surface
(`--current PATH --reference PATH --format json`).
