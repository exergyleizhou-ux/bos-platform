from pathlib import Path

import pytest

from app.services.mineru_parser_service import MinerUParserService
from app.services.reference_ingestion_service import ReferenceIngestionService


VALIDATION_DIR = Path("backend/generated/reference-ingestion/validation-pdfs")


@pytest.mark.skipif(
    not (VALIDATION_DIR / "tenebrio-molitor-distillers-grains-real.pdf").exists()
    or not (VALIDATION_DIR / "hermetia-illucens-sewage-sludge-real.pdf").exists(),
    reason="real validation PDFs are not available",
)
def test_real_pdf_fallback_staging_and_promotion(tmp_path):
    service = ReferenceIngestionService(
        storage_root=tmp_path,
        parser_service=MinerUParserService(command="mineru-not-installed-for-fallback-smoke"),
    )

    pdfs = [
        VALIDATION_DIR / "tenebrio-molitor-distillers-grains-real.pdf",
        VALIDATION_DIR / "hermetia-illucens-sewage-sludge-real.pdf",
    ]
    items = [
        service.parse_document(
            tenant_id=1,
            filename=pdf.name,
            content=pdf.read_bytes(),
            source_title=pdf.stem,
            source_type="pdf",
        )
        for pdf in pdfs
    ]

    assert len(items) == 2
    assert all(item.parser_metadata.extracted_field_count >= 5 for item in items)
    assert all(item.species_chain for item in items)
    assert all(item.feedstocks for item in items)
    assert {item.parser_metadata.execution_mode for item in items} == {"fallback_pypdf_text"}

    promoted = service.promote_to_campaign(
        tenant_id=1,
        item_id=items[0].id,
        notes="real-pdf-smoke",
    )

    assert promoted is not None
    staged, campaign = promoted
    assert staged.status == "promoted"
    assert campaign.species_chain
    assert campaign.feedstocks
    assert campaign.key.startswith("staged_")

