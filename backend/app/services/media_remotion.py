"""
Remotion runtime orchestration for BOS media generation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.config import get_settings
from app.schemas.media import (
    RemotionAssistantRunRequest,
    RemotionHealthResponse,
    RemotionPresetCreateRequest,
    RemotionPresetResponse,
    RemotionPresetUpdateRequest,
    RemotionRenderRequest,
    RemotionSuggestRequest,
    RemotionSuggestResponse,
    RemotionTemplateField,
    RemotionTemplateResponse,
)

settings = get_settings()
logger = logging.getLogger("bos.media.remotion")
_render_lock = asyncio.Lock()


@dataclass(slots=True)
class RemotionArtifact:
    job_id: str
    kind: str
    template_id: str
    file_name: str
    file_path: Path
    mime_type: str
    width: int
    height: int
    fps: int | None
    duration_in_frames: int | None
    created_at: datetime


def _metadata_path_for(file_path: Path) -> Path:
    return file_path.with_suffix(f"{file_path.suffix}.json")


def _tenant_segment(tenant_id: int) -> str:
    return f"tenant-{tenant_id}"


def _preset_store_path(tenant_id: int | None = None) -> Path:
    base_path = Path(settings.BOS_MEDIA_REMOTION_PRESET_STORE_PATH).resolve()
    base_path.parent.mkdir(parents=True, exist_ok=True)
    if tenant_id is None:
        return base_path
    return base_path.parent / f"{base_path.stem}-{_tenant_segment(tenant_id)}{base_path.suffix}"


def _load_preset_rows(tenant_id: int) -> list[dict[str, Any]]:
    path = _preset_store_path(tenant_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _write_preset_rows(rows: list[dict[str, Any]], tenant_id: int) -> None:
    _preset_store_path(tenant_id).write_text(
        json.dumps(rows, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


_TEMPLATES: list[RemotionTemplateResponse] = [
    RemotionTemplateResponse(
        id="bos-assistant-safe-still",
        name="BOS Assistant Safe Still",
        description="High-stability still layout optimized for assistant-triggered Chinese and bilingual headlines.",
        supported_kinds=["still"],
        default_width=1080,
        default_height=1080,
        default_duration_in_frames=1,
        default_fps=30,
        fields=[
            RemotionTemplateField(
                key="eyebrow",
                label="Eyebrow",
                kind="text",
                default="BOS MEDIA",
            ),
            RemotionTemplateField(
                key="supporting_line",
                label="Supporting Line",
                kind="text",
                default="Assistant safe still",
            ),
            RemotionTemplateField(
                key="pill_label",
                label="Pill Label",
                kind="text",
                default="READY",
            ),
        ],
    ),
    RemotionTemplateResponse(
        id="bos-launch-card",
        name="BOS Launch Card",
        description="High-contrast BOS hero card for still graphics and short kinetic loops.",
        supported_kinds=["still", "video"],
        default_width=1080,
        default_height=1080,
        default_duration_in_frames=150,
        default_fps=30,
        fields=[
            RemotionTemplateField(
                key="eyebrow",
                label="Eyebrow",
                kind="text",
                default="BOS MEDIA STUDIO",
            ),
            RemotionTemplateField(
                key="metric_label",
                label="Metric Label",
                kind="text",
                default="Launch Window",
            ),
            RemotionTemplateField(
                key="metric_value",
                label="Metric Value",
                kind="text",
                default="T-09 DAYS",
            ),
            RemotionTemplateField(
                key="orb_count",
                label="Orb Count",
                kind="number",
                default=3,
                min=1,
                max=6,
                step=1,
            ),
        ],
    ),
    RemotionTemplateResponse(
        id="bos-signal-beacon",
        name="BOS Signal Beacon",
        description="Portrait or landscape signal-driven visual for status recaps and release snapshots.",
        supported_kinds=["still", "video"],
        default_width=1920,
        default_height=1080,
        default_duration_in_frames=180,
        default_fps=30,
        fields=[
            RemotionTemplateField(
                key="eyebrow",
                label="Eyebrow",
                kind="text",
                default="SIGNAL REVIEW",
            ),
            RemotionTemplateField(
                key="status",
                label="Status",
                kind="select",
                default="Ready",
                options=[
                    {"value": "Ready", "label": "Ready"},
                    {"value": "Attention", "label": "Attention"},
                    {"value": "Blocked", "label": "Blocked"},
                ],
            ),
            RemotionTemplateField(
                key="detail",
                label="Detail",
                kind="textarea",
                default="Fresh signal, contract aligned, portability checks green.",
            ),
            RemotionTemplateField(
                key="grid_density",
                label="Grid Density",
                kind="number",
                default=5,
                min=3,
                max=10,
                step=1,
            ),
        ],
    ),
    RemotionTemplateResponse(
        id="bos-story-stack",
        name="BOS Story Stack",
        description="Portrait-first story layout for mobile launch moments, product announcements, and status reels.",
        supported_kinds=["still", "video"],
        default_width=1080,
        default_height=1920,
        default_duration_in_frames=180,
        default_fps=30,
        fields=[
            RemotionTemplateField(
                key="eyebrow",
                label="Eyebrow",
                kind="text",
                default="BOS STORY",
            ),
            RemotionTemplateField(
                key="status",
                label="Status",
                kind="select",
                default="Shipping",
                options=[
                    {"value": "Shipping", "label": "Shipping"},
                    {"value": "Watching", "label": "Watching"},
                    {"value": "Blocked", "label": "Blocked"},
                ],
            ),
            RemotionTemplateField(
                key="callout",
                label="Callout",
                kind="textarea",
                default="Programmatic graphics and motion now render directly inside BOS.",
            ),
        ],
    ),
    RemotionTemplateResponse(
        id="bos-metric-board",
        name="BOS Metric Board",
        description="Wide-format board for KPI callouts, dashboard exports, and investor-style proof points.",
        supported_kinds=["still", "video"],
        default_width=1920,
        default_height=1080,
        default_duration_in_frames=150,
        default_fps=30,
        fields=[
            RemotionTemplateField(
                key="eyebrow",
                label="Eyebrow",
                kind="text",
                default="BOS METRICS",
            ),
            RemotionTemplateField(
                key="primary_metric_label",
                label="Primary Metric Label",
                kind="text",
                default="Render Velocity",
            ),
            RemotionTemplateField(
                key="primary_metric_value",
                label="Primary Metric Value",
                kind="text",
                default="+42%",
            ),
            RemotionTemplateField(
                key="secondary_metric_label",
                label="Secondary Metric Label",
                kind="text",
                default="Turnaround",
            ),
            RemotionTemplateField(
                key="secondary_metric_value",
                label="Secondary Metric Value",
                kind="text",
                default="Same Day",
            ),
        ],
    ),
]


def _normalize_brand_voice(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"launch", "campaign", "brand"}:
        return "launch"
    if normalized in {"executive", "exec", "board"}:
        return "executive"
    if normalized in {"social", "story", "creator"}:
        return "social"
    if normalized in {"operations", "ops", "signal"}:
        return "operations"
    return "balanced"


def _normalize_audience(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"executive", "leadership", "board"}:
        return "executives"
    if normalized in {"operator", "operations", "ops"}:
        return "operators"
    if normalized in {"customer", "prospect", "external"}:
        return "external"
    if normalized in {"social", "community"}:
        return "community"
    return "general"


def list_templates() -> list[RemotionTemplateResponse]:
    return _TEMPLATES


def list_saved_presets(tenant_id: int) -> list[RemotionPresetResponse]:
    rows = _load_preset_rows(tenant_id)
    presets: list[RemotionPresetResponse] = []
    for row in rows:
        try:
            presets.append(RemotionPresetResponse.model_validate(row))
        except Exception:
            continue
    presets.sort(key=lambda item: item.updated_at, reverse=True)
    return presets


def save_preset(body: RemotionPresetCreateRequest, tenant_id: int) -> RemotionPresetResponse:
    now = datetime.now(UTC)
    rows = _load_preset_rows(tenant_id)
    next_row = {
        "id": uuid4().hex,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        **body.model_dump(),
    }
    rows.insert(0, next_row)
    _write_preset_rows(rows[:100], tenant_id)
    return RemotionPresetResponse.model_validate(next_row)


def delete_preset(preset_id: str, tenant_id: int) -> bool:
    rows = _load_preset_rows(tenant_id)
    next_rows = [row for row in rows if row.get("id") != preset_id]
    if len(next_rows) == len(rows):
        return False
    _write_preset_rows(next_rows, tenant_id)
    return True


def update_preset(
    preset_id: str,
    body: RemotionPresetUpdateRequest,
    tenant_id: int,
) -> RemotionPresetResponse | None:
    rows = _load_preset_rows(tenant_id)
    now = datetime.now(UTC).isoformat()

    for index, row in enumerate(rows):
        if row.get("id") != preset_id:
            continue
        next_row = {
            **row,
            **body.model_dump(),
            "id": preset_id,
            "created_at": row.get("created_at", now),
            "updated_at": now,
        }
        rows[index] = next_row
        _write_preset_rows(rows, tenant_id)
        return RemotionPresetResponse.model_validate(next_row)

    return None


def get_template(template_id: str) -> RemotionTemplateResponse:
    for template in _TEMPLATES:
        if template.id == template_id:
            return template
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Unknown Remotion template",
    )


def _heuristic_suggest_from_brief(body: RemotionSuggestRequest) -> RemotionSuggestResponse:
    brief = body.brief.strip()
    brief_lower = brief.lower()
    brand_voice = _normalize_brand_voice(body.brand_voice)
    audience = _normalize_audience(body.audience)

    template_id = body.preferred_template_id or "bos-launch-card"
    kind = body.preferred_kind or "still"
    accent_color = "#7CFFB2"
    background_color = "#07111F"
    title = "BOS Media Studio"
    subtitle = brief
    caption = "RENDERED WITH REMOTION"
    rationale: list[str] = []
    extra_props: dict[str, Any] = {}

    if brand_voice == "executive":
        title = "BOS is creating executive clarity"
        caption = "EXECUTIVE BRIEF"
        accent_color = "#F8C15C"
        background_color = "#0A1320"
        rationale.append("Executive voice selected, so the language and palette are calmer and more board-ready.")
    elif brand_voice == "operations":
        title = "BOS keeps the signal legible"
        caption = "OPS SIGNAL"
        accent_color = "#7CFFB2"
        background_color = "#07111F"
        rationale.append("Operations voice selected, so the framing leans toward signal, posture, and execution.")
    elif brand_voice == "social":
        title = "BOS ships in motion"
        caption = "SOCIAL STORY"
        accent_color = "#82B8FF"
        background_color = "#09111B"
        rationale.append("Social voice selected, so the output favors sharper punch lines and motion-friendly framing.")
    elif brand_voice == "launch":
        title = "Launch the next BOS story"
        caption = "CAMPAIGN READY"
        accent_color = "#F8C15C"
        background_color = "#0C1220"
        rationale.append("Launch voice selected, so the output leans more promotional and headline-forward.")

    if any(keyword in brief_lower for keyword in ("signal", "release", "risk", "readiness", "status")):
        template_id = body.preferred_template_id or "bos-signal-beacon"
        kind = body.preferred_kind or "video"
        title = "Release posture is moving"
        caption = "SIGNAL REVIEW"
        extra_props = {
            "eyebrow": "SIGNAL REVIEW",
            "status": "Ready",
            "detail": brief,
            "grid_density": 5,
        }
        rationale.append("Detected release or signal language, so BOS Signal Beacon is a better fit.")

    if any(keyword in brief_lower for keyword in ("story", "vertical", "portrait", "mobile", "reel")):
        template_id = body.preferred_template_id or "bos-story-stack"
        kind = body.preferred_kind or "video"
        title = "BOS ships in motion"
        caption = "STORY STACK"
        extra_props = {
            "eyebrow": "BOS STORY",
            "status": "Shipping",
            "callout": brief,
        }
        rationale.append("Detected portrait or story language, so BOS Story Stack fits better.")

    if any(keyword in brief_lower for keyword in ("metric", "kpi", "dashboard", "board", "proof point", "stats")):
        template_id = body.preferred_template_id or "bos-metric-board"
        kind = body.preferred_kind or "still"
        title = "BOS metrics are compounding"
        caption = "METRIC BOARD"
        extra_props = {
            "eyebrow": "BOS METRICS",
            "primary_metric_label": "Render Velocity",
            "primary_metric_value": "+42%",
            "secondary_metric_label": "Turnaround",
            "secondary_metric_value": "Same Day",
        }
        rationale.append("Detected metrics or dashboard language, so BOS Metric Board is the clearest format.")

    if audience == "executives":
        subtitle = "A higher-level readout built for fast alignment, evidence, and next-step clarity."
        rationale.append("Executive audience selected, so the subtitle is more compressed and strategic.")
    elif audience == "operators":
        subtitle = "A control-room framing built for live decisions, signal clarity, and the next concrete move."
        rationale.append("Operator audience selected, so the subtitle is more execution-oriented.")
    elif audience == "external":
        subtitle = "A cleaner external-facing frame that emphasizes product value and confidence."
        rationale.append("External audience selected, so the subtitle is less internal and more product-facing.")
    elif audience == "community":
        subtitle = "A community-facing frame designed for immediacy, motion, and shareability."
        rationale.append("Community audience selected, so the subtitle is tuned for social readability.")

    if any(keyword in brief_lower for keyword in ("risk", "blocked", "incident", "warning", "alert")):
        accent_color = "#FF7A6A"
        background_color = "#120A0F"
        title = "Attention is required"
        caption = "RISK WATCH"
        if template_id == "bos-signal-beacon":
            extra_props["status"] = "Blocked" if "blocked" in brief_lower else "Attention"
        rationale.append("Risk-oriented language shifted the palette toward alert colors.")
    elif any(keyword in brief_lower for keyword in ("launch", "growth", "campaign", "brand", "marketing", "hero")):
        accent_color = "#F8C15C"
        background_color = "#0C1220"
        title = "Launch the next BOS story"
        caption = "CAMPAIGN READY"
        template_id = body.preferred_template_id or "bos-launch-card"
        kind = body.preferred_kind or "still"
        rationale.append("Marketing-style language nudged the suggestion toward the hero card treatment.")

    if "square" in brief_lower or "instagram" in brief_lower:
        width = 1080
        height = 1080
        rationale.append("Detected square output intent.")
    elif any(keyword in brief_lower for keyword in ("story", "vertical", "portrait", "mobile")):
        width = 1080
        height = 1920
        rationale.append("Detected portrait output intent.")
    elif template_id == "bos-metric-board":
        width = 1920
        height = 1080
    else:
        template = get_template(template_id)
        width = template.default_width
        height = template.default_height

    fps = 30 if kind == "video" else get_template(template_id).default_fps
    duration_in_frames = 150 if kind == "video" else 1

    if template_id == "bos-launch-card":
        metric_label = "Brief"
        if any(keyword in brief_lower for keyword in ("launch", "release")):
            metric_label = "Window"
        metric_value = "LIVE"
        if "today" in brief_lower or "now" in brief_lower:
            metric_value = "NOW"
        elif "week" in brief_lower:
            metric_value = "THIS WEEK"
        extra_props = {
            "eyebrow": "BOS MEDIA STUDIO",
            "metric_label": metric_label,
            "metric_value": metric_value,
            "orb_count": 3,
            **extra_props,
        }
    elif template_id == "bos-story-stack":
        extra_props = {
            "eyebrow": extra_props.get("eyebrow", "BOS STORY"),
            "status": extra_props.get("status", "Shipping"),
            "callout": extra_props.get("callout", brief),
        }
    elif template_id == "bos-metric-board":
        extra_props = {
            "eyebrow": extra_props.get("eyebrow", "BOS METRICS"),
            "primary_metric_label": extra_props.get("primary_metric_label", "Render Velocity"),
            "primary_metric_value": extra_props.get("primary_metric_value", "+42%"),
            "secondary_metric_label": extra_props.get("secondary_metric_label", "Turnaround"),
            "secondary_metric_value": extra_props.get("secondary_metric_value", "Same Day"),
        }
    else:
        extra_props = {
            "eyebrow": extra_props.get("eyebrow", "SIGNAL REVIEW"),
            "status": extra_props.get("status", "Ready"),
            "detail": extra_props.get("detail", brief),
            "grid_density": extra_props.get("grid_density", 5),
        }

    if title == "BOS Media Studio":
        snippets = [segment.strip() for segment in brief.replace("\n", " ").split(".") if segment.strip()]
        if snippets:
            title = snippets[0][:72].rstrip(" ,;:")
        if len(snippets) > 1:
            subtitle = snippets[1][:220].rstrip(" ,;:")

    if not rationale:
        rationale.append("Used the default BOS launch-card treatment because the brief was broad.")

    return RemotionSuggestResponse(
        source="heuristic",
        template_id=template_id,
        kind=kind,
        title=title,
        subtitle=subtitle[:280],
        caption=caption,
        accent_color=accent_color,
        background_color=background_color,
        width=width,
        height=height,
        fps=fps,
        duration_in_frames=duration_in_frames,
        extra_props=extra_props,
        rationale=rationale,
    )


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


def _media_openai_credentials() -> tuple[str, str, str, str]:
    team_api_key = settings.OPENAI_TEAM_API_KEY.strip()
    team_base_url = settings.OPENAI_TEAM_BASE_URL.strip()
    if team_api_key and team_base_url:
        return (
            team_api_key,
            team_base_url,
            settings.OPENAI_TEAM_ORGANIZATION.strip(),
            settings.OPENAI_TEAM_PROJECT.strip(),
        )
    return (
        settings.OPENAI_API_KEY.strip(),
        settings.OPENAI_BASE_URL.strip(),
        settings.OPENAI_ORGANIZATION.strip(),
        settings.OPENAI_PROJECT.strip(),
    )


def _safe_string(value: Any, fallback: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    return value.strip()[:max_len]


def _safe_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed


def _normalize_model_suggestion(
    body: RemotionSuggestRequest,
    raw_payload: dict[str, Any],
) -> RemotionSuggestResponse:
    heuristic = _heuristic_suggest_from_brief(body)
    template_ids = {template.id for template in _TEMPLATES}
    template_id = raw_payload.get("template_id")
    if template_id not in template_ids:
        template_id = heuristic.template_id
    template = get_template(template_id)

    kind = raw_payload.get("kind")
    if kind not in {"still", "video"}:
        kind = heuristic.kind
    if kind not in template.supported_kinds:
        kind = template.supported_kinds[0]

    extra_props = raw_payload.get("extra_props")
    if not isinstance(extra_props, dict):
        extra_props = heuristic.extra_props

    rationale = raw_payload.get("rationale")
    if not isinstance(rationale, list):
        rationale = heuristic.rationale
    rationale = [str(item)[:200] for item in rationale if str(item).strip()][:4] or heuristic.rationale

    return RemotionSuggestResponse(
        source="model",
        template_id=template_id,
        kind=kind,
        title=_safe_string(raw_payload.get("title"), heuristic.title, 140),
        subtitle=_safe_string(raw_payload.get("subtitle"), heuristic.subtitle, 280),
        caption=_safe_string(raw_payload.get("caption"), heuristic.caption, 280),
        accent_color=_safe_string(raw_payload.get("accent_color"), heuristic.accent_color, 32),
        background_color=_safe_string(raw_payload.get("background_color"), heuristic.background_color, 32),
        width=_safe_int(raw_payload.get("width"), heuristic.width),
        height=_safe_int(raw_payload.get("height"), heuristic.height),
        fps=_safe_int(raw_payload.get("fps"), heuristic.fps),
        duration_in_frames=_safe_int(raw_payload.get("duration_in_frames"), heuristic.duration_in_frames),
        extra_props=extra_props,
        rationale=rationale,
    )


async def _suggest_with_model(body: RemotionSuggestRequest) -> RemotionSuggestResponse | None:
    if not settings.BOS_MEDIA_REMOTION_ENABLE_LLM_SUGGESTIONS:
        return None
    api_key, base_url, organization, project = _media_openai_credentials()
    if not api_key or not base_url:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if organization:
        headers["OpenAI-Organization"] = organization
    if project:
        headers["OpenAI-Project"] = project

    templates_payload = [
        {
            "id": template.id,
            "name": template.name,
            "supported_kinds": template.supported_kinds,
            "default_width": template.default_width,
            "default_height": template.default_height,
            "default_duration_in_frames": template.default_duration_in_frames,
            "default_fps": template.default_fps,
            "fields": [field.key for field in template.fields],
        }
        for template in _TEMPLATES
    ]

    payload = {
        "model": settings.BOS_MEDIA_REMOTION_SUGGEST_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are BOS Media Studio. Return exactly one JSON object and no extra prose. "
                            "Choose one template from the provided template list, choose either still or video, "
                            "and produce concise marketing or operational copy that fits the brief. "
                            "Respect the requested audience and brand_voice when present. "
                            "Match the user's language whenever it is clear from the brief. "
                            "JSON keys: template_id, kind, title, subtitle, caption, accent_color, background_color, "
                            "width, height, fps, duration_in_frames, extra_props, rationale."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            {
                                "brief": body.brief,
                                "preferred_kind": body.preferred_kind,
                                "preferred_template_id": body.preferred_template_id,
                                "audience": body.audience,
                                "brand_voice": body.brand_voice,
                                "templates": templates_payload,
                            },
                            ensure_ascii=True,
                        ),
                    }
                ],
            },
        ],
        "reasoning": {"effort": "low"},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url}/responses",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.warning("Remotion model suggestion unavailable; falling back to heuristic", exc_info=exc)
        return None
    if not response.is_success:
        return None

    response_body = response.json()
    output_text = ""
    direct_output_text = response_body.get("output_text")
    if isinstance(direct_output_text, str) and direct_output_text.strip():
        output_text = direct_output_text
    else:
        chunks: list[str] = []
        for output_item in response_body.get("output", []) or []:
            if not isinstance(output_item, dict):
                continue
            for content_item in output_item.get("content", []) or []:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") in {"output_text", "text"}:
                    text = content_item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        output_text = "\n".join(chunks).strip()

    if not output_text:
        return None

    try:
        parsed = _extract_json_object(output_text)
    except (ValueError, json.JSONDecodeError):
        return None

    return _normalize_model_suggestion(body, parsed)


async def suggest_from_brief(body: RemotionSuggestRequest) -> RemotionSuggestResponse:
    model_suggestion = await _suggest_with_model(body)
    if model_suggestion is not None:
        return model_suggestion
    return _heuristic_suggest_from_brief(body)


def _runtime_dir() -> Path:
    return Path(settings.BOS_MEDIA_REMOTION_RUNTIME_DIR).resolve()


def _output_dir(tenant_id: int | None = None) -> Path:
    path = Path(settings.BOS_MEDIA_REMOTION_OUTPUT_DIR).resolve()
    if tenant_id is not None:
        path = path / _tenant_segment(tenant_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _script_path() -> Path:
    return _runtime_dir() / "render.mjs"


def _mime_type_for_kind(kind: str) -> str:
    return "image/png" if kind == "still" else "video/mp4"


def _kind_for_path(file_path: Path) -> str:
    return "still" if file_path.suffix.lower() == ".png" else "video"


def get_health() -> RemotionHealthResponse:
    details: list[str] = []
    ready = True

    runtime_dir = _runtime_dir()
    output_dir = _output_dir()
    node_binary = shutil.which(settings.BOS_MEDIA_REMOTION_NODE_EXECUTABLE)

    if not settings.BOS_MEDIA_REMOTION_ENABLED:
        ready = False
        details.append("Remotion runtime is disabled in configuration.")

    if not runtime_dir.exists():
        ready = False
        details.append(f"Runtime directory is missing: {runtime_dir}")

    if not _script_path().exists():
        ready = False
        details.append(f"Render script is missing: {_script_path()}")

    if not (runtime_dir / "package.json").exists():
        ready = False
        details.append(f"Runtime package.json is missing: {runtime_dir / 'package.json'}")

    if node_binary is None:
        ready = False
        details.append(f"Node executable '{settings.BOS_MEDIA_REMOTION_NODE_EXECUTABLE}' is not available on PATH.")

    if ready:
        details.append("Runtime files are present and Node is available.")

    return RemotionHealthResponse(
        enabled=settings.BOS_MEDIA_REMOTION_ENABLED,
        ready=ready,
        runtime_dir=str(runtime_dir),
        output_dir=str(output_dir),
        node_executable=settings.BOS_MEDIA_REMOTION_NODE_EXECUTABLE,
        details=details,
    )


def _build_runtime_payload(job_id: str, body: RemotionRenderRequest) -> dict[str, Any]:
    template = get_template(body.template_id)
    return {
        "jobId": job_id,
        "kind": body.kind,
        "templateId": template.id,
        "title": body.title,
        "subtitle": body.subtitle,
        "caption": body.caption,
        "accentColor": body.accent_color,
        "backgroundColor": body.background_color,
        "width": body.width,
        "height": body.height,
        "fps": body.fps,
        "durationInFrames": body.duration_in_frames,
        "extraProps": body.extra_props,
        "logLevel": settings.BOS_MEDIA_REMOTION_LOG_LEVEL,
    }


async def _render_media_once(body: RemotionRenderRequest, tenant_id: int) -> RemotionArtifact:
    health = get_health()
    if not health.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Remotion runtime is not ready.",
                "details": health.details,
            },
        )

    job_id = uuid4().hex
    output_dir = _output_dir(tenant_id)
    extension = "png" if body.kind == "still" else "mp4"
    output_path = output_dir / f"{job_id}.{extension}"

    payload = _build_runtime_payload(job_id, body)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix=f"{job_id}-",
        dir=output_dir,
        delete=False,
    ) as temp_file:
        temp_file.write(json.dumps(payload, ensure_ascii=True))
        payload_path = Path(temp_file.name)

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            settings.BOS_MEDIA_REMOTION_NODE_EXECUTABLE,
            str(_script_path()),
            "--payload",
            str(payload_path),
            "--output",
            str(output_path),
            cwd=str(_runtime_dir()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    finally:
        payload_path.unlink(missing_ok=True)

    if process is None or process.returncode != 0:
        error_detail = stderr.decode("utf-8", errors="replace").strip()
        if not error_detail:
            error_detail = stdout.decode("utf-8", errors="replace").strip()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Remotion render failed.",
                "details": error_detail or "Unknown runtime failure.",
            },
        )

    try:
        runtime_payload = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Remotion runtime returned invalid JSON.",
        ) from exc

    artifact_path = Path(runtime_payload["outputPath"]).resolve()
    if not artifact_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Remotion runtime reported success but no artifact was produced.",
        )

    artifact = RemotionArtifact(
        job_id=runtime_payload["jobId"],
        kind=runtime_payload["kind"],
        template_id=runtime_payload["templateId"],
        file_name=artifact_path.name,
        file_path=artifact_path,
        mime_type=_mime_type_for_kind(runtime_payload["kind"]),
        width=int(runtime_payload["width"]),
        height=int(runtime_payload["height"]),
        fps=int(runtime_payload["fps"]) if runtime_payload.get("fps") is not None else None,
        duration_in_frames=(
            int(runtime_payload["durationInFrames"])
            if runtime_payload.get("durationInFrames") is not None
            else None
        ),
        created_at=datetime.now(UTC),
    )

    metadata = {
        "job_id": artifact.job_id,
        "kind": artifact.kind,
        "template_id": artifact.template_id,
        "file_name": artifact.file_name,
        "mime_type": artifact.mime_type,
        "width": artifact.width,
        "height": artifact.height,
        "fps": artifact.fps,
        "duration_in_frames": artifact.duration_in_frames,
        "created_at": artifact.created_at.isoformat(),
    }
    _metadata_path_for(artifact.file_path).write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return artifact


async def render_media(body: RemotionRenderRequest, tenant_id: int) -> RemotionArtifact:
    last_exception: HTTPException | None = None
    async with _render_lock:
        for attempt in range(2):
            try:
                return await _render_media_once(body, tenant_id)
            except HTTPException as exc:
                last_exception = exc
                logger.warning(
                    "Remotion render attempt failed",
                    extra={
                        "attempt": attempt + 1,
                        "kind": body.kind,
                        "template_id": body.template_id,
                        "detail": exc.detail,
                    },
                )
                if attempt == 0:
                    await asyncio.sleep(0.6)
                    continue
                raise

    if last_exception is not None:
        raise last_exception
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Remotion render failed for an unknown reason.",
    )


def list_artifacts(limit: int = 20, tenant_id: int | None = None) -> list[RemotionArtifact]:
    output_dir = _output_dir(tenant_id)
    candidates = sorted(
        output_dir.glob("*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    artifacts: list[RemotionArtifact] = []

    for file_path in candidates:
        if file_path.suffix.lower() not in {".png", ".mp4"}:
            continue

        metadata_path = _metadata_path_for(file_path)
        metadata: dict[str, Any] = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}

        stat = file_path.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        if metadata.get("created_at"):
            with suppress(ValueError):
                created_at = datetime.fromisoformat(metadata["created_at"])

        artifacts.append(
            RemotionArtifact(
                job_id=metadata.get("job_id", file_path.stem),
                kind=metadata.get("kind", _kind_for_path(file_path)),
                template_id=metadata.get("template_id", "unknown-template"),
                file_name=file_path.name,
                file_path=file_path,
                mime_type=metadata.get("mime_type", _mime_type_for_kind(_kind_for_path(file_path))),
                width=int(metadata.get("width", 0)),
                height=int(metadata.get("height", 0)),
                fps=int(metadata["fps"]) if metadata.get("fps") is not None else None,
                duration_in_frames=(
                    int(metadata["duration_in_frames"])
                    if metadata.get("duration_in_frames") is not None
                    else None
                ),
                created_at=created_at,
            )
        )
        if len(artifacts) >= limit:
            break

    return artifacts


def resolve_artifact(file_name: str, tenant_id: int) -> Path:
    output_dir = _output_dir(tenant_id)
    candidate = (output_dir / file_name).resolve()
    if candidate.parent != output_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media file path")
    if not candidate.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media artifact not found")
    return candidate


def _build_safe_still_request(
    *,
    prompt: str,
    suggestion: RemotionSuggestResponse,
) -> RemotionRenderRequest:
    safe_title = suggestion.title[:80] if suggestion.title else "BOS Media"
    safe_subtitle = (suggestion.subtitle or prompt)[:180]
    return RemotionRenderRequest(
        kind="still",
        template_id="bos-launch-card",
        title=safe_title or "BOS Media",
        subtitle=safe_subtitle,
        caption="BOS MEDIA",
        accent_color="#7CFFB2",
        background_color="#07111F",
        width=1080,
        height=1080,
        fps=30,
        duration_in_frames=1,
        extra_props={
            "eyebrow": "BOS MEDIA",
            "metric_label": "Fallback",
            "metric_value": "READY",
            "orb_count": 2,
        },
    )


async def run_assistant_media_request(
    body: RemotionAssistantRunRequest,
    tenant_id: int,
) -> tuple[RemotionSuggestResponse, RemotionArtifact, str]:
    suggestion = await suggest_from_brief(
        RemotionSuggestRequest(
            brief=body.prompt,
            preferred_kind=body.preferred_kind,
            preferred_template_id=body.preferred_template_id,
            audience=body.audience,
            brand_voice=body.brand_voice,
        )
    )
    primary_request = RemotionRenderRequest(
        kind=suggestion.kind,
        template_id=suggestion.template_id,
        title=suggestion.title,
        subtitle=suggestion.subtitle,
        caption=suggestion.caption,
        accent_color=suggestion.accent_color,
        background_color=suggestion.background_color,
        width=suggestion.width,
        height=suggestion.height,
        fps=suggestion.fps,
        duration_in_frames=suggestion.duration_in_frames,
        extra_props=suggestion.extra_props,
    )
    try:
        artifact = await render_media(primary_request, tenant_id)
        summary = (
            f"I turned your request into a {'short animation' if artifact.kind == 'video' else 'still graphic'} "
            f"using {artifact.template_id}. The draft is ready to preview, download, or continue editing in Media Studio."
        )
        return suggestion, artifact, summary
    except HTTPException as exc:
        logger.warning(
            "Assistant media primary render failed, falling back to safe still",
            extra={
                "detail": exc.detail,
                "template_id": suggestion.template_id,
                "kind": suggestion.kind,
            },
        )
        fallback_request = _build_safe_still_request(prompt=body.prompt, suggestion=suggestion)
        artifact = await render_media(fallback_request, tenant_id)
        fallback_suggestion = RemotionSuggestResponse(
            source=suggestion.source,
            template_id=fallback_request.template_id,
            kind=fallback_request.kind,
            title=fallback_request.title,
            subtitle=fallback_request.subtitle or "",
            caption=fallback_request.caption or "",
            accent_color=fallback_request.accent_color,
            background_color=fallback_request.background_color,
            width=fallback_request.width,
            height=fallback_request.height,
            fps=fallback_request.fps,
            duration_in_frames=fallback_request.duration_in_frames,
            extra_props=fallback_request.extra_props,
            rationale=[
                *suggestion.rationale[:3],
                "Primary render failed, so BOS fell back to a stable still graphic.",
            ],
        )
        summary = (
            "The requested render path was unstable just now, so BOS produced a stable still graphic instead. "
            "You can use this draft immediately or reopen Media Studio to retry a richer render."
        )
        return fallback_suggestion, artifact, summary
