"""
Remotion media generation schemas.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BaseMediaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


RenderKind = Literal["still", "video"]


class RemotionTemplateField(BaseModel):
    key: str
    label: str
    kind: Literal["text", "textarea", "color", "number", "select"]
    required: bool = False
    default: Any | None = None
    helper_text: str | None = None
    options: list[dict[str, str]] | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None


class RemotionTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    supported_kinds: list[RenderKind]
    default_width: int
    default_height: int
    default_duration_in_frames: int
    default_fps: int
    fields: list[RemotionTemplateField]


class RemotionHealthResponse(BaseModel):
    enabled: bool
    ready: bool
    runtime_dir: str
    output_dir: str
    node_executable: str
    details: list[str] = Field(default_factory=list)


class RemotionRenderRequest(BaseModel):
    kind: RenderKind
    template_id: str
    title: str = Field(..., min_length=1, max_length=140)
    subtitle: str | None = Field(None, max_length=280)
    caption: str | None = Field(None, max_length=280)
    accent_color: str = Field(default="#7CFFB2", max_length=32)
    background_color: str = Field(default="#07111F", max_length=32)
    width: int = Field(default=1080, ge=320, le=3840)
    height: int = Field(default=1080, ge=320, le=3840)
    fps: int = Field(default=30, ge=1, le=120)
    duration_in_frames: int = Field(default=150, ge=1, le=3600)
    extra_props: dict[str, Any] = Field(default_factory=dict)


class RemotionSuggestRequest(BaseModel):
    brief: str = Field(..., min_length=1, max_length=1200)
    preferred_kind: RenderKind | None = None
    preferred_template_id: str | None = None
    audience: str | None = Field(None, max_length=120)
    brand_voice: str | None = Field(None, max_length=120)


class RemotionSuggestResponse(BaseModel):
    source: Literal["heuristic", "model"]
    template_id: str
    kind: RenderKind
    title: str
    subtitle: str
    caption: str
    accent_color: str
    background_color: str
    width: int
    height: int
    fps: int
    duration_in_frames: int
    extra_props: dict[str, Any] = Field(default_factory=dict)
    rationale: list[str] = Field(default_factory=list)


class RemotionAssistantRunRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    preferred_kind: RenderKind | None = None
    preferred_template_id: str | None = None
    audience: str | None = Field(None, max_length=120)
    brand_voice: str | None = Field(None, max_length=120)


class RemotionAssistantRunResponse(BaseModel):
    summary: str
    suggestion: RemotionSuggestResponse
    render: "RemotionRenderResponse"


class RemotionPresetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    tags: list[str] = Field(default_factory=list)
    snapshot_file_name: str | None = Field(default=None, max_length=255)
    snapshot_kind: RenderKind | None = None
    template_id: str
    kind: RenderKind
    export_recipe_id: str = Field(..., min_length=1, max_length=80)
    creative_brief: str = Field(..., min_length=1, max_length=2000)
    audience: str = Field(default="general", max_length=120)
    brand_voice: str = Field(default="balanced", max_length=120)
    title: str = Field(..., min_length=1, max_length=140)
    subtitle: str = Field(default="", max_length=280)
    caption: str = Field(default="", max_length=280)
    accent_color: str = Field(default="#7CFFB2", max_length=32)
    background_color: str = Field(default="#07111F", max_length=32)
    width: str = Field(..., min_length=1, max_length=16)
    height: str = Field(..., min_length=1, max_length=16)
    fps: str = Field(..., min_length=1, max_length=16)
    duration_in_frames: str = Field(..., min_length=1, max_length=16)
    dynamic_fields: dict[str, str] = Field(default_factory=dict)


class RemotionPresetCreateRequest(RemotionPresetBase):
    pass


class RemotionPresetUpdateRequest(RemotionPresetBase):
    pass


class RemotionPresetResponse(RemotionPresetBase):
    id: str
    created_at: datetime
    updated_at: datetime


class RemotionRenderResponse(BaseMediaModel):
    job_id: str
    kind: RenderKind
    template_id: str
    file_name: str
    mime_type: str
    width: int
    height: int
    fps: int | None = None
    duration_in_frames: int | None = None
    created_at: datetime
    asset_url: str
    download_url: str


RemotionAssistantRunResponse.model_rebuild()
