import pytest
from pydantic import ValidationError

from app.schemas.evidence import EvidenceItemCreate, SimulationEvidenceSource


EXTERNAL_SOURCE_KINDS = [
    "official_standard",
    "peer_reviewed_literature",
    "public_dataset",
    "industry_reference",
    "commercial_database",
    "model_provider_docs",
    "github_reference",
]


@pytest.mark.parametrize("source_kind", EXTERNAL_SOURCE_KINDS)
def test_evidence_schema_accepts_external_source_kinds(source_kind: str):
    item = EvidenceItemCreate(
        kind="external_source_metadata",
        source_kind=source_kind,
        source_ref="BOS_EXTERNAL_KNOWLEDGE_AND_DATA_MATRIX.md",
        payload={
            "external_source_kind": source_kind,
            "license_note": "checked in source matrix",
            "human_review_required": True,
        },
        uncertainty_level="medium",
    )

    assert item.source_kind == source_kind
    assert item.payload["external_source_kind"] == source_kind


def test_simulation_evidence_source_accepts_official_standard():
    source = SimulationEvidenceSource(
        field="release_gate.threshold_rule",
        source_kind="official_standard",
        source_ref="standard-index",
        confidence=0.9,
        notes="Threshold value still requires human review before release use.",
    )

    assert source.source_kind == "official_standard"


def test_evidence_schema_rejects_unknown_source_kind():
    with pytest.raises(ValidationError):
        EvidenceItemCreate(
            kind="external_source_metadata",
            source_kind="unreviewed_blog",
            source_ref="example",
        )
