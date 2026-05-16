"""
Smoke test staged reference ingestion against real PDFs.

This script is intentionally outside pytest so teams can run it against real
documents and an optional real MinerU CLI without changing production data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.reference_ingestion_service import ReferenceIngestionService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdfs", nargs="+", help="PDF files to parse into staging.")
    parser.add_argument("--tenant-id", type=int, default=1)
    parser.add_argument(
        "--storage-root",
        default="backend/generated/reference-ingestion/smoke",
        help="Smoke output root. Kept separate from regular staging.",
    )
    parser.add_argument("--promote-first", action="store_true")
    args = parser.parse_args()

    service = ReferenceIngestionService(storage_root=Path(args.storage_root))
    items = []

    for pdf in args.pdfs:
        path = Path(pdf)
        item = service.parse_document(
            tenant_id=args.tenant_id,
            filename=path.name,
            content=path.read_bytes(),
            source_title=path.stem,
            source_type="pdf",
        )
        items.append(item)

    promoted = None
    promotion_errors = []
    if args.promote_first:
        for item in items:
            try:
                promoted = service.promote_to_campaign(
                    tenant_id=args.tenant_id,
                    item_id=item.id,
                    notes="reference_ingestion_smoke",
                )
                break
            except ValueError as exc:
                promotion_errors.append({"item_id": item.id, "reason": str(exc)})

    summary = {
        "storage_root": args.storage_root,
        "parsed_count": len(items),
        "items": [
            {
                "id": item.id,
                "source_title": item.source_title,
                "status": item.status,
                "species_chain": item.species_chain,
                "feedstocks": item.feedstocks,
                "evidence_level": item.evidence_level,
                "campaign_type": item.campaign_type,
                "field_count": item.parser_metadata.extracted_field_count,
                "execution_mode": item.parser_metadata.execution_mode,
                "fallback_reason": item.parser_metadata.fallback_reason,
            }
            for item in items
        ],
        "promoted_campaign_key": promoted[1].key if promoted else None,
        "promotion_errors": promotion_errors,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
