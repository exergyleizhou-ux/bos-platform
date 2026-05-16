"""Minimal ESG/LCA/TEA kernel schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LCACompareRequest(BaseModel):
    functional_unit: str = Field(..., min_length=1)
    system_boundary: dict[str, Any]
    baseline_scenario: dict[str, Any]
    alternative_scenario: dict[str, Any]
    activity_data: dict[str, Any] = Field(default_factory=dict)
    emission_factors: dict[str, float] = Field(default_factory=dict)


class TEAEstimateRequest(BaseModel):
    functional_unit: str = Field(..., min_length=1)
    system_boundary: dict[str, Any] = Field(default_factory=dict)
    baseline_scenario: dict[str, Any]
    alternative_scenario: dict[str, Any]
    activity_data: dict[str, Any] = Field(default_factory=dict)
    cost_factors: dict[str, float] = Field(default_factory=dict)


class SustainabilityResultResponse(BaseModel):
    result_id: str
    tenant_id: int
    user_id: int
    result_type: Literal["lca", "tea"]
    functional_unit: str
    system_boundary: dict[str, Any]
    baseline_scenario: dict[str, Any] | None = None
    alternative_scenario: dict[str, Any] | None = None
    activity_data: dict[str, Any] | None = None
    emission_factors: dict[str, Any] | None = None
    cost_factors: dict[str, Any] | None = None
    result: dict[str, Any]
    uncertainty_warnings: list[str] = Field(default_factory=list)
    factor_sources: dict[str, Any] = Field(default_factory=dict)
    review_gate: dict[str, Any] = Field(default_factory=dict)
    evidence_pack_id: str | None = None
    created_at: datetime
