from types import SimpleNamespace

from app.services.bos_native_models import build_native_model_catalog, build_native_model_embedding


def test_native_model_catalog_exposes_frontier_model_keys():
    payload = build_native_model_catalog()

    model_keys = {item["key"] for item in payload["models"]}
    assert {"yolo11_dsconv", "insectsam", "insecta", "timer_s1", "chronos_bolt"} <= model_keys
    assert payload["catalog_version"] == "BOS-NATIVE-2026.04"
    assert payload["recommendations"]


def test_native_model_catalog_prioritizes_bsf_loop_for_bsf_batches():
    batch = SimpleNamespace(
        species="BSF",
        temperature=28.0,
        moisture=68.0,
        feed_rate=1.8,
        density=4.2,
        dm_in=10.0,
        dm_out=2.6,
        n_in=0.5,
        n_larvae=None,
        n_frass=None,
    )

    payload = build_native_model_catalog(batch=batch, signal_batch=None)

    recommendation = next(
        item for item in payload["recommendations"] if item["key"] == "bsf_growth_harvest_loop"
    )
    assert recommendation["fit"] == "high"
    assert "yolo11_dsconv" in recommendation["model_keys"]


def test_native_model_embedding_exposes_primary_recommendation():
    payload = build_native_model_embedding()

    assert payload["catalog_version"] == "BOS-NATIVE-2026.04"
    assert payload["primary_recommendation"]["key"] == "vision_forecast_closed_loop"
    assert "yolo11_dsconv" in payload["model_keys"]
