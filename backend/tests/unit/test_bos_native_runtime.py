from types import SimpleNamespace

from io import BytesIO
from pathlib import Path
import urllib.request

from app.services.bos_native_runtime import (
    build_native_download_plan,
    build_native_runtime_status,
    _materialize_image_path,
    run_native_inference_contract,
)


def test_native_runtime_status_exposes_runtime_entries():
    payload = build_native_runtime_status()

    assert "runtimes" in payload
    assert any(item["key"] == "timer_s1" for item in payload["runtimes"])
    assert payload["summary"]["total_models"] >= 5
    insecta = next(item for item in payload["runtimes"] if item["key"] == "insecta")
    assert insecta["runtime_state"] in {"live_adapter_ready", "artifact_detected_contract_only", "missing_dependencies"}


def test_native_runtime_contract_returns_dry_run_preview():
    batch = SimpleNamespace(
        id=12,
        batch_id="B-12",
        species="BSF",
        temperature=28.0,
        moisture=66.0,
        feed_rate=1.3,
        density=4.0,
    )

    result = run_native_inference_contract(
        model_key="yolo11_dsconv",
        payload={"image_path": "frame.jpg"},
        batch=batch,
        dry_run=True,
    )

    assert result["execution_mode"] == "dry_run_contract"
    assert "accepted_inputs" in result["result"]
    assert result["batch_id"] == 12


def test_native_runtime_contract_runs_live_or_fallback_for_chronos_bolt():
    result = run_native_inference_contract(
        model_key="chronos_bolt",
        payload={"sensor_history": [1.0, 1.2, 1.4, 1.5], "horizon": 3},
        batch=None,
        dry_run=False,
    )

    assert result["execution_mode"] in {"bos_fallback_projection", "chronos_bolt_live"}
    assert len(result["result"]["forecast"]) == 3
    assert isinstance(result["result"]["artifact_path"], str)
    assert "forecast_preview" in result["result"]
    assert "prediction_horizon" in result["result"]


def test_native_runtime_contract_uses_forecast_fallback_for_timer_s1():
    result = run_native_inference_contract(
        model_key="timer_s1",
        payload={"sensor_history": [1.0, 1.2, 1.4, 1.5], "horizon": 3},
        batch=None,
        dry_run=False,
    )

    assert result["execution_mode"] == "bos_fallback_projection"
    assert len(result["result"]["forecast"]) == 3
    assert isinstance(result["result"]["artifact_path"], str)
    assert result["result"]["prediction_horizon"] == 3


def test_native_download_plan_exposes_hf_and_zenodo_sources():
    plan = build_native_download_plan()

    assert any(item["model_key"] == "chronos_bolt" for item in plan)
    assert any(item["model_key"] == "yolo11_dsconv" for item in plan)


def test_native_download_plan_flags_timer_s1_as_gated():
    plan = build_native_download_plan(model_key="timer_s1")

    assert plan[0]["model_key"] == "timer_s1"
    assert any("Enable BOS_NATIVE_TIMER_S1_ENABLE_DOWNLOAD" in note for note in plan[0]["notes"])


def test_native_download_plan_mentions_yolo_companion_weight_path():
    plan = build_native_download_plan(model_key="yolo11_dsconv")

    assert plan[0]["model_key"] == "yolo11_dsconv"
    assert any("YOLO11-DSConv-model/best.pt" in note for note in plan[0]["notes"])


def test_yolo_runtime_becomes_live_ready_when_weight_path_exists(monkeypatch, tmp_path: Path):
    weight_path = tmp_path / "best.pt"
    weight_path.write_bytes(b"stub")

    from app.services import bos_native_runtime

    monkeypatch.setattr(
        bos_native_runtime.settings,
        "BOS_NATIVE_YOLO11_DSCONV_WEIGHTS_PATH",
        str(weight_path),
    )
    monkeypatch.setattr(
        bos_native_runtime,
        "find_spec",
        lambda package: object() if package in {"torch", "ultralytics"} else None,
    )

    status = bos_native_runtime.build_native_runtime_status()
    yolo = next(item for item in status["runtimes"] if item["key"] == "yolo11_dsconv")

    assert yolo["ready"] is True
    assert yolo["runtime_state"] == "live_adapter_ready"


def test_materialize_image_path_downloads_remote_image(monkeypatch, tmp_path: Path):
    from app.services import bos_native_runtime

    monkeypatch.setattr(
      bos_native_runtime,
      "_input_cache_root",
      lambda: tmp_path,
    )

    class _Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda _url: _Response(b"fake-image-bytes"),
    )

    resolved = _materialize_image_path({"image_url": "https://example.com/image.jpg"}, model_key="insecta")

    assert resolved is not None
    assert Path(resolved).exists()
    assert Path(resolved).read_bytes() == b"fake-image-bytes"
