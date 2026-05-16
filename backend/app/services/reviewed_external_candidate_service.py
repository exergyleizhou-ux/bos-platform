"""DB-backed reviewed external candidate foundation.

This service persists P0 source metadata, review cards, staged extraction
records, and reviewer-approved candidate records. It deliberately stops before
runtime activation; activation remains owned by external_knowledge_activation_service.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import parse_user_roles
from app.models import User
from app.models_bos import (
    ExternalSourceExtractionRecord,
    ExternalSourceRecord,
    ExternalSourceReviewCardRecord,
    LiteratureExtractionCandidateRecord,
    LiteratureExtractionReviewDraftRecord,
    LiteratureValueOverlayRecord,
    LiteratureValuePromotionApprovalRecord,
    LiteratureValuePromotionRequestRecord,
    LiteratureValueReleaseEvidenceLinkRecord,
    LiteratureValueRollbackRecord,
    LiteratureValueRuntimeActivationRecord,
    ReleaseDecision,
    ReviewedExternalCandidateRecord,
)
from app.engine.external_knowledge_candidates import (
    list_external_factor_candidates,
    list_literature_extraction_candidate_payloads,
)
from app.engine.feedstock_db import FEEDSTOCK_CANDIDATE_DB, FEEDSTOCK_DB
from app.engine.risk_engine import SUBSTRATE_RISK_PROFILES
from app.engine.species_db import BIOEXECUTOR_CANDIDATE_DB, SPECIES_DB
from app.schemas.external_source_review import (
    BsfReviewedMetadataCandidatePayload,
    BusinessKnowledgeReviewPacketExportResponse,
    BusinessKnowledgeReviewPacketResponse,
    BusinessKnowledgeCoverageGroup,
    BusinessKnowledgeCoverageItem,
    BusinessKnowledgeReviewWorkflow,
    METADATA_ONLY_REVIEWED_CANDIDATE_TYPES,
    REVIEWED_CANDIDATE_DOMAINS,
    ReviewedMetadataCandidatePayload,
    ExternalSourceCatalogResponse,
    ExternalSourceExtractionListResponse,
    ExternalSourceExtractionRead,
    ExternalSourcePhase4ADomainSeedResponse,
    ExternalSourcePhase4AReviewedCandidateFillResponse,
    ExternalSourceP0SeedResponse,
    ExternalSourceProcurementSummary,
    ExternalSourceReviewCardListResponse,
    ExternalSourceReviewCardRead,
    ExternalSourceReviewCardResolveRequest,
    ExternalSourceReviewCardResolveResponse,
    ExternalSourceSchemaReadinessResponse,
    ExternalSourceSchemaReadinessTable,
    ExternalKnowledgeCoverageDomain,
    ExternalSourceStagedMetadataArtifact,
    FeedstockDatasetCandidateListResponse,
    FeedstockDatasetCandidateRead,
    LiteratureExtractionCandidateListResponse,
    LiteratureExtractionCandidateRead,
    LiteratureExtractionCandidateReviewPacketBulkExportResponse,
    LiteratureExtractionCandidateReviewPacketExportResponse,
    LiteratureExtractionCandidateReviewPacketResponse,
    LiteratureExtractionCandidateSeedResponse,
    LiteratureExtractionEvidenceChainReadinessResponse,
    LiteratureExtractionReviewDraftCreateRequest,
    LiteratureExtractionReviewDraftComparisonResponse,
    LiteratureExtractionReviewDraftListResponse,
    LiteratureExtractionReviewDraftResponse,
    LiteratureExtractionReviewDraftRevisionRead,
    LiteratureValueOverlayCreateRequest,
    LiteratureValueOverlayResponse,
    LiteratureValuePromotionAuditExportResponse,
    LiteratureValuePromotionApprovalCreateRequest,
    LiteratureValuePromotionApprovalResponse,
    LiteratureValuePromotionLifecycleResponse,
    LiteratureValuePromotionReadinessResponse,
    LiteratureValuePromotionRejectRequest,
    LiteratureValuePromotionRequestCreateRequest,
    LiteratureValuePromotionRequestResponse,
    LiteratureValueReleaseEvidenceLinkCreateRequest,
    LiteratureValueReleaseEvidenceLinkResponse,
    LiteratureValueRollbackCreateRequest,
    LiteratureValueRollbackResponse,
    LiteratureValueRuntimeActivationCreateRequest,
    LiteratureValueRuntimeActivationDeactivateRequest,
    LiteratureValueRuntimeActivationPreviewResponse,
    LiteratureValueRuntimeActivationResponse,
    ReviewedExternalCandidateLaneSummary,
    ReviewedExternalCandidateKnowledgeBaseResponse,
    ReviewedExternalCandidateActivationPreviewResponse,
    ReviewedExternalCandidateListResponse,
    ReviewedExternalCandidateRead,
    ReviewedExternalCandidateRollbackPreviewResponse,
    ReviewedExternalCandidateRuntimeReadinessResponse,
    ReviewedExternalCandidateReviewPacketExportResponse,
    ReviewedExternalCandidateReviewPacketResponse,
    reviewed_candidate_domain,
    reviewed_candidate_types_for_domain,
    reviewed_candidate_type_group,
    review_status_for_action,
)
from app.services.external_knowledge_activation_service import (
    activation_scope_key,
    default_activation_runtime_paths,
    get_active_external_candidate_payload,
    resolve_active_runtime_activation,
)
from app.services.reviewed_external_candidates.ids import (
    new_literature_review_draft_id,
    new_literature_value_overlay_id,
    new_literature_value_promotion_approval_id,
    new_literature_value_promotion_request_id,
    new_literature_value_release_evidence_link_id,
    new_literature_value_rollback_id,
    new_literature_value_runtime_activation_id,
)
from app.services.external_source_catalog_validator import (
    ExternalSourceCatalogRow,
    parse_external_source_catalog,
    validate_external_source_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
P0_CATALOG_PATH = REPO_ROOT / "docs" / "knowledge" / "BOS_EXTERNAL_SOURCE_CATALOG_P0.md"
P0_STAGED_METADATA_PATH = REPO_ROOT / "docs" / "knowledge" / "BOS_P0_BSF_STAGED_METADATA_TEMPLATE.json"
PHASE4A_DOMAIN_METADATA_SEEDS_PATH = REPO_ROOT / "docs" / "knowledge" / "BOS_PHASE4A_DOMAIN_METADATA_SEEDS.json"

DEFAULT_REVIEW_CARD_NEXT_ACTION = "Assign reviewer and resolve license, boundary, allowed use, and blocked use."
APPROVED_FOR_CANDIDATE_USE = "approved_for_candidate_use"

EXTERNAL_SOURCE_REQUIRED_TABLES = {
    ExternalSourceRecord.__tablename__: ExternalSourceRecord,
    ExternalSourceReviewCardRecord.__tablename__: ExternalSourceReviewCardRecord,
    ExternalSourceExtractionRecord.__tablename__: ExternalSourceExtractionRecord,
    LiteratureExtractionCandidateRecord.__tablename__: LiteratureExtractionCandidateRecord,
    LiteratureExtractionReviewDraftRecord.__tablename__: LiteratureExtractionReviewDraftRecord,
    LiteratureValueOverlayRecord.__tablename__: LiteratureValueOverlayRecord,
    LiteratureValuePromotionRequestRecord.__tablename__: LiteratureValuePromotionRequestRecord,
    LiteratureValuePromotionApprovalRecord.__tablename__: LiteratureValuePromotionApprovalRecord,
    LiteratureValueRuntimeActivationRecord.__tablename__: LiteratureValueRuntimeActivationRecord,
    LiteratureValueReleaseEvidenceLinkRecord.__tablename__: LiteratureValueReleaseEvidenceLinkRecord,
    LiteratureValueRollbackRecord.__tablename__: LiteratureValueRollbackRecord,
    ReviewedExternalCandidateRecord.__tablename__: ReviewedExternalCandidateRecord,
}

PHASE4A_DOMAIN_SOURCE_IDS = {
    "lca": {f"C-LCA-{index:03d}" for index in range(10, 16)},
    "tea": {f"D-TEA-{index:03d}" for index in range(8, 14)},
    "compliance": {f"E-COMP-{index:03d}" for index in range(11, 16)},
    "model_provider": {f"F-MODEL-{index:03d}" for index in range(17, 21)},
    "github_reference": {f"G-OSS-{index:03d}" for index in range(11, 14)},
}
PHASE4A_DOMAIN_EXPECTED_COUNTS = {
    domain: len(source_ids) for domain, source_ids in PHASE4A_DOMAIN_SOURCE_IDS.items()
}
PHASE4A_REVIEWED_CANDIDATE_TYPE_BY_DOMAIN = {
    "lca": "lca_factor_candidate",
    "tea": "tea_factor_candidate",
    "compliance": "compliance_rule_candidate",
    "model_provider": "model_provider_capability_candidate",
    "github_reference": "github_reference_candidate",
}
PHASE4A_SOURCE_ID_DOMAIN_BY_ARTIFACT_DOMAIN = {
    source_id: ("github_reference" if domain == "oss" else domain)
    for domain, source_ids in {
        "lca": {f"C-LCA-{index:03d}" for index in range(10, 16)},
        "tea": {f"D-TEA-{index:03d}" for index in range(8, 14)},
        "compliance": {f"E-COMP-{index:03d}" for index in range(11, 16)},
        "model_provider": {f"F-MODEL-{index:03d}" for index in range(17, 21)},
        "oss": {f"G-OSS-{index:03d}" for index in range(11, 14)},
    }.items()
    for source_id in source_ids
}
P0_KNOWLEDGE_COVERAGE_PREFIXES = {
    "bsf_metadata": {
        "label": "BSF literature and extraction metadata",
        "prefix": "A-BSF-",
    },
    "feedstock_metadata": {
        "label": "Feedstock public dataset metadata",
        "prefix": "B-FEED-",
    },
    "lca": {
        "label": "LCA source metadata",
        "prefix": "C-LCA-",
    },
    "tea": {
        "label": "TEA source metadata",
        "prefix": "D-TEA-",
    },
    "compliance": {
        "label": "Compliance source metadata",
        "prefix": "E-COMP-",
    },
    "model_provider": {
        "label": "Model provider capability metadata",
        "prefix": "F-MODEL-",
    },
    "github_reference": {
        "label": "OSS and GitHub reference metadata",
        "prefix": "G-OSS-",
    },
}

BUSINESS_COVERAGE_STATUS_SCORES = {
    "validated_read_model": 1.0,
    "candidate_read_model": 0.75,
    "source_metadata_only": 0.5,
    "partial": 0.5,
    "candidate_needed": 0.0,
    "missing": 0.0,
}


def _catalog_field(row: ExternalSourceCatalogRow, *names: str) -> str | None:
    for name in names:
        value = row.raw.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _source_values(row: ExternalSourceCatalogRow) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "source_name": row.source_name,
        "source_owner": _catalog_field(row, "来源 owner", "source_owner", "owner"),
        "source_category": row.category,
        "license_note": _catalog_field(row, "许可证 / 商用限制", "license_note", "license"),
        "bos_module": _catalog_field(row, "BOS 接入模块", "bos_module"),
        "evidence_source_kind": row.source_kind,
        "ingestion_mode": row.ingestion_mode,
        "auto_ingestion_note": row.auto_ingestion_note,
        "human_review_note": row.human_review_note,
        "next_action": _catalog_field(row, "下一步动作", "next_action"),
        "raw_payload": row.raw,
    }


async def seed_p0_external_sources(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> ExternalSourceP0SeedResponse:
    catalog_rows = validate_external_source_catalog(P0_CATALOG_PATH)
    source_rows_by_id = {row.source_id: row for row in catalog_rows}
    artifact = ExternalSourceStagedMetadataArtifact.model_validate(
        json.loads(P0_STAGED_METADATA_PATH.read_text(encoding="utf-8"))
    )

    for row in catalog_rows:
        await _upsert_source(db, row)
    await db.flush()

    seeded_card_ids: list[str] = []
    for staged_record in artifact.records:
        source = source_rows_by_id.get(staged_record.source_catalog_id)
        if source is None:
            raise ValueError(f"{staged_record.card_id}: source catalog row not found")
        card = await _upsert_review_card(
            db,
            tenant_id=tenant_id,
            staged_record=staged_record.model_dump(mode="json"),
        )
        await db.flush()
        await _upsert_extraction_record(
            db,
            tenant_id=tenant_id,
            review_card=card,
            staged_record=staged_record.model_dump(mode="json"),
        )
        seeded_card_ids.append(staged_record.card_id)

    await db.commit()

    return ExternalSourceP0SeedResponse(
        source_count=len(catalog_rows),
        review_card_count=await _count_review_cards(db, tenant_id=tenant_id),
        extraction_count=await _count_extractions(db, tenant_id=tenant_id),
        reviewed_candidate_count=await _count_reviewed_candidates(db, tenant_id=tenant_id),
        seeded_card_ids=seeded_card_ids,
    )


async def seed_phase4a_domain_metadata_sources(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> ExternalSourcePhase4ADomainSeedResponse:
    """Seed only Phase 4A source metadata rows into the external source catalog."""

    catalog_rows = {row.source_id: row for row in validate_external_source_catalog(P0_CATALOG_PATH)}
    seed_records = _load_phase4a_domain_seed_records()

    created_source_ids: list[str] = []
    updated_source_ids: list[str] = []
    for record in seed_records:
        source_id = str(record["source_id"])
        catalog_row = catalog_rows.get(source_id)
        if catalog_row is None:
            raise ValueError(f"{source_id}: source catalog row not found")
        existing = await get_source_record(db, source_id=source_id)
        source = await _upsert_phase4a_source(db, catalog_row, seed_record=record)
        if existing is None:
            created_source_ids.append(source.source_id)
        else:
            updated_source_ids.append(source.source_id)

    await db.commit()

    readiness = await get_external_source_schema_readiness(db)
    summary = await get_reviewed_candidate_lane_summary(db, tenant_id=tenant_id)
    return ExternalSourcePhase4ADomainSeedResponse(
        source_count=len(seed_records),
        created_source_count=len(created_source_ids),
        updated_source_count=len(updated_source_ids),
        seeded_source_ids=sorted(created_source_ids + updated_source_ids),
        phase4a_domain_metadata_ready=readiness.phase4a_domain_metadata_ready,
        phase4a_domain_candidate_counts=readiness.phase4a_domain_candidate_counts,
        phase4a_domain_expected_counts=readiness.phase4a_domain_expected_counts,
        phase4a_domain_missing_counts=readiness.phase4a_domain_missing_counts,
        runtime_activated_count=summary.runtime_activated_count,
        validated_default_write_enabled_count=summary.validated_default_write_enabled_count,
        numeric_value_candidate_count=summary.numeric_value_candidate_count,
    )


async def fill_phase4a_domain_reviewed_candidates(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer_user_id: int,
    reviewer: str = "BOS Phase 4A metadata reviewer",
) -> ExternalSourcePhase4AReviewedCandidateFillResponse:
    """Promote Phase 4A source metadata into review-gated metadata candidates.

    This records a reviewer-approved candidate lane for every Phase 4A source
    row, but it still does not extract numeric values, activate runtime
    overlays, or write validated defaults.
    """

    await seed_phase4a_domain_metadata_sources(db, tenant_id=tenant_id)
    seed_records = sorted(_load_phase4a_domain_seed_records(), key=lambda record: str(record["source_id"]))
    reviewed_at = datetime.now(UTC)
    created_count = 0
    updated_count = 0
    reviewed_candidate_ids: list[str] = []

    for seed_record in seed_records:
        source_id = str(seed_record["source_id"])
        source = await get_source_record(db, source_id=source_id)
        if source is None:
            raise ValueError(f"{source_id}: Phase 4A source record not found after seed")
        card = await _upsert_phase4a_review_card(
            db,
            tenant_id=tenant_id,
            source=source,
            seed_record=seed_record,
            reviewer_user_id=reviewer_user_id,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        await db.flush()
        extraction = await _upsert_phase4a_extraction_record(
            db,
            tenant_id=tenant_id,
            review_card=card,
            source=source,
            seed_record=seed_record,
        )
        payload = _phase4a_review_resolution_payload(
            source=source,
            seed_record=seed_record,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        candidate, created = await _upsert_reviewed_candidate(
            db,
            tenant_id=tenant_id,
            card=card,
            extraction=extraction,
            payload=payload,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
        reviewed_candidate_ids.append(candidate.candidate_id)

    await db.commit()
    summary = await get_reviewed_candidate_lane_summary(db, tenant_id=tenant_id)
    return ExternalSourcePhase4AReviewedCandidateFillResponse(
        source_count=len(seed_records),
        reviewed_candidate_count=summary.reviewed_candidate_count,
        created_reviewed_candidate_count=created_count,
        updated_reviewed_candidate_count=updated_count,
        reviewed_candidate_ids=reviewed_candidate_ids,
        candidate_types=summary.candidate_types,
        candidate_domains=summary.candidate_domains,
        runtime_activated_count=summary.runtime_activated_count,
        validated_default_write_enabled_count=summary.validated_default_write_enabled_count,
        numeric_value_candidate_count=summary.numeric_value_candidate_count,
    )


def _load_phase4a_domain_seed_records() -> list[dict[str, Any]]:
    artifact = json.loads(PHASE4A_DOMAIN_METADATA_SEEDS_PATH.read_text(encoding="utf-8"))
    for flag in (
        "promotion_enabled",
        "runtime_activated",
        "validated_default_write_enabled",
        "numeric_values_included",
    ):
        if artifact.get(flag) is not False:
            raise ValueError(f"Phase4A seed artifact must keep {flag}=false")

    records = artifact.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Phase4A seed artifact must contain records")

    expected_ids = set().union(*PHASE4A_DOMAIN_SOURCE_IDS.values())
    record_ids = {str(record.get("source_id")) for record in records if isinstance(record, dict)}
    if record_ids != expected_ids:
        missing = sorted(expected_ids - record_ids)
        extra = sorted(record_ids - expected_ids)
        raise ValueError(f"Phase4A seed artifact source mismatch; missing={missing}; extra={extra}")

    validated_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Phase4A seed records must be objects")
        source_id = str(record["source_id"])
        expected_domain = PHASE4A_SOURCE_ID_DOMAIN_BY_ARTIFACT_DOMAIN[source_id]
        artifact_domain = "github_reference" if record.get("domain") == "oss" else record.get("domain")
        if artifact_domain != expected_domain:
            raise ValueError(f"{source_id}: Phase4A seed domain must be {expected_domain}")
        if record.get("human_review_required") is not True:
            raise ValueError(f"{source_id}: Phase4A seed must require human review")
        for flag in (
            "promotion_enabled",
            "runtime_activated",
            "validated_default_write_enabled",
            "numeric_values_included",
        ):
            if record.get(flag, False) is not False:
                raise ValueError(f"{source_id}: Phase4A seed must keep {flag}=false")
        blocked_use = " ".join(str(item) for item in record.get("blocked_use", []))
        blocked_use_lower = blocked_use.lower()
        for phrase in ("validated defaults", "release evidence", "runtime activation"):
            if phrase not in blocked_use_lower:
                raise ValueError(f"{source_id}: blocked_use must include {phrase}")
        validated_records.append(record)

    return validated_records


async def _upsert_phase4a_source(
    db: AsyncSession,
    row: ExternalSourceCatalogRow,
    *,
    seed_record: dict[str, Any],
) -> ExternalSourceRecord:
    values = _source_values(row)
    raw_payload = dict(values["raw_payload"])
    raw_payload["phase4a_domain_metadata_seed"] = {
        **seed_record,
        "review_status": "pending_review",
        "numeric_values_included": False,
        "promotion_enabled": False,
        "runtime_activated": False,
        "validated_default_write_enabled": False,
    }
    values["raw_payload"] = raw_payload

    source = await db.scalar(select(ExternalSourceRecord).where(ExternalSourceRecord.source_id == row.source_id).limit(1))
    if source is None:
        source = ExternalSourceRecord(**values)
        db.add(source)
        await db.flush()
        return source
    for key, value in values.items():
        setattr(source, key, value)
    await db.flush()
    return source


async def _upsert_phase4a_review_card(
    db: AsyncSession,
    *,
    tenant_id: int,
    source: ExternalSourceRecord,
    seed_record: dict[str, Any],
    reviewer_user_id: int,
    reviewer: str,
    reviewed_at: datetime,
) -> ExternalSourceReviewCardRecord:
    card_id = _phase4a_card_id(source.source_id)
    card = await get_review_card_record(db, tenant_id=tenant_id, card_id=card_id)
    blocked_use = _phase4a_blocked_use(seed_record)
    values = {
        "tenant_id": tenant_id,
        "card_id": card_id,
        "shortlist_id": card_id,
        "source_id": source.source_id,
        "doi": _phase4a_source_ref(source),
        "source_url": _phase4a_source_url(source),
        "title": source.source_name,
        "review_status": APPROVED_FOR_CANDIDATE_USE,
        "reviewer": reviewer,
        "reviewer_user_id": reviewer_user_id,
        "reviewed_at": reviewed_at,
        "license_status": "metadata_only",
        "evidence_source_kind": source.evidence_source_kind,
        "ingestion_mode": source.ingestion_mode,
        "human_review_required": True,
        "extracted_numeric_values_allowed": False,
        "boundary_condition_required": True,
        "allowed_use": str(seed_record["allowed_use"]),
        "blocked_use": blocked_use,
        "next_action": "Reviewed metadata candidate filled; runtime activation remains blocked.",
        "boundary_metadata": _phase4a_boundary_metadata(source=source, seed_record=seed_record),
        "raw_payload": {
            "phase4a_domain_metadata_seed": seed_record,
            "source_record": source.raw_payload,
            "review_fill_mode": "metadata_only_reviewed_candidate",
        },
    }
    if card is None:
        card = ExternalSourceReviewCardRecord(**values)
        db.add(card)
        return card
    for key, value in values.items():
        setattr(card, key, value)
    return card


async def _upsert_phase4a_extraction_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    review_card: ExternalSourceReviewCardRecord,
    source: ExternalSourceRecord,
    seed_record: dict[str, Any],
) -> ExternalSourceExtractionRecord:
    extraction_id = f"EXT-{review_card.card_id}"
    extraction = await db.scalar(
        select(ExternalSourceExtractionRecord)
        .where(
            ExternalSourceExtractionRecord.tenant_id == tenant_id,
            ExternalSourceExtractionRecord.extraction_id == extraction_id,
        )
        .limit(1)
    )
    values = {
        "tenant_id": tenant_id,
        "extraction_id": extraction_id,
        "review_card_id": review_card.id,
        "card_id": review_card.card_id,
        "source_id": source.source_id,
        "extraction_status": "reviewed_metadata_only",
        "extracted_metadata": {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "source_owner": source.source_owner,
            "source_category": source.source_category,
            "source_kind": source.evidence_source_kind,
            "ingestion_mode": source.ingestion_mode,
            "bos_module": source.bos_module,
            "license_note": source.license_note,
            "source_focus": seed_record.get("source_focus"),
            "required_metadata": seed_record.get("required_metadata", []),
            "license_strategy": seed_record.get("license_strategy"),
        },
        "extracted_numeric_values": {},
        "numeric_values_included": False,
        "boundary_metadata": _phase4a_boundary_metadata(source=source, seed_record=seed_record),
        "human_review_required": True,
    }
    if extraction is None:
        extraction = ExternalSourceExtractionRecord(**values)
        db.add(extraction)
        return extraction
    for key, value in values.items():
        setattr(extraction, key, value)
    return extraction


def _phase4a_review_resolution_payload(
    *,
    source: ExternalSourceRecord,
    seed_record: dict[str, Any],
    reviewer: str,
    reviewed_at: datetime,
) -> ExternalSourceReviewCardResolveRequest:
    candidate_type = PHASE4A_REVIEWED_CANDIDATE_TYPE_BY_DOMAIN[
        PHASE4A_SOURCE_ID_DOMAIN_BY_ARTIFACT_DOMAIN[source.source_id]
    ]
    return ExternalSourceReviewCardResolveRequest(
        review_action="approve_for_candidate_use",
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        license_status="metadata_only",
        boundary_condition=(
            "Phase 4A metadata-only source reviewed for candidate visibility; "
            "numeric extraction, release evidence, runtime activation, and validated defaults remain blocked."
        ),
        allowed_use=str(seed_record["allowed_use"]),
        blocked_use=_phase4a_blocked_use(seed_record),
        candidate_type=candidate_type,  # type: ignore[arg-type]
        candidate_key=f"{candidate_type}:{source.source_id}",
        candidate_payload={
            "review_scope": "phase4a_domain_metadata_fill",
            "source_id": source.source_id,
            "source_focus": seed_record.get("source_focus"),
            "required_metadata": seed_record.get("required_metadata", []),
            "license_strategy": seed_record.get("license_strategy"),
            "metadata_only": True,
            "numeric_values_included": False,
            "runtime_activation_required_before_use": True,
        },
        extracted_metadata={
            "source_id": source.source_id,
            "source_name": source.source_name,
            "source_kind": source.evidence_source_kind,
            "ingestion_mode": source.ingestion_mode,
            "source_focus": seed_record.get("source_focus"),
        },
    )


def _phase4a_card_id(source_id: str) -> str:
    return f"PHASE4A-{source_id}"


def _phase4a_blocked_use(seed_record: dict[str, Any]) -> str:
    blocked_use = seed_record.get("blocked_use", [])
    if isinstance(blocked_use, list):
        return "; ".join(str(item) for item in blocked_use)
    return str(blocked_use)


def _phase4a_boundary_metadata(*, source: ExternalSourceRecord, seed_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": "phase4a",
        "source_id": source.source_id,
        "source_focus": seed_record.get("source_focus"),
        "candidate_domain": PHASE4A_SOURCE_ID_DOMAIN_BY_ARTIFACT_DOMAIN[source.source_id],
        "required_metadata": seed_record.get("required_metadata", []),
        "license_strategy": seed_record.get("license_strategy"),
        "metadata_only": True,
        "numeric_values_included": False,
        "promotion_enabled": False,
        "runtime_activated": False,
        "validated_default_write_enabled": False,
    }


def _phase4a_source_url(source: ExternalSourceRecord) -> str:
    raw_payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
    for value in raw_payload.values():
        text = str(value)
        markdown_match = re.search(r"\((https?://[^)]+)\)", text)
        if markdown_match:
            return markdown_match.group(1)
        url_match = re.search(r"https?://[^\s|)]+", text)
        if url_match:
            return url_match.group(0)
    return source.source_id


def _phase4a_source_ref(source: ExternalSourceRecord) -> str:
    return _phase4a_source_url(source) or source.source_id


def _as_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


async def _upsert_source(db: AsyncSession, row: ExternalSourceCatalogRow) -> ExternalSourceRecord:
    source = await db.scalar(select(ExternalSourceRecord).where(ExternalSourceRecord.source_id == row.source_id).limit(1))
    values = _source_values(row)
    if source is None:
        source = ExternalSourceRecord(**values)
        db.add(source)
        return source
    for key, value in values.items():
        setattr(source, key, value)
    return source


async def _upsert_review_card(
    db: AsyncSession,
    *,
    tenant_id: int,
    staged_record: dict[str, Any],
) -> ExternalSourceReviewCardRecord:
    card = await get_review_card_record(db, tenant_id=tenant_id, card_id=str(staged_record["card_id"]))
    values = {
        "tenant_id": tenant_id,
        "card_id": staged_record["card_id"],
        "shortlist_id": staged_record["shortlist_id"],
        "source_id": staged_record["source_catalog_id"],
        "doi": staged_record["doi"],
        "source_url": staged_record["source_url"],
        "title": staged_record["title"],
        "review_status": "pending_review",
        "reviewer": "unassigned",
        "reviewer_user_id": None,
        "reviewed_at": None,
        "license_status": staged_record["license_status"],
        "evidence_source_kind": staged_record["evidence_source_kind"],
        "ingestion_mode": staged_record["ingestion_mode"],
        "human_review_required": True,
        "extracted_numeric_values_allowed": False,
        "boundary_condition_required": True,
        "allowed_use": staged_record["allowed_use"],
        "blocked_use": staged_record["blocked_use"],
        "next_action": DEFAULT_REVIEW_CARD_NEXT_ACTION,
        "boundary_metadata": staged_record.get("boundary_metadata") or {},
        "raw_payload": staged_record,
    }
    if card is None:
        card = ExternalSourceReviewCardRecord(**values)
        db.add(card)
        return card
    if card.review_status == "pending_review":
        for key, value in values.items():
            setattr(card, key, value)
    return card


async def _upsert_extraction_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    review_card: ExternalSourceReviewCardRecord,
    staged_record: dict[str, Any],
) -> ExternalSourceExtractionRecord:
    extraction_id = f"EXT-{review_card.card_id}"
    extraction = await db.scalar(
        select(ExternalSourceExtractionRecord)
        .where(
            ExternalSourceExtractionRecord.tenant_id == tenant_id,
            ExternalSourceExtractionRecord.extraction_id == extraction_id,
        )
        .limit(1)
    )
    values = {
        "tenant_id": tenant_id,
        "extraction_id": extraction_id,
        "review_card_id": review_card.id,
        "card_id": review_card.card_id,
        "source_id": review_card.source_id,
        "extraction_status": "staged_metadata_only",
        "extracted_metadata": {
            key: staged_record[key]
            for key in (
                "card_id",
                "shortlist_id",
                "source_catalog_id",
                "doi",
                "source_url",
                "title",
                "evidence_source_kind",
                "ingestion_mode",
                "allowed_use",
                "blocked_use",
            )
            if key in staged_record
        },
        "extracted_numeric_values": {},
        "numeric_values_included": False,
        "boundary_metadata": staged_record.get("boundary_metadata") or {},
        "human_review_required": True,
    }
    if extraction is None:
        extraction = ExternalSourceExtractionRecord(**values)
        db.add(extraction)
        return extraction
    for key, value in values.items():
        setattr(extraction, key, value)
    return extraction


async def list_source_catalog(db: AsyncSession) -> ExternalSourceCatalogResponse:
    result = await db.execute(select(ExternalSourceRecord).order_by(ExternalSourceRecord.source_id.asc()))
    items = result.scalars().all()
    return ExternalSourceCatalogResponse(items=list(items), count=len(items))


async def get_source_procurement_summary(db: AsyncSession) -> ExternalSourceProcurementSummary:
    result = await db.execute(select(ExternalSourceRecord).order_by(ExternalSourceRecord.source_id.asc()))
    sources = list(result.scalars().all())
    source_kind_counts: dict[str, int] = {}
    ingestion_mode_counts: dict[str, int] = {}
    bos_module_counts: dict[str, int] = {}
    review_required_count = 0
    commercial_or_restricted_count = 0

    for source in sources:
        source_kind_counts[source.evidence_source_kind] = source_kind_counts.get(source.evidence_source_kind, 0) + 1
        ingestion_mode_counts[source.ingestion_mode] = ingestion_mode_counts.get(source.ingestion_mode, 0) + 1
        module = source.bos_module or "unmapped"
        bos_module_counts[module] = bos_module_counts.get(module, 0) + 1

        human_review_note = (source.human_review_note or "").lower()
        license_note = (source.license_note or "").lower()
        if human_review_note or source.ingestion_mode == "manual_review_first":
            review_required_count += 1
        if source.evidence_source_kind == "commercial_database" or any(
            marker in license_note for marker in ("commercial", "restricted", "paywall", "license")
        ):
            commercial_or_restricted_count += 1

    metadata_only_count = ingestion_mode_counts.get("metadata_only", 0)
    manual_review_first_count = ingestion_mode_counts.get("manual_review_first", 0)

    return ExternalSourceProcurementSummary(
        source_count=len(sources),
        source_kind_counts=source_kind_counts,
        ingestion_mode_counts=ingestion_mode_counts,
        bos_module_counts=bos_module_counts,
        review_required_count=review_required_count,
        metadata_only_count=metadata_only_count,
        manual_review_first_count=manual_review_first_count,
        other_ingestion_mode_count=max(len(sources) - metadata_only_count - manual_review_first_count, 0),
        commercial_or_restricted_count=commercial_or_restricted_count,
    )


async def get_external_source_schema_readiness(db: AsyncSession) -> ExternalSourceSchemaReadinessResponse:
    present_tables = await db.run_sync(
        lambda sync_session: {
            table_name: inspect(sync_session.bind).has_table(table_name)
            for table_name in EXTERNAL_SOURCE_REQUIRED_TABLES
        }
    )
    table_states: list[ExternalSourceSchemaReadinessTable] = []
    missing_required_tables: list[str] = []

    for table_name, model in EXTERNAL_SOURCE_REQUIRED_TABLES.items():
        present = bool(present_tables.get(table_name))
        if not present:
            missing_required_tables.append(table_name)
            table_states.append(ExternalSourceSchemaReadinessTable(table_name=table_name, present=False))
            continue

        row_count = await db.scalar(select(func.count()).select_from(model))
        table_states.append(
            ExternalSourceSchemaReadinessTable(
                table_name=table_name,
                present=True,
                row_count=int(row_count or 0),
            )
        )

    schema_ready = not missing_required_tables
    feedstock_dataset_candidate_count = 0
    literature_extraction_candidate_count = len(list_literature_extraction_candidate_payloads())
    phase4a_domain_candidate_counts = {domain: 0 for domain in PHASE4A_DOMAIN_SOURCE_IDS}
    catalog_source_ids = [row.source_id for row in validate_external_source_catalog(P0_CATALOG_PATH)]
    seeded_source_ids: set[str] = set()
    if present_tables.get(ExternalSourceRecord.__tablename__):
        feedstock_dataset_candidate_count = int(
            await db.scalar(
                select(func.count())
                .select_from(ExternalSourceRecord)
                .where(ExternalSourceRecord.source_id.like("B-FEED-%"))
            )
            or 0
        )
        source_id_result = await db.execute(select(ExternalSourceRecord.source_id))
        seeded_source_ids = {str(source_id) for source_id in source_id_result.scalars().all()}
        phase4a_domain_candidate_counts = {
            domain: len(source_ids & seeded_source_ids)
            for domain, source_ids in PHASE4A_DOMAIN_SOURCE_IDS.items()
        }
    if present_tables.get(LiteratureExtractionCandidateRecord.__tablename__):
        persisted_literature_candidate_count = int(
            await db.scalar(select(func.count()).select_from(LiteratureExtractionCandidateRecord))
            or 0
        )
        if persisted_literature_candidate_count:
            literature_extraction_candidate_count = persisted_literature_candidate_count

    coverage_domains = _build_knowledge_coverage_domains(
        catalog_source_ids=catalog_source_ids,
        seeded_source_ids=seeded_source_ids,
    )
    business_coverage_groups = _build_business_knowledge_coverage(seeded_source_ids=seeded_source_ids)
    business_expected_count = sum(group.expected_item_count for group in business_coverage_groups)
    business_weighted_score = sum(
        BUSINESS_COVERAGE_STATUS_SCORES[item.status]
        for group in business_coverage_groups
        for item in group.items
    )
    business_knowledge_coverage_percent = _percent_score(business_weighted_score, business_expected_count)
    knowledge_coverage_ready = bool(coverage_domains) and all(
        domain.status == "covered" for domain in coverage_domains
    )
    knowledge_coverage_percent = _percent(
        sum(1 for domain in coverage_domains if domain.status == "covered"),
        len(coverage_domains),
    )
    expected_source_count = sum(domain.expected_source_count for domain in coverage_domains)
    covered_source_count = sum(
        min(domain.covered_source_count, domain.expected_source_count)
        for domain in coverage_domains
    )
    source_metadata_coverage_percent = _percent(covered_source_count, expected_source_count)

    source_catalog_ready = schema_ready and knowledge_coverage_ready
    phase4a_domain_missing_counts = {
        domain: max(PHASE4A_DOMAIN_EXPECTED_COUNTS[domain] - count, 0)
        for domain, count in phase4a_domain_candidate_counts.items()
    }
    phase4a_domain_metadata_ready = schema_ready and all(count == 0 for count in phase4a_domain_missing_counts.values())
    reviewed_metadata_lane_ready = (
        schema_ready
        and bool(present_tables.get(ExternalSourceReviewCardRecord.__tablename__))
        and bool(present_tables.get(ExternalSourceExtractionRecord.__tablename__))
        and bool(present_tables.get(ReviewedExternalCandidateRecord.__tablename__))
    )
    blockers: list[str] = []
    if missing_required_tables:
        blockers.append(f"missing required tables: {', '.join(missing_required_tables)}")
    if schema_ready and feedstock_dataset_candidate_count < 9:
        blockers.append("feedstock public dataset candidates are not seeded to the expected minimum of 9")
    if schema_ready and not knowledge_coverage_ready:
        missing = ", ".join(
            f"{domain.domain_key}:{max(domain.expected_source_count - domain.covered_source_count, 0)}"
            for domain in coverage_domains
            if domain.status != "covered"
        )
        blockers.append(f"external knowledge v1 source metadata coverage incomplete: {missing}")
    if schema_ready and not phase4a_domain_metadata_ready:
        missing = ", ".join(
            f"{domain}:{missing_count}"
            for domain, missing_count in phase4a_domain_missing_counts.items()
            if missing_count
        )
        blockers.append(f"phase4a domain metadata source candidates missing: {missing}")

    return ExternalSourceSchemaReadinessResponse(
        status="ready" if schema_ready and source_catalog_ready and phase4a_domain_metadata_ready else "blocked",
        schema_ready=schema_ready,
        source_catalog_ready=source_catalog_ready,
        knowledge_coverage_ready=knowledge_coverage_ready,
        knowledge_coverage_percent=knowledge_coverage_percent,
        source_metadata_coverage_percent=source_metadata_coverage_percent,
        knowledge_coverage_domains=coverage_domains,
        business_knowledge_coverage_percent=business_knowledge_coverage_percent,
        business_knowledge_coverage_groups=business_coverage_groups,
        feedstock_dataset_candidate_count=feedstock_dataset_candidate_count,
        literature_extraction_candidate_count=literature_extraction_candidate_count,
        phase4a_domain_metadata_ready=phase4a_domain_metadata_ready,
        phase4a_domain_candidate_counts=phase4a_domain_candidate_counts,
        phase4a_domain_expected_counts=PHASE4A_DOMAIN_EXPECTED_COUNTS,
        phase4a_domain_missing_counts=phase4a_domain_missing_counts,
        reviewed_metadata_lane_ready=reviewed_metadata_lane_ready,
        required_tables=table_states,
        missing_required_tables=missing_required_tables,
        blockers=blockers,
    )


def _build_knowledge_coverage_domains(
    *,
    catalog_source_ids: list[str],
    seeded_source_ids: set[str],
) -> list[ExternalKnowledgeCoverageDomain]:
    domains: list[ExternalKnowledgeCoverageDomain] = []
    for domain_key, definition in P0_KNOWLEDGE_COVERAGE_PREFIXES.items():
        prefix = str(definition["prefix"])
        expected = sum(1 for source_id in catalog_source_ids if source_id.startswith(prefix))
        covered = sum(1 for source_id in seeded_source_ids if source_id.startswith(prefix))
        if expected <= 0 or covered <= 0:
            status = "missing"
        elif covered >= expected:
            status = "covered"
        else:
            status = "partial"
        domains.append(
            ExternalKnowledgeCoverageDomain(
                domain_key=domain_key,
                label=str(definition["label"]),
                coverage_basis="source_metadata",
                expected_source_count=expected,
                covered_source_count=covered,
                coverage_percent=_percent(min(covered, expected), expected),
                status=status,
            )
        )
    return domains


def _build_business_knowledge_coverage(*, seeded_source_ids: set[str]) -> list[BusinessKnowledgeCoverageGroup]:
    """Build read-only business coverage without promoting external candidates."""

    external_factor_candidates = list_external_factor_candidates()
    external_candidate_keys = {candidate.key for candidate in external_factor_candidates}
    external_candidate_by_key = {candidate.key: candidate for candidate in external_factor_candidates}
    external_required_assays = {
        assay
        for candidate in external_factor_candidates
        for assay in candidate.payload.get("required_assays", [])
        if isinstance(assay, str)
    }
    has_compliance_source_metadata = _has_seeded_source_prefix(seeded_source_ids, "E-COMP-")
    has_bsf_source_metadata = _has_seeded_source_prefix(seeded_source_ids, "A-BSF-")
    has_feedstock_source_metadata = _has_seeded_source_prefix(seeded_source_ids, "B-FEED-")

    groups = [
        _coverage_group(
            "bioexecutor_species",
            "Bioexecutor species",
            [
                _species_item("BSF", "BSF / 黑水虻 / Hermetia illucens"),
                _species_item("MW", "MW / 黄粉虫 / Tenebrio molitor"),
                _species_item("PB", "PB / 蛴螬 / 白星花金龟 / Protaetia brevitarsis"),
            ],
        ),
        _coverage_group(
            "feedstock_substrates",
            "Feedstock substrates",
            [
                _feedstock_item("distillers_grains", "Distillers grains / 酒糟"),
                _feedstock_item("brewery_spent_grains", "Brewery spent grains / 啤酒糟"),
                _feedstock_item("straw", "Straw / 秸秆"),
                _feedstock_item("straw_sludge_blend", "Straw-sludge blend / 秸秆-污泥混合"),
                _feedstock_item("sewage_sludge", "Sewage sludge / 污泥"),
                _feedstock_item("washed_kitchen_waste", "Washed kitchen waste / 餐厨"),
                _feedstock_item("mixed_food_waste", "Mixed food waste"),
                _feedstock_item("manure_sludge_high_risk", "Manure/sludge high-risk"),
            ],
        ),
        _coverage_group(
            "risk_factors",
            "Risk factors",
            [
                _business_item(
                    "heavy_metals",
                    "Heavy metals / 重金属",
                    "source_metadata_only" if has_compliance_source_metadata or has_bsf_source_metadata else "candidate_needed",
                    ["risk_engine.SUBSTRATE_RISK_PROFILES", "docs/knowledge/BOS_EXTERNAL_SOURCE_CATALOG_P0.md#E-COMP"],
                    "Risk metadata is visible, but no reviewed threshold values are promoted.",
                ),
                _business_item(
                    "pathogen_microbiology",
                    "Pathogen / microbiology",
                    "source_metadata_only" if has_compliance_source_metadata or "microbiology" in external_required_assays else "candidate_needed",
                    ["external_knowledge_candidates.required_assays", "docs/knowledge/BOS_EXTERNAL_SOURCE_CATALOG_P0.md#E-COMP"],
                    "Assay metadata exists; organism-specific safety claims still need review.",
                ),
                _business_item(
                    "sludge_high_risk_gate",
                    "Sludge high-risk gate",
                    "candidate_read_model" if "manure_sludge_high_risk" in FEEDSTOCK_CANDIDATE_DB else "source_metadata_only",
                    ["FEEDSTOCK_CANDIDATE_DB.manure_sludge_high_risk", "FEEDSTOCK_DB.sewage_sludge"],
                    "Review-only substrate gate; it is not a normal deployment default.",
                ),
                _business_item(
                    "mycotoxin_spoilage",
                    "Mycotoxin / spoilage",
                    "partial" if "brewery_spent_grains" in FEEDSTOCK_DB else "candidate_needed",
                    ["FEEDSTOCK_DB.brewery_spent_grains"],
                    "Spoilage is flagged in substrate notes; dedicated reviewed risk candidates are still needed.",
                ),
                _business_item(
                    "salt_preprocessing",
                    "Salt / preprocessing",
                    "partial" if "washed_kitchen_waste" in FEEDSTOCK_DB else "candidate_needed",
                    ["FEEDSTOCK_DB.washed_kitchen_waste"],
                    "Washing/preprocessing is represented, but no numeric salt limits are promoted.",
                ),
                _business_item(
                    "lignocellulose_severity",
                    "Lignocellulose severity",
                    "validated_read_model" if any(profile.lignocellulose_severity for profile in FEEDSTOCK_DB.values()) else "missing",
                    ["FEEDSTOCK_DB.lignocellulose_severity"],
                    "Categorical read model exists for substrate screening.",
                ),
                _business_item(
                    "contamination_risk",
                    "Contamination risk",
                    "validated_read_model" if any(profile.contamination_risk for profile in FEEDSTOCK_DB.values()) else "missing",
                    ["FEEDSTOCK_DB.contamination_risk", "risk_engine.SUBSTRATE_RISK_PROFILES"],
                    "Categorical read model exists; release claims remain review-gated.",
                ),
            ],
        ),
        _coverage_group(
            "product_agronomy_outputs",
            "Product and agronomy outputs",
            [
                _business_item(
                    "frass_organic_fertilizer",
                    "Frass / organic fertilizer metadata",
                    "candidate_read_model" if "frass_organic_fertilizer.cn" in external_candidate_keys else "source_metadata_only",
                    ["external_knowledge_candidates.frass_organic_fertilizer.cn"],
                    "Release-gate candidate exists; fertilizer values and thresholds remain blocked.",
                ),
                _business_item(
                    "germination_rate",
                    "Germination rate / 发芽率",
                    "candidate_read_model" if "germination_rate" in external_candidate_keys else "candidate_needed",
                    [
                        "external_knowledge_candidates.germination_rate",
                        "BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#product-agronomy-gap",
                    ],
                    "Review-gated agronomy metadata candidate exists; no germination percentages or thresholds are promoted.",
                    review_workflow=_business_review_workflow(external_candidate_by_key.get("germination_rate")),
                ),
                _business_item(
                    "germination_index",
                    "Germination index / GI",
                    "candidate_read_model" if "germination_index" in external_candidate_keys else "candidate_needed",
                    [
                        "external_knowledge_candidates.germination_index",
                        "BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#product-agronomy-gap",
                    ],
                    "Review-gated GI metadata candidate exists; no GI values or formal thresholds are promoted.",
                    review_workflow=_business_review_workflow(external_candidate_by_key.get("germination_index")),
                ),
                _business_item(
                    "phytotoxicity",
                    "Phytotoxicity",
                    "candidate_read_model" if "phytotoxicity" in external_candidate_keys else "candidate_needed",
                    [
                        "external_knowledge_candidates.phytotoxicity",
                        "BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md#product-agronomy-gap",
                    ],
                    "Review-gated phytotoxicity metadata candidate exists; validated safety claims remain blocked.",
                    review_workflow=_business_review_workflow(external_candidate_by_key.get("phytotoxicity")),
                ),
                _business_item(
                    "organic_fertilizer_assay_metadata",
                    "Moisture / organic matter / nutrient / safety assay metadata",
                    "source_metadata_only" if has_compliance_source_metadata or external_required_assays else "candidate_needed",
                    ["external_knowledge_candidates.required_assays", "docs/knowledge/BOS_EXTERNAL_SOURCE_CATALOG_P0.md#E-COMP"],
                    "Assay metadata is registered; numeric thresholds remain blocked.",
                ),
            ],
        ),
        _coverage_group(
            "experimental_metrics",
            "Experimental metrics",
            [
                _business_item(
                    "survival",
                    "Survival",
                    "validated_read_model" if all(hasattr(species, "survival_rate") for species in SPECIES_DB.values()) else "missing",
                    ["SPECIES_DB.survival_rate"],
                    "Validated read model has screening defaults; external extraction is still review-gated.",
                ),
                _business_item(
                    "development_days",
                    "Development days",
                    "validated_read_model" if all(hasattr(species, "development_days") for species in SPECIES_DB.values()) else "missing",
                    ["SPECIES_DB.development_days"],
                    "Validated read model has screening defaults.",
                ),
                _business_item(
                    "ser",
                    "SER",
                    "validated_read_model" if all(hasattr(species, "ser_typical") for species in SPECIES_DB.values()) else "missing",
                    ["SPECIES_DB.ser_typical", "SPECIES_DB.ser_excellent"],
                    "SER defaults exist; source-specific conversion extraction is separate.",
                ),
                _business_item(
                    "substrate_reduction_conversion",
                    "Substrate reduction / conversion",
                    "source_metadata_only" if has_bsf_source_metadata or has_feedstock_source_metadata else "candidate_needed",
                    ["docs/knowledge/BOS_EXTERNAL_SOURCE_CATALOG_P0.md#A-BSF", "docs/knowledge/BOS_EXTERNAL_SOURCE_CATALOG_P0.md#B-FEED"],
                    "Source families mention conversion fields; no reviewed numeric extraction is promoted.",
                ),
                _business_item(
                    "body_composition",
                    "Protein / fat / chitin / ash",
                    "validated_read_model" if all(hasattr(SPECIES_DB["BSF"], attr) for attr in ("protein_content", "fat_content", "chitin_content", "ash_content")) else "missing",
                    ["SPECIES_DB.protein_content", "SPECIES_DB.fat_content", "SPECIES_DB.chitin_content", "SPECIES_DB.ash_content"],
                    "Species-level screening defaults exist; external product claims remain review-gated.",
                ),
                _business_item(
                    "cn",
                    "C/N",
                    "validated_read_model" if any(profile.typical_cn_min is not None for profile in FEEDSTOCK_DB.values()) else "missing",
                    ["FEEDSTOCK_DB.typical_cn_min", "FEEDSTOCK_DB.typical_cn_max"],
                    "Categorical substrate read model includes C/N anchors for core feedstocks.",
                ),
                _business_item(
                    "moisture",
                    "Moisture",
                    "validated_read_model" if SPECIES_DB and FEEDSTOCK_DB else "missing",
                    ["SPECIES_DB.moisture_optimal", "FEEDSTOCK_DB.moisture_risk"],
                    "Species and feedstock read models include moisture screening fields.",
                ),
            ],
        ),
    ]
    return groups


def _coverage_group(
    group_key: str,
    label: str,
    items: list[BusinessKnowledgeCoverageItem],
) -> BusinessKnowledgeCoverageGroup:
    expected_count = len(items)
    covered_count = sum(1 for item in items if BUSINESS_COVERAGE_STATUS_SCORES[item.status] > 0)
    weighted_score = sum(BUSINESS_COVERAGE_STATUS_SCORES[item.status] for item in items)
    coverage_percent = _percent_score(weighted_score, expected_count)
    if coverage_percent >= 100:
        status = "covered"
    elif coverage_percent > 0:
        status = "partial"
    else:
        status = "missing"
    return BusinessKnowledgeCoverageGroup(
        group_key=group_key,
        label=label,
        expected_item_count=expected_count,
        covered_item_count=covered_count,
        coverage_percent=coverage_percent,
        status=status,
        items=items,
    )


def _find_business_knowledge_item(
    groups: list[BusinessKnowledgeCoverageGroup],
    *,
    item_key: str,
) -> tuple[str, BusinessKnowledgeCoverageItem] | None:
    for group in groups:
        for item in group.items:
            if item.item_key == item_key:
                return group.group_key, item
    return None


def _species_item(code: str, label: str) -> BusinessKnowledgeCoverageItem:
    if code in SPECIES_DB:
        status = "validated_read_model"
        refs = [f"SPECIES_DB.{code}"]
    elif code in BIOEXECUTOR_CANDIDATE_DB:
        status = "candidate_read_model"
        refs = [f"BIOEXECUTOR_CANDIDATE_DB.{code}"]
    else:
        status = "missing"
        refs = []
    return _business_item(
        code.lower(),
        label,
        status,
        refs,
        "Species coverage is counted separately from source metadata families.",
    )


def _feedstock_item(key: str, label: str) -> BusinessKnowledgeCoverageItem:
    if key in FEEDSTOCK_DB:
        status = "validated_read_model"
        refs = [f"FEEDSTOCK_DB.{key}"]
    elif key in FEEDSTOCK_CANDIDATE_DB:
        status = "candidate_read_model"
        refs = [f"FEEDSTOCK_CANDIDATE_DB.{key}"]
    else:
        status = "missing"
        refs = []
    return _business_item(
        key,
        label,
        status,
        refs,
        "Substrate coverage uses validated/candidate read models, not source family coverage.",
    )


def _business_item(
    item_key: str,
    label: str,
    status: str,
    evidence_refs: list[str],
    notes: str,
    *,
    review_workflow: BusinessKnowledgeReviewWorkflow | None = None,
) -> BusinessKnowledgeCoverageItem:
    coverage_basis_by_status = {
        "validated_read_model": "validated_read_model",
        "candidate_read_model": "candidate_read_model",
        "source_metadata_only": "source_metadata",
        "partial": "partial",
        "candidate_needed": "missing",
        "missing": "missing",
    }
    return BusinessKnowledgeCoverageItem(
        item_key=item_key,
        label=label,
        status=status,  # type: ignore[arg-type]
        coverage_basis=coverage_basis_by_status[status],  # type: ignore[arg-type]
        evidence_refs=evidence_refs,
        notes=notes,
        review_workflow=review_workflow,
    )


def _business_review_workflow(candidate: Any | None) -> BusinessKnowledgeReviewWorkflow | None:
    if candidate is None:
        return None
    payload = candidate.payload
    return BusinessKnowledgeReviewWorkflow(
        review_packet_id=str(payload.get("review_packet_id") or f"AGR-{candidate.key.upper()}-REVIEW-PACKET"),
        review_state=str(payload.get("review_state") or candidate.review_status),  # type: ignore[arg-type]
        source_packet_persistence=str(payload.get("source_packet_persistence") or "read_model_only"),  # type: ignore[arg-type]
        reviewer_notes_required=bool(payload.get("reviewer_notes_required", True)),
        reviewer_notes=str(payload.get("reviewer_notes") or ""),
        allowed_review_actions=[
            str(action)
            for action in payload.get("allowed_review_actions", ["approve_metadata", "request_license_clearance", "reject"])
            if isinstance(action, str)
        ],
        approval_enabled=False,
        rejection_enabled=True,
        release_evidence_allowed=bool(payload.get("release_evidence_allowed", False)),
        runtime_activation_enabled=False,
        validated_default_write_enabled=False,
        numeric_values_allowed=False,
    )


def _has_seeded_source_prefix(seeded_source_ids: set[str], prefix: str) -> bool:
    return any(source_id.startswith(prefix) for source_id in seeded_source_ids)


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _percent_score(numerator: float, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


async def list_feedstock_dataset_candidates(db: AsyncSession) -> FeedstockDatasetCandidateListResponse:
    result = await db.execute(
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.source_id.like("B-FEED-%"))
        .order_by(ExternalSourceRecord.source_id.asc())
    )
    items = [build_feedstock_dataset_candidate(source) for source in result.scalars().all()]
    return FeedstockDatasetCandidateListResponse(items=items, count=len(items))


async def list_literature_extraction_candidates(
    db: AsyncSession,
    *,
    tenant_id: int | None = None,
    metric_key: str | None = None,
) -> LiteratureExtractionCandidateListResponse:
    """Return review-gated literature value candidates without DB mutation."""

    items: list[LiteratureExtractionCandidateRead] = []
    if tenant_id is not None:
        query = select(LiteratureExtractionCandidateRecord).where(
            LiteratureExtractionCandidateRecord.tenant_id == tenant_id
        )
        if metric_key is not None:
            query = query.where(LiteratureExtractionCandidateRecord.metric_key == metric_key)
        result = await db.execute(
            query.order_by(
                LiteratureExtractionCandidateRecord.metric_key.asc(),
                LiteratureExtractionCandidateRecord.candidate_id.asc(),
            )
        )
        records = list(result.scalars().all())
        items = [serialize_literature_extraction_candidate(record) for record in records]

    if not items:
        items = [
            LiteratureExtractionCandidateRead.model_validate(payload)
            for payload in list_literature_extraction_candidate_payloads(metric_key=metric_key)
        ]
    metric_counts: dict[str, int] = {}
    for item in items:
        metric_counts[item.metric_key] = metric_counts.get(item.metric_key, 0) + 1
    return LiteratureExtractionCandidateListResponse(
        items=items,
        count=len(items),
        metric_counts=metric_counts,
    )


async def seed_literature_extraction_candidates(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> LiteratureExtractionCandidateSeedResponse:
    """Persist literature value candidates without enabling runtime or release use."""

    catalog_rows = {row.source_id: row for row in validate_external_source_catalog(P0_CATALOG_PATH)}
    payloads = list_literature_extraction_candidate_payloads()
    created_candidate_ids: list[str] = []
    updated_candidate_ids: list[str] = []

    for payload in payloads:
        source_id = str(payload["source_id"])
        catalog_row = catalog_rows.get(source_id)
        if catalog_row is None:
            raise ValueError(f"{payload['candidate_id']}: source catalog row not found for {source_id}")
        await _upsert_source(db, catalog_row)
        await db.flush()

        existing = await db.scalar(
            select(LiteratureExtractionCandidateRecord)
            .where(
                LiteratureExtractionCandidateRecord.tenant_id == tenant_id,
                LiteratureExtractionCandidateRecord.candidate_id == payload["candidate_id"],
            )
            .limit(1)
        )
        values = _literature_extraction_candidate_values(payload=payload, tenant_id=tenant_id)
        if existing is None:
            db.add(LiteratureExtractionCandidateRecord(**values))
            created_candidate_ids.append(str(payload["candidate_id"]))
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            updated_candidate_ids.append(str(payload["candidate_id"]))

    await db.commit()
    seeded_candidate_ids = sorted(created_candidate_ids + updated_candidate_ids)
    return LiteratureExtractionCandidateSeedResponse(
        tenant_id=tenant_id,
        source_count=len({payload["source_id"] for payload in payloads}),
        candidate_count=len(seeded_candidate_ids),
        created_candidate_count=len(created_candidate_ids),
        updated_candidate_count=len(updated_candidate_ids),
        seeded_candidate_ids=seeded_candidate_ids,
    )


async def get_literature_extraction_candidate_review_packet(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureExtractionCandidateReviewPacketResponse | None:
    record = await _get_literature_extraction_candidate_record(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if record is None:
        return None

    candidate = serialize_literature_extraction_candidate(record)
    source = await get_source_record(db, source_id=record.source_id)
    source_trace = {
        "candidate_id": candidate.candidate_id,
        "candidate_type": candidate.candidate_type,
        "source_id": candidate.source_id,
        "doi": candidate.doi,
        "source_ref": candidate.source_ref,
        "source_kind": candidate.source_kind,
        "source_name": source.source_name if source is not None else None,
        "source_owner": source.source_owner if source is not None else None,
        "source_category": source.source_category if source is not None else None,
        "ingestion_mode": source.ingestion_mode if source is not None else "manual_review_first",
        "license_note": candidate.license_note,
        "review_status": candidate.review_status,
        "human_review_required": candidate.human_review_required,
        "release_evidence_allowed": candidate.release_evidence_allowed,
        "runtime_activation_enabled": candidate.runtime_activation_enabled,
        "validated_default_write_enabled": candidate.validated_default_write_enabled,
        "promotion_enabled": candidate.promotion_enabled,
        "final_action_execution": False,
    }
    return LiteratureExtractionCandidateReviewPacketResponse(
        tenant_id=tenant_id,
        candidate=candidate,
        candidate_payload=candidate.model_dump(mode="json"),
        source_trace=source_trace,
        raw_value=candidate.raw_value,
        unit=candidate.unit,
        conditions={
            "condition_context": candidate.condition_context,
            "experiment_context": candidate.experiment_context,
            "table_or_section_ref": candidate.table_or_section_ref,
            "treatment": candidate.treatment,
        },
        license_note=candidate.license_note,
    )


async def get_literature_extraction_candidate_review_packet_export(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureExtractionCandidateReviewPacketExportResponse | None:
    packet = await get_literature_extraction_candidate_review_packet(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if packet is None:
        return None

    packet_payload = packet.model_dump(mode="json")
    canonical_payload = json.dumps(packet_payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    export_filename = f"{packet.candidate.candidate_id}-literature-extraction-review-packet.json"
    export_manifest = {
        "export_id": f"literature-extraction-review-packet-export:{packet.candidate.candidate_id}:{content_hash[:12]}",
        "candidate_id": packet.candidate.candidate_id,
        "candidate_type": packet.candidate.candidate_type,
        "source_id": packet.candidate.source_id,
        "metric_key": packet.candidate.metric_key,
        "review_status": packet.review_status,
        "human_review_required": packet.human_review_required,
        "release_evidence_allowed": packet.release_evidence_allowed,
        "runtime_activation_enabled": packet.runtime_activation_enabled,
        "validated_default_write_enabled": packet.validated_default_write_enabled,
        "promotion_enabled": packet.promotion_enabled,
        "final_action_execution": packet.final_action_execution,
        "content_hash_algorithm": "sha256",
        "content_hash": content_hash,
        "export_policy": "response_only_no_file_write",
    }
    return LiteratureExtractionCandidateReviewPacketExportResponse(
        tenant_id=tenant_id,
        export_filename=export_filename,
        content_hash=content_hash,
        export_manifest=export_manifest,
        review_packet=packet,
    )


async def get_literature_extraction_candidate_review_packet_bulk_export(
    db: AsyncSession,
    *,
    tenant_id: int,
    metric_key: str | None = None,
) -> LiteratureExtractionCandidateReviewPacketBulkExportResponse:
    query = select(LiteratureExtractionCandidateRecord).where(
        LiteratureExtractionCandidateRecord.tenant_id == tenant_id
    )
    if metric_key is not None:
        query = query.where(LiteratureExtractionCandidateRecord.metric_key == metric_key)
    result = await db.execute(
        query.order_by(
            LiteratureExtractionCandidateRecord.metric_key.asc(),
            LiteratureExtractionCandidateRecord.candidate_id.asc(),
        )
    )
    records = list(result.scalars().all())
    packet_exports: list[LiteratureExtractionCandidateReviewPacketExportResponse] = []
    for record in records:
        exported = await get_literature_extraction_candidate_review_packet_export(
            db,
            tenant_id=tenant_id,
            candidate_id=record.candidate_id,
        )
        if exported is not None:
            packet_exports.append(exported)

    metric_counts: dict[str, int] = {}
    candidate_ids: list[str] = []
    child_hashes: list[str] = []
    for packet_export in packet_exports:
        candidate = packet_export.review_packet.candidate
        metric_counts[candidate.metric_key] = metric_counts.get(candidate.metric_key, 0) + 1
        candidate_ids.append(candidate.candidate_id)
        child_hashes.append(packet_export.content_hash)

    manifest_seed = {
        "tenant_id": tenant_id,
        "candidate_ids": candidate_ids,
        "child_hashes": child_hashes,
        "metric_counts": metric_counts,
        "metric_key_filter": metric_key,
    }
    canonical_manifest_seed = json.dumps(manifest_seed, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical_manifest_seed.encode("utf-8")).hexdigest()
    suffix = f"-{metric_key}" if metric_key else ""
    export_filename = f"literature-extraction-review-packets{suffix}.json"
    export_manifest = {
        "export_id": f"literature-extraction-review-packet-bulk-export:{tenant_id}:{content_hash[:12]}",
        "tenant_id": tenant_id,
        "candidate_count": len(packet_exports),
        "candidate_ids": candidate_ids,
        "metric_counts": metric_counts,
        "metric_key_filter": metric_key,
        "child_content_hashes": child_hashes,
        "content_hash_algorithm": "sha256",
        "content_hash": content_hash,
        "export_policy": "response_only_no_file_write",
        "source_packet_persistence": "persisted_candidate_records_only",
        "release_evidence_allowed": False,
        "runtime_activation_enabled": False,
        "validated_default_write_enabled": False,
        "promotion_enabled": False,
        "final_action_execution": False,
    }
    return LiteratureExtractionCandidateReviewPacketBulkExportResponse(
        tenant_id=tenant_id,
        export_filename=export_filename,
        content_hash=content_hash,
        export_manifest=export_manifest,
        packet_exports=packet_exports,
        count=len(packet_exports),
        metric_counts=metric_counts,
    )


LITERATURE_REVIEW_DRAFT_SIDE_EFFECTS = {
    "candidate_status_update": False,
    "file_written": False,
    "runtime_activation": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
    "release_evidence_use": False,
    "promotion": False,
    "final_action_execution": False,
}


def _iso_or_empty(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _stable_json_hash(payload: Any) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _literature_review_draft_revision_payload(draft: LiteratureExtractionReviewDraftRecord) -> dict[str, Any]:
    return {
        "review_draft_id": draft.review_draft_id,
        "tenant_id": draft.tenant_id,
        "candidate_id": draft.candidate_id,
        "source_id": draft.source_id,
        "reviewer_user_id": draft.reviewer_user_id,
        "review_intent": draft.review_intent,
        "reviewer_notes": draft.reviewer_notes,
        "status": draft.status,
        "source_review_packet_export_id": draft.source_review_packet_export_id,
        "source_review_packet_hash": draft.source_review_packet_hash,
        "candidate_snapshot": draft.candidate_snapshot,
        "export_manifest": draft.export_manifest,
        "side_effects": draft.side_effects,
        "guardrails": draft.guardrail_snapshot,
        "created_at": _iso_or_empty(draft.created_at),
        "updated_at": _iso_or_empty(draft.updated_at),
    }


def _literature_review_draft_changed_fields(
    current: LiteratureExtractionReviewDraftRecord,
    previous: LiteratureExtractionReviewDraftRecord | None,
) -> list[str]:
    if previous is None:
        return []

    comparisons = {
        "candidate_snapshot": current.candidate_snapshot != previous.candidate_snapshot,
        "source_review_packet_hash": current.source_review_packet_hash != previous.source_review_packet_hash,
        "review_intent": current.review_intent != previous.review_intent,
        "side_effects": current.side_effects != previous.side_effects,
        "export_manifest": current.export_manifest != previous.export_manifest,
    }
    return [field for field, changed in comparisons.items() if changed]


def _literature_review_draft_revision_read(
    draft: LiteratureExtractionReviewDraftRecord,
    *,
    revision_index: int,
    previous: LiteratureExtractionReviewDraftRecord | None,
) -> LiteratureExtractionReviewDraftRevisionRead:
    return LiteratureExtractionReviewDraftRevisionRead(
        review_draft_id=draft.review_draft_id,
        revision_index=revision_index,
        revision_hash=_stable_json_hash(_literature_review_draft_revision_payload(draft)),
        candidate_snapshot_hash=_stable_json_hash(draft.candidate_snapshot),
        export_manifest_hash=_stable_json_hash(draft.export_manifest),
        source_review_packet_hash=draft.source_review_packet_hash,
        review_intent=draft.review_intent,  # type: ignore[arg-type]
        changed_fields=_literature_review_draft_changed_fields(draft, previous),
        side_effects={key: bool(value) for key, value in draft.side_effects.items()},
        created_at=_iso_or_empty(draft.created_at),
    )


def serialize_literature_extraction_review_draft(
    draft: LiteratureExtractionReviewDraftRecord,
) -> LiteratureExtractionReviewDraftResponse:
    return LiteratureExtractionReviewDraftResponse(
        review_draft_id=draft.review_draft_id,
        tenant_id=draft.tenant_id,
        candidate_id=draft.candidate_id,
        source_id=draft.source_id,
        reviewer_user_id=draft.reviewer_user_id,
        review_intent=draft.review_intent,  # type: ignore[arg-type]
        reviewer_notes=draft.reviewer_notes,
        status=draft.status,  # type: ignore[arg-type]
        source_review_packet_export_id=draft.source_review_packet_export_id,
        source_review_packet_hash=draft.source_review_packet_hash,
        candidate_snapshot=draft.candidate_snapshot,
        export_manifest=draft.export_manifest,
        side_effects={key: bool(value) for key, value in draft.side_effects.items()},
        guardrails=[str(value) for value in draft.guardrail_snapshot],
        idempotency_key=draft.idempotency_key,
        created_at=_iso_or_empty(draft.created_at),
        updated_at=_iso_or_empty(draft.updated_at),
    )


async def list_literature_extraction_review_drafts(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str | None = None,
    limit: int = 50,
) -> LiteratureExtractionReviewDraftListResponse:
    query = select(LiteratureExtractionReviewDraftRecord).where(
        LiteratureExtractionReviewDraftRecord.tenant_id == tenant_id
    )
    if candidate_id is not None:
        query = query.where(LiteratureExtractionReviewDraftRecord.candidate_id == candidate_id)
    result = await db.execute(
        query.order_by(
            LiteratureExtractionReviewDraftRecord.created_at.desc(),
            LiteratureExtractionReviewDraftRecord.id.desc(),
        ).limit(limit)
    )
    drafts = [serialize_literature_extraction_review_draft(draft) for draft in result.scalars().all()]
    return LiteratureExtractionReviewDraftListResponse(
        tenant_id=tenant_id,
        count=len(drafts),
        drafts=drafts,
    )


async def get_literature_extraction_review_draft_comparison(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
    review_draft_id: str | None = None,
    changed_field: str | None = None,
) -> LiteratureExtractionReviewDraftComparisonResponse | None:
    result = await db.execute(
        select(LiteratureExtractionReviewDraftRecord)
        .where(
            LiteratureExtractionReviewDraftRecord.tenant_id == tenant_id,
            LiteratureExtractionReviewDraftRecord.candidate_id == candidate_id,
        )
        .order_by(
            LiteratureExtractionReviewDraftRecord.created_at.asc(),
            LiteratureExtractionReviewDraftRecord.id.asc(),
        )
    )
    draft_records = list(result.scalars().all())
    if not draft_records:
        return None

    current_index = len(draft_records) - 1
    if review_draft_id is not None:
        matching_index = next(
            (index for index, draft in enumerate(draft_records) if draft.review_draft_id == review_draft_id),
            None,
        )
        if matching_index is None:
            return None
        current_index = matching_index

    current = draft_records[current_index]
    previous = draft_records[current_index - 1] if current_index > 0 else None
    current_packet = await get_literature_extraction_candidate_review_packet_export(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )

    audit_trail = [
        _literature_review_draft_revision_read(
            draft,
            revision_index=index + 1,
            previous=draft_records[index - 1] if index > 0 else None,
        )
        for index, draft in enumerate(draft_records)
    ]
    current_revision = audit_trail[current_index]
    changed_fields = list(current_revision.changed_fields)
    current_candidate_snapshot = (
        current_packet.review_packet.candidate.model_dump(mode="json") if current_packet is not None else None
    )
    current_response_packet_hash = current_packet.content_hash if current_packet is not None else None
    current_packet_export_id = (
        str(current_packet.export_manifest.get("export_id")) if current_packet is not None else None
    )
    if current_response_packet_hash is not None and current_response_packet_hash != current.source_review_packet_hash:
        changed_fields.append("current_response_packet_hash")
    if current_candidate_snapshot is not None and current_candidate_snapshot != current.candidate_snapshot:
        changed_fields.append("current_candidate_snapshot")
    if changed_field is not None:
        changed_fields = [field for field in changed_fields if field == changed_field]
        audit_trail = [
            revision.model_copy(
                update={
                    "changed_fields": [field for field in revision.changed_fields if field == changed_field],
                }
            )
            for revision in audit_trail
        ]

    comparison_summary = {
        "candidate_snapshot_changed_since_previous": "candidate_snapshot" in current_revision.changed_fields,
        "packet_hash_changed_since_previous": "source_review_packet_hash" in current_revision.changed_fields,
        "review_intent_changed_since_previous": "review_intent" in current_revision.changed_fields,
        "side_effect_flags_changed_since_previous": "side_effects" in current_revision.changed_fields,
        "export_manifest_changed_since_previous": "export_manifest" in current_revision.changed_fields,
        "current_response_packet_hash_matches_draft": current_response_packet_hash == current.source_review_packet_hash,
        "current_candidate_snapshot_matches_draft": current_candidate_snapshot == current.candidate_snapshot,
    }
    comparison_seed = {
        "tenant_id": tenant_id,
        "candidate_id": candidate_id,
        "current_review_draft_id": current.review_draft_id,
        "previous_review_draft_id": previous.review_draft_id if previous is not None else None,
        "current_revision_hash": current_revision.revision_hash,
        "current_candidate_snapshot_hash": current_revision.candidate_snapshot_hash,
        "source_review_packet_hash": current.source_review_packet_hash,
        "current_response_packet_hash": current_response_packet_hash,
        "changed_field_filter": changed_field,
        "changed_fields": changed_fields,
        "comparison_summary": comparison_summary,
    }
    comparison_hash = _stable_json_hash(comparison_seed)
    comparison_manifest = {
        "comparison_id": f"literature-extraction-review-draft-comparison:{candidate_id}:{comparison_hash[:12]}",
        "candidate_id": candidate_id,
        "current_review_draft_id": current.review_draft_id,
        "previous_review_draft_id": previous.review_draft_id if previous is not None else None,
        "revision_count": len(audit_trail),
        "current_revision_hash": current_revision.revision_hash,
        "comparison_hash": comparison_hash,
        "comparison_policy": "response_only_no_file_write",
        "changed_field_filter": changed_field,
        "source_review_packet_export_id": current.source_review_packet_export_id,
        "current_response_packet_export_id": current_packet_export_id,
        "source_review_packet_hash": current.source_review_packet_hash,
        "current_response_packet_hash": current_response_packet_hash,
        "candidate_status": str(current.candidate_snapshot.get("review_status")),
        "release_evidence_allowed": False,
        "runtime_activation_enabled": False,
        "validated_default_write_enabled": False,
        "promotion_enabled": False,
        "final_action_execution": False,
    }
    report_manifest = {
        "report_id": f"literature-extraction-review-draft-comparison-report:{candidate_id}:{comparison_hash[:12]}",
        "report_policy": "response_only_no_file_write",
        "report_format": "json_response",
        "candidate_id": candidate_id,
        "current_review_draft_id": current.review_draft_id,
        "previous_review_draft_id": previous.review_draft_id if previous is not None else None,
        "changed_field_filter": changed_field,
        "changed_field_count": len(changed_fields),
        "audit_trail_count": len(audit_trail),
        "content_hash_algorithm": "sha256",
        "content_hash": comparison_hash,
        "file_written": False,
        "release_evidence_allowed": False,
        "runtime_activation_enabled": False,
        "validated_default_write_enabled": False,
        "promotion_enabled": False,
        "final_action_execution": False,
    }
    report_payload = {
        "summary": {
            "candidate_id": candidate_id,
            "current_review_draft_id": current.review_draft_id,
            "previous_review_draft_id": previous.review_draft_id if previous is not None else None,
            "changed_fields": changed_fields,
            "packet_hash_matches": comparison_summary["current_response_packet_hash_matches_draft"],
            "candidate_snapshot_matches": comparison_summary["current_candidate_snapshot_matches_draft"],
        },
        "current_revision": audit_trail[current_index].model_dump(mode="json"),
        "audit_trail": [revision.model_dump(mode="json") for revision in audit_trail],
        "guardrails": [
            "report_is_response_only",
            "candidate_status_remains_pending_review",
            "no_file_write",
            "no_release_evidence_use",
            "no_runtime_activation",
            "no_validated_default_write",
            "no_promotion",
            "no_final_action_execution",
        ],
    }

    return LiteratureExtractionReviewDraftComparisonResponse(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        current_review_draft_id=current.review_draft_id,
        previous_review_draft_id=previous.review_draft_id if previous is not None else None,
        current_revision_hash=current_revision.revision_hash,
        current_candidate_snapshot_hash=current_revision.candidate_snapshot_hash,
        current_export_manifest_hash=current_revision.export_manifest_hash,
        source_review_packet_hash=current.source_review_packet_hash,
        current_response_packet_hash=current_response_packet_hash,
        changed_field_filter=changed_field,
        comparison_manifest=comparison_manifest,
        report_manifest=report_manifest,
        report_payload=report_payload,
        comparison_summary=comparison_summary,
        changed_fields=changed_fields,
        audit_trail=audit_trail,
    )


async def get_literature_extraction_evidence_chain_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> LiteratureExtractionEvidenceChainReadinessResponse:
    candidate_count = int(
        await db.scalar(
            select(func.count())
            .select_from(LiteratureExtractionCandidateRecord)
            .where(LiteratureExtractionCandidateRecord.tenant_id == tenant_id)
        )
        or 0
    )
    review_draft_count = int(
        await db.scalar(
            select(func.count())
            .select_from(LiteratureExtractionReviewDraftRecord)
            .where(LiteratureExtractionReviewDraftRecord.tenant_id == tenant_id)
        )
        or 0
    )
    first_draft_candidate_id = await db.scalar(
        select(LiteratureExtractionReviewDraftRecord.candidate_id)
        .where(LiteratureExtractionReviewDraftRecord.tenant_id == tenant_id)
        .order_by(
            LiteratureExtractionReviewDraftRecord.created_at.desc(),
            LiteratureExtractionReviewDraftRecord.id.desc(),
        )
        .limit(1)
    )

    bulk_export = await get_literature_extraction_candidate_review_packet_bulk_export(
        db,
        tenant_id=tenant_id,
    )
    packet_export_ready = candidate_count > 0 and bulk_export.count == candidate_count
    bulk_export_ready = (
        packet_export_ready
        and bulk_export.export_manifest.get("export_policy") == "response_only_no_file_write"
        and bool(bulk_export.packet_exports)
        and all(not any(packet.side_effects.values()) for packet in bulk_export.packet_exports)
        and not any(bulk_export.side_effects.values())
    )

    comparison = None
    if first_draft_candidate_id is not None:
        comparison = await get_literature_extraction_review_draft_comparison(
            db,
            tenant_id=tenant_id,
            candidate_id=str(first_draft_candidate_id),
        )
    comparison_ready = comparison is not None and not any(comparison.side_effects.values())
    report_ready = (
        comparison_ready
        and comparison is not None
        and comparison.report_manifest.get("report_policy") == "response_only_no_file_write"
        and comparison.report_manifest.get("file_written") is False
        and bool(comparison.report_payload)
    )

    blockers: list[str] = []
    if candidate_count <= 0:
        blockers.append("no persisted literature extraction candidates")
    if not packet_export_ready:
        blockers.append("review packet export is not ready")
    if not bulk_export_ready:
        blockers.append("bulk review packet export is not ready")
    if review_draft_count <= 0:
        blockers.append("no reviewer draft intent recorded")
    if not comparison_ready:
        blockers.append("review draft comparison is not ready")
    if not report_ready:
        blockers.append("response-only comparison report is not ready")

    readiness_notes = [
        "literature raw values are persisted only as pending_review candidates",
        "reviewer packets, bulk export, comparison, and report are response-only",
        "chain completion does not permit release evidence, runtime activation, defaults, promotion, or final actions",
    ]
    if blockers:
        readiness_notes.extend(blockers)

    return LiteratureExtractionEvidenceChainReadinessResponse(
        tenant_id=tenant_id,
        chain_complete=not blockers,
        candidate_count=candidate_count,
        packet_export_ready=packet_export_ready,
        bulk_export_ready=bulk_export_ready,
        review_draft_count=review_draft_count,
        comparison_ready=comparison_ready,
        report_ready=report_ready,
        promotion_ready=not blockers,
        blocking_reason="; ".join(blockers) if blockers else None,
        readiness_notes=readiness_notes,
    )


LITERATURE_VALUE_PROMOTION_REQUEST_SIDE_EFFECTS = {
    "overlay_write": False,
    "runtime_activation": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
    "release_evidence_use": False,
    "promotion": False,
    "final_action_execution": False,
}

LITERATURE_VALUE_PROMOTION_REQUEST_GUARDRAILS = [
    "promotion_request_is_request_only",
    "request_status_requested_not_active",
    "no_overlay_write",
    "no_runtime_activation",
    "no_release_evidence_use",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
    "no_final_action_execution",
]

LITERATURE_VALUE_PROMOTION_APPROVAL_SIDE_EFFECTS = {
    "overlay_write": False,
    "runtime_activation": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
    "release_evidence_use": False,
    "promotion": False,
    "final_action_execution": False,
}

LITERATURE_VALUE_PROMOTION_APPROVAL_GUARDRAILS = [
    "promotion_approval_is_audit_only",
    "requester_self_approval_forbidden",
    "dual_role_approval_required",
    "scientist_and_release_or_compliance_required",
    "approval_does_not_create_overlay",
    "approval_does_not_activate_runtime",
    "approval_does_not_allow_release_evidence",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
    "no_final_action_execution",
]

LITERATURE_VALUE_PROMOTION_APPROVER_ROLES = {
    "scientist",
    "release_manager",
    "compliance_admin",
}

LITERATURE_VALUE_PROMOTION_GOVERNANCE_APPROVER_ROLES = {
    "release_manager",
    "compliance_admin",
}

LITERATURE_VALUE_OVERLAY_SIDE_EFFECTS = {
    "runtime_activation": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
    "release_evidence_use": False,
    "final_action_execution": False,
}

LITERATURE_VALUE_OVERLAY_GUARDRAILS = [
    "overlay_created_inactive",
    "overlay_requires_separate_scoped_runtime_activation",
    "no_runtime_activation",
    "no_release_evidence_use",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
    "no_final_action_execution",
]

LITERATURE_VALUE_RUNTIME_ACTIVATION_GUARDRAILS = [
    "scoped_runtime_activation_only",
    "scope_required",
    "global_activation_forbidden",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
    "no_release_evidence_use",
    "no_final_action_execution",
]

LITERATURE_VALUE_RELEASE_EVIDENCE_LINK_SIDE_EFFECTS = {
    "release_decision_update": False,
    "release_auto_approval": False,
    "final_action_execution": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
}

LITERATURE_VALUE_RELEASE_EVIDENCE_LINK_GUARDRAILS = [
    "release_evidence_link_requires_active_scoped_overlay",
    "release_decision_remains_review_required",
    "human_review_required",
    "no_release_auto_approval",
    "no_final_action_execution",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
]

LITERATURE_VALUE_ROLLBACK_SIDE_EFFECTS = {
    "runtime_activation": False,
    "runtime_deactivation": True,
    "overlay_status_update": True,
    "release_evidence_link_status_update": True,
    "release_decision_update": False,
    "release_auto_approval": False,
    "validated_default_write": False,
    "species_db_write": False,
    "feedstock_db_write": False,
    "final_action_execution": False,
}

LITERATURE_VALUE_ROLLBACK_GUARDRAILS = [
    "rollback_is_append_only_audit_record",
    "runtime_activation_deactivated",
    "overlay_marked_rolled_back",
    "release_evidence_links_retained_and_marked_rolled_back",
    "release_decision_remains_review_required",
    "human_review_required",
    "no_validated_default_writes",
    "no_species_db_writes",
    "no_feedstock_db_writes",
    "no_final_action_execution",
]


def _literature_runtime_scope_key(scope: dict[str, Any]) -> str:
    return "|".join(f"{key}:{scope[key]}" for key in sorted(scope))


def serialize_literature_value_promotion_request(
    request: LiteratureValuePromotionRequestRecord,
) -> LiteratureValuePromotionRequestResponse:
    return LiteratureValuePromotionRequestResponse(
        promotion_request_id=request.promotion_request_id,
        tenant_id=request.tenant_id,
        candidate_id=request.candidate_id,
        source_review_packet_hash=request.source_review_packet_hash,
        review_draft_id=request.review_draft_id,
        comparison_hash=request.comparison_hash,
        raw_value=request.raw_value,
        unit=request.unit,
        conditions={str(key): str(value) for key, value in request.conditions.items()},
        target_use=request.target_use,
        target_scope=request.target_scope,
        request_status=request.request_status,  # type: ignore[arg-type]
        requested_by_user_id=request.requested_by_user_id,
        idempotency_key=request.idempotency_key,
        side_effects={key: bool(value) for key, value in request.side_effects.items()},
        guardrails=[str(value) for value in request.guardrail_snapshot],
        created_at=_iso_or_empty(request.created_at),
        updated_at=_iso_or_empty(request.updated_at),
    )


def serialize_literature_value_promotion_approval(
    approval: LiteratureValuePromotionApprovalRecord,
    *,
    approved_by_user_roles: set[str] | list[str] | tuple[str, ...] | None = None,
) -> LiteratureValuePromotionApprovalResponse:
    return LiteratureValuePromotionApprovalResponse(
        approval_id=approval.approval_id,
        tenant_id=approval.tenant_id,
        promotion_request_id=approval.promotion_request_id,
        candidate_id=approval.candidate_id,
        approval_action=approval.approval_action,  # type: ignore[arg-type]
        request_status_before=approval.request_status_before,  # type: ignore[arg-type]
        request_status_after=approval.request_status_after,  # type: ignore[arg-type]
        approved_by_user_id=approval.approved_by_user_id,
        approved_by_user_roles=sorted(approved_by_user_roles or []),
        approver_notes=approval.approver_notes,
        idempotency_key=approval.idempotency_key,
        source_review_packet_hash=approval.source_review_packet_hash,
        review_draft_id=approval.review_draft_id,
        comparison_hash=approval.comparison_hash,
        target_use=approval.target_use,
        target_scope=approval.target_scope,
        side_effects={key: bool(value) for key, value in approval.side_effects.items()},
        guardrails=[str(value) for value in approval.guardrail_snapshot],
        created_at=_iso_or_empty(approval.created_at),
        updated_at=_iso_or_empty(approval.updated_at),
    )


def serialize_literature_value_overlay(overlay: LiteratureValueOverlayRecord) -> LiteratureValueOverlayResponse:
    source_ref = str(overlay.conditions.get("source_ref") or overlay.source_review_packet_hash)
    normalized_value = f"{overlay.raw_value} {overlay.unit}".strip()
    validity_scope = {
        "target_scope": overlay.target_scope,
        "conditions": overlay.conditions,
        "target_use": overlay.target_use,
    }
    approval_hash = _stable_json_hash(
        {
            "approval_id": overlay.approval_id,
            "promotion_request_id": overlay.promotion_request_id,
            "candidate_id": overlay.candidate_id,
            "source_review_packet_hash": overlay.source_review_packet_hash,
            "comparison_hash": overlay.comparison_hash,
            "target_scope": overlay.target_scope,
        }
    )
    overlay_hash = _stable_json_hash(
        {
            "overlay_id": overlay.overlay_id,
            "promotion_request_id": overlay.promotion_request_id,
            "approval_id": overlay.approval_id,
            "candidate_id": overlay.candidate_id,
            "normalized_value": normalized_value,
            "source_ref": source_ref,
            "validity_scope": validity_scope,
            "overlay_status": overlay.overlay_status,
        }
    )
    return LiteratureValueOverlayResponse(
        overlay_id=overlay.overlay_id,
        tenant_id=overlay.tenant_id,
        promotion_request_id=overlay.promotion_request_id,
        approval_id=overlay.approval_id,
        candidate_id=overlay.candidate_id,
        overlay_status=overlay.overlay_status,  # type: ignore[arg-type]
        source_review_packet_hash=overlay.source_review_packet_hash,
        review_draft_id=overlay.review_draft_id,
        comparison_hash=overlay.comparison_hash,
        raw_value=overlay.raw_value,
        normalized_value=normalized_value,
        unit=overlay.unit,
        source_ref=source_ref,
        approval_hash=approval_hash,
        overlay_hash=overlay_hash,
        conditions={str(key): str(value) for key, value in overlay.conditions.items()},
        target_use=overlay.target_use,
        target_scope=overlay.target_scope,
        validity_scope=validity_scope,
        rollback_pointer={
            "required": True,
            "overlay_id": overlay.overlay_id,
            "rollback_status": "not_rolled_back" if overlay.overlay_status != "rolled_back" else "rolled_back",
            "rollback_endpoint": f"/api/v1/external-sources/runtime-activations/{{activation_id}}/rollback",
        },
        created_by_user_id=overlay.created_by_user_id,
        overlay_notes=overlay.overlay_notes,
        idempotency_key=overlay.idempotency_key,
        side_effects={key: bool(value) for key, value in overlay.side_effects.items()},
        guardrails=[str(value) for value in overlay.guardrail_snapshot],
        created_at=_iso_or_empty(overlay.created_at),
        updated_at=_iso_or_empty(overlay.updated_at),
    )


def serialize_literature_value_runtime_activation(
    activation: LiteratureValueRuntimeActivationRecord,
) -> LiteratureValueRuntimeActivationResponse:
    scoped_enabled = activation.activation_status == "active"
    side_effects = {key: bool(value) for key, value in activation.side_effects.items()}
    side_effects["scoped_runtime_activation"] = scoped_enabled
    display_status = "active" if scoped_enabled else "deactivated"
    return LiteratureValueRuntimeActivationResponse(
        activation_id=activation.activation_id,
        tenant_id=activation.tenant_id,
        overlay_id=activation.overlay_id,
        promotion_request_id=activation.promotion_request_id,
        approval_id=activation.approval_id,
        candidate_id=activation.candidate_id,
        activation_status=activation.activation_status,  # type: ignore[arg-type]
        activation_scope=activation.activation_scope,
        scope_key=activation.scope_key,
        activated_by_user_id=activation.activated_by_user_id,
        operator_attestation=activation.operator_attestation,
        deactivated_by_user_id=activation.deactivated_by_user_id,
        deactivation_reason=activation.deactivation_reason,
        deactivated_at=_iso_or_empty(activation.deactivated_at) if activation.deactivated_at is not None else None,
        idempotency_key=activation.idempotency_key,
        runtime_display=f"external literature overlay active for this scope: {activation.scope_key} ({display_status})",
        scoped_runtime_activation_enabled=scoped_enabled,
        side_effects=side_effects,
        guardrails=[str(value) for value in activation.guardrail_snapshot],
        created_at=_iso_or_empty(activation.created_at),
        updated_at=_iso_or_empty(activation.updated_at),
    )


def serialize_literature_value_release_evidence_link(
    link: LiteratureValueReleaseEvidenceLinkRecord,
) -> LiteratureValueReleaseEvidenceLinkResponse:
    return LiteratureValueReleaseEvidenceLinkResponse(
        link_id=link.link_id,
        tenant_id=link.tenant_id,
        release_decision_id=link.release_decision_id,
        activation_id=link.activation_id,
        overlay_id=link.overlay_id,
        promotion_request_id=link.promotion_request_id,
        approval_id=link.approval_id,
        candidate_id=link.candidate_id,
        link_status=link.link_status,  # type: ignore[arg-type]
        rollback_status=link.rollback_status,  # type: ignore[arg-type]
        activation_scope=link.activation_scope,
        scope_key=link.scope_key,
        source_review_packet_hash=link.source_review_packet_hash,
        comparison_hash=link.comparison_hash,
        release_decision_before=link.release_decision_before,  # type: ignore[arg-type]
        release_decision_after=link.release_decision_after,  # type: ignore[arg-type]
        linked_by_user_id=link.linked_by_user_id,
        link_notes=link.link_notes,
        idempotency_key=link.idempotency_key,
        side_effects={key: bool(value) for key, value in link.side_effects.items()},
        guardrails=[str(value) for value in link.guardrail_snapshot],
        created_at=_iso_or_empty(link.created_at),
        updated_at=_iso_or_empty(link.updated_at),
    )


def serialize_literature_value_rollback(
    rollback: LiteratureValueRollbackRecord,
) -> LiteratureValueRollbackResponse:
    return LiteratureValueRollbackResponse(
        rollback_id=rollback.rollback_id,
        tenant_id=rollback.tenant_id,
        activation_id=rollback.activation_id,
        overlay_id=rollback.overlay_id,
        promotion_request_id=rollback.promotion_request_id,
        approval_id=rollback.approval_id,
        candidate_id=rollback.candidate_id,
        rollback_status=rollback.rollback_status,  # type: ignore[arg-type]
        activation_status_before=rollback.activation_status_before,  # type: ignore[arg-type]
        activation_status_after=rollback.activation_status_after,  # type: ignore[arg-type]
        overlay_status_before=rollback.overlay_status_before,  # type: ignore[arg-type]
        overlay_status_after=rollback.overlay_status_after,  # type: ignore[arg-type]
        affected_release_evidence_link_ids=[str(value) for value in rollback.affected_release_evidence_link_ids],
        release_evidence_link_status_updates=[
            {str(key): value for key, value in update.items()}
            for update in rollback.release_evidence_link_status_updates
        ],
        release_decision_states=[
            {str(key): value for key, value in state.items()}
            for state in rollback.release_decision_states
        ],
        rolled_back_by_user_id=rollback.rolled_back_by_user_id,
        rollback_reason=rollback.rollback_reason,
        operator_attestation=rollback.operator_attestation,
        idempotency_key=rollback.idempotency_key,
        side_effects={key: bool(value) for key, value in rollback.side_effects.items()},
        guardrails=[str(value) for value in rollback.guardrail_snapshot],
        created_at=_iso_or_empty(rollback.created_at),
        updated_at=_iso_or_empty(rollback.updated_at),
    )


async def get_literature_value_promotion_request_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
) -> LiteratureValuePromotionRequestRecord | None:
    return await db.scalar(
        select(LiteratureValuePromotionRequestRecord)
        .where(
            LiteratureValuePromotionRequestRecord.tenant_id == tenant_id,
            LiteratureValuePromotionRequestRecord.promotion_request_id == promotion_request_id,
        )
        .limit(1)
    )


async def get_literature_value_overlay_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    overlay_id: str,
) -> LiteratureValueOverlayRecord | None:
    return await db.scalar(
        select(LiteratureValueOverlayRecord)
        .where(
            LiteratureValueOverlayRecord.tenant_id == tenant_id,
            LiteratureValueOverlayRecord.overlay_id == overlay_id,
        )
        .limit(1)
    )


async def get_literature_value_runtime_activation_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    activation_id: str,
) -> LiteratureValueRuntimeActivationRecord | None:
    return await db.scalar(
        select(LiteratureValueRuntimeActivationRecord)
        .where(
            LiteratureValueRuntimeActivationRecord.tenant_id == tenant_id,
            LiteratureValueRuntimeActivationRecord.activation_id == activation_id,
        )
        .limit(1)
    )


async def _latest_literature_value_promotion_approval(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
) -> LiteratureValuePromotionApprovalRecord | None:
    return await db.scalar(
        select(LiteratureValuePromotionApprovalRecord)
        .where(
            LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
            LiteratureValuePromotionApprovalRecord.promotion_request_id == promotion_request_id,
            LiteratureValuePromotionApprovalRecord.request_status_after == "approved_for_promotion",
        )
        .order_by(
            LiteratureValuePromotionApprovalRecord.created_at.desc(),
            LiteratureValuePromotionApprovalRecord.id.desc(),
        )
        .limit(1)
    )


async def _roles_for_user_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    provided_roles: set[str] | list[str] | tuple[str, ...] | None = None,
) -> set[str]:
    if provided_roles is not None:
        return {str(role) for role in provided_roles if str(role)}

    user = await db.scalar(
        select(User)
        .where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
        .limit(1)
    )
    if user is None:
        return set()
    return parse_user_roles(user.role)


async def _approval_roles_by_user_id(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
    current_user_id: int,
    current_user_roles: set[str],
) -> dict[int, set[str]]:
    approvals = (
        await db.execute(
            select(LiteratureValuePromotionApprovalRecord).where(
                LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
                LiteratureValuePromotionApprovalRecord.promotion_request_id == promotion_request_id,
                LiteratureValuePromotionApprovalRecord.approval_action == "approve",
            )
        )
    ).scalars()

    roles_by_user: dict[int, set[str]] = {current_user_id: set(current_user_roles)}
    for approval in approvals:
        if approval.approved_by_user_id == current_user_id:
            continue
        roles_by_user[approval.approved_by_user_id] = await _roles_for_user_id(
            db,
            tenant_id=tenant_id,
            user_id=approval.approved_by_user_id,
        )
    return roles_by_user


def _has_required_dual_literature_approval(roles_by_user: dict[int, set[str]]) -> bool:
    scientist_users = {
        user_id
        for user_id, roles in roles_by_user.items()
        if "scientist" in roles
    }
    governance_users = {
        user_id
        for user_id, roles in roles_by_user.items()
        if roles & LITERATURE_VALUE_PROMOTION_GOVERNANCE_APPROVER_ROLES
    }
    return any(scientist_user != governance_user for scientist_user in scientist_users for governance_user in governance_users)


async def _latest_literature_promotion_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureValuePromotionRequestRecord | None:
    return await db.scalar(
        select(LiteratureValuePromotionRequestRecord)
        .where(
            LiteratureValuePromotionRequestRecord.tenant_id == tenant_id,
            LiteratureValuePromotionRequestRecord.candidate_id == candidate_id,
        )
        .order_by(
            LiteratureValuePromotionRequestRecord.created_at.desc(),
            LiteratureValuePromotionRequestRecord.id.desc(),
        )
        .limit(1)
    )


async def get_literature_value_promotion_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureValuePromotionReadinessResponse | None:
    packet = await get_literature_extraction_candidate_review_packet_export(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if packet is None:
        return None
    comparison = await get_literature_extraction_review_draft_comparison(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    existing_request = await _latest_literature_promotion_request(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    candidate = packet.review_packet.candidate
    conditions = {
        "condition_context": candidate.condition_context,
        "experiment_context": candidate.experiment_context,
        "table_or_section_ref": candidate.table_or_section_ref,
        "treatment": candidate.treatment,
        "source_ref": candidate.source_ref,
        "source_kind": candidate.source_kind,
        "metric_key": candidate.metric_key,
    }
    chain_complete = (
        comparison is not None
        and comparison.current_review_draft_id is not None
        and comparison.comparison_manifest.get("comparison_hash") is not None
        and comparison.report_manifest.get("report_policy") == "response_only_no_file_write"
        and not any(comparison.side_effects.values())
        and not any(packet.side_effects.values())
    )
    blockers: list[str] = []
    if not chain_complete:
        blockers.append("literature review-only evidence chain is incomplete")

    return LiteratureValuePromotionReadinessResponse(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        chain_complete=chain_complete,
        promotion_ready=chain_complete,
        review_draft_id=comparison.current_review_draft_id if comparison is not None else None,
        source_review_packet_hash=packet.content_hash,
        comparison_hash=str(comparison.comparison_manifest.get("comparison_hash")) if comparison is not None else None,
        raw_value=candidate.raw_value,
        unit=candidate.unit,
        conditions=conditions,
        request_status=existing_request.request_status if existing_request is not None else "not_requested",  # type: ignore[arg-type]
        existing_promotion_request_id=existing_request.promotion_request_id if existing_request is not None else None,
        blocking_reason="; ".join(blockers) if blockers else None,
    )


async def create_literature_value_promotion_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
    requested_by_user_id: int,
    request: LiteratureValuePromotionRequestCreateRequest,
) -> LiteratureValuePromotionRequestResponse | None:
    existing = await db.scalar(
        select(LiteratureValuePromotionRequestRecord)
        .where(
            LiteratureValuePromotionRequestRecord.tenant_id == tenant_id,
            LiteratureValuePromotionRequestRecord.candidate_id == candidate_id,
            LiteratureValuePromotionRequestRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing is not None:
        if existing.target_use != request.target_use or existing.target_scope != request.target_scope:
            raise ValueError("literature_value_promotion_request_idempotency_conflict")
        return serialize_literature_value_promotion_request(existing)

    readiness = await get_literature_value_promotion_readiness(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if readiness is None:
        return None
    if not readiness.promotion_ready:
        raise ValueError("literature_value_promotion_not_ready")
    if readiness.review_draft_id is None or readiness.source_review_packet_hash is None or readiness.comparison_hash is None:
        raise ValueError("literature_value_promotion_missing_review_chain")
    if readiness.raw_value is None or readiness.unit is None:
        raise ValueError("literature_value_promotion_missing_candidate_value")

    record = LiteratureValuePromotionRequestRecord(
        promotion_request_id=new_literature_value_promotion_request_id(),
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        source_review_packet_hash=readiness.source_review_packet_hash,
        review_draft_id=readiness.review_draft_id,
        comparison_hash=readiness.comparison_hash,
        raw_value=readiness.raw_value,
        unit=readiness.unit,
        conditions=readiness.conditions,
        target_use=request.target_use,
        target_scope=request.target_scope,
        request_status="requested",
        requested_by_user_id=requested_by_user_id,
        idempotency_key=request.idempotency_key,
        side_effects=dict(LITERATURE_VALUE_PROMOTION_REQUEST_SIDE_EFFECTS),
        guardrail_snapshot=list(LITERATURE_VALUE_PROMOTION_REQUEST_GUARDRAILS),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return serialize_literature_value_promotion_request(record)


async def create_literature_value_promotion_approval(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
    approved_by_user_id: int,
    approved_by_user_roles: set[str] | list[str] | tuple[str, ...] | None = None,
    request: LiteratureValuePromotionApprovalCreateRequest,
) -> LiteratureValuePromotionApprovalResponse | None:
    promotion_request = await get_literature_value_promotion_request_record(
        db,
        tenant_id=tenant_id,
        promotion_request_id=promotion_request_id,
    )
    if promotion_request is None:
        return None

    approver_roles = await _roles_for_user_id(
        db,
        tenant_id=tenant_id,
        user_id=approved_by_user_id,
        provided_roles=approved_by_user_roles,
    )
    if not approver_roles & LITERATURE_VALUE_PROMOTION_APPROVER_ROLES:
        raise ValueError("literature_value_promotion_approver_role_required")
    if approved_by_user_id == promotion_request.requested_by_user_id:
        raise ValueError("literature_value_promotion_requester_cannot_approve")

    existing = await db.scalar(
        select(LiteratureValuePromotionApprovalRecord)
        .where(
            LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
            LiteratureValuePromotionApprovalRecord.promotion_request_id == promotion_request_id,
            LiteratureValuePromotionApprovalRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing is not None:
        if existing.approval_action != request.approval_action or existing.approver_notes != request.approver_notes:
            raise ValueError("literature_value_promotion_approval_idempotency_conflict")
        return serialize_literature_value_promotion_approval(existing, approved_by_user_roles=approver_roles)

    if promotion_request.request_status != "requested":
        raise ValueError("literature_value_promotion_request_already_closed")

    duplicate_user_approval = await db.scalar(
        select(LiteratureValuePromotionApprovalRecord)
        .where(
            LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
            LiteratureValuePromotionApprovalRecord.promotion_request_id == promotion_request_id,
            LiteratureValuePromotionApprovalRecord.approved_by_user_id == approved_by_user_id,
        )
        .limit(1)
    )
    if duplicate_user_approval is not None:
        raise ValueError("literature_value_promotion_approver_already_recorded")

    request_status_after = "rejected"
    if request.approval_action == "approve":
        roles_by_user = await _approval_roles_by_user_id(
            db,
            tenant_id=tenant_id,
            promotion_request_id=promotion_request_id,
            current_user_id=approved_by_user_id,
            current_user_roles=approver_roles,
        )
        request_status_after = (
            "approved_for_promotion"
            if _has_required_dual_literature_approval(roles_by_user)
            else "requested"
        )
    approval = LiteratureValuePromotionApprovalRecord(
        approval_id=new_literature_value_promotion_approval_id(),
        tenant_id=tenant_id,
        promotion_request_record_id=promotion_request.id,
        promotion_request_id=promotion_request.promotion_request_id,
        candidate_id=promotion_request.candidate_id,
        approval_action=request.approval_action,
        request_status_before=promotion_request.request_status,
        request_status_after=request_status_after,
        approved_by_user_id=approved_by_user_id,
        approver_notes=request.approver_notes,
        idempotency_key=request.idempotency_key,
        source_review_packet_hash=promotion_request.source_review_packet_hash,
        review_draft_id=promotion_request.review_draft_id,
        comparison_hash=promotion_request.comparison_hash,
        target_use=promotion_request.target_use,
        target_scope=promotion_request.target_scope,
        side_effects=dict(LITERATURE_VALUE_PROMOTION_APPROVAL_SIDE_EFFECTS),
        guardrail_snapshot=list(LITERATURE_VALUE_PROMOTION_APPROVAL_GUARDRAILS),
    )
    promotion_request.request_status = request_status_after
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return serialize_literature_value_promotion_approval(approval, approved_by_user_roles=approver_roles)


async def reject_literature_value_promotion_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
    rejected_by_user_id: int,
    rejected_by_user_roles: set[str] | list[str] | tuple[str, ...] | None = None,
    request: LiteratureValuePromotionRejectRequest,
) -> LiteratureValuePromotionApprovalResponse | None:
    return await create_literature_value_promotion_approval(
        db,
        tenant_id=tenant_id,
        promotion_request_id=promotion_request_id,
        approved_by_user_id=rejected_by_user_id,
        approved_by_user_roles=rejected_by_user_roles,
        request=LiteratureValuePromotionApprovalCreateRequest(
            approval_action="reject",
            approver_notes=request.rejector_notes,
            idempotency_key=request.idempotency_key,
        ),
    )


async def promote_literature_value_request_to_overlay(
    db: AsyncSession,
    *,
    tenant_id: int,
    promotion_request_id: str,
    created_by_user_id: int,
    request: LiteratureValueOverlayCreateRequest,
) -> LiteratureValueOverlayResponse | None:
    promotion_request = await get_literature_value_promotion_request_record(
        db,
        tenant_id=tenant_id,
        promotion_request_id=promotion_request_id,
    )
    if promotion_request is None:
        return None

    existing = await db.scalar(
        select(LiteratureValueOverlayRecord)
        .where(
            LiteratureValueOverlayRecord.tenant_id == tenant_id,
            LiteratureValueOverlayRecord.promotion_request_id == promotion_request_id,
        )
        .limit(1)
    )
    if existing is not None:
        if existing.idempotency_key != request.idempotency_key:
            raise ValueError("literature_value_overlay_already_exists")
        if existing.overlay_notes != request.overlay_notes:
            raise ValueError("literature_value_overlay_idempotency_conflict")
        return serialize_literature_value_overlay(existing)

    if promotion_request.request_status != "approved_for_promotion":
        raise ValueError("literature_value_promotion_request_not_approved")

    approval = await _latest_literature_value_promotion_approval(
        db,
        tenant_id=tenant_id,
        promotion_request_id=promotion_request_id,
    )
    if approval is None:
        raise ValueError("literature_value_promotion_approval_required")

    overlay = LiteratureValueOverlayRecord(
        overlay_id=new_literature_value_overlay_id(),
        tenant_id=tenant_id,
        promotion_request_record_id=promotion_request.id,
        approval_record_id=approval.id,
        promotion_request_id=promotion_request.promotion_request_id,
        approval_id=approval.approval_id,
        candidate_id=promotion_request.candidate_id,
        overlay_status="inactive",
        source_review_packet_hash=promotion_request.source_review_packet_hash,
        review_draft_id=promotion_request.review_draft_id,
        comparison_hash=promotion_request.comparison_hash,
        raw_value=promotion_request.raw_value,
        unit=promotion_request.unit,
        conditions=promotion_request.conditions,
        target_use=promotion_request.target_use,
        target_scope=promotion_request.target_scope,
        created_by_user_id=created_by_user_id,
        overlay_notes=request.overlay_notes,
        idempotency_key=request.idempotency_key,
        side_effects=dict(LITERATURE_VALUE_OVERLAY_SIDE_EFFECTS),
        guardrail_snapshot=list(LITERATURE_VALUE_OVERLAY_GUARDRAILS),
    )
    db.add(overlay)
    await db.commit()
    await db.refresh(overlay)
    return serialize_literature_value_overlay(overlay)


async def get_literature_value_runtime_activation_preview(
    db: AsyncSession,
    *,
    tenant_id: int,
    overlay_id: str,
) -> LiteratureValueRuntimeActivationPreviewResponse | None:
    overlay = await get_literature_value_overlay_record(db, tenant_id=tenant_id, overlay_id=overlay_id)
    if overlay is None:
        return None
    approved_overlay = bool(overlay.approval_id)
    can_activate = approved_overlay and overlay.overlay_status == "inactive"
    blocker = None if can_activate else "approved inactive overlay required for scoped activation"
    return LiteratureValueRuntimeActivationPreviewResponse(
        tenant_id=tenant_id,
        overlay_id=overlay.overlay_id,
        candidate_id=overlay.candidate_id,
        overlay_status=overlay.overlay_status,  # type: ignore[arg-type]
        approved_overlay=approved_overlay,
        can_activate_scoped_runtime=can_activate,
        blocking_reason=blocker,
    )


async def create_literature_value_runtime_activation(
    db: AsyncSession,
    *,
    tenant_id: int,
    overlay_id: str,
    activated_by_user_id: int,
    request: LiteratureValueRuntimeActivationCreateRequest,
) -> LiteratureValueRuntimeActivationResponse | None:
    overlay = await get_literature_value_overlay_record(db, tenant_id=tenant_id, overlay_id=overlay_id)
    if overlay is None:
        return None
    if not overlay.approval_id or overlay.overlay_status != "inactive":
        raise ValueError("literature_value_overlay_not_approved_inactive")

    scope_key = _literature_runtime_scope_key(request.activation_scope)
    existing_by_idempotency = await db.scalar(
        select(LiteratureValueRuntimeActivationRecord)
        .where(
            LiteratureValueRuntimeActivationRecord.tenant_id == tenant_id,
            LiteratureValueRuntimeActivationRecord.overlay_id == overlay_id,
            LiteratureValueRuntimeActivationRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing_by_idempotency is not None:
        if (
            existing_by_idempotency.activation_scope != request.activation_scope
            or existing_by_idempotency.operator_attestation != request.operator_attestation
        ):
            raise ValueError("literature_value_runtime_activation_idempotency_conflict")
        return serialize_literature_value_runtime_activation(existing_by_idempotency)

    existing_active = await db.scalar(
        select(LiteratureValueRuntimeActivationRecord)
        .where(
            LiteratureValueRuntimeActivationRecord.tenant_id == tenant_id,
            LiteratureValueRuntimeActivationRecord.overlay_id == overlay_id,
            LiteratureValueRuntimeActivationRecord.scope_key == scope_key,
            LiteratureValueRuntimeActivationRecord.activation_status == "active",
        )
        .limit(1)
    )
    if existing_active is not None:
        raise ValueError("literature_value_runtime_activation_already_active_for_scope")

    activation = LiteratureValueRuntimeActivationRecord(
        activation_id=new_literature_value_runtime_activation_id(),
        tenant_id=tenant_id,
        overlay_record_id=overlay.id,
        overlay_id=overlay.overlay_id,
        promotion_request_id=overlay.promotion_request_id,
        approval_id=overlay.approval_id,
        candidate_id=overlay.candidate_id,
        activation_status="active",
        activation_scope=request.activation_scope,
        scope_key=scope_key,
        activated_by_user_id=activated_by_user_id,
        operator_attestation=request.operator_attestation,
        idempotency_key=request.idempotency_key,
        side_effects={
            "scoped_runtime_activation": True,
            "global_runtime_activation": False,
            "validated_default_write": False,
            "species_db_write": False,
            "feedstock_db_write": False,
            "release_evidence_use": False,
            "final_action_execution": False,
        },
        guardrail_snapshot=list(LITERATURE_VALUE_RUNTIME_ACTIVATION_GUARDRAILS),
    )
    db.add(activation)
    await db.commit()
    await db.refresh(activation)
    return serialize_literature_value_runtime_activation(activation)


async def deactivate_literature_value_runtime_activation(
    db: AsyncSession,
    *,
    tenant_id: int,
    activation_id: str,
    deactivated_by_user_id: int,
    request: LiteratureValueRuntimeActivationDeactivateRequest,
) -> LiteratureValueRuntimeActivationResponse | None:
    activation = await get_literature_value_runtime_activation_record(
        db,
        tenant_id=tenant_id,
        activation_id=activation_id,
    )
    if activation is None:
        return None
    if activation.activation_status == "deactivated":
        if activation.deactivation_reason == request.deactivation_reason:
            return serialize_literature_value_runtime_activation(activation)
        raise ValueError("literature_value_runtime_activation_already_deactivated")

    activation.activation_status = "deactivated"
    activation.deactivated_by_user_id = deactivated_by_user_id
    activation.deactivation_reason = request.deactivation_reason
    activation.deactivated_at = datetime.now(UTC)
    activation.side_effects = {
        "scoped_runtime_activation": False,
        "global_runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "final_action_execution": False,
    }
    await db.commit()
    await db.refresh(activation)
    return serialize_literature_value_runtime_activation(activation)


async def create_literature_value_release_evidence_link(
    db: AsyncSession,
    *,
    tenant_id: int,
    release_decision_id: int,
    linked_by_user_id: int,
    request: LiteratureValueReleaseEvidenceLinkCreateRequest,
) -> LiteratureValueReleaseEvidenceLinkResponse | None:
    release_decision = await db.get(ReleaseDecision, release_decision_id)
    if release_decision is None or release_decision.tenant_id != tenant_id:
        return None
    if release_decision.decision != "review_required":
        raise ValueError("literature_value_release_decision_must_remain_review_required")

    activation = await get_literature_value_runtime_activation_record(
        db,
        tenant_id=tenant_id,
        activation_id=request.activation_id,
    )
    if activation is None:
        raise ValueError("literature_value_runtime_activation_not_found")
    if activation.activation_status != "active":
        raise ValueError("literature_value_release_evidence_requires_active_scoped_activation")
    overlay = await get_literature_value_overlay_record(db, tenant_id=tenant_id, overlay_id=activation.overlay_id)
    if overlay is None:
        raise ValueError("literature_value_overlay_not_found")

    existing = await db.scalar(
        select(LiteratureValueReleaseEvidenceLinkRecord)
        .where(
            LiteratureValueReleaseEvidenceLinkRecord.tenant_id == tenant_id,
            LiteratureValueReleaseEvidenceLinkRecord.release_decision_id == release_decision_id,
            LiteratureValueReleaseEvidenceLinkRecord.activation_id == request.activation_id,
            LiteratureValueReleaseEvidenceLinkRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing is not None:
        if existing.link_notes != request.link_notes:
            raise ValueError("literature_value_release_evidence_link_idempotency_conflict")
        return serialize_literature_value_release_evidence_link(existing)

    link = LiteratureValueReleaseEvidenceLinkRecord(
        link_id=new_literature_value_release_evidence_link_id(),
        tenant_id=tenant_id,
        release_decision_id=release_decision_id,
        activation_record_id=activation.id,
        activation_id=activation.activation_id,
        overlay_id=activation.overlay_id,
        promotion_request_id=activation.promotion_request_id,
        approval_id=activation.approval_id,
        candidate_id=activation.candidate_id,
        link_status="active",
        rollback_status="none",
        activation_scope=activation.activation_scope,
        scope_key=activation.scope_key,
        source_review_packet_hash=overlay.source_review_packet_hash,
        comparison_hash=overlay.comparison_hash,
        release_decision_before=release_decision.decision,
        release_decision_after=release_decision.decision,
        linked_by_user_id=linked_by_user_id,
        link_notes=request.link_notes,
        idempotency_key=request.idempotency_key,
        side_effects=dict(LITERATURE_VALUE_RELEASE_EVIDENCE_LINK_SIDE_EFFECTS),
        guardrail_snapshot=list(LITERATURE_VALUE_RELEASE_EVIDENCE_LINK_GUARDRAILS),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return serialize_literature_value_release_evidence_link(link)


async def rollback_literature_value_runtime_activation(
    db: AsyncSession,
    *,
    tenant_id: int,
    activation_id: str,
    rolled_back_by_user_id: int,
    request: LiteratureValueRollbackCreateRequest,
) -> LiteratureValueRollbackResponse | None:
    activation = await get_literature_value_runtime_activation_record(
        db,
        tenant_id=tenant_id,
        activation_id=activation_id,
    )
    if activation is None:
        return None

    existing = await db.scalar(
        select(LiteratureValueRollbackRecord)
        .where(
            LiteratureValueRollbackRecord.tenant_id == tenant_id,
            LiteratureValueRollbackRecord.activation_id == activation_id,
            LiteratureValueRollbackRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing is not None:
        if (
            existing.rollback_reason != request.rollback_reason
            or existing.operator_attestation != request.operator_attestation
        ):
            raise ValueError("literature_value_rollback_idempotency_conflict")
        return serialize_literature_value_rollback(existing)

    if activation.activation_status != "active":
        raise ValueError("literature_value_runtime_activation_not_active")

    overlay = await get_literature_value_overlay_record(db, tenant_id=tenant_id, overlay_id=activation.overlay_id)
    if overlay is None:
        raise ValueError("literature_value_overlay_not_found")

    release_links_result = await db.execute(
        select(LiteratureValueReleaseEvidenceLinkRecord).where(
            LiteratureValueReleaseEvidenceLinkRecord.tenant_id == tenant_id,
            LiteratureValueReleaseEvidenceLinkRecord.activation_id == activation_id,
        )
    )
    release_links = list(release_links_result.scalars().all())
    release_decision_states: list[dict[str, Any]] = []
    link_updates: list[dict[str, Any]] = []
    for link in release_links:
        release_decision = await db.get(ReleaseDecision, link.release_decision_id)
        if release_decision is None or release_decision.tenant_id != tenant_id:
            raise ValueError("literature_value_release_decision_not_found")
        if release_decision.decision != "review_required":
            raise ValueError("literature_value_release_decision_must_remain_review_required")
        release_decision_states.append(
            {
                "release_decision_id": release_decision.id,
                "link_id": link.link_id,
                "release_decision_before": release_decision.decision,
                "release_decision_after": release_decision.decision,
            }
        )
        link_updates.append(
            {
                "link_id": link.link_id,
                "link_status_before": link.link_status,
                "link_status_after": "rolled_back",
                "rollback_status_before": link.rollback_status,
                "rollback_status_after": "rolled_back",
            }
        )

    activation_status_before = activation.activation_status
    overlay_status_before = overlay.overlay_status

    activation.activation_status = "deactivated"
    activation.deactivated_by_user_id = rolled_back_by_user_id
    activation.deactivation_reason = request.rollback_reason
    activation.deactivated_at = datetime.now(UTC)
    activation.side_effects = {
        "scoped_runtime_activation": False,
        "global_runtime_activation": False,
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "release_evidence_use": False,
        "final_action_execution": False,
    }
    overlay.overlay_status = "rolled_back"
    for link in release_links:
        link.link_status = "rolled_back"
        link.rollback_status = "rolled_back"

    rollback = LiteratureValueRollbackRecord(
        rollback_id=new_literature_value_rollback_id(),
        tenant_id=tenant_id,
        activation_record_id=activation.id,
        overlay_record_id=overlay.id,
        activation_id=activation.activation_id,
        overlay_id=activation.overlay_id,
        promotion_request_id=activation.promotion_request_id,
        approval_id=activation.approval_id,
        candidate_id=activation.candidate_id,
        rollback_status="completed",
        activation_status_before=activation_status_before,
        activation_status_after="deactivated",
        overlay_status_before=overlay_status_before,
        overlay_status_after="rolled_back",
        affected_release_evidence_link_ids=[link.link_id for link in release_links],
        release_evidence_link_status_updates=link_updates,
        release_decision_states=release_decision_states,
        rolled_back_by_user_id=rolled_back_by_user_id,
        rollback_reason=request.rollback_reason,
        operator_attestation=request.operator_attestation,
        idempotency_key=request.idempotency_key,
        side_effects=dict(LITERATURE_VALUE_ROLLBACK_SIDE_EFFECTS),
        guardrail_snapshot=list(LITERATURE_VALUE_ROLLBACK_GUARDRAILS),
    )
    db.add(rollback)
    await db.commit()
    await db.refresh(rollback)
    return serialize_literature_value_rollback(rollback)


async def get_literature_value_promotion_lifecycle(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureValuePromotionLifecycleResponse | None:
    candidate = await _get_literature_extraction_candidate_record(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if candidate is None:
        return None

    promotion_requests = list(
        (
            await db.execute(
                select(LiteratureValuePromotionRequestRecord)
                .where(
                    LiteratureValuePromotionRequestRecord.tenant_id == tenant_id,
                    LiteratureValuePromotionRequestRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValuePromotionRequestRecord.created_at.asc(),
                    LiteratureValuePromotionRequestRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    approvals = list(
        (
            await db.execute(
                select(LiteratureValuePromotionApprovalRecord)
                .where(
                    LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
                    LiteratureValuePromotionApprovalRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValuePromotionApprovalRecord.created_at.asc(),
                    LiteratureValuePromotionApprovalRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    overlays = list(
        (
            await db.execute(
                select(LiteratureValueOverlayRecord)
                .where(
                    LiteratureValueOverlayRecord.tenant_id == tenant_id,
                    LiteratureValueOverlayRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValueOverlayRecord.created_at.asc(),
                    LiteratureValueOverlayRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    activations = list(
        (
            await db.execute(
                select(LiteratureValueRuntimeActivationRecord)
                .where(
                    LiteratureValueRuntimeActivationRecord.tenant_id == tenant_id,
                    LiteratureValueRuntimeActivationRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValueRuntimeActivationRecord.created_at.asc(),
                    LiteratureValueRuntimeActivationRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    release_links = list(
        (
            await db.execute(
                select(LiteratureValueReleaseEvidenceLinkRecord)
                .where(
                    LiteratureValueReleaseEvidenceLinkRecord.tenant_id == tenant_id,
                    LiteratureValueReleaseEvidenceLinkRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValueReleaseEvidenceLinkRecord.created_at.asc(),
                    LiteratureValueReleaseEvidenceLinkRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    rollbacks = list(
        (
            await db.execute(
                select(LiteratureValueRollbackRecord)
                .where(
                    LiteratureValueRollbackRecord.tenant_id == tenant_id,
                    LiteratureValueRollbackRecord.candidate_id == candidate_id,
                )
                .order_by(
                    LiteratureValueRollbackRecord.created_at.asc(),
                    LiteratureValueRollbackRecord.id.asc(),
                )
            )
        )
        .scalars()
        .all()
    )

    release_decision_states = [
        {
            "release_decision_id": link.release_decision_id,
            "link_id": link.link_id,
            "release_decision_before": link.release_decision_before,
            "release_decision_after": link.release_decision_after,
            "link_status": link.link_status,
            "rollback_status": link.rollback_status,
        }
        for link in release_links
    ]
    for rollback in rollbacks:
        release_decision_states.extend(
            {str(key): value for key, value in state.items()}
            for state in rollback.release_decision_states
        )

    return LiteratureValuePromotionLifecycleResponse(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        promotion_request_count=len(promotion_requests),
        approval_count=len(approvals),
        overlay_count=len(overlays),
        runtime_activation_count=len(activations),
        release_evidence_link_count=len(release_links),
        rollback_count=len(rollbacks),
        promotion_request_ids=[record.promotion_request_id for record in promotion_requests],
        approval_ids=[record.approval_id for record in approvals],
        overlay_ids=[record.overlay_id for record in overlays],
        activation_ids=[record.activation_id for record in activations],
        release_evidence_link_ids=[record.link_id for record in release_links],
        rollback_ids=[record.rollback_id for record in rollbacks],
        request_statuses=[record.request_status for record in promotion_requests],
        approval_actions=[record.approval_action for record in approvals],
        overlay_statuses=[record.overlay_status for record in overlays],
        activation_statuses=[record.activation_status for record in activations],
        release_evidence_link_statuses=[record.link_status for record in release_links],
        rollback_statuses=[record.rollback_status for record in rollbacks],
        release_decision_states=release_decision_states,
    )


async def get_literature_value_promotion_audit_export(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureValuePromotionAuditExportResponse | None:
    lifecycle = await get_literature_value_promotion_lifecycle(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if lifecycle is None:
        return None

    promotion_requests = list(
        (
            await db.execute(
                select(LiteratureValuePromotionRequestRecord)
                .where(
                    LiteratureValuePromotionRequestRecord.tenant_id == tenant_id,
                    LiteratureValuePromotionRequestRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValuePromotionRequestRecord.created_at.asc(), LiteratureValuePromotionRequestRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    approvals = list(
        (
            await db.execute(
                select(LiteratureValuePromotionApprovalRecord)
                .where(
                    LiteratureValuePromotionApprovalRecord.tenant_id == tenant_id,
                    LiteratureValuePromotionApprovalRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValuePromotionApprovalRecord.created_at.asc(), LiteratureValuePromotionApprovalRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    overlays = list(
        (
            await db.execute(
                select(LiteratureValueOverlayRecord)
                .where(
                    LiteratureValueOverlayRecord.tenant_id == tenant_id,
                    LiteratureValueOverlayRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValueOverlayRecord.created_at.asc(), LiteratureValueOverlayRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    activations = list(
        (
            await db.execute(
                select(LiteratureValueRuntimeActivationRecord)
                .where(
                    LiteratureValueRuntimeActivationRecord.tenant_id == tenant_id,
                    LiteratureValueRuntimeActivationRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValueRuntimeActivationRecord.created_at.asc(), LiteratureValueRuntimeActivationRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    release_links = list(
        (
            await db.execute(
                select(LiteratureValueReleaseEvidenceLinkRecord)
                .where(
                    LiteratureValueReleaseEvidenceLinkRecord.tenant_id == tenant_id,
                    LiteratureValueReleaseEvidenceLinkRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValueReleaseEvidenceLinkRecord.created_at.asc(), LiteratureValueReleaseEvidenceLinkRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    rollbacks = list(
        (
            await db.execute(
                select(LiteratureValueRollbackRecord)
                .where(
                    LiteratureValueRollbackRecord.tenant_id == tenant_id,
                    LiteratureValueRollbackRecord.candidate_id == candidate_id,
                )
                .order_by(LiteratureValueRollbackRecord.created_at.asc(), LiteratureValueRollbackRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )

    request_payload = (
        serialize_literature_value_promotion_request(promotion_requests[-1]).model_dump(mode="json")
        if promotion_requests
        else None
    )
    approval_payloads = [
        serialize_literature_value_promotion_approval(approval).model_dump(mode="json")
        for approval in approvals
    ]
    overlay_payload = serialize_literature_value_overlay(overlays[-1]).model_dump(mode="json") if overlays else None
    activation_payload = (
        serialize_literature_value_runtime_activation(activations[-1]).model_dump(mode="json")
        if activations
        else None
    )
    release_link_payload = (
        serialize_literature_value_release_evidence_link(release_links[-1]).model_dump(mode="json")
        if release_links
        else None
    )
    rollback_payload = serialize_literature_value_rollback(rollbacks[-1]).model_dump(mode="json") if rollbacks else None

    release_decision_states = [
        {
            "release_decision_id": link.release_decision_id,
            "link_id": link.link_id,
            "release_decision_before": link.release_decision_before,
            "release_decision_after": link.release_decision_after,
        }
        for link in release_links
    ]
    for rollback in rollbacks:
        release_decision_states.extend(
            {str(key): value for key, value in state.items()}
            for state in rollback.release_decision_states
        )

    db_pollution_proof = {
        "validated_default_write": False,
        "species_db_write": False,
        "feedstock_db_write": False,
        "candidate_id_present_in_species_db": candidate_id in SPECIES_DB,
        "candidate_id_present_in_feedstock_db": candidate_id in FEEDSTOCK_DB,
        "species_db_key_count": len(SPECIES_DB),
        "feedstock_db_key_count": len(FEEDSTOCK_DB),
    }
    final_action_non_execution_proof = {
        "final_action_execution": False,
        "release_auto_approval": False,
        "release_decision_update": False,
        "release_decision_states": release_decision_states,
        "release_decisions_all_review_required": all(
            state.get("release_decision_before") == "review_required"
            and state.get("release_decision_after") == "review_required"
            for state in release_decision_states
        ),
    }
    export_payload = {
        "tenant_id": tenant_id,
        "candidate_id": candidate_id,
        "request": request_payload,
        "approvals": approval_payloads,
        "overlay": overlay_payload,
        "runtime_activation": activation_payload,
        "release_evidence_link": release_link_payload,
        "rollback": rollback_payload,
        "db_pollution_proof": db_pollution_proof,
        "final_action_non_execution_proof": final_action_non_execution_proof,
        "lifecycle": lifecycle.model_dump(mode="json"),
    }
    content_hash = _stable_json_hash(export_payload)
    export_manifest = {
        "export_id": f"literature-value-promotion-audit-export:{candidate_id}:{content_hash[:12]}",
        "candidate_id": candidate_id,
        "content_hash_algorithm": "sha256",
        "content_hash": content_hash,
        "export_policy": "response_only_no_file_write",
        "file_written": False,
        "promotion_request_count": len(promotion_requests),
        "approval_count": len(approvals),
        "overlay_count": len(overlays),
        "runtime_activation_count": len(activations),
        "release_evidence_link_count": len(release_links),
        "rollback_count": len(rollbacks),
        "request_statuses": lifecycle.request_statuses,
        "release_decision_states": release_decision_states,
        "db_pollution_proof_included": True,
        "final_action_non_execution_proof_included": True,
    }
    return LiteratureValuePromotionAuditExportResponse(
        tenant_id=tenant_id,
        candidate_id=candidate_id,
        content_hash=content_hash,
        export_manifest=export_manifest,
        request=request_payload,
        approvals=approval_payloads,
        overlay=overlay_payload,
        runtime_activation=activation_payload,
        release_evidence_link=release_link_payload,
        rollback=rollback_payload,
        db_pollution_proof=db_pollution_proof,
        final_action_non_execution_proof=final_action_non_execution_proof,
    )


async def create_literature_extraction_review_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
    reviewer_user_id: int,
    request: LiteratureExtractionReviewDraftCreateRequest,
) -> LiteratureExtractionReviewDraftResponse | None:
    existing = await db.scalar(
        select(LiteratureExtractionReviewDraftRecord)
        .where(
            LiteratureExtractionReviewDraftRecord.tenant_id == tenant_id,
            LiteratureExtractionReviewDraftRecord.candidate_id == candidate_id,
            LiteratureExtractionReviewDraftRecord.idempotency_key == request.idempotency_key,
        )
        .limit(1)
    )
    if existing is not None:
        if existing.review_intent != request.review_intent:
            raise ValueError("literature_extraction_review_draft_idempotency_conflict")
        return serialize_literature_extraction_review_draft(existing)

    exported = await get_literature_extraction_candidate_review_packet_export(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if exported is None:
        return None

    candidate = exported.review_packet.candidate
    if candidate.review_status != "pending_review":
        raise ValueError("literature_extraction_candidate_not_pending_review")

    export_manifest = exported.export_manifest
    guardrails = [
        "literature_extraction_review_draft_records_intent_only",
        "candidate_status_remains_pending_review",
        "draft_is_not_release_evidence",
        "runtime_activation_enabled_false",
        "validated_default_write_enabled_false",
        "promotion_enabled_false",
        "no_species_db_writes",
        "no_feedstock_db_writes",
        "no_final_action_execution",
    ]
    draft = LiteratureExtractionReviewDraftRecord(
        review_draft_id=new_literature_review_draft_id(),
        tenant_id=tenant_id,
        candidate_id=candidate.candidate_id,
        source_id=candidate.source_id,
        reviewer_user_id=reviewer_user_id,
        review_intent=request.review_intent,
        reviewer_notes=request.reviewer_notes,
        source_review_packet_export_id=str(export_manifest["export_id"]),
        source_review_packet_hash=exported.content_hash,
        candidate_snapshot=candidate.model_dump(mode="json"),
        export_manifest=export_manifest,
        guardrail_snapshot=guardrails,
        side_effects=dict(LITERATURE_REVIEW_DRAFT_SIDE_EFFECTS),
        idempotency_key=request.idempotency_key,
        status="draft_intent_recorded",
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return serialize_literature_extraction_review_draft(draft)


def _literature_extraction_candidate_values(*, payload: dict[str, Any], tenant_id: int) -> dict[str, Any]:
    candidate = LiteratureExtractionCandidateRead.model_validate(payload)
    return {
        "tenant_id": tenant_id,
        "candidate_id": candidate.candidate_id,
        "source_id": candidate.source_id,
        "doi": candidate.doi,
        "source_ref": candidate.source_ref,
        "title": candidate.title,
        "species": candidate.species,
        "feedstock": candidate.feedstock,
        "treatment": candidate.treatment,
        "metric_key": candidate.metric_key,
        "metric_label": candidate.metric_label,
        "raw_value": candidate.raw_value,
        "unit": candidate.unit,
        "condition_context": candidate.condition_context,
        "experiment_context": candidate.experiment_context,
        "table_or_section_ref": candidate.table_or_section_ref,
        "extraction_note": candidate.extraction_note,
        "license_note": candidate.license_note,
        "source_kind": candidate.source_kind,
        "review_status": candidate.review_status,
        "human_review_required": candidate.human_review_required,
        "numeric_values_included": candidate.numeric_values_included,
        "release_evidence_allowed": candidate.release_evidence_allowed,
        "runtime_activation_enabled": candidate.runtime_activation_enabled,
        "validated_default_write_enabled": candidate.validated_default_write_enabled,
        "promotion_enabled": candidate.promotion_enabled,
        "guardrails": list(candidate.guardrails),
        "raw_payload": candidate.model_dump(mode="json"),
    }


def build_feedstock_dataset_candidate(source: ExternalSourceRecord) -> FeedstockDatasetCandidateRead:
    raw_payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
    source_ref = str(raw_payload.get("鎺ㄨ崘閾炬帴") or source.source_name)
    return FeedstockDatasetCandidateRead(
        candidate_uid=f"feedstock_dataset_candidate:{source.source_id}",
        source_id=source.source_id,
        source_name=source.source_name,
        source_owner=source.source_owner,
        source_kind=source.evidence_source_kind,
        source_ref=source_ref,
        license_note=source.license_note,
        ingestion_mode=source.ingestion_mode,
        geography=str(raw_payload.get("鍦板尯") or "") or None,
        units=str(raw_payload.get("鍗曚綅") or "") or None,
        waste_proxy_warning=(
            "Public food/feed composition datasets are staged as feedstock proxy metadata only; "
            "they do not represent heterogeneous waste-stream batches until reviewed mapping is approved."
        ),
        next_action=source.next_action,
    )


async def get_source_record(
    db: AsyncSession,
    *,
    source_id: str,
) -> ExternalSourceRecord | None:
    return await db.scalar(select(ExternalSourceRecord).where(ExternalSourceRecord.source_id == source_id).limit(1))


async def list_review_cards(
    db: AsyncSession,
    *,
    tenant_id: int,
    review_status: str | None = None,
) -> ExternalSourceReviewCardListResponse:
    query = select(ExternalSourceReviewCardRecord).where(ExternalSourceReviewCardRecord.tenant_id == tenant_id)
    if review_status:
        query = query.where(ExternalSourceReviewCardRecord.review_status == review_status)
    result = await db.execute(query.order_by(ExternalSourceReviewCardRecord.card_id.asc()))
    items = [serialize_review_card(card) for card in result.scalars().all()]
    return ExternalSourceReviewCardListResponse(items=items, count=len(items))


async def get_review_card_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    card_id: str,
) -> ExternalSourceReviewCardRecord | None:
    return await db.scalar(
        select(ExternalSourceReviewCardRecord)
        .where(
            ExternalSourceReviewCardRecord.tenant_id == tenant_id,
            ExternalSourceReviewCardRecord.card_id == card_id,
        )
        .limit(1)
    )


async def get_review_card(
    db: AsyncSession,
    *,
    tenant_id: int,
    card_id: str,
) -> ExternalSourceReviewCardRead | None:
    card = await get_review_card_record(db, tenant_id=tenant_id, card_id=card_id)
    if card is None:
        return None
    return serialize_review_card(card)


async def list_extraction_records(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> ExternalSourceExtractionListResponse:
    result = await db.execute(
        select(ExternalSourceExtractionRecord)
        .where(ExternalSourceExtractionRecord.tenant_id == tenant_id)
        .order_by(ExternalSourceExtractionRecord.extraction_id.asc())
    )
    items = [serialize_extraction_record(record) for record in result.scalars().all()]
    return ExternalSourceExtractionListResponse(items=items, count=len(items))


async def get_extraction_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    extraction_id: str,
) -> ExternalSourceExtractionRead | None:
    record = await db.scalar(
        select(ExternalSourceExtractionRecord)
        .where(
            ExternalSourceExtractionRecord.tenant_id == tenant_id,
            ExternalSourceExtractionRecord.extraction_id == extraction_id,
        )
        .limit(1)
    )
    if record is None:
        return None
    return serialize_extraction_record(record)


async def resolve_review_card(
    db: AsyncSession,
    *,
    tenant_id: int,
    reviewer_user_id: int,
    card_id: str,
    payload: ExternalSourceReviewCardResolveRequest,
) -> ExternalSourceReviewCardResolveResponse | None:
    card = await get_review_card_record(db, tenant_id=tenant_id, card_id=card_id)
    if card is None:
        return None
    _enforce_resolution_payload(payload)

    resolved_status = review_status_for_action(payload.review_action)
    card.review_status = resolved_status
    card.reviewer = payload.reviewer
    card.reviewer_user_id = reviewer_user_id
    card.reviewed_at = payload.reviewed_at
    card.license_status = payload.license_status
    card.allowed_use = payload.allowed_use
    card.blocked_use = payload.blocked_use
    card.next_action = payload.next_action

    extraction = await _resolve_extraction_record(db, tenant_id=tenant_id, card=card, payload=payload)
    candidate: ReviewedExternalCandidateRecord | None = None
    created_candidate = False
    if payload.review_action == "approve_for_candidate_use":
        candidate, created_candidate = await _upsert_reviewed_candidate(
            db,
            tenant_id=tenant_id,
            card=card,
            extraction=extraction,
            payload=payload,
        )

    await db.commit()
    await db.refresh(card)
    if candidate is not None:
        await db.refresh(candidate)

    return ExternalSourceReviewCardResolveResponse(
        review_card=serialize_review_card(card),
        reviewed_candidate=serialize_reviewed_candidate(candidate) if candidate is not None else None,
        created_reviewed_candidate=created_candidate,
    )


def _enforce_resolution_payload(payload: ExternalSourceReviewCardResolveRequest) -> None:
    required_text = {
        "reviewer": payload.reviewer,
        "boundary_condition": payload.boundary_condition,
        "allowed_use": payload.allowed_use,
        "blocked_use": payload.blocked_use,
    }
    missing = [field for field, value in required_text.items() if not value.strip()]
    if missing:
        raise ValueError(f"review resolution missing required fields: {', '.join(missing)}")
    if payload.license_status in {"pending_review", "blocked"} and payload.review_action == "approve_for_candidate_use":
        raise ValueError("approved candidate use requires a resolved non-blocked license status")
    if payload.candidate_type not in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES:
        raise ValueError(f"unsupported reviewed candidate type: {payload.candidate_type}")
    if payload.numeric_values_included or payload.extracted_numeric_values:
        raise ValueError("reviewed candidate resolutions cannot include numeric values")
    if payload.promotion_enabled or payload.runtime_activated or payload.validated_default_write_enabled:
        raise ValueError("review resolution cannot enable promotion, runtime activation, or validated default writes")
    _enforce_candidate_payload_guardrails(payload.candidate_payload)


def _enforce_candidate_payload_guardrails(candidate_payload: dict[str, Any]) -> None:
    blocked_keys = {
        "numeric_values_included",
        "extracted_numeric_values",
        "promotion_enabled",
        "runtime_activated",
        "validated_default_write_enabled",
    }
    enabled_keys = [
        key
        for key in blocked_keys
        if key in candidate_payload
        and (
            candidate_payload[key] is True
            or (key == "extracted_numeric_values" and bool(candidate_payload[key]))
        )
    ]
    if enabled_keys:
        raise ValueError(f"candidate payload cannot enable guarded fields: {', '.join(sorted(enabled_keys))}")


async def _resolve_extraction_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    card: ExternalSourceReviewCardRecord,
    payload: ExternalSourceReviewCardResolveRequest,
) -> ExternalSourceExtractionRecord:
    extraction_id = f"EXT-{card.card_id}"
    extraction = await db.scalar(
        select(ExternalSourceExtractionRecord)
        .where(
            ExternalSourceExtractionRecord.tenant_id == tenant_id,
            ExternalSourceExtractionRecord.extraction_id == extraction_id,
        )
        .limit(1)
    )
    if extraction is None:
        extraction = ExternalSourceExtractionRecord(
            tenant_id=tenant_id,
            extraction_id=extraction_id,
            review_card_id=card.id,
            card_id=card.card_id,
            source_id=card.source_id,
            extraction_status="review_resolved",
            extracted_metadata={},
            extracted_numeric_values={},
            numeric_values_included=False,
            boundary_metadata=card.boundary_metadata,
            human_review_required=True,
        )
        db.add(extraction)

    extraction.extraction_status = "review_resolved"
    extraction.extracted_metadata = payload.extracted_metadata or extraction.extracted_metadata or {}
    extraction.extracted_numeric_values = payload.extracted_numeric_values
    extraction.numeric_values_included = payload.numeric_values_included
    extraction.boundary_metadata = {
        **(card.boundary_metadata or {}),
        "review_boundary_condition": payload.boundary_condition,
    }
    extraction.human_review_required = payload.human_review_required
    await db.flush()
    return extraction


async def _upsert_reviewed_candidate(
    db: AsyncSession,
    *,
    tenant_id: int,
    card: ExternalSourceReviewCardRecord,
    extraction: ExternalSourceExtractionRecord,
    payload: ExternalSourceReviewCardResolveRequest,
) -> tuple[ReviewedExternalCandidateRecord, bool]:
    candidate_id = f"REC-{card.card_id}"
    candidate = await db.scalar(
        select(ReviewedExternalCandidateRecord)
        .where(
            ReviewedExternalCandidateRecord.tenant_id == tenant_id,
            ReviewedExternalCandidateRecord.candidate_id == candidate_id,
        )
        .limit(1)
    )
    source_ref = card.doi if card.doi else card.source_url
    candidate_key = payload.candidate_key or f"{payload.candidate_type}:{card.card_id}"
    candidate_payload = _build_candidate_payload(card=card, extraction=extraction, payload=payload, source_ref=source_ref)
    audit_payload = {
        "review_card_id": card.card_id,
        "reviewer_user_id": card.reviewer_user_id,
        "review_action": payload.review_action,
        "approved_for_candidate_use": True,
        "runtime_activation_required_before_use": True,
        "promotion_enabled": False,
        "runtime_activated": False,
        "validated_default_write_enabled": False,
    }
    values = {
        "tenant_id": tenant_id,
        "candidate_id": candidate_id,
        "candidate_type": payload.candidate_type,
        "candidate_key": candidate_key,
        "review_card_id": card.id,
        "extraction_id": extraction.id,
        "card_id": card.card_id,
        "source_id": card.source_id,
        "source_kind": card.evidence_source_kind,
        "source_ref": source_ref,
        "license_status": payload.license_status,
        "license_note": f"Resolved as {payload.license_status}; preserve source license and allowed-use boundaries.",
        "ingestion_mode": card.ingestion_mode,
        "review_status": APPROVED_FOR_CANDIDATE_USE,
        "reviewer": payload.reviewer,
        "reviewed_at": payload.reviewed_at,
        "boundary_condition": payload.boundary_condition,
        "allowed_use": payload.allowed_use,
        "blocked_use": payload.blocked_use,
        "candidate_payload": candidate_payload,
        "human_review_required": payload.human_review_required,
        "promotion_enabled": False,
        "runtime_activated": False,
        "validated_default_write_enabled": False,
        "activation_relation_id": None,
        "audit_payload": audit_payload,
    }
    created = candidate is None
    if candidate is None:
        candidate = ReviewedExternalCandidateRecord(**values)
        db.add(candidate)
        await db.flush()
        return candidate, created

    for key, value in values.items():
        setattr(candidate, key, value)
    await db.flush()
    return candidate, created


async def list_reviewed_candidates(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_type: str | None = None,
    candidate_domain: str | None = None,
    review_status: str | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> ReviewedExternalCandidateListResponse:
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than 0")
    query = _reviewed_candidate_query(
        tenant_id=tenant_id,
        candidate_type=candidate_type,
        candidate_domain=candidate_domain,
        review_status=review_status,
    )
    total_count = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    page_query = query.order_by(ReviewedExternalCandidateRecord.created_at.desc(), ReviewedExternalCandidateRecord.id.desc())
    if offset:
        page_query = page_query.offset(offset)
    if limit is not None:
        page_query = page_query.limit(limit)
    result = await db.execute(
        page_query
    )
    items = [serialize_reviewed_candidate(candidate) for candidate in result.scalars().all()]
    return ReviewedExternalCandidateListResponse(
        items=items,
        count=len(items),
        total_count=total_count,
        offset=offset,
        limit=limit,
        has_more=(offset + len(items)) < total_count,
        candidate_types=_candidate_type_counts(items),
        candidate_domains=_candidate_domain_counts(items),
    )


async def get_reviewed_candidate_lane_summary(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_type: str | None = None,
    candidate_domain: str | None = None,
    review_status: str | None = None,
) -> ReviewedExternalCandidateLaneSummary:
    query = _reviewed_candidate_query(
        tenant_id=tenant_id,
        candidate_type=candidate_type,
        candidate_domain=candidate_domain,
        review_status=review_status,
    )
    result = await db.execute(
        query.order_by(ReviewedExternalCandidateRecord.created_at.desc(), ReviewedExternalCandidateRecord.id.desc())
    )
    candidates = list(result.scalars().all())
    statuses: dict[str, int] = {}
    candidate_types: dict[str, int] = {}
    candidate_domains: dict[str, int] = {}
    reviewed_metadata_count = 0
    pending_runtime_activation_count = 0
    runtime_activated_count = 0
    validated_default_write_enabled_count = 0
    numeric_value_candidate_count = 0
    release_evidence_blocked_count = 0
    latest_reviewed_at = None

    for candidate in candidates:
        statuses[candidate.review_status] = statuses.get(candidate.review_status, 0) + 1
        candidate_types[candidate.candidate_type] = candidate_types.get(candidate.candidate_type, 0) + 1
        candidate_domain = reviewed_candidate_domain(candidate.candidate_type)
        candidate_domains[candidate_domain] = candidate_domains.get(candidate_domain, 0) + 1

        payload = candidate.candidate_payload if isinstance(candidate.candidate_payload, dict) else {}
        if candidate.candidate_type in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES or payload.get("candidate_family") in {
            "bsf_reviewed_metadata",
            "reviewed_metadata_candidate",
        }:
            reviewed_metadata_count += 1

        if candidate.runtime_activated:
            runtime_activated_count += 1
        else:
            pending_runtime_activation_count += 1

        if candidate.validated_default_write_enabled:
            validated_default_write_enabled_count += 1

        extracted_numeric_values = payload.get("extracted_numeric_values")
        if payload.get("numeric_values_included") is True or bool(extracted_numeric_values):
            numeric_value_candidate_count += 1

        if "release evidence" in candidate.blocked_use.lower():
            release_evidence_blocked_count += 1

        reviewed_at = _as_utc_naive(candidate.reviewed_at)
        if reviewed_at is not None and (latest_reviewed_at is None or reviewed_at > latest_reviewed_at):
            latest_reviewed_at = reviewed_at

    return ReviewedExternalCandidateLaneSummary(
        tenant_id=tenant_id,
        reviewed_candidate_count=len(candidates),
        reviewed_metadata_candidate_count=reviewed_metadata_count,
        pending_runtime_activation_count=pending_runtime_activation_count,
        runtime_activated_count=runtime_activated_count,
        validated_default_write_enabled_count=validated_default_write_enabled_count,
        numeric_value_candidate_count=numeric_value_candidate_count,
        release_evidence_blocked_count=release_evidence_blocked_count,
        statuses=statuses,
        candidate_types=candidate_types,
        candidate_domains=candidate_domains,
        latest_reviewed_at=latest_reviewed_at,
    )


async def get_reviewed_candidate_knowledge_base(
    db: AsyncSession,
    *,
    tenant_id: int,
) -> ReviewedExternalCandidateKnowledgeBaseResponse:
    readiness = await get_external_source_schema_readiness(db)
    summary = await get_reviewed_candidate_lane_summary(db, tenant_id=tenant_id)
    blockers = list(readiness.blockers)
    if summary.runtime_activated_count:
        blockers.append("runtime activated candidates are outside reviewed candidate KB read-only scope")
    if summary.validated_default_write_enabled_count:
        blockers.append("validated default write-enabled candidates violate reviewed candidate KB guardrails")
    if summary.numeric_value_candidate_count:
        blockers.append("numeric value candidates violate reviewed candidate KB metadata-only guardrails")

    status = "ready_for_review" if not blockers and readiness.schema_ready and readiness.phase4a_domain_metadata_ready else "blocked"
    return ReviewedExternalCandidateKnowledgeBaseResponse(
        tenant_id=tenant_id,
        status=status,
        schema_ready=readiness.schema_ready,
        source_catalog_ready=readiness.source_catalog_ready,
        reviewed_metadata_lane_ready=readiness.reviewed_metadata_lane_ready,
        knowledge_coverage_ready=readiness.knowledge_coverage_ready,
        knowledge_coverage_percent=readiness.knowledge_coverage_percent,
        source_metadata_coverage_percent=readiness.source_metadata_coverage_percent,
        knowledge_coverage_domains=readiness.knowledge_coverage_domains,
        business_knowledge_coverage_percent=readiness.business_knowledge_coverage_percent,
        business_knowledge_coverage_groups=readiness.business_knowledge_coverage_groups,
        supported_candidate_types=sorted(METADATA_ONLY_REVIEWED_CANDIDATE_TYPES),
        supported_candidate_domains=sorted(REVIEWED_CANDIDATE_DOMAINS),
        phase4a_domain_metadata_ready=readiness.phase4a_domain_metadata_ready,
        phase4a_domain_candidate_counts=readiness.phase4a_domain_candidate_counts,
        phase4a_domain_expected_counts=readiness.phase4a_domain_expected_counts,
        phase4a_domain_missing_counts=readiness.phase4a_domain_missing_counts,
        reviewed_candidate_count=summary.reviewed_candidate_count,
        reviewed_metadata_candidate_count=summary.reviewed_metadata_candidate_count,
        pending_runtime_activation_count=summary.pending_runtime_activation_count,
        runtime_activated_count=summary.runtime_activated_count,
        validated_default_write_enabled_count=summary.validated_default_write_enabled_count,
        numeric_value_candidate_count=summary.numeric_value_candidate_count,
        candidate_types=summary.candidate_types,
        candidate_domains=summary.candidate_domains,
        blockers=blockers,
    )


async def get_business_knowledge_review_packet(
    db: AsyncSession,
    *,
    tenant_id: int,
    item_key: str,
) -> BusinessKnowledgeReviewPacketResponse | None:
    readiness = await get_external_source_schema_readiness(db)
    match = _find_business_knowledge_item(readiness.business_knowledge_coverage_groups, item_key=item_key)
    if match is None:
        return None

    group_key, item = match
    if item.review_workflow is None:
        return None

    candidate = {candidate.key: candidate for candidate in list_external_factor_candidates()}.get(item.item_key)
    candidate_payload = candidate.to_payload() if candidate is not None else {}
    source_trace = {
        "item_key": item.item_key,
        "group_key": group_key,
        "review_packet_id": item.review_workflow.review_packet_id,
        "review_state": item.review_workflow.review_state,
        "source_packet_persistence": item.review_workflow.source_packet_persistence,
        "coverage_basis": item.coverage_basis,
        "candidate_type": candidate.candidate_type if candidate is not None else "business_knowledge_candidate",
        "source_kind": candidate.source_kind if candidate is not None else None,
        "source_ref": candidate.source_ref if candidate is not None else None,
        "license_note": candidate.license_note if candidate is not None else None,
        "human_review_required": candidate.human_review_required if candidate is not None else True,
        "runtime_activation_required_before_use": True,
        "release_evidence_allowed": False,
        "numeric_values_included": False,
    }
    return BusinessKnowledgeReviewPacketResponse(
        tenant_id=tenant_id,
        group_key=group_key,
        item=item,
        review_workflow=item.review_workflow,
        candidate_payload=candidate_payload,
        source_trace=source_trace,
    )


async def get_business_knowledge_review_packet_export(
    db: AsyncSession,
    *,
    tenant_id: int,
    item_key: str,
) -> BusinessKnowledgeReviewPacketExportResponse | None:
    packet = await get_business_knowledge_review_packet(db, tenant_id=tenant_id, item_key=item_key)
    if packet is None:
        return None

    packet_payload = packet.model_dump(mode="json")
    canonical_payload = json.dumps(packet_payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    export_filename = f"{packet.review_workflow.review_packet_id}.json"
    export_manifest = {
        "export_id": f"business-knowledge-review-packet-export:{packet.item.item_key}:{content_hash[:12]}",
        "item_key": packet.item.item_key,
        "group_key": packet.group_key,
        "review_packet_id": packet.review_workflow.review_packet_id,
        "review_state": packet.review_workflow.review_state,
        "source_packet_persistence": packet.review_workflow.source_packet_persistence,
        "content_hash_algorithm": "sha256",
        "content_hash": content_hash,
        "export_policy": "response_only_no_file_write",
    }
    return BusinessKnowledgeReviewPacketExportResponse(
        tenant_id=tenant_id,
        export_filename=export_filename,
        content_hash=content_hash,
        export_manifest=export_manifest,
        review_packet=packet,
    )


async def get_reviewed_candidate_review_packet(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateReviewPacketResponse | None:
    candidate = await _get_reviewed_candidate_record(db, tenant_id=tenant_id, candidate_id=candidate_id)
    if candidate is None:
        return None

    card = await get_review_card_record(db, tenant_id=tenant_id, card_id=candidate.card_id)
    if card is None:
        return None

    extraction: ExternalSourceExtractionRecord | None = None
    if candidate.extraction_id is not None:
        extraction = await db.scalar(
            select(ExternalSourceExtractionRecord)
            .where(
                ExternalSourceExtractionRecord.tenant_id == tenant_id,
                ExternalSourceExtractionRecord.id == candidate.extraction_id,
            )
            .limit(1)
        )
    if extraction is None:
        extraction = await db.scalar(
            select(ExternalSourceExtractionRecord)
            .where(
                ExternalSourceExtractionRecord.tenant_id == tenant_id,
                ExternalSourceExtractionRecord.card_id == candidate.card_id,
            )
            .limit(1)
        )

    source_trace = {
        "candidate_id": candidate.candidate_id,
        "candidate_type": candidate.candidate_type,
        "candidate_domain": reviewed_candidate_domain(candidate.candidate_type),
        "candidate_key": candidate.candidate_key,
        "card_id": card.card_id,
        "source_id": candidate.source_id,
        "source_kind": candidate.source_kind,
        "source_ref": candidate.source_ref,
        "license_status": candidate.license_status,
        "ingestion_mode": candidate.ingestion_mode,
        "review_status": candidate.review_status,
        "human_review_required": candidate.human_review_required,
        "runtime_activation_required_before_use": True,
    }

    return ReviewedExternalCandidateReviewPacketResponse(
        tenant_id=tenant_id,
        candidate=serialize_reviewed_candidate(candidate),
        review_card=serialize_review_card(card),
        extraction=serialize_extraction_record(extraction) if extraction is not None else None,
        source_trace=source_trace,
    )


async def get_reviewed_candidate_review_packet_export(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateReviewPacketExportResponse | None:
    packet = await get_reviewed_candidate_review_packet(db, tenant_id=tenant_id, candidate_id=candidate_id)
    if packet is None:
        return None

    packet_payload = packet.model_dump(mode="json")
    canonical_payload = json.dumps(packet_payload, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    export_filename = f"{packet.candidate.candidate_id}-review-packet.json"
    export_manifest = {
        "export_id": f"review-packet-export:{packet.candidate.candidate_id}:{content_hash[:12]}",
        "candidate_id": packet.candidate.candidate_id,
        "candidate_type": packet.candidate.candidate_type,
        "candidate_domain": packet.candidate.candidate_domain,
        "card_id": packet.review_card.card_id,
        "extraction_id": packet.extraction.extraction_id if packet.extraction is not None else None,
        "review_status": packet.candidate.review_status,
        "content_hash_algorithm": "sha256",
        "content_hash": content_hash,
        "export_policy": "response_only_no_file_write",
    }
    return ReviewedExternalCandidateReviewPacketExportResponse(
        tenant_id=tenant_id,
        export_filename=export_filename,
        content_hash=content_hash,
        export_manifest=export_manifest,
        review_packet=packet,
    )


async def get_reviewed_candidate_activation_preview(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateActivationPreviewResponse | None:
    candidate = await _get_reviewed_candidate_record(db, tenant_id=tenant_id, candidate_id=candidate_id)
    if candidate is None:
        return None

    scope_key = activation_scope_key(
        tenant_id=tenant_id,
        candidate_type=candidate.candidate_type,
        candidate_key=candidate.candidate_key,
    )
    activation_scope = {
        "tenant_id": tenant_id,
        "tenant_scoped": True,
        "candidate_id": candidate.candidate_id,
        "candidate_type": candidate.candidate_type,
        "candidate_domain": reviewed_candidate_domain(candidate.candidate_type),
        "candidate_key": candidate.candidate_key,
        "scope_key": scope_key,
        "runtime_paths": default_activation_runtime_paths(candidate.candidate_type),
        "source_lineage": {
            "source_id": candidate.source_id,
            "source_kind": candidate.source_kind,
            "source_ref": candidate.source_ref,
            "reviewer": candidate.reviewer,
            "reviewed_at": candidate.reviewed_at.isoformat(),
            "review_status": candidate.review_status,
        },
    }
    active_overlay_state = await resolve_active_runtime_activation(db, tenant_id=tenant_id, scope_key=scope_key)
    activation_audit_contract = {
        "activation_audit_id_required": True,
        "activation_execution_endpoint_enabled": False,
        "required_fields": [
            "candidate_id",
            "tenant_id",
            "source_id",
            "candidate_type",
            "candidate_key",
            "reviewer",
            "reviewed_at",
            "operator_attestation",
            "rollback_plan",
            "idempotency_key",
        ],
        "candidate_guardrails": {
            "promotion_enabled": False,
            "runtime_activated": False,
            "validated_default_write_enabled": False,
            "numeric_values_included": False,
        },
        "release_evidence_allowed": False,
        "final_action_execution_allowed": False,
    }
    return ReviewedExternalCandidateActivationPreviewResponse(
        tenant_id=tenant_id,
        candidate=serialize_reviewed_candidate(candidate),
        activation_scope=activation_scope,
        active_overlay_state=active_overlay_state,
        activation_audit_contract=activation_audit_contract,
    )


async def get_reviewed_candidate_runtime_readiness(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateRuntimeReadinessResponse | None:
    candidate = await _get_reviewed_candidate_record(db, tenant_id=tenant_id, candidate_id=candidate_id)
    if candidate is None:
        return None

    scope_key = activation_scope_key(
        tenant_id=tenant_id,
        candidate_type=candidate.candidate_type,
        candidate_key=candidate.candidate_key,
    )
    activation_scope = {
        "tenant_id": tenant_id,
        "tenant_scoped": True,
        "candidate_id": candidate.candidate_id,
        "candidate_type": candidate.candidate_type,
        "candidate_domain": reviewed_candidate_domain(candidate.candidate_type),
        "candidate_key": candidate.candidate_key,
        "scope_key": scope_key,
        "runtime_paths": default_activation_runtime_paths(candidate.candidate_type),
    }
    active_overlay_state = await resolve_active_runtime_activation(db, tenant_id=tenant_id, scope_key=scope_key)
    active_candidate_payload = await get_active_external_candidate_payload(
        db,
        tenant_id=tenant_id,
        candidate_type=candidate.candidate_type,
        candidate_key=candidate.candidate_key,
    )
    rollback_contract = {
        "rollback_required": True,
        "rollback_execution_endpoint_enabled": False,
        "rollback_target_required": active_overlay_state.get("active_activation_id") is not None,
        "active_activation_id": active_overlay_state.get("active_activation_id"),
        "active_registry_patch_id": active_overlay_state.get("active_registry_patch_id"),
        "required_fields": [
            "tenant_id",
            "candidate_id",
            "scope_key",
            "active_activation_id",
            "rollback_reason",
            "operator_attestation",
            "idempotency_key",
        ],
    }
    return ReviewedExternalCandidateRuntimeReadinessResponse(
        tenant_id=tenant_id,
        candidate=serialize_reviewed_candidate(candidate),
        activation_scope=activation_scope,
        active_overlay_state=active_overlay_state,
        active_candidate_payload=active_candidate_payload,
        rollback_contract=rollback_contract,
    )


async def get_reviewed_candidate_rollback_preview(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateRollbackPreviewResponse | None:
    readiness = await get_reviewed_candidate_runtime_readiness(
        db,
        tenant_id=tenant_id,
        candidate_id=candidate_id,
    )
    if readiness is None:
        return None

    active_activation_id = readiness.active_overlay_state.get("active_activation_id")
    rollback_target_available = active_activation_id is not None
    rollback_blockers = [] if rollback_target_available else ["no_active_runtime_activation_to_rollback"]
    rollback_audit_packet = {
        "tenant_id": tenant_id,
        "candidate_id": readiness.candidate.candidate_id,
        "candidate_type": readiness.candidate.candidate_type,
        "candidate_key": readiness.candidate.candidate_key,
        "scope_key": readiness.activation_scope.get("scope_key"),
        "active_activation_id": active_activation_id,
        "active_registry_patch_id": readiness.active_overlay_state.get("active_registry_patch_id"),
        "active_registry_version": readiness.active_overlay_state.get("active_registry_version"),
        "rollback_target_available": rollback_target_available,
        "rollback_execution_endpoint_enabled": False,
        "required_attestations": [
            "operator_attestation",
            "rollback_reason",
            "idempotency_key",
            "post_rollback_verification_plan",
        ],
        "blocked_until": rollback_blockers,
    }
    return ReviewedExternalCandidateRollbackPreviewResponse(
        tenant_id=tenant_id,
        candidate=readiness.candidate,
        activation_scope=readiness.activation_scope,
        active_overlay_state=readiness.active_overlay_state,
        rollback_contract=readiness.rollback_contract,
        rollback_audit_packet=rollback_audit_packet,
        rollback_target_available=rollback_target_available,
        rollback_blockers=rollback_blockers,
    )


def _reviewed_candidate_query(
    *,
    tenant_id: int,
    candidate_type: str | None = None,
    candidate_domain: str | None = None,
    review_status: str | None = None,
):
    if candidate_type is not None and candidate_type not in METADATA_ONLY_REVIEWED_CANDIDATE_TYPES:
        raise ValueError(f"unsupported reviewed candidate type: {candidate_type}")
    domain_candidate_types: set[str] | None = None
    if candidate_domain is not None:
        if candidate_domain not in REVIEWED_CANDIDATE_DOMAINS:
            raise ValueError(f"unsupported reviewed candidate domain: {candidate_domain}")
        domain_candidate_types = reviewed_candidate_types_for_domain(candidate_domain)
    if candidate_type is not None and domain_candidate_types is not None and candidate_type not in domain_candidate_types:
        raise ValueError(f"candidate_type {candidate_type} does not belong to candidate_domain {candidate_domain}")

    query = select(ReviewedExternalCandidateRecord).where(ReviewedExternalCandidateRecord.tenant_id == tenant_id)
    if candidate_type is not None:
        query = query.where(ReviewedExternalCandidateRecord.candidate_type == candidate_type)
    elif domain_candidate_types is not None:
        query = query.where(ReviewedExternalCandidateRecord.candidate_type.in_(sorted(domain_candidate_types)))
    if review_status is not None:
        query = query.where(ReviewedExternalCandidateRecord.review_status == review_status)
    return query


async def get_reviewed_candidate(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateRead | None:
    candidate = await _get_reviewed_candidate_record(db, tenant_id=tenant_id, candidate_id=candidate_id)
    if candidate is None:
        return None
    return serialize_reviewed_candidate(candidate)


async def _get_reviewed_candidate_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> ReviewedExternalCandidateRecord | None:
    return await db.scalar(
        select(ReviewedExternalCandidateRecord)
        .where(
            ReviewedExternalCandidateRecord.tenant_id == tenant_id,
            ReviewedExternalCandidateRecord.candidate_id == candidate_id,
        )
        .limit(1)
    )


async def _get_literature_extraction_candidate_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    candidate_id: str,
) -> LiteratureExtractionCandidateRecord | None:
    return await db.scalar(
        select(LiteratureExtractionCandidateRecord)
        .where(
            LiteratureExtractionCandidateRecord.tenant_id == tenant_id,
            LiteratureExtractionCandidateRecord.candidate_id == candidate_id,
        )
        .limit(1)
    )


def serialize_review_card(card: ExternalSourceReviewCardRecord) -> ExternalSourceReviewCardRead:
    return ExternalSourceReviewCardRead.model_validate(card)


def serialize_extraction_record(record: ExternalSourceExtractionRecord) -> ExternalSourceExtractionRead:
    return ExternalSourceExtractionRead.model_validate(record)


def serialize_literature_extraction_candidate(
    record: LiteratureExtractionCandidateRecord,
) -> LiteratureExtractionCandidateRead:
    return LiteratureExtractionCandidateRead(
        candidate_uid=f"literature_extraction_candidate:{record.candidate_id}",
        candidate_id=record.candidate_id,
        source_id=record.source_id,
        doi=record.doi,
        source_ref=record.source_ref,
        title=record.title,
        species=record.species,
        feedstock=record.feedstock,
        treatment=record.treatment,
        metric_key=record.metric_key,
        metric_label=record.metric_label,
        raw_value=record.raw_value,
        unit=record.unit,
        condition_context=record.condition_context,
        experiment_context=record.experiment_context,
        table_or_section_ref=record.table_or_section_ref,
        extraction_note=record.extraction_note,
        license_note=record.license_note,
        source_kind=record.source_kind,  # type: ignore[arg-type]
        review_status="pending_review",
        human_review_required=record.human_review_required,
        numeric_values_included=record.numeric_values_included,
        release_evidence_allowed=record.release_evidence_allowed,
        runtime_activation_enabled=record.runtime_activation_enabled,
        validated_default_write_enabled=record.validated_default_write_enabled,
        promotion_enabled=record.promotion_enabled,
        guardrails=list(record.guardrails or []),
    )


def serialize_reviewed_candidate(candidate: ReviewedExternalCandidateRecord) -> ReviewedExternalCandidateRead:
    return ReviewedExternalCandidateRead.model_validate(candidate)


def _candidate_type_counts(items: list[ReviewedExternalCandidateRead]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.candidate_type] = counts.get(item.candidate_type, 0) + 1
    return counts


def _candidate_domain_counts(items: list[ReviewedExternalCandidateRead]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.candidate_domain] = counts.get(item.candidate_domain, 0) + 1
    return counts


def _build_candidate_payload(
    *,
    card: ExternalSourceReviewCardRecord,
    extraction: ExternalSourceExtractionRecord,
    payload: ExternalSourceReviewCardResolveRequest,
    source_ref: str,
) -> dict[str, Any]:
    if payload.candidate_type == "bsf_reviewed_metadata_candidate":
        boundary_metadata = extraction.boundary_metadata if isinstance(extraction.boundary_metadata, dict) else {}
        candidate_payload = BsfReviewedMetadataCandidatePayload(
            card_id=card.card_id,
            shortlist_id=card.shortlist_id,
            source_catalog_id=card.source_id,
            doi=card.doi,
            source_url=card.source_url,
            title=card.title,
            article_type=str(boundary_metadata.get("article_type") or "reviewed_metadata_source"),
            target_boundary_fields=str(boundary_metadata.get("target_boundary_fields") or payload.boundary_condition),
            boundary_condition=payload.boundary_condition,
            allowed_use=payload.allowed_use,
            blocked_use=payload.blocked_use,
            evidence_source_kind=card.evidence_source_kind,  # type: ignore[arg-type]
            ingestion_mode=card.ingestion_mode,  # type: ignore[arg-type]
            license_status=payload.license_status,
            source_kind=card.evidence_source_kind,  # type: ignore[arg-type]
            source_ref=source_ref,
            numeric_values_included=False,
            extracted_numeric_values={},
            promotion_enabled=False,
            runtime_activated=False,
            validated_default_write_enabled=False,
            reviewer_annotations=payload.candidate_payload,
        )
        return candidate_payload.model_dump(mode="json")

    candidate_payload = ReviewedMetadataCandidatePayload(
        candidate_type=payload.candidate_type,
        candidate_type_group=reviewed_candidate_type_group(payload.candidate_type),  # type: ignore[arg-type]
        candidate_domain=reviewed_candidate_domain(payload.candidate_type),
        card_id=card.card_id,
        shortlist_id=card.shortlist_id,
        source_catalog_id=card.source_id,
        doi=card.doi,
        source_url=card.source_url,
        title=card.title,
        boundary_condition=payload.boundary_condition,
        allowed_use=payload.allowed_use,
        blocked_use=payload.blocked_use,
        evidence_source_kind=card.evidence_source_kind,  # type: ignore[arg-type]
        ingestion_mode=card.ingestion_mode,  # type: ignore[arg-type]
        license_status=payload.license_status,
        source_kind=card.evidence_source_kind,  # type: ignore[arg-type]
        source_ref=source_ref,
        boundary_metadata=extraction.boundary_metadata if isinstance(extraction.boundary_metadata, dict) else {},
        extracted_metadata=extraction.extracted_metadata if isinstance(extraction.extracted_metadata, dict) else {},
        numeric_values_included=False,
        extracted_numeric_values={},
        promotion_enabled=False,
        runtime_activated=False,
        validated_default_write_enabled=False,
        reviewer_annotations=payload.candidate_payload,
    )
    return candidate_payload.model_dump(mode="json")


async def _count_review_cards(db: AsyncSession, *, tenant_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(ExternalSourceReviewCardRecord)
            .where(ExternalSourceReviewCardRecord.tenant_id == tenant_id)
        )
        or 0
    )


async def _count_extractions(db: AsyncSession, *, tenant_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(ExternalSourceExtractionRecord)
            .where(ExternalSourceExtractionRecord.tenant_id == tenant_id)
        )
        or 0
    )


async def _count_reviewed_candidates(db: AsyncSession, *, tenant_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(ReviewedExternalCandidateRecord)
            .where(ReviewedExternalCandidateRecord.tenant_id == tenant_id)
        )
        or 0
    )
