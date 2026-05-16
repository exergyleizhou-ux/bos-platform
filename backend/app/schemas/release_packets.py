"""Release packet attachment and human approval schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SimulationAppendixAttachRequest(BaseModel):
    simulation_id: str = Field(..., min_length=1)
    run_id: str | None = None


class ReleasePacketAttachmentResponse(BaseModel):
    attachment_id: str
    release_decision_id: int
    tenant_id: int
    user_id: int
    attachment_type: str
    simulation_id: str | None
    run_id: str | None
    evidence_pack_id: str | None
    appendix_hash: str
    payload: dict[str, Any]
    created_at: datetime


class HumanApprovalRequestCreate(BaseModel):
    subject_type: str = "release_decision"
    subject_id: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class HumanApprovalRequestResponse(BaseModel):
    approval_request_id: str
    release_decision_id: int | None
    tenant_id: int
    user_id: int
    subject_type: str
    subject_id: str
    status: str
    reason: str | None
    payload: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None
