"""
BOS Pipeline v9.0 batch schemas.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, Field

from app.schemas.bos import BatchBOSOverview
from app.schemas.calculation import CalculationResponse


class BatchCreate(BaseModel):
    """Create batch request."""

    batch_id: str = Field(..., min_length=1, max_length=100)
    species: str = Field(default="BSF", max_length=100)
    substrate: Optional[str] = Field(None, max_length=255)
    status: str = Field(default="logged", pattern=r"^(logged|active|completed|archived)$")
    dm_in: float = Field(..., gt=0, description="Dry matter input (kg)")
    dm_out: float = Field(..., ge=0, description="Dry matter output in larvae (kg)")
    n_in: Optional[float] = Field(None, ge=0, description="Nitrogen input (g)")
    n_larvae: Optional[float] = Field(None, ge=0, description="Nitrogen in larvae (g)")
    n_frass: Optional[float] = Field(None, ge=0, description="Nitrogen in frass (g)")
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    temperature: Optional[float] = Field(None, ge=-10, le=60)
    moisture: Optional[float] = Field(None, ge=0, le=100)
    feed_rate: Optional[float] = Field(None, ge=0)
    density: Optional[float] = Field(None, ge=0)
    operator: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=5000)
    batch_date: Optional[date] = None
    metadata_json: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("metadata_json", "metadata"),
        serialization_alias="metadata",
    )

    model_config = {"populate_by_name": True}


class BatchUpdate(BaseModel):
    """Update batch request (partial)."""

    species: Optional[str] = Field(None, max_length=100)
    substrate: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, pattern=r"^(logged|active|completed|archived)$")
    dm_in: Optional[float] = Field(None, gt=0)
    dm_out: Optional[float] = Field(None, ge=0)
    n_in: Optional[float] = Field(None, ge=0)
    n_larvae: Optional[float] = Field(None, ge=0)
    n_frass: Optional[float] = Field(None, ge=0)
    ash_in: Optional[float] = Field(None, ge=0)
    ash_out: Optional[float] = Field(None, ge=0)
    fat_in: Optional[float] = Field(None, ge=0)
    fat_out: Optional[float] = Field(None, ge=0)
    temperature: Optional[float] = Field(None, ge=-10, le=60)
    moisture: Optional[float] = Field(None, ge=0, le=100)
    feed_rate: Optional[float] = Field(None, ge=0)
    density: Optional[float] = Field(None, ge=0)
    operator: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=5000)
    batch_date: Optional[date] = None
    metadata_json: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("metadata_json", "metadata"),
        serialization_alias="metadata",
    )

    model_config = {"populate_by_name": True}


class BatchResponse(BaseModel):
    """Batch list/create response."""

    id: int
    batch_id: str
    species: str
    substrate: Optional[str] = None
    status: str
    dm_in: Optional[float] = None
    dm_out: Optional[float] = None
    score: Optional[float] = None
    temperature: Optional[float] = None
    moisture: Optional[float] = None
    operator: Optional[str] = None
    notes: Optional[str] = None
    batch_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchDetailResponse(BatchResponse):
    """Detailed batch response with calculations."""

    n_in: Optional[float] = None
    n_larvae: Optional[float] = None
    n_frass: Optional[float] = None
    ash_in: Optional[float] = None
    ash_out: Optional[float] = None
    fat_in: Optional[float] = None
    fat_out: Optional[float] = None
    feed_rate: Optional[float] = None
    density: Optional[float] = None
    metadata_json: Optional[Dict[str, Any]] = Field(
        None,
        validation_alias=AliasChoices("metadata_json", "metadata"),
        serialization_alias="metadata",
    )
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    calculations: List[CalculationResponse] = Field(default_factory=list)
    bos: Optional[BatchBOSOverview] = None

    model_config = {"from_attributes": True, "populate_by_name": True}
