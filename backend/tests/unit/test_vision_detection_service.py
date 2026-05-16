from pathlib import Path

from PIL import Image

from app.schemas import VisionDetection
from app.services import vision_detection_service


def make_png_bytes(path: Path) -> bytes:
    image = Image.new("RGB", (100, 80), color=(24, 32, 48))
    image.save(path, format="PNG")
    return path.read_bytes()


def test_detect_image_normalizes_ultralytics_output(tmp_path, monkeypatch):
    monkeypatch.setattr(vision_detection_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(vision_detection_service, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(vision_detection_service, "ARTIFACT_ROOT", tmp_path / "runs")

    def fake_infer(image_path: Path, *, model_name: str):
        assert image_path.exists()
        assert model_name
        return (
            [
                VisionDetection(label="larvae_cluster", confidence=0.9, bbox=[0, 0, 40, 40]),
                VisionDetection(label="foreign_object", confidence=0.7, bbox=[50, 10, 90, 50]),
            ],
            [],
            "ultralytics_live",
        )

    monkeypatch.setattr(vision_detection_service, "_infer_with_ultralytics", fake_infer)
    file_bytes = make_png_bytes(tmp_path / "source.png")

    response = vision_detection_service.detect_image(
        file_bytes=file_bytes,
        file_name="tray.png",
        content_type="image/png",
        tenant_id=7,
    )

    assert response.model_status == "ultralytics_live"
    assert response.fallback_used is False
    assert response.observation.image_id == response.image_id
    assert response.observation.detected_classes == ["foreign_object", "larvae_cluster"]
    assert response.observation.dominant_label == "larvae_cluster"
    assert response.observation.confidence_mean == 0.8
    assert response.observation.anomaly_flag is True
    assert response.observation.bbox_coverage_ratio == 0.4
    assert response.artifact_path is not None
    assert Path(response.artifact_path).exists()


def test_detect_image_returns_reviewable_fallback_when_inference_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(vision_detection_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(vision_detection_service, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(vision_detection_service, "ARTIFACT_ROOT", tmp_path / "runs")

    def fail_infer(image_path: Path, *, model_name: str):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(vision_detection_service, "_infer_with_ultralytics", fail_infer)
    file_bytes = make_png_bytes(tmp_path / "source.png")

    response = vision_detection_service.detect_image(
        file_bytes=file_bytes,
        file_name="tray with spaces.png",
        content_type="image/png",
        tenant_id=7,
    )

    assert response.model_status == "fallback_empty_observation"
    assert response.fallback_used is True
    assert response.observation.detections == []
    assert response.observation.detected_classes == []
    assert response.observation.dominant_label is None
    assert response.observation.confidence_mean is None
    assert response.observation.anomaly_flag is False
    assert response.warnings
    assert "model unavailable" in response.warnings[0]


def test_list_detection_runs_filters_by_tenant(tmp_path, monkeypatch):
    monkeypatch.setattr(vision_detection_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(vision_detection_service, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(vision_detection_service, "ARTIFACT_ROOT", tmp_path / "runs")

    def fake_infer(image_path: Path, *, model_name: str):
        return ([VisionDetection(label="larvae_cluster", confidence=0.9, bbox=[0, 0, 10, 10])], [], "ultralytics_live")

    monkeypatch.setattr(vision_detection_service, "_infer_with_ultralytics", fake_infer)
    file_bytes = make_png_bytes(tmp_path / "source.png")

    visible = vision_detection_service.detect_image(
        file_bytes=file_bytes,
        file_name="visible.png",
        content_type="image/png",
        tenant_id=7,
    )
    vision_detection_service.detect_image(
        file_bytes=file_bytes,
        file_name="hidden.png",
        content_type="image/png",
        tenant_id=8,
    )

    runs = vision_detection_service.list_detection_runs(tenant_id=7, limit=10)

    assert [item.run_id for item in runs] == [visible.run_id]
