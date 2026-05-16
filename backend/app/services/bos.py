"""
Minimal BOS protocol services.

These helpers provide the persistence and serialization layer that powers the
frontend BOS console until a richer policy engine is introduced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from copy import deepcopy
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.engine.bos_mechanistic_engine import build_compile_diagnostics
from app.services.bos_native_models import build_native_model_embedding
from app.services.bos_native_runtime import summarize_latest_native_run
from app.models import (
    AuditPacket,
    Batch,
    BoundaryLedger,
    ControlAPIProfile,
    ExecutorProfile,
    LocalityProfile,
    PortabilityAudit,
    ReleaseDecision,
    SignalBatch,
    User,
)
from app.schemas import (
    AuditPacketResponse,
    BatchBOSOverview,
    BoundaryLedgerResponse,
    ControlAPIProfileResponse,
    PortabilityAuditResponse,
    PortabilityRecommendationResponse,
    ReleaseDecisionResponse,
    SignalBatchResponse,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator / denominator, 4)


def _compute_metering_completeness(batch: Batch) -> float:
    observed = [
        batch.dm_in,
        batch.dm_out,
        batch.n_in,
        batch.n_larvae,
        batch.n_frass,
        batch.temperature,
        batch.moisture,
    ]
    populated = sum(value is not None for value in observed)
    return round(populated / len(observed), 4)


def _derive_signal_freshness(
    *,
    batch: Batch,
    stability_window_hours: float | None,
) -> tuple[str, float, float]:
    if batch.updated_at is None:
        return "Fresh", 1.0, 1.0

    batch_updated_at = batch.updated_at
    if batch_updated_at.tzinfo is None:
        batch_updated_at = batch_updated_at.replace(tzinfo=timezone.utc)

    age_hours = max(0.0, (datetime.now(timezone.utc) - batch_updated_at).total_seconds() / 3600)
    if stability_window_hours is None or stability_window_hours <= 0:
        if age_hours <= 24:
            return "Fresh", 0.8, 0.75
        if age_hours <= 72:
            return "Stable", 0.55, 0.45
        return "Stale", 0.2, 0.15

    freshness_score = _clamp(1 - (age_hours / max(stability_window_hours, 1)))
    release_readiness_score = _clamp(freshness_score * 0.9 + (_compute_metering_completeness(batch) * 0.1))
    if freshness_score >= 0.7:
        return "Fresh", round(freshness_score, 4), round(release_readiness_score, 4)
    if freshness_score >= 0.35:
        return "Stable", round(freshness_score, 4), round(release_readiness_score, 4)
    return "Stale", round(freshness_score, 4), round(release_readiness_score, 4)


def _serialize_signal_batch(signal_batch: SignalBatch) -> dict:
    return SignalBatchResponse.model_validate(signal_batch).model_dump()


def _ensure_qc_markers(signal_batch: SignalBatch) -> dict[str, Any]:
    qc_markers = signal_batch.qc_markers or {}
    if not isinstance(qc_markers, dict):
        qc_markers = {}
    return deepcopy(qc_markers)


def persist_supervisor_snapshot(
    signal_batch: SignalBatch,
    *,
    observation: dict[str, Any],
    decision: dict[str, Any],
    mode: str,
    history_limit: int = 10,
) -> dict[str, Any]:
    qc_markers = _ensure_qc_markers(signal_batch)
    snapshot = {
        "mode": mode,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "observation": observation,
        "decision": decision,
    }
    history = qc_markers.get("supervisor_history") or []
    if not isinstance(history, list):
        history = []
    history.append(snapshot)
    qc_markers["supervisor_history"] = history[-history_limit:]
    qc_markers["supervisor_latest"] = snapshot
    signal_batch.qc_markers = qc_markers
    flag_modified(signal_batch, "qc_markers")
    return snapshot


async def compile_signal_for_batch(
    db: AsyncSession,
    *,
    batch: Batch,
    current_user: User,
    control_profile: ControlAPIProfile | None,
    locality_profile: LocalityProfile | None,
    signal_api_version: str = "SIG-1.0",
    compiler_version: str = "BOS-2.0",
    notes: str | None = None,
    dose_window_min: float | None = None,
    dose_window_max: float | None = None,
    stability_window_hours: float | None = None,
    kernel_residence_time_hours: float | None = None,
    apply_locality_shifts: bool = True,
) -> tuple[SignalBatch, dict]:
    potency = batch.score if batch.score is not None else _safe_ratio(batch.dm_out, batch.dm_in)

    effective_dose_min = dose_window_min if dose_window_min is not None else (control_profile.dose_window_min if control_profile else None)
    effective_dose_max = dose_window_max if dose_window_max is not None else (control_profile.dose_window_max if control_profile else None)
    effective_stability = (
        stability_window_hours
        if stability_window_hours is not None
        else (control_profile.stability_window_hours if control_profile and control_profile.stability_window_hours is not None else control_profile.mtt if control_profile else None)
    )

    applied_locality_shift = None
    if apply_locality_shifts and locality_profile is not None:
        if effective_dose_min is not None:
            effective_dose_min = round(effective_dose_min * (1 + (locality_profile.dose_window_shift_pct or 0) / 100), 4)
        if effective_dose_max is not None:
            effective_dose_max = round(effective_dose_max * (1 + (locality_profile.dose_window_shift_pct or 0) / 100), 4)
        if effective_stability is not None:
            effective_stability = round(effective_stability * (1 + (locality_profile.mtt_shift_pct or 0) / 100), 4)
        applied_locality_shift = {
            "id": locality_profile.id,
            "name": locality_profile.name,
            "dose_window_shift_pct": locality_profile.dose_window_shift_pct,
            "mtt_shift_pct": locality_profile.mtt_shift_pct,
        }

    freshness_state, freshness_score, release_readiness_score = _derive_signal_freshness(
        batch=batch,
        stability_window_hours=effective_stability,
    )
    locality_shift_pct = 0.0
    if locality_profile is not None:
        locality_shift_pct = max(
            abs(locality_profile.dose_window_shift_pct or 0.0),
            abs(locality_profile.mtt_shift_pct or 0.0),
        )

    mechanistic_context = build_compile_diagnostics(
        dm_in=batch.dm_in,
        dm_out=batch.dm_out,
        potency=potency,
        stability_window_hours=effective_stability,
        metering_completeness=_compute_metering_completeness(batch),
        locality_shift_pct=locality_shift_pct,
    )
    native_model_stack = build_native_model_embedding(batch=batch, signal_batch=None)

    compiled_signal_id = f"SIG-{batch.batch_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    signal_batch = SignalBatch(
        batch_id=batch.id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        signal_api_version=signal_api_version,
        compiled_signal_id=compiled_signal_id,
        potency=potency,
        potency_unit="SER-equivalent",
        potency_basis="matched_boundary",
        dose_window_min=effective_dose_min,
        dose_window_max=effective_dose_max,
        stability_window_hours=effective_stability,
        kernel_residence_time_hours=kernel_residence_time_hours,
        freshness_state=freshness_state,
        qc_markers={
            "metering_completeness": _compute_metering_completeness(batch),
            "ser_proxy": potency,
        },
        notes=notes,
        released_at=datetime.now(timezone.utc),
        expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=effective_stability)
            if effective_stability is not None
            else None
        ),
    )
    db.add(signal_batch)
    await db.flush()

    compile_context = {
        "compiler_version": compiler_version,
        "source_batch_id": batch.id,
        "control_profile_id": control_profile.id if control_profile else None,
        "locality_profile_id": locality_profile.id if locality_profile else None,
        "applied_locality_shift": applied_locality_shift,
        "freshness_score": freshness_score,
        "release_readiness_score": release_readiness_score,
        "mechanistic_context": mechanistic_context,
        "native_model_stack": native_model_stack,
    }
    return signal_batch, compile_context


async def refresh_signal_batch_state(
    db: AsyncSession,
    *,
    signal_batch: SignalBatch,
    batch: Batch,
) -> dict:
    freshness_state, freshness_score, release_readiness_score = _derive_signal_freshness(
        batch=batch,
        stability_window_hours=signal_batch.stability_window_hours,
    )
    signal_batch.freshness_state = freshness_state
    signal_batch.released_at = signal_batch.released_at or datetime.now(timezone.utc)
    signal_batch.expires_at = (
        signal_batch.released_at + timedelta(hours=signal_batch.stability_window_hours)
        if signal_batch.released_at and signal_batch.stability_window_hours is not None
        else signal_batch.expires_at
    )
    await db.flush()
    if batch.updated_at is not None:
        batch_updated_at = batch.updated_at
        if batch_updated_at.tzinfo is None:
            batch_updated_at = batch_updated_at.replace(tzinfo=timezone.utc)
        metering_age_hours = max(0.0, (datetime.now(timezone.utc) - batch_updated_at).total_seconds() / 3600)
    else:
        metering_age_hours = None
    return {
        "signal_batch": _serialize_signal_batch(signal_batch),
        "refreshed_state": freshness_state,
        "metering_age_hours": round(metering_age_hours, 4) if metering_age_hours is not None else None,
        "freshness_score": freshness_score,
        "release_readiness_score": release_readiness_score,
    }


def _window_contains(value: float, lower: float | None, upper: float | None) -> bool:
    if lower is not None and value < lower:
        return False
    if upper is not None and value > upper:
        return False
    return True


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _materialize_signal_validity(signal_batch: SignalBatch | None) -> dict:
    if signal_batch is None:
        return {
            "status": "missing",
            "freshness_state": None,
            "potency": None,
            "stability_window_hours": None,
            "checks": ["signal missing"],
            "mechanistic_context": {},
            "supervisor_snapshot": None,
            "supervisor_history": [],
        }

    checks: list[str] = []
    freshness = (signal_batch.freshness_state or "unknown").lower()
    if "fresh" in freshness:
        checks.append("freshness OK")
    elif "stable" in freshness:
        checks.append("freshness borderline")
    elif "stale" in freshness:
        checks.append("freshness stale")
    else:
        checks.append("freshness unknown")

    if signal_batch.potency is None:
        checks.append("potency missing")
    elif signal_batch.potency > 0:
        checks.append("potency present")
    else:
        checks.append("potency invalid")

    if signal_batch.stability_window_hours is None:
        checks.append("stability window missing")
    else:
        checks.append(f"stability {signal_batch.stability_window_hours:.2f}h")

    qc_markers = signal_batch.qc_markers or {}
    compile_context = qc_markers.get("compile_context") or {}
    mechanistic_context = compile_context.get("mechanistic_context") or {}
    native_model_stack = compile_context.get("native_model_stack") or {}
    supervisor_snapshot = qc_markers.get("supervisor_latest")
    supervisor_history = qc_markers.get("supervisor_history")
    vision_observation = qc_markers.get("vision_observation")

    status = "valid"
    if "stale" in freshness or signal_batch.potency in (None, 0):
        status = "blocked"
    elif "stable" in freshness or signal_batch.stability_window_hours is None:
        status = "review"

    return {
        "status": status,
        "freshness_state": signal_batch.freshness_state,
        "potency": signal_batch.potency,
        "stability_window_hours": signal_batch.stability_window_hours,
        "checks": checks,
        "mechanistic_context": mechanistic_context,
        "native_model_stack": native_model_stack if isinstance(native_model_stack, dict) else {},
        "supervisor_snapshot": supervisor_snapshot if isinstance(supervisor_snapshot, dict) else None,
        "supervisor_history": supervisor_history if isinstance(supervisor_history, list) else [],
        "vision_observation": vision_observation if isinstance(vision_observation, dict) else None,
    }


def _materialize_contract_evaluation(
    *,
    signal_batch: SignalBatch | None,
    control_profile: ControlAPIProfile | None,
) -> dict:
    if control_profile is None:
        return {
            "status": "missing_contract",
            "contract_name": None,
            "contract_version": None,
            "dose_window_ok": None,
            "stability_ratio": None,
            "threshold_breaches": [],
        }

    threshold_breaches: list[str] = []
    dose_window_ok = None
    stability_ratio = None

    if signal_batch and signal_batch.potency is not None:
        dose_window_ok = _window_contains(
            signal_batch.potency,
            control_profile.dose_window_min,
            control_profile.dose_window_max,
        )
        if not dose_window_ok:
            threshold_breaches.append("dose_window")

    if control_profile.mtt and signal_batch and signal_batch.stability_window_hours is not None:
        stability_ratio = round(signal_batch.stability_window_hours / control_profile.mtt, 4)
        if stability_ratio < 1:
            threshold_breaches.append("stability_vs_mtt")
    elif control_profile.mtt:
        threshold_breaches.append("missing_stability_window")

    status = "pass" if not threshold_breaches else "review"
    if "dose_window" in threshold_breaches:
        status = "blocked"

    return {
        "status": status,
        "contract_name": control_profile.name,
        "contract_version": control_profile.version,
        "dose_window_ok": dose_window_ok,
        "stability_ratio": stability_ratio,
        "threshold_breaches": threshold_breaches,
    }


def _materialize_evidence_profile(batch: Batch) -> dict:
    metering_completeness = _compute_metering_completeness(batch)
    evidence_status = "high"
    if metering_completeness < 0.45:
        evidence_status = "low"
    elif metering_completeness < 0.75:
        evidence_status = "medium"

    return {
        "metering_completeness": metering_completeness,
        "evidence_status": evidence_status,
        "mass_balance_ratio": _safe_ratio(batch.dm_out, batch.dm_in),
    }


def recommend_portability(
    *,
    signal_batch: SignalBatch,
    executor_profile: ExecutorProfile,
    locality_profile: LocalityProfile | None,
    control_profile: ControlAPIProfile | None,
) -> dict:
    retuning_axes: list[str] = []
    locality_shift = None
    if locality_profile is not None:
        locality_shift = max(abs(locality_profile.dose_window_shift_pct or 0), abs(locality_profile.mtt_shift_pct or 0))
        if (locality_profile.dose_window_shift_pct or 0) != 0:
            retuning_axes.append("dose_window")
        if (locality_profile.mtt_shift_pct or 0) != 0:
            retuning_axes.append("mtt")

    plugin_mode = (executor_profile.plugin_mode or "").lower()
    if plugin_mode and plugin_mode not in {"standard", "default"}:
        retuning_axes.append("plugin_mode")

    score = 1.0
    if signal_batch.freshness_state and "stable" in signal_batch.freshness_state.lower():
        score -= 0.08
    if signal_batch.freshness_state and "stale" in signal_batch.freshness_state.lower():
        score -= 0.35
    if locality_shift is not None:
        score -= min(0.35, locality_shift / 100)
    if executor_profile.hal_min is not None and signal_batch.potency is not None and signal_batch.potency < executor_profile.hal_min:
        score -= 0.25
        retuning_axes.append("executor_hal")
    if executor_profile.hal_max is not None and signal_batch.potency is not None and signal_batch.potency > executor_profile.hal_max:
        score -= 0.25
        retuning_axes.append("executor_hal")
    if control_profile and control_profile.mtt and signal_batch.stability_window_hours is not None:
        score -= max(0.0, min(0.2, (control_profile.mtt - signal_batch.stability_window_hours) / max(control_profile.mtt, 1)))

    deduped_axes = list(dict.fromkeys(retuning_axes))
    portability_score = round(_clamp(score), 4)

    if portability_score < 0.45:
        recommended_outcome = "FAIL"
    elif deduped_axes:
        recommended_outcome = "PASS_WITH_RETUNING"
    else:
        recommended_outcome = "PASS"

    retuning_magnitude = None
    if deduped_axes:
        retuning_magnitude = round(max(0.05, min(0.5, 1 - portability_score)), 3)

    override_outcome = None
    if control_profile is None and recommended_outcome == "PASS":
        override_outcome = "PASS_WITH_RETUNING"

    executor_label = getattr(executor_profile, "name", None) or f"Executor {executor_profile.id}"
    locality_label = (
        getattr(locality_profile, "name", None)
        if locality_profile is not None
        else "the current locality context"
    ) or "the current locality context"
    if recommended_outcome == "PASS":
        rationale = (
            f"The signal stays within the current portability envelope for {executor_label} under {locality_label}."
        )
        recommended_action = "Proceed with the current executor-locality pairing."
        requires_requalification = False
    elif recommended_outcome == "PASS_WITH_RETUNING":
        axis_text = ", ".join(deduped_axes) if deduped_axes else "the active execution settings"
        rationale = (
            f"The signal can transfer to {executor_label}, but portability risk remains elevated around {axis_text}."
        )
        recommended_action = f"Retune {axis_text} before formal release."
        requires_requalification = False
    else:
        axis_text = ", ".join(deduped_axes) if deduped_axes else "the active executor-locality pairing"
        rationale = (
            f"The current signal and portability context remain outside the safe transfer envelope for {executor_label}."
        )
        recommended_action = f"Requalify the signal under a different contract, executor, or locality instead of releasing through {axis_text}."
        requires_requalification = True

    payload = PortabilityRecommendationResponse(
        signal_batch_id=signal_batch.id,
        executor_profile_id=executor_profile.id,
        locality_profile_id=locality_profile.id if locality_profile else None,
        recommended_outcome=recommended_outcome,
        rationale=rationale,
        recommended_action=recommended_action,
        requires_requalification=requires_requalification,
        retuning_axes=deduped_axes,
        retuning_magnitude=retuning_magnitude,
        override_outcome=override_outcome,
    ).model_dump()
    payload["portability_score"] = portability_score
    return payload


async def _latest_for_batch(
    db: AsyncSession,
    model,
    *,
    batch_id: int,
    tenant_id: int,
):
    result = await db.execute(
        select(model)
        .where(model.batch_id == batch_id, model.tenant_id == tenant_id)
        .order_by(desc(model.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_batch_bos_overview(
    db: AsyncSession,
    *,
    batch: Batch,
    tenant_id: int,
) -> BatchBOSOverview:
    signal_batch = await _latest_for_batch(db, SignalBatch, batch_id=batch.id, tenant_id=tenant_id)
    boundary_ledger = await _latest_for_batch(db, BoundaryLedger, batch_id=batch.id, tenant_id=tenant_id)
    release_decision = await _latest_for_batch(db, ReleaseDecision, batch_id=batch.id, tenant_id=tenant_id)

    control_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at), desc(ControlAPIProfile.id))
        .limit(1)
    )
    control_profile = control_result.scalar_one_or_none()

    audit_packet_result = await db.execute(
        select(AuditPacket)
        .where(AuditPacket.batch_id == batch.id, AuditPacket.tenant_id == tenant_id)
        .order_by(desc(AuditPacket.created_at), desc(AuditPacket.id))
        .limit(1)
    )
    audit_packet = audit_packet_result.scalar_one_or_none()

    portability_result = await db.execute(
        select(PortabilityAudit)
        .join(SignalBatch, PortabilityAudit.signal_batch_id == SignalBatch.id)
        .where(
            PortabilityAudit.tenant_id == tenant_id,
            SignalBatch.batch_id == batch.id,
            SignalBatch.tenant_id == tenant_id,
        )
        .order_by(desc(PortabilityAudit.created_at), desc(PortabilityAudit.id))
    )
    portability_audits = portability_result.scalars().all()

    signal_ids = {audit.signal_batch_id for audit in portability_audits}
    executor_ids = {audit.executor_profile_id for audit in portability_audits}
    locality_ids = {
        audit.locality_profile_id for audit in portability_audits if audit.locality_profile_id is not None
    }

    signals = (
        {
            item.id: item
            for item in (
                await db.execute(
                    select(SignalBatch).where(
                        SignalBatch.id.in_(signal_ids),
                        SignalBatch.tenant_id == tenant_id,
                    )
                )
            ).scalars().all()
        }
        if signal_ids
        else {}
    )
    executors = (
        {
            item.id: item
            for item in (
                await db.execute(
                    select(ExecutorProfile).where(
                        ExecutorProfile.id.in_(executor_ids),
                        ExecutorProfile.tenant_id == tenant_id,
                    )
                )
            ).scalars().all()
        }
        if executor_ids
        else {}
    )
    localities = (
        {
            item.id: item
            for item in (
                await db.execute(
                    select(LocalityProfile).where(
                        LocalityProfile.id.in_(locality_ids),
                        LocalityProfile.tenant_id == tenant_id,
                    )
                )
            ).scalars().all()
        }
        if locality_ids
        else {}
    )

    portability_payload = []
    for audit in portability_audits:
        recommendation = None
        signal = signals.get(audit.signal_batch_id)
        executor = executors.get(audit.executor_profile_id)
        if signal is not None and executor is not None:
            recommendation = recommend_portability(
                signal_batch=signal,
                executor_profile=executor,
                locality_profile=(
                    localities.get(audit.locality_profile_id)
                    if audit.locality_profile_id is not None
                    else None
                ),
                control_profile=control_profile,
            )
        portability_payload.append(PortabilityAuditResponse(**serialize_portability_audit(audit, recommendation)))

    compile_status = "not_started"
    if signal_batch is not None:
        compile_status = (
            "compiled"
            if isinstance(signal_batch.qc_markers, dict) and signal_batch.qc_markers.get("compile_context")
            else "manual"
        )

    latest_signal_status = "missing"
    if audit_packet and isinstance(audit_packet.packet, dict):
        signal_validity = audit_packet.packet.get("signal_validity")
        if isinstance(signal_validity, dict) and isinstance(signal_validity.get("status"), str):
            latest_signal_status = signal_validity["status"]
    elif signal_batch is not None:
        latest_signal_status = signal_batch.freshness_state or "unknown"

    latest_native_run = summarize_latest_native_run(batch_id=batch.id)

    return BatchBOSOverview(
        signal_batch=SignalBatchResponse.model_validate(signal_batch) if signal_batch else None,
        control_profile=(
            ControlAPIProfileResponse.model_validate(control_profile) if control_profile else None
        ),
        boundary_ledger=(
            BoundaryLedgerResponse.model_validate(boundary_ledger) if boundary_ledger else None
        ),
        release_decision=(
            ReleaseDecisionResponse(**serialize_release_decision(release_decision))
            if release_decision
            else None
        ),
        audit_packet=AuditPacketResponse(**serialize_audit_packet(audit_packet)) if audit_packet else None,
        portability_audits=portability_payload,
        compile_status=compile_status,
        latest_signal_status=latest_signal_status,
        latest_native_run=latest_native_run,
    )


def serialize_release_decision(decision: ReleaseDecision) -> dict:
    payload = ReleaseDecisionResponse.model_validate(decision).model_dump()
    trigger_metrics = payload.get("trigger_metrics") or {}
    payload["applied_contract"] = trigger_metrics.get("applied_contract")
    payload["applied_locality_shift"] = trigger_metrics.get("applied_locality_shift")
    payload["decision_confidence"] = payload.get("decision_confidence")
    if payload["decision_confidence"] is None:
        payload["decision_confidence"] = trigger_metrics.get("decision_confidence")
    payload["reason_codes"] = payload.get("reason_codes") or []
    payload["blocking_factors"] = payload.get("blocking_factors") or []
    payload["warning_factors"] = payload.get("warning_factors") or []
    payload["passed_checks"] = payload.get("passed_checks") or []
    payload["trigger_metrics"] = trigger_metrics
    return payload


def serialize_audit_packet(packet: AuditPacket) -> dict:
    payload = AuditPacketResponse.model_validate(packet).model_dump()
    packet_payload = packet.packet or {}
    payload["contract_evaluation"] = packet_payload.get("contract_evaluation") or {}
    payload["signal_validity"] = packet_payload.get("signal_validity") or {}
    payload["retuning_axes"] = packet_payload.get("retuning_axes") or {}
    return payload


def serialize_portability_audit(audit: PortabilityAudit, recommendation: dict | None = None) -> dict:
    data = PortabilityAuditResponse.model_validate(audit).model_dump()
    data["recommended_outcome"] = recommendation.get("recommended_outcome") if recommendation else None
    data["rationale"] = recommendation.get("rationale") if recommendation else None
    data["recommended_action"] = recommendation.get("recommended_action") if recommendation else None
    data["requires_requalification"] = recommendation.get("requires_requalification") if recommendation else False
    data["retuning_axes"] = recommendation.get("retuning_axes") if recommendation else None
    data["retuning_magnitude"] = recommendation.get("retuning_magnitude") if recommendation else None
    data["portability_score"] = recommendation.get("portability_score") if recommendation else None
    data["override_outcome"] = recommendation.get("override_outcome") if recommendation else data.get("override_outcome")
    return data


def _build_release_outcome(
    *,
    batch: Batch,
    signal_batch: SignalBatch | None,
    control_profile: ControlAPIProfile | None,
) -> tuple[str, list[str], list[str], list[str], list[str], dict, str]:
    reason_codes: list[str] = []
    blocking_factors: list[str] = []
    warning_factors: list[str] = []
    passed_checks: list[str] = []
    trigger_metrics: dict[str, Any] = {
        "potency": signal_batch.potency if signal_batch else None,
        "freshness_state": signal_batch.freshness_state if signal_batch else None,
        "mtt": control_profile.mtt if control_profile else None,
    }

    if signal_batch is None:
        reason_codes.append("missing_signal_batch")
        blocking_factors.append("No signal batch is available for release evaluation.")
        rationale = "Release evaluation could not proceed because the batch has no compiled signal."
        trigger_metrics["contract_status"] = "present" if control_profile else "missing"
        return "INSUFFICIENT_EVIDENCE", reason_codes, blocking_factors, warning_factors, passed_checks, trigger_metrics, rationale

    freshness = (signal_batch.freshness_state or "").lower()
    if "stale" in freshness:
        reason_codes.append("stale_signal")
        blocking_factors.append("Signal freshness is stale.")
    elif "fresh" not in freshness and "stable" not in freshness:
        warning_factors.append("Signal freshness state is unspecified or non-standard.")
    else:
        passed_checks.append("signal_freshness")

    if signal_batch.potency is None:
        reason_codes.append("missing_potency")
        blocking_factors.append("Signal potency is missing.")
    elif signal_batch.potency <= 0:
        reason_codes.append("invalid_potency")
        blocking_factors.append("Signal potency must be greater than zero.")
    else:
        passed_checks.append("signal_potency_present")

    if control_profile is None:
        warning_factors.append("No control profile was attached to the evaluation.")
    else:
        passed_checks.append("control_profile_present")
        if signal_batch.potency is not None and not _window_contains(
            signal_batch.potency,
            control_profile.dose_window_min,
            control_profile.dose_window_max,
        ):
            reason_codes.append("potency_out_of_contract")
            blocking_factors.append("Signal potency falls outside the configured dose window.")
        if (
            control_profile.mtt is not None
            and signal_batch.stability_window_hours is None
        ):
            reason_codes.append("missing_stability_window")
            blocking_factors.append("Signal stability window is missing for the configured MTT.")
        elif (
            control_profile.mtt is not None
            and signal_batch.stability_window_hours is not None
            and signal_batch.stability_window_hours < control_profile.mtt * 0.75
        ):
            reason_codes.append("stability_critically_below_mtt")
            blocking_factors.append("Signal stability is materially below the configured MTT.")
        elif (
            control_profile.mtt is not None
            and signal_batch.stability_window_hours is not None
            and signal_batch.stability_window_hours < control_profile.mtt
        ):
            reason_codes.append("stability_below_mtt")
            warning_factors.append("Signal stability is shorter than the configured MTT.")

    metering_completeness = _compute_metering_completeness(batch)
    trigger_metrics["metering_completeness"] = metering_completeness
    if metering_completeness < 0.45:
        reason_codes.append("metering_too_sparse")
        blocking_factors.append("Batch metering completeness is too low for a confident release.")
    elif metering_completeness < 0.75:
        warning_factors.append("Batch metering completeness is below the preferred confidence band.")
    else:
        passed_checks.append("metering_completeness")

    if batch.dm_in is not None and batch.dm_out is not None and batch.dm_in > 0:
        passed_checks.append("mass_balance_inputs_present")
        trigger_metrics["ser_ratio"] = _safe_ratio(batch.dm_out, batch.dm_in)

    qc_markers = getattr(signal_batch, "qc_markers", None) or {}
    vision_observation = qc_markers.get("vision_observation") if signal_batch else None
    if isinstance(vision_observation, dict):
        trigger_metrics["vision_observation"] = vision_observation
        if vision_observation.get("anomaly_flag") is True:
            reason_codes.append("vision_anomaly_review")
            warning_factors.append("Vision observation flagged a possible anomaly for operator review.")
        confidence_mean = vision_observation.get("confidence_mean")
        if isinstance(confidence_mean, int | float) and confidence_mean < 0.45:
            warning_factors.append("Vision observation confidence is below the preferred review band.")

    if blocking_factors:
        decision = "FAIL"
    elif warning_factors:
        decision = "PASS_WITH_RETUNING"
    else:
        decision = "PASS"

    rationale = {
        "PASS": "All available protocol checks passed with the current signal and batch evidence.",
        "PASS_WITH_RETUNING": "The release can proceed, but the current protocol context suggests retuning or closer monitoring.",
        "FAIL": "The protocol checks found a blocking condition that prevents release.",
        "INSUFFICIENT_EVIDENCE": "The available protocol evidence is not sufficient for a confident release decision.",
    }[decision]

    trigger_metrics["contract_status"] = "present" if control_profile else "missing"
    return decision, reason_codes, blocking_factors, warning_factors, passed_checks, trigger_metrics, rationale


async def refresh_audit_packet_for_signal(
    db: AsyncSession,
    *,
    signal_batch: SignalBatch,
    current_user: User,
) -> AuditPacket:
    batch = await db.get(Batch, signal_batch.batch_id)
    if batch is None:
        raise ValueError(f"Batch {signal_batch.batch_id} was not found for audit packet refresh")

    control_profile_result = await db.execute(
        select(ControlAPIProfile)
        .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
        .order_by(desc(ControlAPIProfile.updated_at))
        .limit(1)
    )
    control_profile = control_profile_result.scalar_one_or_none()

    boundary_ledger = await _latest_for_batch(db, BoundaryLedger, batch_id=batch.id, tenant_id=current_user.tenant_id)
    release_decision = await _latest_for_batch(
        db, ReleaseDecision, batch_id=batch.id, tenant_id=current_user.tenant_id
    )

    portability_result = await db.execute(
        select(PortabilityAudit)
        .where(PortabilityAudit.signal_batch_id == signal_batch.id, PortabilityAudit.tenant_id == current_user.tenant_id)
        .order_by(desc(PortabilityAudit.created_at))
    )
    portability_audits = portability_result.scalars().all()
    executor_ids = {audit.executor_profile_id for audit in portability_audits}
    locality_ids = {audit.locality_profile_id for audit in portability_audits if audit.locality_profile_id is not None}

    executor_names: dict[int, str] = {}
    locality_names: dict[int, str] = {}
    if executor_ids:
        executor_result = await db.execute(
            select(ExecutorProfile.id, ExecutorProfile.name).where(ExecutorProfile.id.in_(executor_ids))
        )
        executor_names = {row[0]: row[1] for row in executor_result.all()}
    if locality_ids:
        locality_result = await db.execute(
            select(LocalityProfile.id, LocalityProfile.name).where(LocalityProfile.id.in_(locality_ids))
        )
        locality_names = {row[0]: row[1] for row in locality_result.all()}

    contract_evaluation = _materialize_contract_evaluation(
        signal_batch=signal_batch,
        control_profile=control_profile,
    )
    signal_validity = _materialize_signal_validity(signal_batch)
    evidence_profile = _materialize_evidence_profile(batch)
    mechanistic_context = signal_validity.get("mechanistic_context") or {}
    native_model_stack = build_native_model_embedding(batch=batch, signal_batch=signal_batch)
    latest_native_run = summarize_latest_native_run(batch_id=batch.id)

    recommendation_lookup: dict[int, dict] = {}
    locality_by_id: dict[int, LocalityProfile] = {}
    if locality_ids:
        locality_model_result = await db.execute(
            select(LocalityProfile).where(LocalityProfile.id.in_(locality_ids))
        )
        locality_by_id = {item.id: item for item in locality_model_result.scalars().all()}
    executor_by_id: dict[int, ExecutorProfile] = {}
    if executor_ids:
        executor_model_result = await db.execute(
            select(ExecutorProfile).where(ExecutorProfile.id.in_(executor_ids))
        )
        executor_by_id = {item.id: item for item in executor_model_result.scalars().all()}
    for audit in portability_audits:
        executor = executor_by_id.get(audit.executor_profile_id)
        if executor is None:
            continue
        recommendation_lookup[audit.id] = recommend_portability(
            signal_batch=signal_batch,
            executor_profile=executor,
            locality_profile=locality_by_id.get(audit.locality_profile_id) if audit.locality_profile_id else None,
            control_profile=control_profile,
        )

    packet_payload = {
        "batch": {
            "id": batch.id,
            "batch_id": batch.batch_id,
            "species": batch.species,
            "status": batch.status,
        },
        "signal_batch": {
            "id": signal_batch.id,
            "signal_api_version": signal_batch.signal_api_version,
            "compiled_signal_id": signal_batch.compiled_signal_id,
            "potency": signal_batch.potency,
            "potency_unit": signal_batch.potency_unit,
            "freshness_state": signal_batch.freshness_state,
        },
        "control_profile": (
            {
                "id": control_profile.id,
                "name": control_profile.name,
                "version": control_profile.version,
                "mtt": control_profile.mtt,
                "hal_min": control_profile.hal_min,
                "hal_max": control_profile.hal_max,
                "dose_window_min": control_profile.dose_window_min,
                "dose_window_max": control_profile.dose_window_max,
                "stability_window_hours": control_profile.stability_window_hours,
            }
            if control_profile
            else None
        ),
        "boundary_ledger": (
            {
                "id": boundary_ledger.id,
                "d_prime": boundary_ledger.d_prime,
                "g_prime": boundary_ledger.g_prime,
                "ser_value": boundary_ledger.ser_value,
                "ser_system": None,
                "delta_delta_ser": boundary_ledger.delta_delta_ser,
                "closure_residual": boundary_ledger.closure_residual,
                "closure_penalty": None,
                "evidence_penalty": None,
                "metering_completeness": boundary_ledger.metering_completeness,
                "qc_flags": boundary_ledger.qc_flags or [],
                "evidence_level": boundary_ledger.evidence_level,
                "notes": boundary_ledger.notes,
            }
            if boundary_ledger
            else None
        ),
        "release_decision": (
            {
                "decision": release_decision.decision,
                "reason_codes": release_decision.reason_codes or [],
                "blocking_factors": release_decision.blocking_factors or [],
                "warning_factors": release_decision.warning_factors or [],
                "passed_checks": release_decision.passed_checks or [],
                "trigger_metrics": {
                    **(release_decision.trigger_metrics or {}),
                    **({"vision_observation": signal_validity.get("vision_observation")} if signal_validity.get("vision_observation") else {}),
                },
                "decision_confidence": (
                    getattr(release_decision, "decision_confidence", None)
                    if getattr(release_decision, "decision_confidence", None) is not None
                    else (release_decision.trigger_metrics or {}).get("decision_confidence")
                ),
                "rationale": release_decision.rationale,
            }
            if release_decision
            else None
        ),
        "portability_audits": [
            {
                "id": audit.id,
                "executor_profile_id": audit.executor_profile_id,
                "locality_profile_id": audit.locality_profile_id,
                "executor_name": executor_names.get(audit.executor_profile_id),
                "locality_name": locality_names.get(audit.locality_profile_id) if audit.locality_profile_id else None,
                "outcome": audit.outcome,
                "retuning_required": audit.retuning_required,
                "recommended_outcome": recommendation_lookup.get(audit.id, {}).get("recommended_outcome"),
                "rationale": recommendation_lookup.get(audit.id, {}).get("rationale"),
                "recommended_action": recommendation_lookup.get(audit.id, {}).get("recommended_action"),
                "requires_requalification": recommendation_lookup.get(audit.id, {}).get("requires_requalification", False),
                "retuning_axes": recommendation_lookup.get(audit.id, {}).get("retuning_axes", []),
                "retuning_magnitude": recommendation_lookup.get(audit.id, {}).get("retuning_magnitude"),
                "portability_score": recommendation_lookup.get(audit.id, {}).get("portability_score"),
                "trigger_metrics": audit.trigger_metrics or {},
            }
            for audit in portability_audits
        ],
        "contract_evaluation": contract_evaluation,
        "signal_validity": signal_validity,
        "retuning_axes": {
            "recommended_by_portability": [
                {
                    "audit_id": audit_id,
                    "recommended_outcome": recommendation["recommended_outcome"],
                    "rationale": recommendation["rationale"],
                    "recommended_action": recommendation["recommended_action"],
                    "requires_requalification": recommendation["requires_requalification"],
                    "retuning_axes": recommendation["retuning_axes"],
                    "retuning_magnitude": recommendation["retuning_magnitude"],
                    "portability_score": recommendation["portability_score"],
                }
                for audit_id, recommendation in recommendation_lookup.items()
            ],
            "evidence_profile": evidence_profile,
        },
        "mechanistic_context": mechanistic_context,
        "native_model_stack": native_model_stack,
        "native_forecast_evidence": latest_native_run,
        "generation_context": {
            "schema_version": "BOS-1.0",
            "compiled_at": _now_iso(),
            "compiled_by_user_id": current_user.id,
            "source_ids": {
                "batch_id": batch.id,
                "signal_batch_id": signal_batch.id,
                "control_profile_id": control_profile.id if control_profile else None,
                "boundary_ledger_id": boundary_ledger.id if boundary_ledger else None,
                "release_decision_id": release_decision.id if release_decision else None,
                "portability_audit_ids": [audit.id for audit in portability_audits],
            },
            "hash": hashlib.sha256(
                json.dumps(
                    {
                        "batch_id": batch.id,
                        "signal_batch_id": signal_batch.id,
                        "release_decision_id": release_decision.id if release_decision else None,
                        "portability_ids": [audit.id for audit in portability_audits],
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest(),
            "source_mode": "refresh",
        },
    }

    existing_result = await db.execute(
        select(AuditPacket)
        .where(AuditPacket.batch_id == batch.id, AuditPacket.tenant_id == current_user.tenant_id)
        .order_by(desc(AuditPacket.created_at))
        .limit(1)
    )
    audit_packet = existing_result.scalar_one_or_none()
    if audit_packet is None:
        audit_packet = AuditPacket(
            batch_id=batch.id,
            release_decision_id=release_decision.id if release_decision else None,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            packet_version="AUD-1.0",
            evidence_level=(boundary_ledger.evidence_level if boundary_ledger else None),
            packet=packet_payload,
        )
        db.add(audit_packet)
    else:
        audit_packet.release_decision_id = release_decision.id if release_decision else None
        audit_packet.user_id = current_user.id
        audit_packet.evidence_level = boundary_ledger.evidence_level if boundary_ledger else None
        audit_packet.packet = packet_payload
        audit_packet.generated_at = datetime.now(timezone.utc)

    await db.flush()
    return audit_packet


async def evaluate_release_for_batch(
    db: AsyncSession,
    *,
    batch: Batch,
    current_user: User,
    control_profile_id: int | None = None,
    signal_batch_id: int | None = None,
    locality_profile_id: int | None = None,
    persist: bool = True,
):
    if signal_batch_id is not None:
        signal_batch = await db.get(SignalBatch, signal_batch_id)
    else:
        signal_batch = await _latest_for_batch(db, SignalBatch, batch_id=batch.id, tenant_id=current_user.tenant_id)

    if control_profile_id is not None:
        control_profile = await db.get(ControlAPIProfile, control_profile_id)
    else:
        control_result = await db.execute(
            select(ControlAPIProfile)
            .where(ControlAPIProfile.tenant_id == current_user.tenant_id, ControlAPIProfile.active.is_(True))
            .order_by(desc(ControlAPIProfile.updated_at))
            .limit(1)
        )
        control_profile = control_result.scalar_one_or_none()

    decision_name, reason_codes, blocking_factors, warning_factors, passed_checks, trigger_metrics, rationale = _build_release_outcome(
        batch=batch,
        signal_batch=signal_batch,
        control_profile=control_profile,
    )

    ser_value = batch.score if batch.score is not None else _safe_ratio(batch.dm_out, batch.dm_in)
    decision_confidence = round(
        _clamp(
            (
                (0.55 if signal_batch is not None else 0.15)
                + (0.2 if control_profile is not None else 0.0)
                + (_compute_metering_completeness(batch) * 0.25)
            )
        ),
        4,
    )
    locality_profile = None
    if locality_profile_id is not None:
        locality_profile = await db.get(LocalityProfile, locality_profile_id)
    boundary_ledger = BoundaryLedger(
        batch_id=batch.id,
        signal_batch_id=signal_batch.id if signal_batch else None,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        d_prime=signal_batch.potency if signal_batch else None,
        g_prime=signal_batch.stability_window_hours if signal_batch else None,
        ser_value=ser_value,
        delta_delta_ser=None,
        closure_residual=None if ser_value is not None else 1.0,
        metering_completeness=_compute_metering_completeness(batch),
        qc_flags=[],
        measured_vs_estimated={"dm_in": batch.dm_in, "dm_out": batch.dm_out},
        evidence_level="Validated" if decision_name == "PASS" else "Supported",
        notes="Generated by minimal BOS protocol evaluator.",
    )

    release_decision = ReleaseDecision(
        batch_id=batch.id,
        signal_batch_id=signal_batch.id if signal_batch else None,
        boundary_ledger_id=None,
        control_profile_id=control_profile.id if control_profile else None,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        decision=decision_name,
        reason_codes=reason_codes,
        trigger_metrics={
            **trigger_metrics,
            "potency": signal_batch.potency if signal_batch else None,
            "stability_window_hours": signal_batch.stability_window_hours if signal_batch else None,
            "mtt": control_profile.mtt if control_profile else None,
            "ser_value": ser_value,
            "decision_confidence": decision_confidence,
            "mechanistic_context": (
                ((signal_batch.qc_markers or {}).get("compile_context") or {}).get("mechanistic_context")
                if signal_batch is not None
                else {}
            ),
            "applied_contract": (
                {
                    "name": control_profile.name,
                    "version": control_profile.version,
                    "dose_window_min": control_profile.dose_window_min,
                    "dose_window_max": control_profile.dose_window_max,
                    "mtt": control_profile.mtt,
                }
                if control_profile
                else None
            ),
            "applied_locality_shift": (
                {
                    "id": locality_profile.id,
                    "name": locality_profile.name,
                    "dose_window_shift_pct": locality_profile.dose_window_shift_pct,
                    "mtt_shift_pct": locality_profile.mtt_shift_pct,
                }
                if locality_profile
                else None
            ),
        },
        approver=current_user.full_name or current_user.username,
        rationale=rationale,
        blocking_factors=blocking_factors,
        warning_factors=warning_factors,
        passed_checks=passed_checks,
    )

    audit_packet = None
    if persist:
        db.add(boundary_ledger)
        await db.flush()
        release_decision.boundary_ledger_id = boundary_ledger.id
        db.add(release_decision)
        await db.flush()
        audit_packet = await refresh_audit_packet_for_signal(
            db,
            signal_batch=signal_batch if signal_batch is not None else SignalBatch(
                batch_id=batch.id,
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
            ),
            current_user=current_user,
        )
        await db.commit()
        await db.refresh(boundary_ledger)
        await db.refresh(release_decision)
        if audit_packet is not None:
            await db.refresh(audit_packet)

    return signal_batch, control_profile, boundary_ledger, release_decision, audit_packet
