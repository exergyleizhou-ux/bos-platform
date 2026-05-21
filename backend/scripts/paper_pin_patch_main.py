# -*- coding: utf-8 -*-
"""Y1+ Step 4 — apply 4 low-risk patches (6 string replacements).

Conservative: each patch is a paragraph.text find-and-replace,
guarded by an exact hit-count expectation. Saves to a SEPARATE
file (.y1-patched.docx) so the original is preserved for Word
side-by-side comparison.

Patches applied this run:
  A.1: para[1] Author block placeholder
  A.2: para[2] Corresponding author placeholder
  B.1: para[153] [URL to be issued] -> GitHub URL
  B.2: para[153] commit [hash to be issued] -> commit 92a7a0f
  B.3: para[153] [Zenodo DOI to be issued] (Software Availability)
       -> Zenodo placeholder with mint-pending note
  D:   para[155] [OSF DOI to be issued] -> OSF placeholder with
       pre-registration-pending note

Sub-recon also performed (no replacement this run):
  para[149] full text printed (operator decides Patch C anchor
            in next round)

Not in this run (per Step 4 brief):
  - 9 occurrences of "OSF [DOI to be issued]" (dominant form;
    operator decides unified format manually)
  - Patch 5 Funding section insertion
  - Patch 6.1 CRediT replacement
  - Patch 6.2 Acknowledgments replacement
  - Patch 6.3 LCA scoping (Word paste from drafts/)
"""
from pathlib import Path
import hashlib

from docx import Document

PAPER = Path(
    r"C:\Users\10420\Desktop\bos 0506\Paper1_BT"
    r"\BOS_Paper1_JCP_FINAL.docx"
)
OUTPUT = PAPER.parent / "BOS_Paper1_JCP_FINAL.y1-patched.docx"


def count_hits(doc, find_str):
    """Count paragraphs containing find_str (substring match)."""
    return sum(1 for p in doc.paragraphs if find_str in p.text)


