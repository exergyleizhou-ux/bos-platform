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
    "2FD4387028B2B160388C65CCB0F269967E05B55F"
    "DEAF6BA62B1570BCB533118D"
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
