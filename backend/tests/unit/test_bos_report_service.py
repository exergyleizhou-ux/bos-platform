from app.services.bos_report_service import render_audit_packet_markdown


def test_render_audit_packet_markdown_includes_mechanistic_diagnostics():
    packet = {
        "packet_version": "AUD-1.0",
        "generated_at": "2026-04-15T00:00:00Z",
        "signal_validity": {
            "supervisor_snapshot": {
                "mode": "handover",
                "recorded_at": "2026-04-15T00:05:00Z",
                "decision": {
                    "trigger_reason": "negative_slope_persistence",
                    "recommended_handover": True,
                },
            },
            "supervisor_history": [
                {
                    "mode": "supervisor",
                    "recorded_at": "2026-04-15T00:01:00Z",
                    "decision": {"confidence": 0.9},
                },
                {
                    "mode": "handover",
                    "recorded_at": "2026-04-15T00:05:00Z",
                    "decision": {"confidence": 0.84},
                },
            ],
            "mechanistic_context": {
                "c_di_ser": {
                    "score": 0.42,
                    "alpha_s": 0.51,
                    "beta_s": 0.49,
                    "information_loss": 0.18,
                },
                "handover_envelope": {
                    "tau_star_min": 92.5,
                    "c_peak": 0.73,
                    "f_clock": 0.0108,
                },
                "inputs": {
                    "mass_balance_ratio": 0.33,
                    "metering_completeness": 0.86,
                },
            }
        },
        "packet": {
            "batch": {"batch_id": "REPORT-001", "species": "BSF", "status": "completed"},
            "signal_batch": {"compiled_signal_id": "SIG-REPORT-001", "signal_api_version": "SIG-1.0"},
            "control_profile": {"name": "Report Control", "version": "CTRL-1.0"},
            "boundary_ledger": {"ser_value": 0.22},
            "release_decision": {"decision": "PASS", "trigger_metrics": {}},
            "portability_audits": [],
            "native_model_stack": {
                "catalog_version": "BOS-NATIVE-2026.04",
                "verified_on": "2026-04-15",
                "primary_recommendation": {
                    "title": "图像 + 预测闭环",
                    "model_keys": ["yolo11_dsconv", "insectsam", "timer_s1", "chronos_bolt"],
                },
            },
            "native_forecast_evidence": {
                "model_key": "chronos_bolt",
                "modality": "time-series",
                "evidence_tier": "stabilized_live_timeseries",
                "evidence_label": "Stabilized live timeseries",
                "evidence_summary": "decomposition_rate · horizon 3 · 0.41, 0.44, 0.48",
                "execution_mode": "chronos_bolt_live",
                "metric_name": "decomposition_rate",
                "prediction_horizon": 3,
                "forecast_preview": ["0.41", "0.44", "0.48"],
            },
            "generation_context": {"schema_version": "BOS-1.0", "compiled_at": "2026-04-15T00:00:00Z"},
        },
    }

    rendered = render_audit_packet_markdown(packet)

    assert "## Mechanistic Diagnostics" in rendered
    assert "- C-DI-SER: 0.42" in rendered
    assert "- Tau star (min): 92.5" in rendered
    assert "- Mass balance ratio: 0.33" in rendered
    assert "## Supervisor Snapshot" in rendered
    assert "- Trigger reason: negative_slope_persistence" in rendered
    assert "- History points: 2" in rendered
    assert "## Native Model Stack" in rendered
    assert "- Primary recommendation: 图像 + 预测闭环" in rendered
    assert "## Native Forecast Evidence" in rendered
    assert "- Model key: chronos_bolt" in rendered
    assert "- Evidence label: Stabilized live timeseries" in rendered
    assert "- Evidence summary: decomposition_rate · horizon 3 · 0.41, 0.44, 0.48" in rendered
    assert "- Forecast preview: 0.41, 0.44, 0.48" in rendered


