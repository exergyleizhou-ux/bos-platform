"""
Vision observation schemas for BOS detection-first review.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VisionDetection(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)


class VisionObservation(BaseModel):
    image_id: str
    detected_classes: list[str] = Field(default_factory=list)
    detections: list[VisionDetection] = Field(default_factory=list)
    dominant_label: str | None = None
    confidence_mean: float | None = Field(None, ge=0, le=1)
    anomaly_flag: bool = False
    observation_summary: str
    bbox_coverage_ratio: float | None = Field(None, ge=0, le=1)


class VisionDetectionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: str
    created_at: datetime
    image_id: str
    file_name: str
    content_type: str | None = None
    model_name: str
    model_status: str
    fallback_used: bool = False
    observation: VisionObservation
    warnings: list[str] = Field(default_factory=list)
    artifact_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisionObservationAttachRequest(BaseModel):
    signal_batch_id: int = Field(gt=0)


class VisionObservationAttachResponse(BaseModel):
    signal_batch_id: int
    run_id: str
    attached: bool
    observation: VisionObservation
    audit_packet_refreshed: bool = False
