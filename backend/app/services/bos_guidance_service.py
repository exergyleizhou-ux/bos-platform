"""
BOS guidance service.

Turns evidence gaps into actionable next steps for operators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.models import Batch, ControlAPIProfile, LocalityProfile, PortabilityAudit, ReleaseDecision, SignalBatch


SEVERITY_ORDER = {
    "critical": 0,
    "warning": 1,
    "info": 2,
}

CODE_PRIORITY = {
    "missing_signal_batch": 0,
    "stale_signal_window": 1,
    "release_blocked": 2,
    "release_insufficient_evidence": 3,
    "metering_too_sparse": 4,
    "missing_potency": 5,
    "portability_failed": 6,
    "release_retuning_required": 7,
    "portability_retuning_required": 8,
    "missing_control_profile": 9,
    "missing_stability_window": 10,
    "release_not_evaluated": 11,
    "locality_not_selected": 12,
    "native_model_stack_ready": 13,
}


@dataclass(slots=True)
class GuidanceItem:
    code: str
    severity: str
    title: str
    message: str
    recommended_action: str
    blocking: bool


def _reason_code_action(reason_code: str) -> str | None:
    return {
        "missing_signal_batch": "Compile a signal batch before evaluating release again.",
        "stale_signal": "Refresh or recompile the signal before evaluating release again.",
        "missing_potency": "Capture potency or recompile the signal before making a release decision.",
        "invalid_potency": "Correct the signal potency inputs before making a release decision.",
        "potency_out_of_contract": "Retune the control profile or compile a signal that fits the dose window.",
        "missing_stability_window": "Refresh the signal state or compile a signal with a stability window.",
        "stability_critically_below_mtt": "Increase the stability window or lower the contract MTT before release.",
        "stability_below_mtt": "Review the MTT mismatch and retune the handover plan before release.",
        "metering_too_sparse": "Capture the missing metering before evaluating release again.",
    }.get(reason_code)


def build_batch_guidance(
    *,
    batch: Batch,
    signal_batch: SignalBatch | None,
    control_profile: ControlAPIProfile | None,
    locality_profile: LocalityProfile | None,
    release_decision: ReleaseDecision | None,
    portability_audits: list[PortabilityAudit],
    native_model_stack: dict | None = None,
) -> dict:
    items: list[GuidanceItem] = []

    def add(
        code: str,
        severity: str,
        title: str,
        message: str,
        recommended_action: str,
        *,
        blocking: bool,
    ) -> None:
        items.append(
            GuidanceItem(
                code=code,
                severity=severity,
                title=title,
                message=message,
                recommended_action=recommended_action,
                blocking=blocking,
            )
        )

    freshness = (signal_batch.freshness_state or "").lower() if signal_batch is not None else ""

    if signal_batch is None:
        add(
            "missing_signal_batch",
            "critical",
            "Signal not compiled",
            "This batch does not have a compiled BOS signal yet.",
            "Compile the signal first.",
            blocking=True,
        )
    else:
        if "stale" in freshness:
            add(
                "stale_signal_window",
                "critical",
                "Signal is outside the freshness window",
                "The latest signal is stale, so the current release posture should not be trusted without refreshing or recompiling it.",
                "Refresh or recompile the signal before continuing.",
                blocking=True,
            )
        if signal_batch.potency is None:
            add(
                "missing_potency",
                "critical",
                "Signal potency missing",
                "The current signal is missing potency, so release confidence is limited.",
                "Capture potency or recompile the signal.",
                blocking=True,
            )
        if signal_batch.stability_window_hours is None:
            add(
                "missing_stability_window",
                "warning",
                "Signal stability window missing",
                "The signal does not include a stability window, so downstream release judgement will stay conservative.",
                "Refresh signal state or recompile with a stability window.",
                blocking=False,
            )

    if batch.n_larvae is None:
        add(
            "missing_n_larvae",
            "warning",
            "Larval nitrogen missing",
            "Nitrogen recovery is less trustworthy because larval nitrogen has not been recorded.",
            "Capture larval nitrogen recovery data.",
            blocking=False,
        )
    if batch.n_frass is None:
        add(
            "missing_n_frass",
            "warning",
            "Frass nitrogen missing",
            "Nitrogen closure is incomplete because frass nitrogen is missing.",
            "Capture frass nitrogen recovery data.",
            blocking=False,
        )

    observed_values = [
        batch.dm_in,
        batch.dm_out,
        batch.n_in,
        batch.n_larvae,
        batch.n_frass,
        batch.temperature,
        batch.moisture,
    ]
    metering_completeness = sum(value is not None for value in observed_values) / len(observed_values)
    if metering_completeness < 0.45:
        add(
            "metering_too_sparse",
            "critical",
            "Evidence coverage too low",
            "Current metering completeness is too low for a confident release judgement.",
            "Capture the missing metering before deciding release.",
            blocking=True,
        )

    if locality_profile is None:
        add(
            "locality_not_selected",
            "info",
            "No locality selected",
            "Release and portability logic are currently running without a site-specific locality context.",
            "Select a locality profile before re-evaluating release.",
            blocking=False,
        )

    if not portability_audits:
        add(
            "no_portability_check",
            "warning",
            "No portability check recorded",
            "This batch has not been checked against any executor or locality portability target yet.",
            "Run a portability check for the target executor and locality.",
            blocking=False,
        )
    else:
        failing_audit = next((audit for audit in portability_audits if audit.outcome == "FAIL"), None)
        if failing_audit is not None:
            add(
                "portability_failed",
                "critical",
                "Portability failed for the current target",
                "At least one persisted portability audit failed, so the current signal should not be released into that executor context.",
                "Retune the executor or locality pairing before release.",
                blocking=True,
            )
        elif any(audit.retuning_required for audit in portability_audits):
            add(
                "portability_retuning_required",
                "warning",
                "Portability retuning is still required",
                "A persisted portability audit indicates the target context can work only with retuning.",
                "Retune the executor or locality settings before release.",
                blocking=False,
            )

    if control_profile is None:
        add(
            "missing_control_profile",
            "warning",
            "No active control contract",
            "BOS is evaluating this batch without a control profile, which reduces confidence.",
            "Select or create a control profile first.",
            blocking=False,
        )

    if release_decision is None and signal_batch is not None:
        add(
            "release_not_evaluated",
            "info",
            "Release not evaluated",
            "The batch has a signal, but release evaluation has not been run yet.",
            "Run the release evaluation next.",
            blocking=False,
        )
    elif release_decision is not None:
        primary_action = next(
            (
                action
                for action in (_reason_code_action(reason_code) for reason_code in (release_decision.reason_codes or []))
                if action
            ),
            None,
        )
        decision = (release_decision.decision or "").upper()
        if decision == "FAIL":
            add(
                "release_blocked",
                "critical",
                "Release is currently blocked",
                (
                    release_decision.blocking_factors[0]
                    if release_decision.blocking_factors
                    else "The latest release evaluation found a blocking condition."
                ),
                primary_action or "Resolve the blocking condition and evaluate release again.",
                blocking=True,
            )
        elif decision == "PASS_WITH_RETUNING":
            add(
                "release_retuning_required",
                "warning",
                "Release can proceed only with retuning",
                (
                    release_decision.warning_factors[0]
                    if release_decision.warning_factors
                    else "The latest release evaluation recommends retuning or closer monitoring."
                ),
                primary_action or "Retune the release conditions and evaluate again before scale-up.",
                blocking=False,
            )
        elif decision == "INSUFFICIENT_EVIDENCE":
            add(
                "release_insufficient_evidence",
                "critical",
                "Release evidence is still incomplete",
                release_decision.rationale or "The latest release evaluation could not reach a confident decision.",
                primary_action or "Fill the evidence gaps and re-evaluate release.",
                blocking=True,
            )

    primary_recommendation = (native_model_stack or {}).get("primary_recommendation") or {}
    if primary_recommendation:
        add(
            "native_model_stack_ready",
            "info",
            "Native model stack available",
            f"BOS can natively attach the recommended stack: {primary_recommendation.get('title', 'frontier model stack')}.",
            f"Attach the recommended native model stack: {primary_recommendation.get('title', 'frontier model stack')}.",
            blocking=False,
        )

    items.sort(
        key=lambda item: (
            not item.blocking,
            SEVERITY_ORDER.get(item.severity, 99),
            CODE_PRIORITY.get(item.code, 99),
            item.code,
        )
    )
    recommended_actions: list[str] = []
    for item in items:
        if item.recommended_action not in recommended_actions:
            recommended_actions.append(item.recommended_action)

    return {
        "batch_id": batch.id,
        "gap_items": [asdict(item) for item in items],
        "recommended_actions": recommended_actions[:5],
    }
