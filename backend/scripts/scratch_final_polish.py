# -*- coding: utf-8 -*-
"""Final OpenAI-critic-informed polish patches.

Applies the 8 OpenAI suggestions we accepted (with our 3 calibrations):
- Title shift to JCP-friendly framing
- Highlights 5 lines result-oriented
- Abstract: keep one in-silico line as load-bearing-tag, drop dense stack
- Software availability wording: AI/platform -> audit-facing implementation
- in-silico tagging in mediation prose
- (Acknowledgments already anonymised in 8f8c192)

Main paper SHA will re-pin.
"""
from pathlib import Path
import hashlib

from docx import Document

MAIN = Path(
    r"C:\Users\10420\Desktop\bos 0506\Paper1_BT"
    r"\BOS_Paper1_JCP_FINAL.docx"
)


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_hits(doc, find_str):
    return sum(1 for p in doc.paragraphs if find_str in p.text)


def apply(doc, find_str, replace_str, name, expected_hits=1):
    hits = count_hits(doc, find_str)
    if hits != expected_hits:
        print(f"  [{name}] SKIP: expected {expected_hits}, found {hits}")
        return False
    for p in doc.paragraphs:
        if find_str in p.text:
            p.text = p.text.replace(find_str, replace_str)
    print(f"  [{name}] OK")
    return True


def main():
    print(f"Loading: {MAIN}")
    print(f"  pre SHA:  {sha256_of_file(MAIN)}")
    doc = Document(str(MAIN))
    print(f"  paragraphs: {len(doc.paragraphs)}")
    print()

    # ============================================================
    # POLISH 1 - Title shift to JCP framing
    # ============================================================
    print("=" * 70)
    print("Polish 1: Title")
    print("=" * 70)
    apply(doc,
          find_str=("Staged bioconversion via a protocol-first Biological "
                    "Operating System: Decoupling waste deconstruction "
                    "from nutrient recovery"),
          replace_str=("Staged insect bioconversion through a protocol-"
                       "first Biological Operating System improves "
                       "resource recovery from distillers' grains"),
          name="P1 title")

    # ============================================================
    # POLISH 2 - Highlights 5 lines (replace whole lines)
    # ============================================================
    print()
    print("=" * 70)
    print("Polish 2: Highlights 5 lines (result-oriented)")
    print("=" * 70)
    apply(doc,
          find_str=("BOS is a protocol-first staged bioconversion "
                    "architecture that resolves the conversion-recovery "
                    "trade-off by decoupling dissipative deconstruction "
                    "from anabolic recovery across modules under a "
                    "declared interface."),
          replace_str=("A staged insect-bioconversion relay improved "
                       "matched-boundary resource efficiency on "
                       "distillers' grains."),
          name="P2.1 highlight 1")

    apply(doc,
          find_str=("Mechanistic hardening shows that Signal-API activity "
                    "persists after viable-load exclusion and localizes "
                    "predominantly to a heat-labile 3–10 kDa fraction, "
                    "supporting a constrained functional interface."),
          replace_str=("The relay increased SER from 0.53 to 0.68 by "
                       "jointly improving dry-matter reduction and "
                       "nitrogen recovery."),
          name="P2.2 highlight 2")

    apply(doc,
          find_str=("Dose-response data, validated by both Hill fitting "
                    "and non-parametric restricted cubic spline analysis, "
                    "convert the inter-stage handover into a deployable "
                    "specification with defined operating envelopes."),
          replace_str=("Signal-API hardening localised activity to a "
                       "heat-labile, protease-sensitive 3–10 kDa "
                       "fraction within a defined dose and stability "
                       "envelope."),
          name="P2.3 highlight 3")

    apply(doc,
          find_str=("Cross-executor transfer is auditable but not "
                    "universal: PASS, PASS-with-retuning, and FAIL "
                    "outcomes formalize portability as a compatibility "
                    "problem with explicit acceptance criteria."),
          replace_str=("Control-API rules convert biological handover "
                       "into auditable dose, hydraulic-load, stability, "
                       "and reject criteria with PASS / PASS-with-"
                       "retuning / FAIL outcomes."),
          name="P2.4 highlight 4")

    apply(doc,
          find_str=("Progressive covariate adjustment across three "
                    "nested models (Model 1 directly measured; Models "
                    "2 / 3 reported as pre-registered in-silico "
                    "sensitivity envelopes) preserves the direction of "
                    "the relay advantage (ΔΔSER = 0.15), with full wet-"
                    "lab adjusted confirmation pre-registered as V14."),
          replace_str=("An audit software layer links cleaner-production "
                       "claims to frozen code, schemas, and tests, with "
                       "in-silico covariate audits pre-registered as "
                       "V14 wet-lab targets."),
          name="P2.5 highlight 5")

    # ============================================================
    # POLISH 3 - Software availability wording (Tier 2 paragraph)
    # ============================================================
    print()
    print("=" * 70)
    print("Polish 3: Software availability wording")
    print("=" * 70)
    apply(doc,
          find_str=("The full computational core is encapsulated in the "
                    "BOS Pipeline v9.0 archive — a reconciled snapshot "
                    "comprising 13 named domain engines"),
          replace_str=("The audit-facing implementation reference for "
                       "this manuscript is encapsulated in the BOS "
                       "Pipeline v9.0 archive — a reconciled snapshot "
                       "comprising 13 named domain engines"),
          name="P3.1 audit-facing framing")

    # The Control-API paradigm sentence already mentions verifiable
    # reference-based reward; keep as-is. Soften the "verifiable" line.

    # ============================================================
    # POLISH 4 - in-silico tagging on the 70% mediation claim
    # ============================================================
    print()
    print("=" * 70)
    print("Polish 4: in-silico tagging for mediation 70% claim")
    print("=" * 70)
    # The mediation paragraph (para[100]) already says "in-silico,
    # pre-registered for V14" - the body is honest. Add one additional
    # sentence at end of abstract / front matter to make sure the
    # reader catches the framing.

    # We do this via locating a known anchor in the abstract.
    apply(doc,
          find_str=("the proportion of the Signal-API → SER effect "
                    "mediated through κ is estimated at approximately "
                    "70%"),
          replace_str=("a pre-registered in-silico estimate maps "
                       "the proportion of the Signal-API → SER effect "
                       "mediated through κ at approximately 70%"),
          name="P4 mediation in-silico tag")

    # Save in-place
    doc.save(str(MAIN))

    new_sha = sha256_of_file(MAIN)
    new_size = MAIN.stat().st_size
    print()
    print("=" * 70)
    print("Saved")
    print("=" * 70)
    print(f"  new SHA: {new_sha}")
    print(f"  uppercase: {new_sha.upper()}")
    print(f"  size: {new_size} bytes")


if __name__ == "__main__":
    main()