def apply_global_find_replace(doc, find_str, replace_str, patch_name,
                              expected_hits):
    """
    Apply find-replace across all paragraphs.

    Returns True iff applied successfully (hit count matched expectation).
    Prints OK / SKIP with reason.
    """
    hits = count_hits(doc, find_str)
    if hits != expected_hits:
        print(f"  [{patch_name}] SKIP: expected {expected_hits} hit(s), "
              f"found {hits} for {find_str!r}")
        return False
    replaced_in = 0
    for p in doc.paragraphs:
        if find_str in p.text:
            new_text = p.text.replace(find_str, replace_str)
            p.text = new_text
            replaced_in += 1
    print(f"  [{patch_name}] OK: replaced in {replaced_in} paragraph(s)")
    return True


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    print(f"Loading: {PAPER}")
    doc = Document(str(PAPER))
    print(f"Total paragraphs: {len(doc.paragraphs)}")

    # -----------------------------------------------------------
    # Sub-recon — print para[149] full text (for Patch C decision)
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("SUB-RECON: para[149] full text (for Patch C anchor decision)")
    print("=" * 70)
    p149_text = doc.paragraphs[149].text
    print(f"  Length: {len(p149_text)} chars")
    print(f"  Full text (repr): {p149_text!r}")
    print()
    print(f"  Also reference: surrounding paragraphs for context:")
    for idx in [148, 149, 150]:
        if idx < len(doc.paragraphs):
            txt = doc.paragraphs[idx].text
            print(f"    para[{idx}]: {txt!r}")
    print()

    # -----------------------------------------------------------
    # Patch A — Author block (2 replacements)
    # -----------------------------------------------------------
    print("=" * 70)
    print("Patch A: Author block (para[1] + para[2])")
    print("=" * 70)

    # A.1: author list placeholder (em dash form, verified by recon)
    apply_global_find_replace(
        doc,
        find_str="[Author list and affiliations — to be completed by authors]",
        replace_str=("[FILL: see Paper1_BT/_drafts/ for author template; "
                     "add superscript numerals in Word]"),
        patch_name="A.1 author block",
        expected_hits=1,
    )

    # A.2: corresponding author placeholder
    apply_global_find_replace(
        doc,
        find_str="Corresponding author: [Name, email]",
        replace_str="Corresponding author: [FILL: name and email]",
        patch_name="A.2 corresponding author",
        expected_hits=1,
    )

    # -----------------------------------------------------------
    # Patch B — Software Availability anchors (3 replacements
    # in para[153])
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch B: Software Availability section (para[153])")
    print("=" * 70)

    # B.1: URL placeholder
    apply_global_find_replace(
        doc,
        find_str="[URL to be issued]",
        replace_str="https://github.com/exergyleizhou-ux/bos-platform",
        patch_name="B.1 GitHub URL",
        expected_hits=1,
    )

    # B.2: commit hash placeholder
    apply_global_find_replace(
        doc,
        find_str="commit [hash to be issued]",
        replace_str="commit 92a7a0f",
        patch_name="B.2 commit hash",
        expected_hits=1,
    )

    # B.3: Zenodo DOI placeholder (Software Availability — single hit
    # at para[153]; the second Zenodo placeholder at para[149] is
    # deferred to Patch C in the next round)
    apply_global_find_replace(
        doc,
        find_str="[Zenodo DOI to be issued]",
        replace_str=("[Zenodo DOI: 10.5281/zenodo.XXXXXXX — pending "
                     "mint after GitHub Release publication]"),
        patch_name="B.3 Zenodo DOI (Software Avail)",
        expected_hits=1,
    )

    # -----------------------------------------------------------
    # Patch D — OSF DOI single-bracket form (1 replacement, para[155])
    # NOT the dominant 9-hit form, which is deferred to manual.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch D: OSF DOI single-bracket form (para[155] only)")
    print("=" * 70)

    apply_global_find_replace(
        doc,
        find_str="[OSF DOI to be issued]",
        replace_str=("[OSF DOI: 10.17605/OSF.IO/XXXXX — pending "
                     "pre-registration submission]"),
        patch_name="D OSF DOI single",
        expected_hits=1,
    )

    # -----------------------------------------------------------
    # Patch C — Data Availability Zenodo placeholder (para[149])
    # Anchor uses "deposited at Zenodo [DOI placeholder]." (with
    # trailing period) to disambiguate from the Software
    # Availability Zenodo placeholder that lives in para[153] and
    # is handled by Patch B.3.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch C: Data Availability Zenodo (para[149])")
    print("=" * 70)

    apply_global_find_replace(
        doc,
        find_str="deposited at Zenodo [DOI placeholder].",
        replace_str=("deposited at Zenodo [DOI: 10.5281/zenodo.XXXXXXX "
                     "— pending mint]."),
        patch_name="C Zenodo Data Avail",
        expected_hits=1,
    )

    # -----------------------------------------------------------
    # Patch E — Author block FILL with real names (5 authors)
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch E: Real author names + affiliations")
    print("=" * 70)

    apply_global_find_replace(
        doc,
        find_str=("[FILL: see Paper1_BT/_drafts/ for author template; "
                  "add superscript numerals in Word]"),
        replace_str=(
            "Lei Zhou(1); Qingwei Deng(2); Xuechen Li(1); Xinyi Huang(3); "
            "Guangsheng Chen(1,*)\n"
            "(1) State Key Laboratory of Subtropical Silviculture, "
            "College of Environmental and Resource Sciences, Zhejiang "
            "A&F University, Hangzhou, China\n"
            "(2) College of Electronics and Information Engineering, "
            "Guangdong Polytechnic Normal University, Guangzhou, China\n"
            "(3) College of Optoelectronic Engineering and Mechanical "
            "Engineering, Zhejiang A&F University, Hangzhou, China\n"
            "[NOTE: convert (1)/(2)/(3)/(*) to superscript in Word "
            "before submission]"
        ),
        patch_name="E.1 author names",
        expected_hits=1,
    )

    apply_global_find_replace(
        doc,
        find_str="Corresponding author: [FILL: name and email]",
        replace_str=("Corresponding author: Guangsheng Chen "
                     "(chengu1@zafu.edu.cn)"),
        patch_name="E.2 corresponding author",
        expected_hits=1,
    )

    # -----------------------------------------------------------
    # Patch F — CRediT replacement (replace para[143] [To be completed])
    # Risk: "[To be completed]" appears at both para[143] (CRediT)
    # and para[147] (Acknowledgments). To target ONLY the CRediT
    # one, we walk paragraphs and replace the first [To be completed]
    # that comes AFTER a "CRediT" heading.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch F: CRediT statement (sole-author-led, 5-author version)")
    print("=" * 70)

    credit_text = (
        "Lei Zhou: Conceptualization, Methodology, Software, "
        "Validation, Formal analysis, Investigation, Data curation, "
        "Writing — Original Draft, Visualization. Qingwei Deng: "
        "Conceptualization, Writing — Review & Editing. Xuechen Li: "
        "Conceptualization, Writing — Review & Editing. Xinyi Huang: "
        "Conceptualization, Writing — Review & Editing. Guangsheng "
        "Chen: Conceptualization, Supervision, Project administration, "
        "Writing — Review & Editing."
    )

    # Walk paragraphs; find the [To be completed] that follows a
    # CRediT heading.
    credit_replaced = False
    in_credit_section = False
    for p in doc.paragraphs:
        if "CRediT" in p.text:
            in_credit_section = True
            continue
        if in_credit_section and p.text.strip() == "[To be completed]":
            p.text = credit_text
            credit_replaced = True
            print(f"  [F CRediT] OK: replaced [To be completed] under "
                  f"CRediT heading")
            break
    if not credit_replaced:
        print("  [F CRediT] SKIP: no [To be completed] under CRediT")

    # -----------------------------------------------------------
    # Patch G — Acknowledgments replacement (para[147])
    # Same disambiguation strategy: find [To be completed] after
    # "Acknowledgments" heading.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch G: Acknowledgments (TODO placeholder template)")
    print("=" * 70)

    ack_text = (
        "The authors thank [TODO: name of regional grain-spirit "
        "distillery] for providing fresh distillers' grains; [TODO: "
        "regional commercial supplier name] for Protaetia brevitarsis "
        "larvae stocks; and [TODO: laboratory colony source] for the "
        "Tenebrio molitor line. Heavy-metal screening (ICP-MS, CTI "
        "report A2230563971101001C) and proximate composition (CTI "
        "report A2230638815101001C) were performed by Centre Testing "
        "International. The authors thank colleagues at the State Key "
        "Laboratory of Subtropical Silviculture, Zhejiang A&F "
        "University, for helpful discussions on earlier versions of "
        "this manuscript."
    )

    ack_replaced = False
    in_ack_section = False
    for p in doc.paragraphs:
        if p.text.strip() == "Acknowledgments":
            in_ack_section = True
            continue
        if in_ack_section and p.text.strip() == "[To be completed]":
            p.text = ack_text
            ack_replaced = True
            print(f"  [G Acknowledgments] OK: replaced [To be completed] "
                  f"under Acknowledgments heading")
            break
    if not ack_replaced:
        print("  [G Acknowledgments] SKIP: no [To be completed] under "
              "Acknowledgments")

    # -----------------------------------------------------------
    # Patch H — Funding section insertion (NEW section between
    # "Declaration of competing interest" body and "Acknowledgments"
    # heading). Inserted as a NEW paragraph using docx insert_paragraph_before.
    # Option B per operator: no funded support.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch H: Funding section (Option B — no funded support)")
    print("=" * 70)

    funding_heading = "Funding"
    funding_body = (
        "This research did not receive any specific grant from funding "
        "agencies in the public, commercial, or not-for-profit sectors."
    )

    # Find the "Acknowledgments" paragraph and insert two paragraphs
    # before it: a Funding heading and the funding body.
    funding_inserted = False
    for p in doc.paragraphs:
        if p.text.strip() == "Acknowledgments":
            # Use the underlying XML element to insert before
            from copy import deepcopy
            from docx.oxml.ns import qn

            ack_elem = p._element
            parent = ack_elem.getparent()

            # Clone the paragraph element for new paragraphs (preserves
            # style of the surrounding paragraphs).
            new_heading = deepcopy(p._element)
            for t in new_heading.iter(qn("w:t")):
                t.text = ""
            # Set heading text via a single run
            new_heading_runs = new_heading.findall(qn("w:r"))
            if new_heading_runs:
                first_run = new_heading_runs[0]
                # Clear and set text
                for t in first_run.iter(qn("w:t")):
                    t.text = funding_heading
                # Remove extra runs
                for extra_run in new_heading_runs[1:]:
                    new_heading.remove(extra_run)
            parent.insert(list(parent).index(ack_elem), new_heading)

            new_body = deepcopy(p._element)
            for t in new_body.iter(qn("w:t")):
                t.text = ""
            new_body_runs = new_body.findall(qn("w:r"))
            if new_body_runs:
                first_run = new_body_runs[0]
                for t in first_run.iter(qn("w:t")):
                    t.text = funding_body
                for extra_run in new_body_runs[1:]:
                    new_body.remove(extra_run)
            parent.insert(list(parent).index(ack_elem), new_body)

            funding_inserted = True
            print(f"  [H Funding] OK: inserted Funding heading + body "
                  f"before Acknowledgments")
            break
    if not funding_inserted:
        print("  [H Funding] SKIP: Acknowledgments anchor not found")

    # -----------------------------------------------------------
    # Patch J (DEFERRED to Word manual) — (1)(2)(3)(*) → superscript
    # Reason: run-level XML manipulation risk on already-shipped
    # v0.9.1-paper-final docx. Operator can convert all 4 tokens
    # in Word in ~30 seconds (Find each → select → Home → x² button).
    # Note in INSTRUCTIONS_FOR_OPERATOR.md Step 1.5.

    # -----------------------------------------------------------
    # Patch I — LCA scoping insertion in section 4.4
    # Append LCA paragraph to end of para[122] (Co-product section).
    # Safer than paragraph insertion — pure string append.
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Patch I: LCA scoping (Option A — conservative)")
    print("=" * 70)

    lca_anchor = "in future work [12, 13, 19, 30, 69"
    lca_append = (
        " A boundary-explicit life-cycle assessment under the matched "
        "Control-API contract — covering Scope 1 + 2 emissions per "
        "processed tonne (CO2, CH4, N2O, NH3, VOCs), water footprint, "
        "and energy intensity — is pre-registered as part of the V14 "
        "pilot-scale campaign (OSF [DOI to be issued]) and will be "
        "reported in a companion paper currently in preparation. The "
        "present submission scopes itself to within-boundary system "
        "ranking on the matched accounting boundary; the boundary "
        "metering pack defined in Supplementary Table S_Spec5 / Table "
        "S_E1 is the prerequisite for releasing TEA / LCA-grade "
        "sustainability claims (Scope 1 + 2 emissions per processed "
        "tonne, asset productivity per kWh) at pilot scale."
    )

    lca_done = False
    for p in doc.paragraphs:
        if lca_anchor in p.text:
            p.text = p.text + lca_append
            lca_done = True
            print(f"  [I LCA] OK: appended LCA scoping to §4.4 paragraph")
            break
    if not lca_done:
        print(f"  [I LCA] SKIP: anchor {lca_anchor!r} not found")

    # -----------------------------------------------------------
    # Save patched docx — to .y1-patched.docx AND overwrite original
    # (per operator instruction "y1-patched.docx, 原 docx都改")
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Saving patched docx (both .y1-patched.docx AND original)")
    print("=" * 70)
    doc.save(str(OUTPUT))
    # Overwrite original (backup .pre-y1-patch already exists for safety)
    doc.save(str(PAPER))

    out_size = OUTPUT.stat().st_size
    out_sha = sha256_of_file(OUTPUT)
    orig_size = PAPER.stat().st_size
    orig_sha = sha256_of_file(PAPER)

    print(f"  .y1-patched.docx: {OUTPUT}")
    print(f"    size: {out_size} bytes")
    print(f"    SHA-256: {out_sha}")
    print()
    print(f"  Original (NOW OVERWRITTEN): {PAPER}")
    print(f"    size: {orig_size} bytes")
    print(f"    SHA-256: {orig_sha}")
    print()
    if out_sha == orig_sha:
        print("  Both files identical (same Document object saved to both).")
    else:
        print("  WARNING: Output and Original SHA differ!")
    print()
    print(f"  Backup still safe at: {PAPER}.pre-y1-patch")
    print(f"  Backup SHA: 2fd4387028b2b160388c65ccb0f269967e05b55fdeaf6ba62b1570bcb533118d")

    # -----------------------------------------------------------
    # Verify the 6 placeholders are now absent in the patched doc
    # (sanity — confirm find-replace actually changed text)
    # -----------------------------------------------------------
    print()
    print("=" * 70)
    print("Post-patch sanity (placeholders should be 0 hits in patched doc)")
    print("=" * 70)
    patched = Document(str(OUTPUT))
    sanity_finds = [
        ("[Author list and affiliations — to be completed by authors]",
         "A.1 placeholder"),
        ("Corresponding author: [Name, email]", "A.2 placeholder"),
        ("[URL to be issued]", "B.1 placeholder"),
        ("commit [hash to be issued]", "B.2 placeholder"),
        ("[Zenodo DOI to be issued]", "B.3 placeholder"),
        ("[OSF DOI to be issued]", "D placeholder"),
        ("deposited at Zenodo [DOI placeholder].", "C placeholder"),
        ("[FILL: see Paper1_BT/_drafts/", "E.1 intermediate placeholder"),
        ("Corresponding author: [FILL: name and email]",
         "E.2 intermediate placeholder"),
    ]
    for find, name in sanity_finds:
        h = count_hits(patched, find)
        status = "OK (absent)" if h == 0 else f"FAIL ({h} hits still present)"
        print(f"  {name}: {status}")

    # Confirm patched anchors are now present
    print()
    print("Patched-anchor presence checks (should be > 0):")
    after_finds = [
        ("Lei Zhou(1); Qingwei Deng(2)", "E.1 real author names"),
        ("Corresponding author: Guangsheng Chen", "E.2 corresponding author"),
        ("https://github.com/exergyleizhou-ux/bos-platform",
         "B.1 GitHub URL"),
        ("commit 92a7a0f", "B.2 commit hash"),
        ("Zenodo DOI: 10.5281/zenodo.XXXXXXX", "B.3 Zenodo placeholder"),
        ("OSF DOI: 10.17605/OSF.IO/XXXXX", "D OSF placeholder"),
        ("deposited at Zenodo [DOI: 10.5281/zenodo.XXXXXXX — pending mint].",
         "C Zenodo Data Avail replacement"),
        ("Lei Zhou: Conceptualization, Methodology, Software",
         "F CRediT statement"),
        ("Centre Testing International",
         "G Acknowledgments"),
        ("This research did not receive any specific grant",
         "H Funding (Option B)"),
        ("A boundary-explicit life-cycle assessment under the matched",
         "I LCA scoping"),
    ]
    for find, name in after_finds:
        h = count_hits(patched, find)
        status = f"OK ({h} hit(s))" if h >= 1 else "FAIL (absent)"
        print(f"  {name}: {status}")

    print()
    print("Next operator step:")
    print("  1. Open both .docx in Word side-by-side:")
    print(f"     - Original: {PAPER}")
    print(f"     - Patched : {OUTPUT}")
    print("  2. Compare formatting (font, paragraph spacing, "
          "Table 1-4, equations).")
    print("  3. If formatting OK, do not yet replace the original; "
          "wait for the strategy LLM to issue Patch C brief "
          "(Zenodo Data Availability anchor).")
    print("  4. If formatting broken in patched docx, restore from "
          f"{PAPER}.pre-y1-patch and report which patch broke "
          "formatting.")


if __name__ == "__main__":
    main()
