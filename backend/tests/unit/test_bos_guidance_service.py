from types import SimpleNamespace

from app.services.bos_guidance_service import build_batch_guidance


def make_batch(**overrides):
    defaults = {
        "id": 1,
        "dm_in": 10.0,
        "dm_out": 3.0,
        "n_in": 1.0,
        "n_larvae": 0.5,
        "n_frass": 0.2,
        "temperature": 28.0,
        "moisture": 65.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_guidance_detects_missing_signal_batch():
    guidance = build_batch_guidance(
        batch=make_batch(),
        signal_batch=None,
        control_profile=None,
        locality_profile=None,
        release_decision=None,
        portability_audits=[],
    )

    codes = [item["code"] for item in guidance["gap_items"]]
    assert "missing_signal_batch" in codes
    assert "Compile the signal first." in guidance["recommended_actions"]


def test_guidance_detects_missing_nitrogen_inputs():
    guidance = build_batch_guidance(
        batch=make_batch(n_larvae=None, n_frass=None),
        signal_batch=SimpleNamespace(potency=0.2, stability_window_hours=8.0, freshness_state="Fresh"),
        control_profile=SimpleNamespace(),
        locality_profile=None,
        release_decision=None,
        portability_audits=[],
    )

    codes = [item["code"] for item in guidance["gap_items"]]
    assert "missing_n_larvae" in codes
    assert "missing_n_frass" in codes


def test_guidance_detects_sparse_metering():
    guidance = build_batch_guidance(
        batch=make_batch(dm_out=None, n_in=None, n_larvae=None, n_frass=None, temperature=None),
        signal_batch=SimpleNamespace(potency=0.2, stability_window_hours=8.0, freshness_state="Fresh"),
        control_profile=SimpleNamespace(),
        locality_profile=None,
        release_decision=None,
        portability_audits=[],
    )

    codes = [item["code"] for item in guidance["gap_items"]]
    assert "metering_too_sparse" in codes
    assert any(item["blocking"] for item in guidance["gap_items"])


def test_guidance_surfaces_native_model_stack_when_available():
    guidance = build_batch_guidance(
        batch=make_batch(),
        signal_batch=SimpleNamespace(potency=0.2, stability_window_hours=8.0, freshness_state="Fresh"),
        control_profile=SimpleNamespace(),
        locality_profile=None,
        release_decision=None,
        portability_audits=[],
        native_model_stack={
            "primary_recommendation": {
                "title": "Vision + forecast closed loop",
            }
        },
    )

    codes = [item["code"] for item in guidance["gap_items"]]
    assert "native_model_stack_ready" in codes
    assert any("Vision + forecast closed loop" in action for action in guidance["recommended_actions"])


def test_guidance_surfaces_release_blockers_from_latest_decision():
    guidance = build_batch_guidance(
        batch=make_batch(),
        signal_batch=SimpleNamespace(
            potency=0.42,
            stability_window_hours=8.0,
            freshness_state="Fresh",
        ),
        control_profile=SimpleNamespace(),
        locality_profile=SimpleNamespace(),
        release_decision=SimpleNamespace(
            decision="FAIL",
            reason_codes=["potency_out_of_contract"],
            blocking_factors=["Signal potency falls outside the configured dose window."],
            warning_factors=[],
            rationale="The protocol checks found a blocking condition that prevents release.",
        ),
        portability_audits=[],
    )

    items_by_code = {item["code"]: item for item in guidance["gap_items"]}
    assert items_by_code["release_blocked"]["blocking"] is True
    assert (
        items_by_code["release_blocked"]["recommended_action"]
        == "Retune the control profile or compile a signal that fits the dose window."
    )


def test_guidance_flags_failed_portability_as_blocking():
    guidance = build_batch_guidance(
        batch=make_batch(),
        signal_batch=SimpleNamespace(
            potency=0.2,
            stability_window_hours=8.0,
            freshness_state="Fresh",
        ),
        control_profile=SimpleNamespace(),
        locality_profile=SimpleNamespace(),
        release_decision=None,
        portability_audits=[
            SimpleNamespace(outcome="FAIL", retuning_required=False),
        ],
    )

    items_by_code = {item["code"]: item for item in guidance["gap_items"]}
    assert items_by_code["portability_failed"]["blocking"] is True
    assert items_by_code["portability_failed"]["severity"] == "critical"
