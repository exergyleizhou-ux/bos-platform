"""Compliance and product quality gate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ProductCategory = Literal[
    "insect_dry_matter",
    "insect_oil",
    "frass_organic_fertilizer",
    "residue_handling",
]


class BatchAssayCreate(BaseModel):
    assay_type: str
    value: float | None = None
    unit: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class BatchAssayResponse(BaseModel):
    assay_id: str
    batch_id: int
    tenant_id: int
    user_id: int
    assay_type: str
    value: float | None = None
    unit: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class ComplianceEvaluateRequest(BaseModel):
    batch_id: int
    jurisdiction: str = Field(..., min_length=1)
    product_category: ProductCategory


class ComplianceRulesResponse(BaseModel):
    rules: dict[str, list[str]]


class ReleaseGateResponse(BaseModel):
    gate_id: str
    batch_id: int
    tenant_id: int
    user_id: int
    jurisdiction: str
    product_category: str
    status: Literal["ready_for_review", "blocked", "insufficient_evidence"]
    missing_assays: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    human_review_required: bool
    evidence_pack_id: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime
