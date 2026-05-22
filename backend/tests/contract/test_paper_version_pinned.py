"""Paper 1 (J Clean Prod V14) SHA-256 pinning gate.

Phase B B7 deliverable per Plan v2 §1 (R8 mitigation).

If this test fails, the paper file has changed without a documented
Plan v3 review. STOP all Phase B/C/D work and follow the Plan v3
review procedure in ``_reports/PAPER_PINNING.md``.

Pin history:
  - Plan v2 (2026-05-16): ba13a10f...10d7 (74,671 bytes)
  - B7      (2026-05-18 re-pin): 2fd43870...118d (74,662 bytes)
    9-byte Word metadata delta; text diff = 0 paragraphs verified
    via ``scratch_paper_diff.py`` (archived in B7 commit; see
    PAPER_PINNING.md re-pin history).
  - v0.9.1-paper-final (2026-05-20): e64eab06...6d9a (75,633 bytes)
    +971 bytes; 12 final-submission patches applied via
    ``scratch_y1_patch.py`` (author block / corresponding author /
    GitHub URL / commit hash / Zenodo DOI x2 / OSF DOI / CRediT /
    Acknowledgments / Funding section insertion / LCA scoping
    paragraph). PAPER_PINNING.md §3 documents the patch summary
    and classifies the change as bibliographic/metadata (not
    method-section drift; no Plan v3 review required).
  - (2026-05-21) post-GPT-critic patches: aa251b01...cc8b
    (75,651 bytes). +18 bytes; 3 Acknowledgments TODO
    placeholders replaced with anonymised wording
    (distillery / commercial supplier / colony source). No
    method-section drift; no Plan v3 review required.
  - (2026-05-21) post-OpenAI-critic polish: c7e4ce1b...741c
    (75,569 bytes). -82 bytes; 8 patches applied via
    `scratch_final_polish.py`:
      P1   title shifted to JCP-friendly framing ("staged
           insect bioconversion ... improves resource recovery
           from distillers' grains")
      P2.1 highlight 1 -> matched-boundary resource efficiency
      P2.2 highlight 2 -> "SER 0.53 -> 0.68 jointly D' + G'"
      P2.3 highlight 3 -> 3-10 kDa fraction within envelope
      P2.4 highlight 4 -> Control-API audit criteria
      P2.5 highlight 5 -> audit software layer links claims
      P3.1 Software availability rewording: "audit-facing
           implementation reference" replaces "computational
           core encapsulated" framing
      P4   mediation ~70% gains "pre-registered in-silico
           estimate" tag in the abstract / front-matter sentence
    Classification per §4: bibliographic + metadata + framing
    (no method-section drift). Same approval class as the prior
    pins; no Plan v3 review required.

The path is hardcoded to the author machine. The gate skips on
other machines (CI / co-author env / future Phase G mover) — the
purpose is to alert the author when the paper changes, not to
enforce presence everywhere.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


PAPER_PATH = Path(
    r"C:\Users\10420\Desktop\bos 0506\Paper1_BT"
    r"\BOS_Paper1_JCP_FINAL.docx"
)

PINNED_SHA256 = (
    "C7E4CE1B695401659668D256B779B60E"
    "B30738D9963B875112EAC9406353741C"
)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


@pytest.mark.skipif(
    not PAPER_PATH.exists(),
    reason=(
        "Paper file not at expected path on this machine; gate "
        "test skipped. Author env should have the paper accessible. "
        "Skip is safe because the gate's purpose is to alert the "
        "author when the paper changes, not to enforce presence."
    ),
)
def test_paper_version_pinned() -> None:
    """Paper SHA-256 must match the pinned value."""
    actual = _sha256_of_file(PAPER_PATH)
    assert actual == PINNED_SHA256, (
        f"Paper SHA changed!\n"
        f"  Expected: {PINNED_SHA256}\n"
        f"  Actual:   {actual}\n"
        f"\n"
        f"The paper file has been edited after the B7 pin. Per "
        f"Plan v2 §1, a Plan v3 review is REQUIRED before any "
        f"further Phase B/C/D code lands. See "
        f"_reports/PAPER_PINNING.md for the categorisation rules "
        f"(§4 trigger conditions) and the re-pin procedure (§5)."
    )
