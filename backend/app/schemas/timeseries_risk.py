"""Schemas for BOS model-backed time-series risk outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.bos import DEFAULT_BOS_VERSION


class ConfidenceBand(BaseModel):
    """Compact confidence envelope for the model-backed forecast."""

    lower: float
    upper: float


class TimeseriesRiskResponse(BaseModel):
    """BOS-native risk response consumed by assistant, release, and forecast surfaces."""

    version: str = DEFAULT_BOS_VERSION
    batch_id: int
    batch_label: str
    future_risk_score: float = Field(..., ge=0, le=1)
    freshness_drift_score: float = Field(..., ge=0, le=1)
    release_warning_score: float = Field(..., ge=0, le=1)
    driver_features: list[str] = Field(default_factory=list)
    forecast_window: str
    model_name: str
    confidence_band: ConfidenceBand
    execution_mode: str
    fallback_used: bool
    forecast_preview: list[float] = Field(default_factory=list)
    heuristic_baseline: dict[str, Any] = Field(default_factory=dict)
    explanation: str

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class RecentTimeseriesRiskResponse(BaseModel):
    """Recent risk collection for release-center and assistant summaries."""

    version: str = DEFAULT_BOS_VERSION
    items: list[TimeseriesRiskResponse] = Field(default_factory=list)
    count: int
