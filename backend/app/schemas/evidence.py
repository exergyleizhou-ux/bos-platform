"""Evidence kernel schemas for BOS decision traceability."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceSourceKind = Literal[
    "operator_input",
    "imported_reference",
    "manuscript_campaign",
    "staged_reference",
    "promoted_campaign",
    "synthetic",
    "deterministic_model",
    "chronos_model",
    "fallback_default",
    "assumed",
    "official_standard",
    "peer_reviewed_literature",
    "public_dataset",
    "industry_reference",
    "commercial_database",
    "model_provider_docs",
    "github_reference",
]
UncertaintyLevel = Literal["low", "medium", "high"]


class SimulationEvidenceSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: str
    source_kind: EvidenceSourceKind
    source_ref: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    fallback_used: bool = False
    notes: str | None = None


class EvidenceItemCreate(BaseModel):
    kind: str
    source_kind: EvidenceSourceKind
    source_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    uncertainty_level: UncertaintyLevel = "low"


class EvidencePackCreate(BaseModel):
    subject_type: str
    subject_id: str
    title: str
    summary: str | None = None
    verification_status: str = "created"
    human_review_required: bool = False
    items: list[EvidenceItemCreate] = Field(default_factory=list)


class EvidenceItemResponse(EvidenceItemCreate):
    evidence_item_id: str
    evidence_pack_id: str
    tenant_id: int
    created_at: datetime


class EvidencePackResponse(BaseModel):
    evidence_pack_id: str
    tenant_id: int
    user_id: int
    subject_type: str
    subject_id: str
    title: str
    summary: str | None
    verification_status: str
    human_review_required: bool
    created_at: datetime
    items: list[EvidenceItemResponse] = Field(default_factory=list)


class InputSnapshotResponse(BaseModel):
    input_snapshot_id: str
    tenant_id: int
    subject_type: str
    subject_id: str
    payload: dict[str, Any]
    payload_hash: str
    created_at: datetime
