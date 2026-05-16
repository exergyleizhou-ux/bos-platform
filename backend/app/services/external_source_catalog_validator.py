"""Validation helpers for the P0 external source catalog.

The catalog is documentation and staged-ingestion readiness metadata. These
helpers intentionally do not connect rows to runtime activation or defaults.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SOURCE_ID_RE = re.compile(r"^(A-BSF|B-FEED|C-LCA|D-TEA|E-COMP|F-MODEL|G-OSS)-\d{3}$")
SHORTLIST_ID_RE = re.compile(r"^BSF-LIT-\d{3}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
REVIEW_CARD_ID_RE = re.compile(r"^BSF-CARD-\d{3}$")

VALID_INGESTION_MODES = {
    "manual_review_first",
    "auto_ingest_allowed",
    "metadata_only",
    "reference_only",
}

VALID_SOURCE_KINDS = {
    "official_standard",
    "peer_reviewed_literature",
    "public_dataset",
    "industry_reference",
    "commercial_database",
    "model_provider_docs",
    "github_reference",
}

REQUIRED_COLUMNS = {
    "ID",
    "来源名称",
    "来源 owner",
    "许可证 / 商用限制",
    "BOS 接入模块",
    "BOS evidence_source_kind",
    "ingestion_mode",
    "是否可自动 ingestion",
    "是否需要人工审核",
    "下一步动作",
}

SENSITIVE_SOURCE_KINDS = {
    "official_standard",
    "peer_reviewed_literature",
    "commercial_database",
    "model_provider_docs",
    "github_reference",
}

SENSITIVE_CATEGORY_MARKERS = ("LCA", "TEA", "Compliance", "合规")
RESTRICTED_SOURCE_MARKERS = ("paywall", "publisher", "commercial", "market report", "ecoinvent", "IEA", "ISO")
AUTO_ALLOWED_METADATA_MARKERS = ("staged", "metadata", "元数据", "API", "CSV", "citation", "indicator", "license")
FORBIDDEN_PROMOTION_MARKERS = (
    "write to species_db",
    "write to feedstock_db",
    "modify species_db",
    "modify feedstock_db",
    "validated-default",
    "promote into validated defaults",
    "promote to validated defaults",
    "insert as validated defaults",
)

SHORTLIST_REQUIRED_COLUMNS = {
    "shortlist_id",
    "source_catalog_id",
    "title",
    "DOI",
    "source_url",
    "article_type",
    "extraction_focus",
    "ingestion_mode",
    "human_review_required",
    "blocked_use",
    "next_action",
}

REVIEW_CARD_REQUIRED_COLUMNS = {
    "card_id",
    "shortlist_id",
    "source_catalog_id",
    "DOI",
    "review_status",
    "reviewer",
    "reviewed_at",
    "license_status",
    "evidence_source_kind",
    "ingestion_mode",
    "human_review_required",
    "extracted_numeric_values_allowed",
    "boundary_condition_required",
    "allowed_use",
    "blocked_use",
    "next_action",
}


@dataclass(frozen=True, slots=True)
class ExternalSourceCatalogRow:
    raw: dict[str, str]

    @property
    def source_id(self) -> str:
        return self.raw["ID"]

    @property
    def category(self) -> str:
        return self.raw["资料类别"]

    @property
    def source_name(self) -> str:
        return self.raw["来源名称"]

    @property
    def source_kind(self) -> str:
        return self.raw["BOS evidence_source_kind"]

    @property
    def ingestion_mode(self) -> str:
        return self.raw["ingestion_mode"]

    @property
    def auto_ingestion_note(self) -> str:
        return self.raw["是否可自动 ingestion"]

    @property
    def human_review_note(self) -> str:
        return self.raw["是否需要人工审核"]

    @property
    def all_text(self) -> str:
        return " | ".join(self.raw.values())


@dataclass(frozen=True, slots=True)
class BsfExtractionShortlistRow:
    raw: dict[str, str]

    @property
    def shortlist_id(self) -> str:
        return self.raw["shortlist_id"]

    @property
    def source_catalog_id(self) -> str:
        return self.raw["source_catalog_id"]

    @property
    def doi(self) -> str:
        return self.raw["DOI"]

    @property
    def ingestion_mode(self) -> str:
        return self.raw["ingestion_mode"]

    @property
    def human_review_required(self) -> str:
        return self.raw["human_review_required"]

    @property
    def all_text(self) -> str:
        return " | ".join(self.raw.values())


@dataclass(frozen=True, slots=True)
class BsfReviewerExtractionCardRow:
    raw: dict[str, str]

    @property
    def card_id(self) -> str:
        return self.raw["card_id"]

    @property
    def shortlist_id(self) -> str:
        return self.raw["shortlist_id"]

    @property
    def source_catalog_id(self) -> str:
        return self.raw["source_catalog_id"]

    @property
    def doi(self) -> str:
        return self.raw["DOI"]

    @property
    def review_status(self) -> str:
        return self.raw["review_status"]

    @property
    def ingestion_mode(self) -> str:
        return self.raw["ingestion_mode"]

    @property
    def human_review_required(self) -> str:
        return self.raw["human_review_required"]

    @property
    def extracted_numeric_values_allowed(self) -> str:
        return self.raw["extracted_numeric_values_allowed"]

    @property
    def boundary_condition_required(self) -> str:
        return self.raw["boundary_condition_required"]

    @property
    def all_text(self) -> str:
        return " | ".join(self.raw.values())


def parse_external_source_catalog(path: Path) -> list[ExternalSourceCatalogRow]:
    return parse_external_source_catalog_text(path.read_text(encoding="utf-8"))


def parse_external_source_catalog_text(text: str) -> list[ExternalSourceCatalogRow]:
    headers: list[str] | None = None
    rows: list[ExternalSourceCatalogRow] = []

    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _split_markdown_row(line)
        if not cells:
            continue
        if cells[0] == "ID":
            headers = cells
            continue
        if cells[0] == "---" or not SOURCE_ID_RE.match(cells[0]):
            continue
        if headers is None:
            raise ValueError("Catalog row appeared before the source catalog header.")
        if len(cells) != len(headers):
            raise ValueError(f"{cells[0]} has {len(cells)} cells; expected {len(headers)}.")
        rows.append(ExternalSourceCatalogRow(dict(zip(headers, cells, strict=True))))

    return rows


def validate_external_source_catalog(path: Path) -> list[ExternalSourceCatalogRow]:
    rows = parse_external_source_catalog(path)
    errors = collect_external_source_catalog_errors(rows)
    if errors:
        raise ValueError("\n".join(errors))
    return rows


def collect_external_source_catalog_errors(rows: list[ExternalSourceCatalogRow]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for row in rows:
        source_id = row.source_id
        if source_id in seen:
            errors.append(f"{source_id}: duplicate source ID.")
        seen.add(source_id)

        missing = [column for column in REQUIRED_COLUMNS if not row.raw.get(column, "").strip()]
        if missing:
            errors.append(f"{source_id}: missing required columns: {', '.join(sorted(missing))}.")

        if row.ingestion_mode not in VALID_INGESTION_MODES:
            errors.append(f"{source_id}: invalid ingestion_mode {row.ingestion_mode!r}.")
        if row.source_kind not in VALID_SOURCE_KINDS:
            errors.append(f"{source_id}: invalid evidence source kind {row.source_kind!r}.")

        if _requires_human_review(row) and not _is_yes(row.human_review_note):
            errors.append(f"{source_id}: sensitive source must require human review.")

        if row.ingestion_mode == "auto_ingest_allowed":
            auto_text = f"{row.auto_ingestion_note} {row.all_text}".lower()
            if not any(marker.lower() in auto_text for marker in AUTO_ALLOWED_METADATA_MARKERS):
                errors.append(f"{source_id}: auto ingestion must be staged metadata only.")
            if row.source_kind not in {"public_dataset", "peer_reviewed_literature"}:
                errors.append(f"{source_id}: auto ingestion is not allowed for {row.source_kind}.")

        lowered = row.all_text.lower().replace("`", "")
        if any(marker in lowered for marker in FORBIDDEN_PROMOTION_MARKERS):
            errors.append(f"{source_id}: row appears to promote external data into validated defaults.")

    return errors


def parse_bsf_extraction_shortlist(path: Path) -> list[BsfExtractionShortlistRow]:
    return parse_bsf_extraction_shortlist_text(path.read_text(encoding="utf-8"))


def parse_bsf_extraction_shortlist_text(text: str) -> list[BsfExtractionShortlistRow]:
    headers: list[str] | None = None
    rows: list[BsfExtractionShortlistRow] = []

    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _split_markdown_row(line)
        if not cells:
            continue
        if cells[0] == "shortlist_id":
            headers = cells
            continue
        if cells[0] == "---" or not SHORTLIST_ID_RE.match(cells[0]):
            continue
        if headers is None:
            raise ValueError("Shortlist row appeared before the shortlist header.")
        if len(cells) != len(headers):
            raise ValueError(f"{cells[0]} has {len(cells)} cells; expected {len(headers)}.")
        rows.append(BsfExtractionShortlistRow(dict(zip(headers, cells, strict=True))))

    return rows


def validate_bsf_extraction_shortlist(path: Path) -> list[BsfExtractionShortlistRow]:
    rows = parse_bsf_extraction_shortlist(path)
    errors = collect_bsf_extraction_shortlist_errors(rows)
    if errors:
        raise ValueError("\n".join(errors))
    return rows


def collect_bsf_extraction_shortlist_errors(rows: list[BsfExtractionShortlistRow]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for row in rows:
        shortlist_id = row.shortlist_id
        if shortlist_id in seen:
            errors.append(f"{shortlist_id}: duplicate shortlist ID.")
        seen.add(shortlist_id)

        missing = [column for column in SHORTLIST_REQUIRED_COLUMNS if not row.raw.get(column, "").strip()]
        if missing:
            errors.append(f"{shortlist_id}: missing required columns: {', '.join(sorted(missing))}.")

        if not SOURCE_ID_RE.match(row.source_catalog_id):
            errors.append(f"{shortlist_id}: invalid source catalog ID {row.source_catalog_id!r}.")
        if not DOI_RE.match(row.doi):
            errors.append(f"{shortlist_id}: invalid DOI {row.doi!r}.")
        if row.ingestion_mode not in {"manual_review_first", "metadata_only"}:
            errors.append(f"{shortlist_id}: shortlist rows must be manual_review_first or metadata_only.")
        if row.human_review_required.lower() != "true":
            errors.append(f"{shortlist_id}: human_review_required must be true.")

        lowered = row.all_text.lower().replace("`", "")
        if any(marker in lowered for marker in FORBIDDEN_PROMOTION_MARKERS):
            errors.append(f"{shortlist_id}: row appears to promote external data into validated defaults.")

    return errors


def parse_bsf_reviewer_extraction_cards(path: Path) -> list[BsfReviewerExtractionCardRow]:
    return parse_bsf_reviewer_extraction_cards_text(path.read_text(encoding="utf-8"))


def parse_bsf_reviewer_extraction_cards_text(text: str) -> list[BsfReviewerExtractionCardRow]:
    headers: list[str] | None = None
    rows: list[BsfReviewerExtractionCardRow] = []

    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = _split_markdown_row(line)
        if not cells:
            continue
        if cells[0] == "card_id":
            headers = cells
            continue
        if cells[0] == "---" or not REVIEW_CARD_ID_RE.match(cells[0]):
            continue
        if headers is None:
            raise ValueError("Reviewer card row appeared before the card header.")
        if len(cells) != len(headers):
            raise ValueError(f"{cells[0]} has {len(cells)} cells; expected {len(headers)}.")
        rows.append(BsfReviewerExtractionCardRow(dict(zip(headers, cells, strict=True))))

    return rows


def validate_bsf_reviewer_extraction_cards(path: Path) -> list[BsfReviewerExtractionCardRow]:
    rows = parse_bsf_reviewer_extraction_cards(path)
    errors = collect_bsf_reviewer_extraction_card_errors(rows)
    if errors:
        raise ValueError("\n".join(errors))
    return rows


def collect_bsf_reviewer_extraction_card_errors(rows: list[BsfReviewerExtractionCardRow]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()

    for row in rows:
        card_id = row.card_id
        if card_id in seen:
            errors.append(f"{card_id}: duplicate card ID.")
        seen.add(card_id)

        missing = [column for column in REVIEW_CARD_REQUIRED_COLUMNS if not row.raw.get(column, "").strip()]
        if missing:
            errors.append(f"{card_id}: missing required columns: {', '.join(sorted(missing))}.")

        if not SHORTLIST_ID_RE.match(row.shortlist_id):
            errors.append(f"{card_id}: invalid shortlist ID {row.shortlist_id!r}.")
        if not SOURCE_ID_RE.match(row.source_catalog_id):
            errors.append(f"{card_id}: invalid source catalog ID {row.source_catalog_id!r}.")
        if not DOI_RE.match(row.doi):
            errors.append(f"{card_id}: invalid DOI {row.doi!r}.")
        if row.review_status != "pending_review":
            errors.append(f"{card_id}: P0 reviewer cards must start as pending_review.")
        if row.ingestion_mode not in {"manual_review_first", "metadata_only"}:
            errors.append(f"{card_id}: reviewer cards must be manual_review_first or metadata_only.")
        if row.human_review_required.lower() != "true":
            errors.append(f"{card_id}: human_review_required must be true.")
        if row.extracted_numeric_values_allowed.lower() != "false":
            errors.append(f"{card_id}: extracted numeric values must remain blocked.")
        if row.boundary_condition_required.lower() != "true":
            errors.append(f"{card_id}: boundary_condition_required must be true.")

        lowered = row.all_text.lower().replace("`", "")
        if any(marker in lowered for marker in FORBIDDEN_PROMOTION_MARKERS):
            errors.append(f"{card_id}: row appears to promote external data into validated defaults.")
        if "default" not in row.raw["blocked_use"].lower() or "release evidence" not in row.raw["blocked_use"].lower():
            errors.append(f"{card_id}: blocked_use must block defaults and release evidence.")

    return errors


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_yes(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("是") or stripped.startswith("部分")


def _requires_human_review(row: ExternalSourceCatalogRow) -> bool:
    if row.source_kind in SENSITIVE_SOURCE_KINDS:
        return True
    if any(marker in row.category for marker in SENSITIVE_CATEGORY_MARKERS):
        return True
    return any(marker.lower() in row.all_text.lower() for marker in RESTRICTED_SOURCE_MARKERS)
