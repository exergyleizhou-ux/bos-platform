"""
BOS report export helpers.
"""

from __future__ import annotations

import json


def render_audit_packet_markdown(packet: dict) -> str:
    packet_payload = packet.get("packet") or {}
    batch = packet_payload.get("batch") or {}
    signal = packet_payload.get("signal_batch") or {}
    control = packet_payload.get("control_profile") or {}
    boundary = packet_payload.get("boundary_ledger") or {}
    decision = packet_payload.get("release_decision") or {}
    portability = packet_payload.get("portability_audits") or []
    native_model_stack = packet_payload.get("native_model_stack") or {}
    native_forecast_evidence = packet_payload.get("native_forecast_evidence") or {}
    context = packet_payload.get("generation_context") or {}
    signal_validity = packet.get("signal_validity") or {}
    contract_evaluation = packet.get("contract_evaluation") or {}
    retuning_axes = packet.get("retuning_axes") or {}
    evidence_profile = retuning_axes.get("evidence_profile") or {}
    supervisor_snapshot = signal_validity.get("supervisor_snapshot") or {}
    supervisor_history = signal_validity.get("supervisor_history") or []
    mechanistic = (
        packet_payload.get("mechanistic_context")
        or signal_validity.get("mechanistic_context")
        or (decision.get("trigger_metrics") or {}).get("mechanistic_context")
        or {}
    )
    c_di_ser = mechanistic.get("c_di_ser") or {}
    handover = mechanistic.get("handover_envelope") or {}
    mech_inputs = mechanistic.get("inputs") or {}
    primary_recommendation = native_model_stack.get("primary_recommendation") or {}

    sections = [
        "# BOS Code Technical Audit Report",
        "",
        "## Batch Summary",
        f"- Batch ID: {batch.get('batch_id', packet.get('batch_id', 'N/A'))}",
        f"- Species: {batch.get('species', 'N/A')}",
        f"- Status: {batch.get('status', 'N/A')}",
        "",
        "## Signal Snapshot",
        f"- Compiled signal: {signal.get('compiled_signal_id', 'N/A')}",
        f"- Signal API version: {signal.get('signal_api_version', 'N/A')}",
        f"- Potency: {signal.get('potency', 'N/A')}",
        f"- Freshness state: {signal.get('freshness_state', 'N/A')}",
        "",
        "## Control Snapshot",
        f"- Control profile: {control.get('name', 'N/A')}",
        f"- Version: {control.get('version', 'N/A')}",
        f"- MTT: {control.get('mtt', 'N/A')}",
        f"- Dose window: {control.get('dose_window_min', 'N/A')} to {control.get('dose_window_max', 'N/A')}",
        f"- Contract status: {contract_evaluation.get('status', 'N/A')}",
        f"- Threshold breaches: {', '.join(contract_evaluation.get('threshold_breaches', [])) or 'None'}",
        "",
        "## Boundary Ledger",
        f"- SER: {boundary.get('ser_value', 'N/A')}",
        f"- D': {boundary.get('d_prime', 'N/A')}",
        f"- G': {boundary.get('g_prime', 'N/A')}",
        f"- Closure residual: {boundary.get('closure_residual', 'N/A')}",
        f"- DeltaDeltaSER: {boundary.get('delta_delta_ser', 'N/A')}",
        f"- Metering completeness: {boundary.get('metering_completeness', 'N/A')}",
        f"- Evidence level: {boundary.get('evidence_level', packet.get('evidence_level', 'N/A'))}",
        "",
        "## Mechanistic Diagnostics",
        f"- C-DI-SER: {c_di_ser.get('score', 'N/A')}",
        f"- Alpha / beta: {c_di_ser.get('alpha_s', 'N/A')} / {c_di_ser.get('beta_s', 'N/A')}",
        f"- Information loss: {c_di_ser.get('information_loss', 'N/A')}",
        f"- Tau star (min): {handover.get('tau_star_min', 'N/A')}",
        f"- Peak envelope: {handover.get('c_peak', 'N/A')}",
        f"- Clock frequency: {handover.get('f_clock', 'N/A')}",
        f"- Mass balance ratio: {mech_inputs.get('mass_balance_ratio', 'N/A')}",
        f"- Mechanistic metering completeness: {mech_inputs.get('metering_completeness', 'N/A')}",
        "",
        "## Supervisor Snapshot",
        f"- Mode: {supervisor_snapshot.get('mode', 'N/A')}",
        f"- Recorded at: {supervisor_snapshot.get('recorded_at', 'N/A')}",
        f"- Trigger reason: {(supervisor_snapshot.get('decision') or {}).get('trigger_reason', 'N/A')}",
        f"- Recommended handover: {(supervisor_snapshot.get('decision') or {}).get('recommended_handover', 'N/A')}",
        f"- History points: {len(supervisor_history) if isinstance(supervisor_history, list) else 0}",
        "",
        "## Native Model Stack",
        f"- Catalog version: {native_model_stack.get('catalog_version', 'N/A')}",
        f"- Verified on: {native_model_stack.get('verified_on', 'N/A')}",
        f"- Primary recommendation: {primary_recommendation.get('title', 'N/A')}",
        f"- Recommended model keys: {', '.join(primary_recommendation.get('model_keys', [])) or 'None'}",
        "",
        "## Native Forecast Evidence",
        f"- Model key: {native_forecast_evidence.get('model_key', 'N/A')}",
        f"- Modality: {native_forecast_evidence.get('modality', 'N/A')}",
        f"- Evidence tier: {native_forecast_evidence.get('evidence_tier', 'N/A')}",
        f"- Evidence label: {native_forecast_evidence.get('evidence_label', 'N/A')}",
        f"- Evidence summary: {native_forecast_evidence.get('evidence_summary', 'N/A')}",
        f"- Execution mode: {native_forecast_evidence.get('execution_mode', 'N/A')}",
        f"- Metric: {native_forecast_evidence.get('metric_name', 'N/A')}",
        f"- Prediction horizon: {native_forecast_evidence.get('prediction_horizon', 'N/A')}",
        f"- Forecast preview: {', '.join(native_forecast_evidence.get('forecast_preview', [])) or 'N/A'}",
        f"- Detection count: {native_forecast_evidence.get('detection_count', 'N/A')}",
        f"- Top label: {native_forecast_evidence.get('top_label', 'N/A')}",
        f"- Top candidates: {', '.join(native_forecast_evidence.get('top_candidates', [])) or 'N/A'}",
        f"- BBox summary: {native_forecast_evidence.get('bbox_summary', 'N/A')}",
        "",
        "## Release Decision",
        f"- Decision: {decision.get('decision', 'N/A')}",
        f"- Reason codes: {', '.join(decision.get('reason_codes', [])) or 'None'}",
        f"- Blocking factors: {', '.join(decision.get('blocking_factors', [])) or 'None'}",
        f"- Warning factors: {', '.join(decision.get('warning_factors', [])) or 'None'}",
        f"- Rationale: {decision.get('rationale', 'N/A')}",
        "",
        "## Portability Audits",
    ]

    if portability:
        for audit in portability:
            sections.extend(
                [
                    f"- Audit #{audit.get('id', 'N/A')}: {audit.get('outcome', 'N/A')}",
                    f"  - Executor: {audit.get('executor_name', audit.get('executor_profile_id', 'N/A'))}",
                    f"  - Locality: {audit.get('locality_name', audit.get('locality_profile_id', 'N/A'))}",
                    f"  - Retuning required: {audit.get('retuning_required', False)}",
                    f"  - Recommended outcome: {audit.get('recommended_outcome', 'N/A')}",
                    f"  - Retuning axes: {', '.join(audit.get('retuning_axes', [])) or 'None'}",
                    f"  - Retuning magnitude: {audit.get('retuning_magnitude', 'N/A')}",
                    f"  - Portability score: {audit.get('portability_score', 'N/A')}",
                ]
            )
    else:
        sections.append("- None")

    sections.extend(
        [
            "",
            "## Evidence Profile",
            f"- Metering completeness: {evidence_profile.get('metering_completeness', 'N/A')}",
            f"- Evidence status: {evidence_profile.get('evidence_status', 'N/A')}",
            f"- Mass balance ratio: {evidence_profile.get('mass_balance_ratio', 'N/A')}",
            "",
            "## Generation Context",
            f"- Schema version: {context.get('schema_version', packet.get('packet_version', 'N/A'))}",
            f"- Compiled at: {context.get('compiled_at', packet.get('generated_at', 'N/A'))}",
            f"- Compiled by user: {context.get('compiled_by_user_id', packet.get('user_id', 'N/A'))}",
            f"- Source mode: {context.get('source_mode', 'N/A')}",
            f"- Source batch id: {(context.get('source_ids') or {}).get('batch_id', 'N/A')}",
            f"- Source signal id: {(context.get('source_ids') or {}).get('signal_batch_id', 'N/A')}",
            f"- Source control profile id: {(context.get('source_ids') or {}).get('control_profile_id', 'N/A')}",
            f"- Source release decision id: {(context.get('source_ids') or {}).get('release_decision_id', 'N/A')}",
            f"- Integrity hash: {context.get('hash', 'N/A')}",
        ]
    )

    return "\n".join(sections) + "\n"


def render_audit_packet_json(packet: dict) -> str:
    return json.dumps(packet, indent=2, ensure_ascii=False, default=str)