def test_render_audit_packet_markdown_includes_portability_recommendation_metadata():
    packet = {
        "packet_version": "AUD-1.0",
        "generated_at": "2026-04-15T00:00:00Z",
        "contract_evaluation": {
            "status": "review",
            "threshold_breaches": ["dose_window"],
        },
        "retuning_axes": {
            "evidence_profile": {
                "metering_completeness": 0.86,
                "evidence_status": "medium",
                "mass_balance_ratio": 0.33,
            }
        },
        "packet": {
            "batch": {"batch_id": "REPORT-003", "species": "BSF", "status": "active"},
            "signal_batch": {"compiled_signal_id": "SIG-REPORT-003", "signal_api_version": "SIG-1.0"},
            "control_profile": {"name": "Portability Control", "version": "CTRL-1.1"},
            "boundary_ledger": {
                "ser_value": 0.22,
                "delta_delta_ser": 0.05,
            },
            "release_decision": {"decision": "PASS_WITH_RETUNING", "trigger_metrics": {}},
            "portability_audits": [
                {
                    "id": 51,
                    "executor_name": "Shanghai Executor",
                    "locality_name": "Shanghai Site A",
                    "outcome": "PASS_WITH_RETUNING",
                    "retuning_required": True,
                    "recommended_outcome": "PASS_WITH_RETUNING",
                    "retuning_axes": ["dose_window", "executor_hal"],
                    "retuning_magnitude": 0.18,
                    "portability_score": 0.82,
                }
            ],
            "native_model_stack": {},
            "generation_context": {
                "schema_version": "BOS-1.0",
                "compiled_at": "2026-04-15T00:00:00Z",
                "compiled_by_user_id": 9,
                "source_mode": "refresh",
                "source_ids": {
                    "batch_id": 7,
                    "signal_batch_id": 11,
                    "control_profile_id": 12,
                    "release_decision_id": 13,
                },
                "hash": "abc123",
            },
        },
    }

    rendered = render_audit_packet_markdown(packet)

    assert "- Contract status: review" in rendered
    assert "- Threshold breaches: dose_window" in rendered
    assert "- DeltaDeltaSER: 0.05" in rendered
    assert "- Recommended outcome: PASS_WITH_RETUNING" in rendered
    assert "- Retuning axes: dose_window, executor_hal" in rendered
    assert "- Portability score: 0.82" in rendered
    assert "## Evidence Profile" in rendered
    assert "- Evidence status: medium" in rendered
    assert "- Source mode: refresh" in rendered
    assert "- Source signal id: 11" in rendered


def test_render_audit_packet_markdown_includes_visual_native_evidence():
    packet = {
        "packet_version": "AUD-1.0",
        "generated_at": "2026-04-15T00:00:00Z",
        "packet": {
            "batch": {"batch_id": "REPORT-002", "species": "BSF", "status": "completed"},
            "signal_batch": None,
            "control_profile": None,
            "boundary_ledger": None,
            "release_decision": None,
            "portability_audits": [],
            "native_model_stack": {},
            "native_forecast_evidence": {
                "model_key": "insecta",
                "modality": "vision",
                "evidence_tier": "bootstrap_public_vision",
                "evidence_label": "Bootstrap public vision",
                "evidence_summary": "3 detections · top label 鞘翅目_步甲科,Carabidae",
                "execution_mode": "insecta_bootstrap_live",
                "metric_name": None,
                "prediction_horizon": None,
                "forecast_preview": [],
                "detection_count": 3,
                "top_label": "鞘翅目_步甲科,Carabidae",
                "top_candidates": [
                    "鞘翅目_步甲科,Carabidae",
                    "鞘翅目_步甲科_麻步甲,Carabus brandti",
                ],
                "bbox_summary": "544, 289, 546, 303",
            },
            "generation_context": {"schema_version": "BOS-1.0", "compiled_at": "2026-04-15T00:00:00Z"},
        },
    }

    rendered = render_audit_packet_markdown(packet)

    assert "- Model key: insecta" in rendered
    assert "- Evidence label: Bootstrap public vision" in rendered
    assert "- Detection count: 3" in rendered
    assert "- Top label: 鞘翅目_步甲科,Carabidae" in rendered
    assert "- Top candidates: 鞘翅目_步甲科,Carabidae, 鞘翅目_步甲科_麻步甲,Carabus brandti" in rendered
    assert "- BBox summary: 544, 289, 546, 303" in rendered
