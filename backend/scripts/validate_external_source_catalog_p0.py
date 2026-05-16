"""Validate the BOS P0 external-source intake artifacts.

This is a read-only handoff/CI helper. It validates Markdown governance docs
and the staged metadata JSON template without opening any runtime ingestion or
validated-default write path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.external_source_review import ExternalSourceStagedMetadataArtifact
from app.services.external_source_catalog_validator import (
    validate_bsf_extraction_shortlist,
    validate_bsf_reviewer_extraction_cards,
    validate_external_source_catalog,
)


DEFAULT_CATALOG = REPO_ROOT / "docs" / "knowledge" / "BOS_EXTERNAL_SOURCE_CATALOG_P0.md"
DEFAULT_SHORTLIST = REPO_ROOT / "docs" / "knowledge" / "BOS_P0_BSF_EXTRACTION_SHORTLIST.md"
DEFAULT_CARDS = REPO_ROOT / "docs" / "knowledge" / "BOS_P0_BSF_REVIEWER_EXTRACTION_CARDS.md"
DEFAULT_STAGED_METADATA = REPO_ROOT / "docs" / "knowledge" / "BOS_P0_BSF_STAGED_METADATA_TEMPLATE.json"


def validate_artifacts(
    *,
    catalog_path: Path = DEFAULT_CATALOG,
    shortlist_path: Path = DEFAULT_SHORTLIST,
    cards_path: Path = DEFAULT_CARDS,
    staged_metadata_path: Path = DEFAULT_STAGED_METADATA,
) -> dict[str, Any]:
    catalog_rows = validate_external_source_catalog(catalog_path)
    shortlist_rows = validate_bsf_extraction_shortlist(shortlist_path)
    card_rows = validate_bsf_reviewer_extraction_cards(cards_path)
    staged_payload = json.loads(staged_metadata_path.read_text(encoding="utf-8"))
    staged_artifact = ExternalSourceStagedMetadataArtifact(**staged_payload)

    catalog_ids = {row.source_id for row in catalog_rows}
    shortlist_ids = {row.shortlist_id for row in shortlist_rows}
    card_shortlist_ids = {row.shortlist_id for row in card_rows}
    staged_card_ids = {record.card_id for record in staged_artifact.records}
    card_ids = {row.card_id for row in card_rows}

    missing_catalog_refs = sorted({row.source_catalog_id for row in shortlist_rows if row.source_catalog_id not in catalog_ids})
    missing_card_shortlist_refs = sorted(card_shortlist_ids - shortlist_ids)
    missing_staged_card_refs = sorted(staged_card_ids - card_ids)
    missing_cards_in_staged = sorted(card_ids - staged_card_ids)

    cross_reference_errors = {
        "missing_catalog_refs": missing_catalog_refs,
        "missing_card_shortlist_refs": missing_card_shortlist_refs,
        "missing_staged_card_refs": missing_staged_card_refs,
        "missing_cards_in_staged": missing_cards_in_staged,
    }
    if any(cross_reference_errors.values()):
        raise ValueError(json.dumps(cross_reference_errors, indent=2, ensure_ascii=False))

    return {
        "ok": True,
        "catalog_rows": len(catalog_rows),
        "shortlist_rows": len(shortlist_rows),
        "review_card_rows": len(card_rows),
        "staged_metadata_records": len(staged_artifact.records),
        "promotion_enabled": staged_artifact.promotion_enabled,
        "numeric_values_included": staged_artifact.numeric_values_included,
        "validated_default_write_enabled": staged_artifact.validated_default_write_enabled,
        "artifact_status": staged_artifact.artifact_status,
        "paths": {
            "catalog": str(catalog_path),
            "shortlist": str(shortlist_path),
            "review_cards": str(cards_path),
            "staged_metadata": str(staged_metadata_path),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate BOS P0 source catalog intake artifacts.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--shortlist", type=Path, default=DEFAULT_SHORTLIST)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--staged-metadata", type=Path, default=DEFAULT_STAGED_METADATA)
    args = parser.parse_args()

    summary = validate_artifacts(
        catalog_path=args.catalog,
        shortlist_path=args.shortlist,
        cards_path=args.cards,
        staged_metadata_path=args.staged_metadata,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
