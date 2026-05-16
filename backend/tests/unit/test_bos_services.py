from datetime import datetime, UTC
from types import SimpleNamespace

from app.services.bos import (
    _build_release_outcome,
    recommend_portability,
    serialize_audit_packet,
    serialize_release_decision,
)


def make_batch(**overrides):
    defaults = {
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


def make_signal(**overrides):
    defaults = {
        "potency": 0.18,
        "freshness_state": "Fresh",
        "stability_window_hours": 8.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_control(**overrides):
    defaults = {
        "mtt": 6.0,
        "dose_window_min": 0.1,
        "dose_window_max": 0.25,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_release_outcome_returns_insufficient_evidence_when_signal_missing():
    decision, reason_codes, blocking, warning, passed, trigger_metrics, rationale = _build_release_outcome(
        batch=make_batch(),
        signal_batch=None,
        control_profile=make_control(),
    )

    assert decision == "INSUFFICIENT_EVIDENCE"
    assert "missing_signal_batch" in reason_codes
    assert blocking
    assert warning == []
    assert passed == []
    assert trigger_metrics["contract_status"] == "present"
    assert "no compiled signal" in rationale.lower()


def test_build_release_outcome_fails_for_stale_or_out_of_contract_signal():
    decision, reason_codes, blocking, warning, passed, trigger_metrics, _ = _build_release_outcome(
        batch=make_batch(),
        signal_batch=make_signal(freshness_state="Stale", potency=0.4),
        control_profile=make_control(),
    )

    assert decision == "FAIL"
    assert "stale_signal" in reason_codes
    assert "potency_out_of_contract" in reason_codes
    assert any("dose window" in item.lower() for item in blocking)
    assert warning == []
    assert "signal_freshness" not in passed
    assert trigger_metrics["contract_status"] == "present"


def test_build_release_outcome_returns_pass_with_retuning_for_borderline_state():
    decision, reason_codes, blocking, warning, passed, trigger_metrics, _ = _build_release_outcome(
        batch=make_batch(n_in=None, n_larvae=None, n_frass=None),
        signal_batch=make_signal(stability_window_hours=5.5),
        control_profile=make_control(mtt=6.0),
    )

    assert decision == "PASS_WITH_RETUNING"
    assert "stability_below_mtt" in reason_codes
    assert blocking == []
    assert warning
    assert "control_profile_present" in passed
    assert trigger_metrics["metering_completeness"] < 0.75


def test_build_release_outcome_returns_pass_for_well_formed_release():
    decision, reason_codes, blocking, warning, passed, trigger_metrics, _ = _build_release_outcome(
        batch=make_batch(),
        signal_batch=make_signal(),
        control_profile=make_control(),
    )

    assert decision == "PASS"
    assert reason_codes == []
    assert blocking == []
    assert warning == []
    assert "signal_freshness" in passed
    assert "signal_potency_present" in passed
    assert "metering_completeness" in passed
    assert trigger_metrics["metering_completeness"] == 1.0


def test_recommend_portability_returns_retuning_for_locality_shift():
    recommendation = recommend_portability(
        signal_batch=SimpleNamespace(id=1, potency=0.18, freshness_state="Fresh", stability_window_hours=8.0),
        executor_profile=SimpleNamespace(id=2, hal_min=0.1, hal_max=0.3, plugin_mode="adaptive"),
        locality_profile=SimpleNamespace(id=3, dose_window_shift_pct=12.0, mtt_shift_pct=0.0),
        control_profile=make_control(),
    )

    assert recommendation["recommended_outcome"] == "PASS_WITH_RETUNING"
    assert "dose_window" in recommendation["retuning_axes"]
    assert recommendation["portability_score"] < 1.0
    assert recommendation["requires_requalification"] is False
    assert "Retune" in recommendation["recommended_action"]
    assert "portability risk remains elevated" in recommendation["rationale"]


def test_recommend_portability_fails_for_out_of_hal_signal():
    recommendation = recommend_portability(
        signal_batch=SimpleNamespace(id=1, potency=0.4, freshness_state="Stale", stability_window_hours=2.0),
        executor_profile=SimpleNamespace(id=2, hal_min=0.1, hal_max=0.2, plugin_mode="standard"),
        locality_profile=None,
        control_profile=make_control(mtt=6.0),
    )

    assert recommendation["recommended_outcome"] == "FAIL"
    assert "executor_hal" in recommendation["retuning_axes"]
    assert recommendation["portability_score"] < 0.45
    assert recommendation["requires_requalification"] is True
    assert "Requalify" in recommendation["recommended_action"]
    assert "outside the safe transfer envelope" in recommendation["rationale"]


def test_serialize_release_decision_preserves_top_level_confidence():
    payload = serialize_release_decision(
        SimpleNamespace(
            id=9,
            batch_id=4,
            signal_batch_id=5,
            boundary_ledger_id=6,
            control_profile_id=7,
            decision="PASS",
            reason_codes=None,
            blocking_factors=None,
            warning_factors=None,
            passed_checks=None,
            trigger_metrics={"applied_contract": {"version": "CTRL-2.0"}},
            approver=None,
            rationale="Release is supported.",
            applied_contract=None,
            applied_locality_shift=None,
            decision_confidence=0.87,
            user_id=2,
            tenant_id=1,
            decision_time=datetime(2026, 4, 16, tzinfo=UTC),
            created_at=datetime(2026, 4, 16, tzinfo=UTC),
        )
    )

    assert payload["decision_confidence"] == 0.87
    assert payload["applied_contract"] == {"version": "CTRL-2.0"}
    assert payload["reason_codes"] == []


def test_serialize_audit_packet_preserves_portability_recommendation_metadata():
    payload = serialize_audit_packet(
        SimpleNamespace(
            id=5,
            batch_id=4,
            release_decision_id=7,
            user_id=2,
            tenant_id=1,
            packet_version="AUD-1.0",
            evidence_level="Supported",
            contract_evaluation=None,
            signal_validity=None,
            retuning_axes=None,
            generated_at=datetime(2026, 4, 16, tzinfo=UTC),
            created_at=datetime(2026, 4, 16, tzinfo=UTC),
            packet={
                "contract_evaluation": {"status": "review"},
                "signal_validity": {"status": "valid"},
                "retuning_axes": {
                    "recommended_by_portability": [
                        {
                            "audit_id": 51,
                            "recommended_outcome": "PASS_WITH_RETUNING",
                            "rationale": "The signal can transfer, but HAL still needs retuning.",
                            "recommended_action": "Retune executor_hal before formal release.",
                            "requires_requalification": False,
                            "retuning_axes": ["executor_hal"],
                            "retuning_magnitude": 0.14,
                            "portability_score": 0.83,
                        }
                    ]
                },
                "batch": {"id": 4, "batch_id": "BOS-004", "species": "BSF", "status": "active"},
                "signal_batch": None,
                "control_profile": None,
                "boundary_ledger": None,
                "release_decision": None,
                "portability_audits": [
                    {
                        "id": 51,
                        "executor_profile_id": 9,
                        "locality_profile_id": None,
                        "executor_name": "Executor 9",
                        "locality_name": None,
                        "outcome": "PASS_WITH_RETUNING",
                        "retuning_required": True,
                        "recommended_outcome": "PASS_WITH_RETUNING",
                        "rationale": "The signal can transfer, but HAL still needs retuning.",
                        "recommended_action": "Retune executor_hal before formal release.",
                        "requires_requalification": False,
                        "retuning_axes": ["executor_hal"],
                        "retuning_magnitude": 0.14,
                        "portability_score": 0.83,
                        "trigger_metrics": {"hal_margin": 0.06},
                    }
                ],
                "generation_context": {
                    "schema_version": "BOS-1.0",
                    "compiled_at": "2026-04-16T00:00:00Z",
                    "compiled_by_user_id": 2,
                    "source_ids": {},
                    "hash": "abc",
                },
            },
        )
    )

    assert payload["contract_evaluation"]["status"] == "review"
    assert payload["retuning_axes"]["recommended_by_portability"][0]["portability_score"] == 0.83
    assert payload["packet"]["portability_audits"][0]["recommended_outcome"] == "PASS_WITH_RETUNING"
    assert payload["packet"]["portability_audits"][0]["rationale"] == "The signal can transfer, but HAL still needs retuning."
    assert payload["packet"]["portability_audits"][0]["recommended_action"] == "Retune executor_hal before formal release."
    assert payload["packet"]["portability_audits"][0]["retuning_axes"] == ["executor_hal"]
    assert payload["packet"]["portability_audits"][0]["portability_score"] == 0.83
