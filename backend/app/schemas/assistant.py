"""Assistant control plane schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AssistantMode = Literal["simulation_lab", "research_review"]


class AssistantRunCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mode: AssistantMode = "simulation_lab"
    thread_id: str | None = Field(default=None, max_length=120)
    parent_run_id: str | None = Field(default=None, max_length=120)


class AssistantToolCallResponse(BaseModel):
    call_id: str
    tool_name: str
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    status: str
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AssistantConfirmationRequestResponse(BaseModel):
    confirmation_id: str
    action_name: str
    action_payload: dict[str, Any] | None = None
    status: str
    reason: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class AssistantRunResponse(BaseModel):
    run_id: str
    tenant_id: int
    user_id: int
    user_message: str
    parsed_intent: dict[str, Any]
    status: str
    result_summary: dict[str, Any] | None = None
    evidence_pack_id: str | None = None
    tool_registry: dict[str, Any] | None = None
    team_plan: list[dict[str, Any]] = Field(default_factory=list)
    specialist_cards: list[dict[str, Any]] = Field(default_factory=list)
    handoff_records: list[dict[str, Any]] = Field(default_factory=list)
    review_verdicts: list[dict[str, Any]] = Field(default_factory=list)
    action_ledger: list[dict[str, Any]] = Field(default_factory=list)
    memory_tags: list[str] = Field(default_factory=list)
    final_synthesis: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None
    tool_calls: list[AssistantToolCallResponse] = Field(default_factory=list)
    confirmation_requests: list[AssistantConfirmationRequestResponse] = Field(default_factory=list)


class AssistantConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool
    reason: str | None = None


class HumanApprovalResolveRequest(BaseModel):
    approved: bool
    reason: str | None = None


class AssistantReviewConfirmationItem(BaseModel):
    confirmation_id: str
    action_name: str
    action_payload: dict[str, Any] | None = None
    status: str
    reason: str | None = None
    source_assistant_run_id: str
    source_evidence_pack_id: str | None = None
    evidence_pack_ids: list[str] = Field(default_factory=list)
    risk_guardrails: list[str] = Field(default_factory=list)
    created_at: datetime
    resolved_at: datetime | None = None


class AssistantReviewHumanApprovalItem(BaseModel):
    approval_request_id: str
    release_decision_id: int | None = None
    subject_type: str
    subject_id: str
    status: str
    reason: str | None = None
    payload: dict[str, Any] | None = None
    source_assistant_run_id: str | None = None
    source_evidence_pack_id: str | None = None
    evidence_pack_ids: list[str] = Field(default_factory=list)
    risk_guardrails: list[str] = Field(default_factory=list)
    created_at: datetime
    resolved_at: datetime | None = None


class AssistantReviewWorkbenchResponse(BaseModel):
    assistant_confirmations: list[AssistantReviewConfirmationItem] = Field(default_factory=list)
    human_approval_requests: list[AssistantReviewHumanApprovalItem] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
