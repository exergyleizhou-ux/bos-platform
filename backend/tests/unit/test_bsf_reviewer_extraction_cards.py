from pathlib import Path

from app.schemas.external_source_review import ExternalSourceReviewCard
from app.services.external_source_catalog_validator import (
    collect_bsf_reviewer_extraction_card_errors,
    validate_bsf_reviewer_extraction_cards,
)


CARDS_PATH = Path(__file__).resolve().parents[3] / "docs" / "knowledge" / "BOS_P0_BSF_REVIEWER_EXTRACTION_CARDS.md"


def test_bsf_reviewer_extraction_cards_are_review_gated_metadata_only():
    rows = validate_bsf_reviewer_extraction_cards(CARDS_PATH)

    assert len(rows) == 8
    assert collect_bsf_reviewer_extraction_card_errors(rows) == []
    assert {row.review_status for row in rows} == {"pending_review"}
    assert {row.human_review_required for row in rows} == {"true"}
    assert {row.extracted_numeric_values_allowed for row in rows} == {"false"}


def test_bsf_reviewer_extraction_cards_match_pydantic_schema():
    rows = validate_bsf_reviewer_extraction_cards(CARDS_PATH)

    cards = [
        ExternalSourceReviewCard(
            card_id=row.raw["card_id"],
            shortlist_id=row.raw["shortlist_id"],
            source_catalog_id=row.raw["source_catalog_id"],
            doi=row.raw["DOI"],
            review_status=row.raw["review_status"],
            reviewer=row.raw["reviewer"],
            reviewed_at=row.raw["reviewed_at"],
            license_status=row.raw["license_status"],
            evidence_source_kind=row.raw["evidence_source_kind"],
            ingestion_mode=row.raw["ingestion_mode"],
            human_review_required=row.raw["human_review_required"].lower() == "true",
            extracted_numeric_values_allowed=row.raw["extracted_numeric_values_allowed"].lower() == "true",
            boundary_condition_required=row.raw["boundary_condition_required"].lower() == "true",
            allowed_use=row.raw["allowed_use"],
            blocked_use=row.raw["blocked_use"],
            next_action=row.raw["next_action"],
        )
        for row in rows
    ]

    assert cards[0].card_id == "BSF-CARD-001"
    assert cards[-1].shortlist_id == "BSF-LIT-008"


def test_bsf_reviewer_extraction_cards_keep_defaults_and_release_blocked():
    rows = validate_bsf_reviewer_extraction_cards(CARDS_PATH)

    for row in rows:
        blocked_use = row.raw["blocked_use"].lower()
        assert "default" in blocked_use
        assert "release evidence" in blocked_use
        assert "species_db" not in row.all_text.lower()
        assert "feedstock_db" not in row.all_text.lower()
