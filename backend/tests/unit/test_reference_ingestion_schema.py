from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.reference_ingestion import (
    ReferenceIngestionHealthResponse,
    ReferenceIngestionStagedItem,
    ReferenceParserMetadata,
)


def test_reference_ingestion_staged_item_requires_bos_fields():
    metadata = ReferenceParserMetadata(
        parser_name="mineru",
        execution_mode="fallback_simple_pdf_text",
        parsed_at=datetime.now(UTC),
        extracted_field_count=5,
    )

    item = ReferenceIngestionStagedItem(
        id="refing_test",
        tenant_id=1,
        source_title="Core relay manuscript",
        source_anchor="Methods 2.2 + Results",
        source_type="pdf",
        species_chain=["MW", "PB"],
        feedstocks=["distillers_grains"],
        evidence_level="manuscript_core",
        campaign_type="core_validation",
        summary="Core validation on distillers grains.",
        key_parameters={"ser": 0.68},
        observed_outputs={"best_single_stage_ser": 0.53},
        references=["Parsed source: Core relay manuscript"],
        parser_metadata=metadata,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert item.species_chain == ["MW", "PB"]
    assert item.feedstocks == ["distillers_grains"]
    assert item.parser_metadata.extracted_field_count == 5
    assert item.ingestion_mode == "manual_review_first"
    assert item.human_review_required is True


def test_reference_ingestion_staged_item_accepts_external_source_metadata():
    metadata = ReferenceParserMetadata(
        parser_name="mineru",
        execution_mode="fallback_simple_pdf_text",
        parsed_at=datetime.now(UTC),
        extracted_field_count=5,
    )

    item = ReferenceIngestionStagedItem(
        id="refing_external",
        tenant_id=1,
        source_title="EPA WARM food waste factors",
        source_anchor="EPA WARM documentation",
        source_type="pdf",
        source_owner="US EPA",
        license_note="US government source; cite EPA and review regional fit.",
        region="US",
        units={"emission_factor": "kgCO2e/short ton"},
        ingestion_mode="auto_ingest_allowed",
        human_review_required=True,
        species_chain=["BSF"],
        feedstocks=["washed_kitchen_waste"],
        evidence_level="official_standard",
        campaign_type="lca_factor_reference",
        summary="Food waste baseline factors for LCA comparisons.",
        parser_metadata=metadata,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert item.source_owner == "US EPA"
    assert item.license_note.startswith("US government")
    assert item.region == "US"
    assert item.units["emission_factor"] == "kgCO2e/short ton"
    assert item.ingestion_mode == "auto_ingest_allowed"


def test_reference_ingestion_staged_item_rejects_missing_source_anchor():
    metadata = ReferenceParserMetadata(
        parser_name="mineru",
        execution_mode="fallback_simple_pdf_text",
        parsed_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        ReferenceIngestionStagedItem(
            id="refing_test",
            tenant_id=1,
            source_title="Core relay manuscript",
            source_type="pdf",
            species_chain=["MW"],
            feedstocks=["distillers_grains"],
            evidence_level="manuscript_core",
            campaign_type="core_validation",
            summary="Core validation on distillers grains.",
            key_parameters={},
            observed_outputs={},
            references=[],
            parser_metadata=metadata,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def test_reference_ingestion_health_schema_exposes_rollback_state():
    health = ReferenceIngestionHealthResponse(
        parser_name="mineru",
        parser_command="mineru",
        parser_extra_args="-b pipeline -m txt",
        parser_available=False,
        promotion_enabled=False,
        storage_root="C:/tmp/reference-ingestion",
        staged_count=2,
        promoted_count=0,
        rollback_mode="staging_only",
    )

    assert health.rollback_mode == "staging_only"
    assert health.promotion_enabled is False
