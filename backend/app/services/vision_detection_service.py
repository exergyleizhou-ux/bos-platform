"""
Detection-first vision observation service for BOS operator review.

The service is intentionally isolated from supervisor execution. It converts an
uploaded image into a reviewable structured observation and persists a compact
artifact for later review.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any
from uuid import uuid4

from app.config import REPO_ROOT, get_settings
from app.schemas.vision_observation import (
    VisionDetection,
    VisionDetectionResponse,
    VisionObservation,
)

settings = get_settings()

RUN_ROOT = REPO_ROOT / "backend" / "generated" / "vision-observations"
UPLOAD_ROOT = RUN_ROOT / "uploads"
ARTIFACT_ROOT = RUN_ROOT / "runs"
ANOMALY_LABEL_HINTS = (
    "anomaly",
    "foreign",
    "intrusion",
    "contamination",
    "non_target",
    "non-target",
)


def _safe_filename(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {".", "-", "_"} else "_" for char in name.strip())
    return cleaned or "image.bin"


def _image_dimensions(image_path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            width, height = image.size
        return width, height
    except Exception:
        return None, None


def _bbox_area(bbox: list[float]) -> float:
    if len(bbox) != 4:
        return 0.0
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _bbox_coverage_ratio(detections: list[VisionDetection], width: int | None, height: int | None) -> float | None:
    if not width or not height or width <= 0 or height <= 0:
        return None
    total_area = float(width * height)
    covered = sum(_bbox_area(item.bbox) for item in detections)
    return round(max(0.0, min(1.0, covered / total_area)), 4)


def _is_anomaly_label(label: str) -> bool:
    value = label.lower()
    return any(hint in value for hint in ANOMALY_LABEL_HINTS)


def _normalize_observation(
    *,
    image_id: str,
    detections: list[VisionDetection],
    width: int | None,
    height: int | None,
) -> VisionObservation:
    detected_classes = sorted({item.label for item in detections})
    dominant = max(detections, key=lambda item: item.confidence, default=None)
    confidence_mean = round(fmean(item.confidence for item in detections), 4) if detections else None
    anomaly_flag = any(_is_anomaly_label(item.label) for item in detections)
    bbox_coverage = _bbox_coverage_ratio(detections, width, height)

    if detections and dominant is not None:
        summary = (
            f"{len(detections)} detections; dominant label {dominant.label}; "
            f"mean confidence {confidence_mean:.2f}."
        )
        if anomaly_flag:
            summary += " Anomaly-like label detected for operator review."
    else:
        summary = "No confident detections returned; keep this as an operator-reviewed empty observation."

    return VisionObservation(
        image_id=image_id,
        detected_classes=detected_classes,
        detections=detections,
        dominant_label=dominant.label if dominant else None,
        confidence_mean=confidence_mean,
        anomaly_flag=anomaly_flag,
        observation_summary=summary,
        bbox_coverage_ratio=bbox_coverage,
    )


def _infer_with_ultralytics(image_path: Path, *, model_name: str) -> tuple[list[VisionDetection], list[str], str]:
    from ultralytics import YOLO

    detector = YOLO(model_name)
    prediction = detector.predict(source=str(image_path), verbose=False)
    detections: list[VisionDetection] = []
    if prediction:
        result = prediction[0]
        names = getattr(result, "names", {}) or {}
        boxes = getattr(result, "boxes", None)
        if boxes is not None and getattr(boxes, "cls", None) is not None:
            cls_values = boxes.cls.tolist()
            conf_values = boxes.conf.tolist() if getattr(boxes, "conf", None) is not None else []
            xyxy_values = boxes.xyxy.tolist() if getattr(boxes, "xyxy", None) is not None else []
            for index, cls_value in enumerate(cls_values):
                class_id = int(cls_value)
                label = str(names.get(class_id, class_id))
                confidence = float(conf_values[index]) if index < len(conf_values) else 0.0
                bbox = [float(value) for value in xyxy_values[index]] if index < len(xyxy_values) else [0, 0, 0, 0]
                detections.append(
                    VisionDetection(
                        label=label,
                        confidence=round(max(0.0, min(1.0, confidence)), 4),
                        bbox=bbox,
                    )
                )
    return detections, [], "ultralytics_live"


def _persist_response(response: VisionDetectionResponse, *, tenant_id: int) -> str:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_ROOT / f"{response.created_at.strftime('%Y%m%dT%H%M%SZ')}-{response.run_id}.json"
    payload = response.model_dump(mode="json")
    payload["tenant_id"] = tenant_id
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(artifact_path)


def detect_image(
    *,
    file_bytes: bytes,
    file_name: str,
    content_type: str | None,
    tenant_id: int,
) -> VisionDetectionResponse:
    run_id = uuid4().hex
    image_id = f"vision-{run_id}"
    created_at = datetime.now(UTC)
    safe_name = _safe_filename(file_name)
    upload_dir = UPLOAD_ROOT / str(tenant_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / f"{image_id}-{safe_name}"
    upload_path.write_bytes(file_bytes)

    width, height = _image_dimensions(upload_path)
    model_name = settings.BOS_NATIVE_YOLO11_DSCONV_WEIGHTS_PATH or "yolo11n.pt"
    warnings: list[str] = []
    fallback_used = False
    model_status = "ultralytics_live"
    detections: list[VisionDetection] = []

    try:
        detections, inference_warnings, model_status = _infer_with_ultralytics(upload_path, model_name=model_name)
        warnings.extend(inference_warnings)
    except Exception as exc:
        fallback_used = True
        model_status = "fallback_empty_observation"
        warnings.append(f"Ultralytics inference unavailable: {exc!s}")

    observation = _normalize_observation(
        image_id=image_id,
        detections=detections,
        width=width,
        height=height,
    )
    response = VisionDetectionResponse(
        run_id=run_id,
        created_at=created_at,
        image_id=image_id,
        file_name=safe_name,
        content_type=content_type,
        model_name=model_name,
        model_status=model_status,
        fallback_used=fallback_used,
        observation=observation,
        warnings=warnings,
        metadata={
            "image_width": width,
            "image_height": height,
            "phase": "operator_review",
            "supervisor_auto_execution": False,
        },
    )
    artifact_path = _persist_response(response, tenant_id=tenant_id)
    return response.model_copy(update={"artifact_path": artifact_path})


def list_detection_runs(*, tenant_id: int, limit: int = 20) -> list[VisionDetectionResponse]:
    if not ARTIFACT_ROOT.exists():
        return []

    responses: list[VisionDetectionResponse] = []
    for path in sorted(ARTIFACT_ROOT.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("tenant_id") != tenant_id:
            continue
        payload.pop("tenant_id", None)
        responses.append(VisionDetectionResponse.model_validate(payload))
        if len(responses) >= max(1, limit):
            break
    return responses


def get_detection_run(*, tenant_id: int, run_id: str) -> VisionDetectionResponse | None:
    if not ARTIFACT_ROOT.exists():
        return None

    for path in ARTIFACT_ROOT.glob(f"*-{run_id}.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("tenant_id") != tenant_id:
            continue
        payload.pop("tenant_id", None)
        return VisionDetectionResponse.model_validate(payload)
    return None
