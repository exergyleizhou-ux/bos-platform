from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.schemas import VisionDetection, VisionDetectionResponse, VisionObservation


def fake_vision_response() -> VisionDetectionResponse:
    observation = VisionObservation(
        image_id="vision-test-001",
        detected_classes=["larvae_cluster", "residue_patch"],
        detections=[
            VisionDetection(
                label="larvae_cluster",
                confidence=0.91,
                bbox=[10.0, 20.0, 120.0, 160.0],
            ),
            VisionDetection(
                label="residue_patch",
                confidence=0.73,
                bbox=[130.0, 40.0, 220.0, 180.0],
            ),
        ],
        dominant_label="larvae_cluster",
        confidence_mean=0.82,
        anomaly_flag=False,
        observation_summary="2 detections; dominant label larvae_cluster; mean confidence 0.82.",
        bbox_coverage_ratio=0.31,
    )
    return VisionDetectionResponse(
        run_id="run-test-001",
        created_at=datetime.now(UTC),
        image_id=observation.image_id,
        file_name="tray.png",
        content_type="image/png",
        model_name="yolo11n.pt",
        model_status="ultralytics_live",
        fallback_used=False,
        observation=observation,
        warnings=[],
        artifact_path="/tmp/vision-run.json",
        metadata={"phase": "operator_review", "supervisor_auto_execution": False},
    )


class TestBosVisionRouter:
    @pytest.mark.asyncio
    async def test_vision_detect_accepts_image_upload(
        self,
        client: AsyncClient,
        operator_headers,
        monkeypatch,
    ):
        captured: dict[str, object] = {}

        def fake_detect_image(**kwargs):
            captured.update(kwargs)
            return fake_vision_response()

        monkeypatch.setattr(
            "app.routers.bos.vision_detection_service.detect_image",
            fake_detect_image,
        )

        response = await client.post(
            "/api/v1/bos/vision/detect",
            files={"file": ("tray.png", b"fake-png-bytes", "image/png")},
            headers=operator_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["image_id"] == "vision-test-001"
        assert payload["observation"]["detected_classes"] == ["larvae_cluster", "residue_patch"]
        assert payload["observation"]["dominant_label"] == "larvae_cluster"
        assert payload["observation"]["confidence_mean"] == 0.82
        assert payload["observation"]["anomaly_flag"] is False
        assert payload["observation"]["detections"][0]["label"] == "larvae_cluster"
        assert payload["observation"]["detections"][0]["bbox"] == [10.0, 20.0, 120.0, 160.0]
        assert captured["content_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_vision_detect_rejects_non_image_upload(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.post(
            "/api/v1/bos/vision/detect",
            files={"file": ("notes.txt", b"not-an-image", "text/plain")},
            headers=operator_headers,
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Vision detection requires an image upload."

    @pytest.mark.asyncio
    async def test_vision_runs_returns_recent_observations(
        self,
        client: AsyncClient,
        operator_headers,
        monkeypatch,
    ):
        def fake_list_detection_runs(**kwargs):
            assert kwargs["limit"] == 5
            return [fake_vision_response()]

        monkeypatch.setattr(
            "app.routers.bos.vision_detection_service.list_detection_runs",
            fake_list_detection_runs,
        )

        response = await client.get(
            "/api/v1/bos/vision/runs?limit=5",
            headers=operator_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["observation"]["observation_summary"].startswith("2 detections")

    @pytest.mark.asyncio
    async def test_vision_run_can_attach_reviewed_observation_to_signal(
        self,
        client: AsyncClient,
        operator_headers,
        monkeypatch,
    ):
        batch_response = await client.post(
            "/api/v1/batches",
            json={
                "batch_id": "VISION-ATTACH-001",
                "dm_in": 10.0,
                "dm_out": 2.4,
                "temperature": 28.0,
                "moisture": 66.0,
            },
            headers=operator_headers,
        )
        assert batch_response.status_code == 201
        batch = batch_response.json()

        signal_response = await client.post(
            "/api/v1/signals",
            json={
                "batch_id": batch["id"],
                "signal_api_version": "SIG-1.0",
                "compiled_signal_id": "SIG-VISION-ATTACH-001",
                "potency": 0.22,
                "stability_window_hours": 8.0,
                "freshness_state": "Fresh",
            },
            headers=operator_headers,
        )
        assert signal_response.status_code == 201
        signal = signal_response.json()

        monkeypatch.setattr(
            "app.routers.bos.vision_detection_service.get_detection_run",
            lambda **_: fake_vision_response(),
        )
        monkeypatch.setattr(
            "app.routers.bos.refresh_audit_packet_for_signal",
            lambda **_: None,
        )

        response = await client.post(
            "/api/v1/bos/vision/runs/run-test-001/attach",
            json={"signal_batch_id": signal["id"]},
            headers=operator_headers,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["attached"] is True
        assert payload["signal_batch_id"] == signal["id"]
        assert payload["observation"]["dominant_label"] == "larvae_cluster"

        signals_response = await client.get("/api/v1/signals", headers=operator_headers)
        assert signals_response.status_code == 200
        updated_signal = next(item for item in signals_response.json() if item["id"] == signal["id"])
        vision_observation = updated_signal["qc_markers"]["vision_observation"]
        assert vision_observation["run_id"] == "run-test-001"
        assert vision_observation["dominant_label"] == "larvae_cluster"
        assert vision_observation["supervisor_auto_execution"] is False

    @pytest.mark.asyncio
    async def test_vision_detect_rejects_oversized_upload(
        self,
        client: AsyncClient,
        operator_headers,
    ):
        response = await client.post(
            "/api/v1/bos/vision/detect",
            files={"file": ("large.png", b"0" * (12 * 1024 * 1024 + 1), "image/png")},
            headers=operator_headers,
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "Uploaded image exceeds the 12MB phase-1 limit."
