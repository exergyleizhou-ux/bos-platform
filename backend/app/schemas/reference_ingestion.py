"""
Staged document ingestion schemas for BOS references.

Phase 1 keeps parsed documents in staging until an operator explicitly
promotes a candidate into a campaign-compatible shape.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReferenceIngestionMode = Literal["manual_review_first", "auto_ingest_allowed", "metadata_only", "reference_only"]


class ReferenceParserMetadata(BaseModel):
    parser_name: str = Field(..., min_length=1)
    parser_version: str | None = None
    execution_mode: str = Field(..., min_length=1)
    raw_markdown_path: str | None = None
    raw_json_path: str | None = None
    source_file_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
    extracted_field_count: int = Field(default=0, ge=0)
    parsed_at: datetime


class ReferenceIngestionStagedItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: int
    source_title: str
    source_anchor: str
    source_type: str = "pdf"
    source_owner: str | None = None
    license_note: str | None = None
    region: str | None = None
    units: dict[str, str] = Field(default_factory=dict)
    ingestion_mode: ReferenceIngestionMode = "manual_review_first"
    human_review_required: bool = True
    species_chain: list[str] = Field(default_factory=list)
    feedstocks: list[str] = Field(default_factory=list)
    evidence_level: str
    campaign_type: str
    summary: str
    key_parameters: dict[str, Any] = Field(default_factory=dict)
    observed_outputs: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
    parser_metadata: ReferenceParserMetadata
    status: Literal["staged", "promoted", "failed"] = "staged"
    promoted_campaign_key: str | None = None
    created_at: datetime
    updated_at: datetime


class ReferenceIngestionListResponse(BaseModel):
    items: list[ReferenceIngestionStagedItem]
    count: int


class ReferenceIngestionHealthResponse(BaseModel):
    parser_name: str
    parser_command: str
    parser_extra_args: str
    parser_available: bool
    promotion_enabled: bool
    storage_root: str
    staged_count: int
    promoted_count: int
    rollback_mode: str


class ReferenceIngestionPromoteRequest(BaseModel):
    target_type: Literal["campaign"] = "campaign"
    notes: str | None = None


class ReferenceIngestionCampaignCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    title: str
    species_chain: list[str]
    feedstocks: list[str]
    campaign_type: str
    evidence_level: str
    summary: str
    key_parameters: dict[str, Any] = Field(default_factory=dict)
    observed_outputs: dict[str, Any] = Field(default_factory=dict)
    source_anchor: str
    references: list[str] = Field(default_factory=list)
    staging_meta: dict[str, Any] = Field(default_factory=dict)


class ReferenceIngestionPromoteResponse(BaseModel):
    staged_item: ReferenceIngestionStagedItem
    campaign: ReferenceIngestionCampaignCandidate
