from app.engine.bos_supervisor_engine import evaluate_bos_supervisor_state


def test_evaluate_bos_supervisor_state_returns_stable_decision():
    decision = evaluate_bos_supervisor_state(
        uv254=2.5,
        od280=2.1,
        do_value=5.2,
        ph=7.2,
        elapsed_hours=10.0,
        previous_c_signal_hat=0.6,
        previous_elapsed_hours=8.0,
    )

    assert 0.0 <= decision.c_signal_hat <= 1.0
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.missing_channels == []
    assert sorted(decision.channels_used) == ["do", "od280", "ph", "uv254"]
    assert decision.trigger_reason is None
    assert decision.expected_freshness_window_hours is not None


def test_evaluate_bos_supervisor_state_flags_missing_channels():
    decision = evaluate_bos_supervisor_state(
        uv254=None,
        od280=1.2,
        do_value=None,
        ph=None,
        elapsed_hours=4.0,
        previous_c_signal_hat=None,
        previous_elapsed_hours=None,
        confidence_threshold=0.9,
    )

    assert sorted(decision.missing_channels) == ["do", "ph", "uv254"]
    assert decision.confidence < 0.9
    assert decision.recommended_handover is True
    assert decision.trigger_reason == "confidence_threshold"


def test_evaluate_bos_supervisor_state_respects_negative_slope_persistence():
    decision = evaluate_bos_supervisor_state(
        uv254=0.8,
        od280=0.9,
        do_value=1.5,
        ph=6.9,
        elapsed_hours=12.0,
        previous_c_signal_hat=0.72,
        previous_elapsed_hours=11.0,
        previous_dc_dt_hat=-0.08,
        previous_negative_slope_streak=2,
        negative_slope_persistence=3,
    )

    assert decision.dc_dt_hat is not None
    assert decision.dc_dt_hat < 0
    assert decision.negative_slope_streak >= 3
    assert decision.recommended_handover is True
    assert decision.trigger_reason == "negative_slope_persistence"
