"""
Summarize staged reference-ingestion smoke outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="backend/generated/reference-ingestion",
        help="Reference ingestion generated root.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    staged_files = sorted(root.rglob("staging/*.json"))
    promoted_files = sorted(root.rglob("promoted/campaigns.json"))

    items = []
    for path in staged_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "id": payload.get("id"),
                "source_title": payload.get("source_title"),
                "status": payload.get("status"),
                "species_chain": payload.get("species_chain", []),
                "feedstocks": payload.get("feedstocks", []),
                "field_count": (payload.get("parser_metadata") or {}).get("extracted_field_count"),
                "execution_mode": (payload.get("parser_metadata") or {}).get("execution_mode"),
                "fallback_reason": (payload.get("parser_metadata") or {}).get("fallback_reason"),
            }
        )

    promoted_count = 0
    for path in promoted_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        promoted_count += len(payload) if isinstance(payload, list) else 0

    report = {
        "root": str(root),
        "staged_count": len(items),
        "promoted_count": promoted_count,
        "items_with_5plus_fields": sum(1 for item in items if (item.get("field_count") or 0) >= 5),
        "items_with_species": sum(1 for item in items if item.get("species_chain")),
        "items_with_feedstocks": sum(1 for item in items if item.get("feedstocks")),
        "items": items,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
