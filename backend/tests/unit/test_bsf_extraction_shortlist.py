from pathlib import Path

from app.services.external_source_catalog_validator import (
    collect_bsf_extraction_shortlist_errors,
    validate_bsf_extraction_shortlist,
)


SHORTLIST_PATH = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_P0_BSF_EXTRACTION_SHORTLIST.md"


def test_bsf_extraction_shortlist_is_doi_backed_and_review_gated():
    rows = validate_bsf_extraction_shortlist(SHORTLIST_PATH)

    assert len(rows) == 8
    assert collect_bsf_extraction_shortlist_errors(rows) == []
    assert {row.human_review_required for row in rows} == {"true"}
    assert {row.ingestion_mode for row in rows} <= {"manual_review_first", "metadata_only"}


def test_bsf_extraction_shortlist_keeps_defaults_and_runtime_paths_blocked():
    rows = validate_bsf_extraction_shortlist(SHORTLIST_PATH)

    for row in rows:
        lowered = row.all_text.lower().replace("`", "")
        assert "species_db" not in lowered
        assert "feedstock_db" not in lowered
        assert "promote into validated defaults" not in lowered
        assert "release evidence" not in lowered or "no release evidence" in lowered or "no compliance/release evidence" in lowered


def test_bsf_extraction_shortlist_links_back_to_catalog_rows():
    rows = validate_bsf_extraction_shortlist(SHORTLIST_PATH)
    catalog_ids = {row.source_catalog_id for row in rows}

    assert "A-BSF-002" in catalog_ids
    assert "A-BSF-003" in catalog_ids
    assert "C-LCA-009" in catalog_ids
    assert all(source_id.startswith(("A-BSF-", "C-LCA-")) for source_id in catalog_ids)
