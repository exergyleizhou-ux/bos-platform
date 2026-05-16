"""
BOS native model runtime orchestration.

This layer exposes honest runtime readiness and a minimal inference contract.
Frontier model execution is only reported as ready when the required runtime
artifacts and dependencies are available. Until then, BOS can still provide:
- dry-run contract previews for all models
- explicit next-step guidance for missing runtime pieces
- transparent fallback projection for time-series models using BOS forecast logic
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Any
import urllib.request
from urllib.parse import urlparse
import zipfile

from app.config import get_settings
from app.engine.forecast import ForecastInput, run_forecast
from app.models import Batch
from app.services.bos_native_models import build_native_model_catalog

settings = get_settings()

VISION_MODEL_KEYS = {"yolo11_dsconv", "insectsam", "insecta"}
TIME_SERIES_MODEL_KEYS = {"timer_s1", "chronos_bolt"}

MODEL_DEPENDENCIES: dict[str, list[str]] = {
    "yolo11_dsconv": ["torch", "ultralytics"],
    "insectsam": ["torch", "transformers"],
    "insecta": ["onnxruntime", "cv2", "huggingface_hub"],
    "timer_s1": ["torch", "transformers"],
    "chronos_bolt": ["torch", "transformers"],
}

MODEL_INPUTS: dict[str, list[str]] = {
    "yolo11_dsconv": ["image_path", "image_url", "camera_frame_ref"],
    "insectsam": ["image_path", "image_url", "camera_frame_ref"],
    "insecta": ["image_path", "image_url", "camera_frame_ref"],
    "timer_s1": ["sensor_history", "horizon", "metric_name"],
    "chronos_bolt": ["sensor_history", "horizon", "metric_name"],
}

ZENODO_RECORDS: dict[str, str] = {
    "yolo11_dsconv": "15044013",
}

HF_MODEL_REFS: dict[str, str] = {
    "insectsam": "martintomov/InsectSAM",
    "insecta": "Genius-Society/insecta",
    "timer_s1": settings.BOS_NATIVE_TIMER_S1_MODEL_REF,
    "chronos_bolt": settings.BOS_NATIVE_CHRONOS_BOLT_MODEL_REF,
}


def _cache_root() -> Path:
    return Path(settings.BOS_NATIVE_MODELS_CACHE_DIR)


def _runs_root() -> Path:
    return _cache_root() / "runs"


def _yolo_companions_root() -> Path:
    return _cache_root() / "yolo11-companions"


def _input_cache_root() -> Path:
    return _cache_root() / "tmp-inputs"


def _find_first(root: Path, pattern: str) -> Path | None:
    matches = list(root.rglob(pattern))
    return matches[0] if matches else None


def _persist_inference_result(
    *,
    model_key: str,
    execution_mode: str,
    payload_echo: dict[str, Any],
    result: dict[str, Any],
    warnings: list[str],
) -> str:
    run_dir = _runs_root() / model_key
    run_dir.mkdir(parents=True, exist_ok=True)
    target_path = run_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{execution_mode}.json"
    target_path.write_text(
        json.dumps(
            {
                "model_key": model_key,
                "execution_mode": execution_mode,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "payload_echo": payload_echo,
                "result": result,
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return str(target_path)


def list_native_inference_runs(
    *,
    model_key: str | None = None,
    batch_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    runs_root = _runs_root()
    if not runs_root.exists():
        return []

    candidates: list[Path] = []
    if model_key:
        target_dir = runs_root / model_key
        if target_dir.exists():
            candidates = sorted(target_dir.glob("*.json"), reverse=True)
    else:
        candidates = sorted(runs_root.rglob("*.json"), reverse=True)

    artifacts: list[dict[str, Any]] = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload_batch_id = (
            ((payload.get("result") or {}).get("batch_context") or {}).get("batch_id")
        )
        if batch_id is not None and payload_batch_id != batch_id:
            continue
        artifacts.append(
            {
                "model_key": payload.get("model_key", path.parent.name),
                "execution_mode": payload.get("execution_mode", "unknown"),
                "recorded_at": payload.get("recorded_at", ""),
                "artifact_path": str(path),
                "payload_echo": payload.get("payload_echo", {}),
                "result": payload.get("result", {}),
                "warnings": payload.get("warnings", []),
            }
        )
        if len(artifacts) >= max(limit, 1):
            break
    return artifacts


def summarize_latest_native_run(
    *,
    batch_id: int | None = None,
    model_key: str | None = None,
) -> dict[str, Any] | None:
    runs = list_native_inference_runs(model_key=model_key, batch_id=batch_id, limit=1)
    if not runs:
        return None
    latest = runs[0]
    result = latest.get("result") or {}
    raw_preview = result.get("forecast_preview")
    if not isinstance(raw_preview, list):
        raw_preview = (result.get("forecast") or [])[:4] if isinstance(result.get("forecast"), list) else []
    prediction_horizon = result.get("prediction_horizon")
    if not isinstance(prediction_horizon, int):
        forecast = result.get("forecast")
        prediction_horizon = len(forecast) if isinstance(forecast, list) else None
    latest_model_key = latest["model_key"]
    modality = "vision" if latest_model_key in VISION_MODEL_KEYS else "time-series"
    if latest_model_key == "chronos_bolt":
        evidence_tier = "stabilized_live_timeseries"
        evidence_label = "Stabilized live timeseries"
    elif latest_model_key == "timer_s1":
        evidence_tier = "gated_timeseries_fallback"
        evidence_label = "Gated timeseries fallback"
    elif latest_model_key == "insecta":
        evidence_tier = "bootstrap_public_vision"
        evidence_label = "Bootstrap public vision"
    elif latest_model_key == "yolo11_dsconv":
        evidence_tier = "specialized_bsf_vision"
        evidence_label = "Specialized BSF vision"
    else:
        evidence_tier = "native_model_evidence"
        evidence_label = "Native model evidence"

    if latest_model_key in TIME_SERIES_MODEL_KEYS:
        metric_name = result.get("metric_name") if isinstance(result.get("metric_name"), str) else "sensor_metric"
        preview_text = ", ".join(str(item) for item in raw_preview[:3]) if raw_preview else "no preview"
        evidence_summary = f"{metric_name} · horizon {prediction_horizon or 'N/A'} · {preview_text}"
    else:
        detection_count = result.get("detection_count") if isinstance(result.get("detection_count"), int) else None
        detections = result.get("detections") if isinstance(result.get("detections"), list) else []
        top_label = None
        top_candidates: list[str] = []
        bbox_summary = None
        if detections:
            first = detections[0]
            if isinstance(first, dict):
                top_label = first.get("top_label")
                bbox = first.get("bbox_xyxy")
                if isinstance(bbox, list):
                    bbox_summary = ", ".join(str(item) for item in bbox)
                candidates = first.get("species_candidates")
                if isinstance(candidates, list):
                    top_candidates = [
                        str(candidate.get("label"))
                        for candidate in candidates[:5]
                        if isinstance(candidate, dict) and candidate.get("label") is not None
                    ]
        evidence_summary = (
            f"{detection_count or 0} detections · top label {top_label}"
            if top_label
            else f"{detection_count or 0} detections"
        )

    return {
        "model_key": latest["model_key"],
        "modality": modality,
        "evidence_tier": evidence_tier,
        "evidence_label": evidence_label,
        "evidence_summary": evidence_summary,
        "execution_mode": latest["execution_mode"],
        "recorded_at": latest["recorded_at"],
        "artifact_path": latest["artifact_path"],
        "metric_name": result.get("metric_name") if isinstance(result.get("metric_name"), str) else None,
        "prediction_horizon": prediction_horizon,
        "forecast_preview": [str(item) for item in raw_preview],
        "detection_count": detection_count if modality == "vision" else None,
        "top_label": top_label if modality == "vision" else None,
        "top_candidates": top_candidates if modality == "vision" else [],
        "bbox_summary": bbox_summary if modality == "vision" else None,
        "is_live": "live" in latest["execution_mode"],
    }


def _resolve_yolo_weight_path() -> Path | None:
    artifact = _artifact_contract("yolo11_dsconv")
    configured = artifact.get("configured_location")
    if configured and str(configured).lower().endswith(".pt"):
        candidate = Path(configured)
        if candidate.exists():
            return candidate
    bundle_root = _cache_root() / "yolo11-dsconv"
    if bundle_root.exists():
        direct_weight = _find_first(bundle_root, "*.pt")
        if direct_weight is not None:
            return direct_weight
    companions_root = _yolo_companions_root()
    if companions_root.exists():
        best_weight = _find_first(companions_root, "best.pt")
        if best_weight is not None:
            return best_weight
    return None


def _resolve_insecta_assets() -> dict[str, Path] | None:
    root = _cache_root() / "insecta"
    if not root.exists():
        return None
    detector = root / "quarrying_insect_detector.onnx"
    identifier = root / "quarrying_insect_identifier.onnx"
    label_map = root / "quarrying_insectid_label_map.txt"
    if detector.exists() and identifier.exists() and label_map.exists():
        return {
            "detector": detector,
            "identifier": identifier,
            "label_map": label_map,
        }
    return None


def _load_image_rgb(image_path: str) -> tuple[Any, tuple[int, int]]:
    import cv2
    import numpy as np

    data = np.frombuffer(Path(image_path).read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"unable_to_decode_image:{image_path}")
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return rgb, (image.shape[1], image.shape[0])


def _materialize_image_path(payload: dict[str, Any], *, model_key: str) -> str | None:
    image_path_value = payload.get("image_path")
    if isinstance(image_path_value, str) and Path(image_path_value).exists():
        return image_path_value

    image_url_value = payload.get("image_url")
    if isinstance(image_url_value, str) and image_url_value.startswith(("http://", "https://")):
        parsed = urlparse(image_url_value)
        suffix = Path(parsed.path).suffix or ".jpg"
        target_dir = _input_cache_root() / model_key
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{suffix}"
        with urllib.request.urlopen(image_url_value) as response, target_path.open("wb") as out:
            shutil.copyfileobj(response, out)
        return str(target_path)

    return None


def _artifact_contract(model_key: str) -> dict[str, Any]:
    cache_root = _cache_root()
    if model_key == "yolo11_dsconv":
        configured = settings.BOS_NATIVE_YOLO11_DSCONV_WEIGHTS_PATH or None
        bundle_root = cache_root / "yolo11-dsconv"
        companions_root = _yolo_companions_root()
        discovered_weight = _find_first(bundle_root, "*.pt") if bundle_root.exists() else None
        companion_weight = _find_first(companions_root, "best.pt") if companions_root.exists() else None
        discovered_code_bundle = _find_first(bundle_root, "pyproject.toml") if bundle_root.exists() else None
        companion_server_main = _find_first(companions_root, "main.py") if companions_root.exists() else None
        expected = (
            companion_server_main.parent / "models" / "YOLO11-DSConv-model" / "best.pt"
            if companion_server_main is not None
            else bundle_root / "yolo11-dsconv_bsf.pt"
        )
        source_reference = "https://zenodo.org/records/15044013"
    elif model_key == "insectsam":
        expected = cache_root / "insectsam"
        configured = settings.BOS_NATIVE_INSECTSAM_MODEL_PATH or (str(expected) if expected.exists() else None)
        source_reference = "https://huggingface.co/martintomov/InsectSAM"
    elif model_key == "insecta":
        expected = cache_root / "insecta"
        configured = settings.BOS_NATIVE_INSECTA_MODEL_PATH or (str(expected) if expected.exists() else None)
        source_reference = "https://huggingface.co/Genius-Society/insecta"
    elif model_key == "timer_s1":
        expected = cache_root / "timer-s1"
        configured = str(expected) if expected.exists() else (settings.BOS_NATIVE_TIMER_S1_MODEL_REF or None)
        source_reference = settings.BOS_NATIVE_TIMER_S1_MODEL_REF
    elif model_key == "chronos_bolt":
        expected = cache_root / "chronos-bolt"
        configured = str(expected) if expected.exists() else (settings.BOS_NATIVE_CHRONOS_BOLT_MODEL_REF or None)
        source_reference = settings.BOS_NATIVE_CHRONOS_BOLT_MODEL_REF
    else:
        raise ValueError(f"unsupported_model_key:{model_key}")

    is_local_path = bool(
        configured
        and "://" not in configured
        and ("/" in configured or "\\" in configured)
    )
    configured_path = Path(configured) if is_local_path else None
    if model_key == "yolo11_dsconv":
        exists = bool(
            (configured_path and configured_path.exists())
            or discovered_weight
            or companion_weight
            or discovered_code_bundle
        )
        configured_location = (
            configured
            or (str(discovered_weight) if discovered_weight else None)
            or (str(companion_weight) if companion_weight else None)
            or (str(discovered_code_bundle.parent) if discovered_code_bundle else None)
        )
        artifact_kind = (
            "weight_file"
            if discovered_weight or companion_weight or (configured_path and configured_path.suffix == ".pt")
            else "code_bundle"
        )
    else:
        exists = configured_path.exists() if configured_path else expected.exists()
        configured_location = configured
        artifact_kind = "model_snapshot"
    return {
        "expected_location": str(expected),
        "configured_location": configured_location,
        "exists": exists,
        "source_reference": source_reference,
        "artifact_kind": artifact_kind,
    }


def _dependency_contract(model_key: str) -> list[dict[str, Any]]:
    return [
        {
            "package": package,
            "installed": find_spec(package) is not None,
        }
        for package in MODEL_DEPENDENCIES.get(model_key, [])
    ]


def _download_plan(model_key: str) -> dict[str, Any]:
    artifact = _artifact_contract(model_key)
    target_path = artifact["expected_location"]
    notes: list[str] = []
    if model_key in ZENODO_RECORDS:
        source_kind = "zenodo_record"
        source_reference = f"https://zenodo.org/records/{ZENODO_RECORDS[model_key]}"
        notes.append("BOS will resolve the Zenodo record through the official Zenodo API and download the primary file.")
        if model_key == "yolo11_dsconv":
            notes.append("The companion server package expects the BSF weight at ./models/YOLO11-DSConv-model/best.pt.")
    elif model_key in HF_MODEL_REFS:
        source_kind = "huggingface_snapshot"
        source_reference = HF_MODEL_REFS[model_key]
        if find_spec("huggingface_hub") is None:
            notes.append("Install huggingface_hub to enable managed Hugging Face snapshot downloads.")
        if model_key == "timer_s1" and not settings.BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD:
            notes.append("Timer-S1 download is intentionally gated. Enable BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD to allow managed download.")
    else:
        source_kind = "unsupported"
        source_reference = artifact["source_reference"]
        notes.append("No managed downloader is registered for this model.")

    return {
        "model_key": model_key,
        "supported": source_kind != "unsupported",
        "source_kind": source_kind,
        "source_reference": source_reference,
        "target_path": target_path,
        "notes": notes,
    }


def build_native_download_plan(*, model_key: str | None = None) -> list[dict[str, Any]]:
    keys = [model_key] if model_key else [item["key"] for item in build_native_model_catalog()["models"]]
    return [_download_plan(key) for key in keys]


def _download_file(url: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, target_path.open("wb") as target:
        shutil.copyfileobj(response, target)


def _download_zenodo_record(model_key: str) -> tuple[str, str | None]:
    record_id = ZENODO_RECORDS[model_key]
    api_url = f"https://zenodo.org/api/records/{record_id}"
    with urllib.request.urlopen(api_url) as response:
        payload = json.load(response)
    files = payload.get("files") or []
    if not files:
        raise RuntimeError(f"zenodo_record_has_no_files:{record_id}")
    primary_file = files[0]
    download_url = primary_file["links"]["self"]
    target_path = _cache_root() / "yolo11-dsconv" / primary_file["key"].split("/")[-1]
    _download_file(download_url, target_path)
    extracted_path = None
    if target_path.suffix.lower() == ".zip":
        extract_dir = target_path.parent / target_path.stem
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target_path, "r") as archive:
            archive.extractall(extract_dir)
        extracted_path = str(extract_dir)
    return str(target_path), extracted_path


def _download_hf_snapshot(model_key: str) -> tuple[str, str | None]:
    if find_spec("huggingface_hub") is None:
        raise RuntimeError("missing_dependency:huggingface_hub")
    from huggingface_hub import snapshot_download

    repo_id = HF_MODEL_REFS[model_key]
    local_dir = _cache_root() / model_key.replace("_", "-")
    snapshot_download(repo_id=repo_id, local_dir=str(local_dir))
    return str(local_dir), str(local_dir)


def download_native_model_artifact(*, model_key: str) -> dict[str, Any]:
    plan = _download_plan(model_key)
    if not plan["supported"]:
        return {
            "model_key": model_key,
            "downloaded": False,
            "runtime_state": "unsupported",
            "target_path": plan["target_path"],
            "source_reference": plan["source_reference"],
            "detail": "No managed downloader is registered for this model.",
            "extracted_path": None,
        }

    if model_key == "timer_s1" and not settings.BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD:
        raise RuntimeError("timer_s1_download_disabled_enable_BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD")

    if plan["source_kind"] == "zenodo_record":
        target_path, extracted_path = _download_zenodo_record(model_key)
    elif plan["source_kind"] == "huggingface_snapshot":
        target_path, extracted_path = _download_hf_snapshot(model_key)
    else:
        raise RuntimeError(f"unsupported_source_kind:{plan['source_kind']}")

    runtime_entry = _runtime_entry({"key": model_key, "modality": "vision" if model_key in VISION_MODEL_KEYS else "time-series"})
    return {
        "model_key": model_key,
        "downloaded": True,
        "runtime_state": runtime_entry["runtime_state"],
        "target_path": target_path,
        "source_reference": plan["source_reference"],
        "detail": "Artifact downloaded into the BOS native model cache.",
        "extracted_path": extracted_path,
    }


def _runtime_entry(model: dict[str, Any]) -> dict[str, Any]:
    model_key = model["key"]
    artifact = _artifact_contract(model_key)
    dependencies = _dependency_contract(model_key)
    deps_ready = all(item["installed"] for item in dependencies) if dependencies else True
    modality = model["modality"]

    live_ready = False
    if model_key == "yolo11_dsconv" and deps_ready:
        live_ready = _resolve_yolo_weight_path() is not None
    if model_key == "insecta" and deps_ready:
        live_ready = _resolve_insecta_assets() is not None
    if model_key == "chronos_bolt" and deps_ready and (
        artifact["exists"] or settings.BOS_NATIVE_MODELS_ALLOW_REMOTE_REFERENCES
    ):
        live_ready = find_spec("chronos") is not None and find_spec("torch") is not None

    if not settings.BOS_NATIVE_MODELS_ENABLED:
        runtime_state = "disabled"
    elif live_ready:
        runtime_state = "live_adapter_ready"
    elif not deps_ready:
        runtime_state = "missing_dependencies"
    elif model_key == "yolo11_dsconv" and artifact["exists"] and artifact.get("artifact_kind") == "code_bundle":
        runtime_state = "code_bundle_detected"
    elif artifact["exists"]:
        runtime_state = "artifact_detected_contract_only"
    elif settings.BOS_NATIVE_MODELS_ALLOW_REMOTE_REFERENCES and model_key in TIME_SERIES_MODEL_KEYS:
        runtime_state = "remote_reference_contract_only"
    else:
        runtime_state = "awaiting_artifact"

    next_steps = []
    if runtime_state == "disabled":
        next_steps.append("Enable BOS_NATIVE_MODELS_ENABLED to expose runtime execution.")
    if runtime_state == "missing_dependencies":
        missing = [item["package"] for item in dependencies if not item["installed"]]
        next_steps.append(f"Install runtime packages: {', '.join(missing)}.")
    if not artifact["exists"]:
        next_steps.append(
            f"Place the model artifact under {artifact['expected_location']} or set a configured path/reference."
        )
    if model_key == "yolo11_dsconv" and runtime_state == "code_bundle_detected":
        next_steps.append(
            "The YOLO code bundle is present, but BOS still needs a .pt weight file for live inference. The companion server expects ./models/YOLO11-DSConv-model/best.pt."
        )
    if model_key == "timer_s1" and not settings.BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD:
        next_steps.append("Timer-S1 download is disabled by default because the model is large; enable BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD when you want a managed pull.")
    next_steps.append("Connect a model-specific execution adapter when you are ready for live inference.")

    adapter_status = "contract_with_forecast_fallback" if model_key in TIME_SERIES_MODEL_KEYS else "contract_only"
    return {
        "key": model_key,
        "ready": live_ready,
        "runtime_state": runtime_state,
        "modality": modality,
        "adapter_status": adapter_status,
        "artifact": artifact,
        "dependencies": dependencies,
        "expected_inputs": MODEL_INPUTS.get(model_key, []),
        "next_steps": next_steps,
    }


def build_native_runtime_status() -> dict[str, Any]:
    catalog = build_native_model_catalog()
    runtimes = [_runtime_entry(model) for model in catalog["models"]]
    ready_count = sum(1 for item in runtimes if item["ready"])
    return {
        "enabled": settings.BOS_NATIVE_MODELS_ENABLED,
        "cache_dir": str(_cache_root()),
        "summary": {
            "total_models": len(runtimes),
            "ready_models": ready_count,
            "contract_only_models": sum(1 for item in runtimes if item["adapter_status"].startswith("contract")),
            "missing_dependency_models": sum(1 for item in runtimes if item["runtime_state"] == "missing_dependencies"),
        },
        "runtimes": runtimes,
    }


def _batch_context(batch: Batch | None) -> dict[str, Any]:
    if batch is None:
        return {}
    return {
        "batch_id": batch.id,
        "batch_label": batch.batch_id,
        "species": batch.species,
        "temperature": batch.temperature,
        "moisture": batch.moisture,
        "feed_rate": batch.feed_rate,
        "density": batch.density,
    }


def run_native_inference_contract(
    *,
    model_key: str,
    payload: dict[str, Any],
    batch: Batch | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    runtime_status = build_native_runtime_status()
    runtime_entry = next((item for item in runtime_status["runtimes"] if item["key"] == model_key), None)
    if runtime_entry is None:
        raise ValueError(f"unsupported_model_key:{model_key}")

    if dry_run:
        payload_result = {
            "accepted_inputs": runtime_entry["expected_inputs"],
            "batch_context": _batch_context(batch),
            "adapter_status": runtime_entry["adapter_status"],
        }
        warnings = [
            "This is a dry run. BOS is returning the runtime contract and readiness only.",
        ]
        artifact_path = _persist_inference_result(
            model_key=model_key,
            execution_mode="dry_run_contract",
            payload_echo=payload,
            result=payload_result,
            warnings=warnings,
        )
        return {
            "model_key": model_key,
            "batch_id": batch.id if batch else None,
            "ready": runtime_entry["ready"],
            "runtime_state": runtime_entry["runtime_state"],
            "execution_mode": "dry_run_contract",
            "payload_echo": payload,
            "result": {**payload_result, "artifact_path": artifact_path},
            "warnings": warnings,
            "next_steps": runtime_entry["next_steps"],
        }

    if model_key == "yolo11_dsconv":
        image_path_value = _materialize_image_path(payload, model_key=model_key)
        weight_path = _resolve_yolo_weight_path()
        if (
            weight_path is not None
            and image_path_value is not None
            and find_spec("ultralytics") is not None
        ):
            from ultralytics import YOLO

            detector = YOLO(str(weight_path))
            prediction = detector.predict(source=image_path_value, verbose=False)
            detections: list[dict[str, Any]] = []
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
                        detections.append(
                            {
                                "class_id": class_id,
                                "label": names.get(class_id, str(class_id)),
                                "confidence": conf_values[index] if index < len(conf_values) else None,
                                "bbox_xyxy": xyxy_values[index] if index < len(xyxy_values) else None,
                            }
                        )
            payload_result = {
                "image_path": image_path_value,
                "weight_path": str(weight_path),
                "detections": detections,
                "detection_count": len(detections),
                "top_label": detections[0]["label"] if detections else None,
                "top_candidates": [item["label"] for item in detections[:5] if isinstance(item, dict) and item.get("label")],
                "bbox_summary": ", ".join(str(item) for item in detections[0]["bbox_xyxy"]) if detections and detections[0].get("bbox_xyxy") else None,
                "batch_context": _batch_context(batch),
            }
            artifact_path = _persist_inference_result(
                model_key=model_key,
                execution_mode="yolo11_dsconv_live",
                payload_echo=payload,
                result=payload_result,
                warnings=[],
            )
            return {
                "model_key": model_key,
                "batch_id": batch.id if batch else None,
                "ready": True,
                "runtime_state": "live_adapter_ready",
                "execution_mode": "yolo11_dsconv_live",
                "payload_echo": payload,
                "result": {**payload_result, "artifact_path": artifact_path},
                "warnings": [],
                "next_steps": [],
            }

    if model_key == "insecta":
        image_path_value = _materialize_image_path(payload, model_key=model_key)
        assets = _resolve_insecta_assets()
        if (
            assets is not None
            and image_path_value is not None
            and find_spec("onnxruntime") is not None
        ):
            import cv2
            import numpy as np
            import onnxruntime as ort

            rgb, (width, height) = _load_image_rgb(image_path_value)

            detector_session = ort.InferenceSession(str(assets["detector"]), providers=["CPUExecutionProvider"])
            detector_input = cv2.resize(rgb, (640, 640)).astype("float32") / 255.0
            detector_input = np.transpose(detector_input, (2, 0, 1))[None, ...]
            detector_output = detector_session.run(None, {detector_session.get_inputs()[0].name: detector_input})[0][0]

            boxes: list[list[float]] = []
            scores: list[float] = []
            for row in detector_output:
                score = float(row[4])
                if score < float(payload.get("confidence_threshold", 0.35)):
                    continue
                x1 = max(0.0, min(float(row[0]) * width / 640.0, width))
                y1 = max(0.0, min(float(row[1]) * height / 640.0, height))
                x2 = max(0.0, min(float(row[2]) * width / 640.0, width))
                y2 = max(0.0, min(float(row[3]) * height / 640.0, height))
                w = max(0.0, x2 - x1)
                h = max(0.0, y2 - y1)
                if w <= 1 or h <= 1:
                    continue
                boxes.append([x1, y1, w, h])
                scores.append(score)

            selected_indexes = cv2.dnn.NMSBoxes(
                bboxes=boxes,
                scores=scores,
                score_threshold=float(payload.get("confidence_threshold", 0.35)),
                nms_threshold=float(payload.get("nms_threshold", 0.45)),
            )
            if len(selected_indexes) == 0:
                selected_flat: list[int] = []
            else:
                selected_flat = [int(item) for item in np.array(selected_indexes).reshape(-1).tolist()]

            label_map = assets["label_map"].read_text(encoding="utf-8", errors="ignore").splitlines()
            labels = [line.split(",", 1)[1] if "," in line else line for line in label_map]
            classifier_session = ort.InferenceSession(str(assets["identifier"]), providers=["CPUExecutionProvider"])

            detections: list[dict[str, Any]] = []
            for idx in selected_flat[: int(payload.get("max_detections", 3))]:
                x, y, w, h = boxes[idx]
                x1 = int(max(0, x))
                y1 = int(max(0, y))
                x2 = int(min(width, x + w))
                y2 = int(min(height, y + h))
                crop = rgb[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                identifier_input = cv2.resize(crop, (224, 224)).astype("float32") / 255.0
                identifier_input = np.transpose(identifier_input, (2, 0, 1))[None, ...]
                logits = classifier_session.run(None, {classifier_session.get_inputs()[0].name: identifier_input})[0][0]
                top_indices = np.argsort(logits)[-5:][::-1]
                species_candidates = [
                    {
                        "class_id": int(class_index),
                        "label": labels[int(class_index)] if int(class_index) < len(labels) else str(class_index),
                        "score": float(logits[int(class_index)]),
                    }
                    for class_index in top_indices
                ]
                detections.append(
                    {
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "confidence": scores[idx],
                        "species_candidates": species_candidates,
                        "top_label": species_candidates[0]["label"] if species_candidates else None,
                    }
                )

            payload_result = {
                "image_path": image_path_value,
                "detector_path": str(assets["detector"]),
                "identifier_path": str(assets["identifier"]),
                "detection_count": len(detections),
                "detections": detections,
                "top_label": detections[0]["top_label"] if detections else None,
                "top_candidates": detections[0]["species_candidates"][:5] if detections and detections[0].get("species_candidates") else [],
                "bbox_summary": ", ".join(str(item) for item in detections[0]["bbox_xyxy"]) if detections and detections[0].get("bbox_xyxy") else None,
                "execution_mode": "insecta_bootstrap_live",
                "batch_context": _batch_context(batch),
            }
            artifact_path = _persist_inference_result(
                model_key=model_key,
                execution_mode="insecta_bootstrap_live",
                payload_echo=payload,
                result=payload_result,
                warnings=[],
            )
            return {
                "model_key": model_key,
                "batch_id": batch.id if batch else None,
                "ready": True,
                "runtime_state": "live_adapter_ready",
                "execution_mode": "insecta_bootstrap_live",
                "payload_echo": payload,
                "result": {**payload_result, "artifact_path": artifact_path},
                "warnings": [],
                "next_steps": [],
            }

    if model_key == "chronos_bolt":
        local_chronos_dir = _cache_root() / "chronos-bolt"
        chronos_ref = str(local_chronos_dir) if local_chronos_dir.exists() else settings.BOS_NATIVE_CHRONOS_BOLT_MODEL_REF
        if (
            find_spec("chronos") is not None
            and find_spec("torch") is not None
            and isinstance(payload.get("sensor_history"), list)
            and len(payload["sensor_history"]) >= 2
        ):
            import torch
            from chronos import ChronosBoltPipeline

            series = torch.tensor([float(item) for item in payload["sensor_history"]], dtype=torch.float32)
            pipeline = ChronosBoltPipeline.from_pretrained(chronos_ref)
            prediction_length = int(payload.get("horizon", 6))
            quantiles = pipeline.predict(series, prediction_length=prediction_length)
            if hasattr(quantiles, "detach"):
                quantiles = quantiles.detach().cpu().numpy()
            values = quantiles.tolist() if hasattr(quantiles, "tolist") else quantiles
            median = values[0][1] if values and isinstance(values[0], list) and len(values[0]) > 1 else values
            payload_result = {
                "metric_name": payload.get("metric_name", "sensor_metric"),
                "forecast": median,
                "forecast_preview": median[:4] if isinstance(median, list) else median,
                "prediction_horizon": prediction_length,
                "quantiles": values,
                "model_ref": chronos_ref,
                "execution_mode": "chronos_bolt_live",
                "batch_context": _batch_context(batch),
            }
            artifact_path = _persist_inference_result(
                model_key=model_key,
                execution_mode="chronos_bolt_live",
                payload_echo=payload,
                result=payload_result,
                warnings=[],
            )
            return {
                "model_key": model_key,
                "batch_id": batch.id if batch else None,
                "ready": True,
                "runtime_state": "live_adapter_ready",
                "execution_mode": "chronos_bolt_live",
                "payload_echo": payload,
                "result": {**payload_result, "artifact_path": artifact_path},
                "warnings": [],
                "next_steps": [],
            }

    if model_key in TIME_SERIES_MODEL_KEYS:
        sensor_history = payload.get("sensor_history")
        if isinstance(sensor_history, list) and len(sensor_history) >= 2:
            values = [float(item) for item in sensor_history]
            horizon = int(payload.get("horizon", 6))
            method = "holt_winters" if model_key == "timer_s1" else "ewma"
            forecast = run_forecast(ForecastInput(values=values, method=method, horizon=horizon))
            payload_result = {
                "metric_name": payload.get("metric_name", "sensor_metric"),
                "forecast": forecast.forecast,
                "forecast_preview": forecast.forecast[:4],
                "prediction_horizon": horizon,
                "ci_lower": forecast.ci_lower,
                "ci_upper": forecast.ci_upper,
                "fallback_method": method,
                "execution_mode": "bos_fallback_projection",
                "batch_context": _batch_context(batch),
            }
            warnings = [
                "Frontier model runtime is not wired yet; BOS used the built-in forecast engine as a transparent fallback.",
            ]
            artifact_path = _persist_inference_result(
                model_key=model_key,
                execution_mode="bos_fallback_projection",
                payload_echo=payload,
                result=payload_result,
                warnings=warnings,
            )
            return {
                "model_key": model_key,
                "batch_id": batch.id if batch else None,
                "ready": runtime_entry["ready"],
                "runtime_state": runtime_entry["runtime_state"],
                "execution_mode": "bos_fallback_projection",
                "payload_echo": payload,
                "result": {**payload_result, "artifact_path": artifact_path},
                "warnings": warnings,
                "next_steps": runtime_entry["next_steps"],
            }

    payload_result = {
        "accepted_inputs": runtime_entry["expected_inputs"],
        "batch_context": _batch_context(batch),
    }
    warnings = [
        "Live frontier inference is not available for this model yet in the current runtime state.",
    ]
    artifact_path = _persist_inference_result(
        model_key=model_key,
        execution_mode="runtime_unavailable",
        payload_echo=payload,
        result=payload_result,
        warnings=warnings,
    )
    return {
        "model_key": model_key,
        "batch_id": batch.id if batch else None,
        "ready": runtime_entry["ready"],
        "runtime_state": runtime_entry["runtime_state"],
        "execution_mode": "runtime_unavailable",
        "payload_echo": payload,
        "result": {**payload_result, "artifact_path": artifact_path},
        "warnings": warnings,
        "next_steps": runtime_entry["next_steps"],
    }
