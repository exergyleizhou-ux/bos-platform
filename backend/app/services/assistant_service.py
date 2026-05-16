"""Deterministic assistant control plane for BOS Simulation Lab."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import uuid
from typing import Any, Awaitable, Callable, Literal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import (
    AssistantConfirmationRequestRecord,
    AssistantRunRecord,
    AssistantToolCallRecord,
    BenchmarkRunRecord,
    HumanApprovalRequestRecord,
    KnowledgeRelationRecord,
    ModelRegistryRecord,
    ModelVersionRecord,
    ReleaseDecision,
)
from app.schemas.assistant import (
    AssistantConfirmRequest,
    AssistantConfirmationRequestResponse,
    AssistantReviewConfirmationItem,
    AssistantReviewHumanApprovalItem,
    AssistantReviewWorkbenchResponse,
    AssistantRunCreate,
    AssistantRunResponse,
    AssistantToolCallResponse,
    HumanApprovalResolveRequest,
)
from app.schemas.compliance import ComplianceEvaluateRequest
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate
from app.schemas.simulation_lab import SimulationPolicyCompareRequest, SimulationScenarioCreate, SimulationScenarioImportRequest
from app.schemas.sustainability_kernel import LCACompareRequest, TEAEstimateRequest
from app.services.bos_benchmark_cases import ensure_default_benchmark_cases
from app.services.compliance_service import evaluate_compliance
from app.services.evidence_service import create_evidence_pack
from app.services.release_packet_service import attach_simulation_appendix
from app.services.research_review_service import create_research_review_run_record
from app.services.simulation_lab_service import (
    compare_policies,
    create_scenario,
    export_run,
    get_audit_trace,
    get_cycles,
    import_scenario_from_reference,
    list_runs,
    run_scenario,
)
from app.services.sustainability_kernel_service import compare_lca, estimate_tea

ToolPolicy = Literal["auto_allowed", "requires_confirmation", "forbidden"]

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "simulation_lab.import_reference": {
        "canonical_tool": "simulation_lab.import_scenario_from_reference",
        "policy": "auto_allowed",
        "description": "Import a reference profile into a persisted Simulation Lab scenario.",
        "evidence_role": "input_snapshot",
    },
    "simulation_lab.create_run_compare": {
        "canonical_tool": "simulation_lab.create_scenario",
        "policy": "auto_allowed",
        "description": "Create or reuse a scenario, run the virtual loop, compare policy options, and export an appendix draft.",
        "evidence_role": "simulation_verification",
    },
    "release.attach_appendix": {
        "canonical_tool": "release.attach_simulation_appendix",
        "policy": "auto_allowed",
        "description": "Attach a Simulation Lab appendix draft without changing the release decision.",
        "evidence_role": "release_appendix",
    },
    "benchmark.run_suite": {
        "canonical_tool": "benchmark.run_suite",
        "policy": "auto_allowed",
        "description": "Run the deterministic Simulation Lab regression suite and produce review-gated scorecard evidence.",
        "evidence_role": "benchmark_scorecard",
    },
    "model.request_review": {
        "canonical_tool": "model.request_governance_review",
        "policy": "auto_allowed",
        "description": "Create a pending model governance review request from benchmark evidence; never activates a model automatically.",
        "evidence_role": "model_governance",
    },
    "model.complete_review": {
        "canonical_tool": "model.complete_governance_review",
        "policy": "requires_confirmation",
        "description": "Complete a model governance decision after human review.",
        "evidence_role": "human_review",
    },
    "compliance.evaluate": {
        "canonical_tool": "compliance.evaluate",
        "policy": "auto_allowed",
        "description": "Evaluate release blockers and review requirements from assay and quality evidence.",
        "evidence_role": "compliance_gate",
    },
    "lca.compare": {
        "canonical_tool": "lca.compare",
        "policy": "auto_allowed",
        "description": "Compare CO2e, energy, and water impact with uncertainty warnings.",
        "evidence_role": "value_proof",
    },
    "tea.estimate": {
        "canonical_tool": "tea.estimate",
        "policy": "auto_allowed",
        "description": "Estimate operating cost and margin with explicit default-factor uncertainty.",
        "evidence_role": "value_proof",
    },
    "release.request_human_approval": {
        "canonical_tool": "release.request_human_approval",
        "policy": "requires_confirmation",
        "description": "Ask a human reviewer to complete the release approval step.",
        "evidence_role": "human_review",
    },
    "external.share_release_packet": {
        "canonical_tool": "external.share_release_packet",
        "policy": "requires_confirmation",
        "description": "Share release evidence outside BOS after explicit human confirmation.",
        "evidence_role": "external_share_review",
    },
    "hardware.execute": {
        "canonical_tool": "hardware_execution",
        "policy": "forbidden",
        "description": "Real hardware execution is outside this baseline and cannot be triggered by Assistant.",
        "evidence_role": "forbidden_action",
    },
    "release.auto_approve": {
        "canonical_tool": "release_decision_auto_pass",
        "policy": "forbidden",
        "description": "Automatic release approval is forbidden; release movement remains human-gated.",
        "evidence_role": "forbidden_action",
    },
    "tenant.cross_action": {
        "canonical_tool": "cross_tenant_operation",
        "policy": "forbidden",
        "description": "Cross-tenant operations are forbidden.",
        "evidence_role": "forbidden_action",
    },
}

_CANONICAL_TOOL_POLICY = {
    str(entry["canonical_tool"]): str(entry["policy"])
    for entry in TOOL_REGISTRY.values()
    if entry.get("status") != "planned"
}

SAFE_TOOLS = {tool for tool, policy in _CANONICAL_TOOL_POLICY.items() if policy == "auto_allowed"} | {
    "simulation_lab.run_scenario",
    "simulation_lab.compare_policies",
    "simulation_lab.get_cycles",
    "simulation_lab.get_audit_trace",
    "simulation_lab.export_release_appendix",
    "model.register_candidate"
}
REQUIRES_CONFIRMATION = {tool for tool, policy in _CANONICAL_TOOL_POLICY.items() if policy == "requires_confirmation"}
FORBIDDEN_TOOLS = {tool for tool, policy in _CANONICAL_TOOL_POLICY.items() if policy == "forbidden"} | {
    "production_batch_mutation"
}

def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def assistant_tool_registry_contract() -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    for registry_name, entry in TOOL_REGISTRY.items():
        tools.append(
            {
                "name": registry_name,
                "canonical_tool": entry["canonical_tool"],
                "policy": entry["policy"],
                "status": entry.get("status", "available"),
                "description": entry["description"],
                "evidence_role": entry["evidence_role"],
            }
        )
    return {
        "version": "assistant-tool-registry-v1",
        "tools": tools,
        "confirmation_policy": {
            "auto_allowed": sorted(name for name, item in TOOL_REGISTRY.items() if item["policy"] == "auto_allowed"),
            "requires_confirmation": sorted(
                name for name, item in TOOL_REGISTRY.items() if item["policy"] == "requires_confirmation"
            ),
            "forbidden": sorted(name for name, item in TOOL_REGISTRY.items() if item["policy"] == "forbidden"),
        },
    }


def parse_simulation_lab_intent(message: str) -> dict[str, Any]:
    text = message.lower()
    scenario = "normal"
    if "moisture drift" in text or "湿度漂移" in message:
        scenario = "moisture_drift"
    elif "temperature spike" in text or "温度" in message:
        scenario = "temperature_spike"
    elif "underfeeding" in text or "欠投喂" in message:
        scenario = "underfeeding"
    elif "moisture" in text or "湿度" in message:
        scenario = "moisture_drift"

    cycles_match = re.search(r"(\d+)\s*(?:cycles|cycle|轮|次)", text)
    seed_match = re.search(r"seed[:\s]+(\d+)", text)
    simulation_match = re.search(r"\b(SIM-\d{8}-[A-Fa-f0-9]+)\b", message)
    run_match = re.search(r"\b(RUN-[A-Za-z0-9_\-]+)\b", message)
    release_decision_match = re.search(r"(?:release[_\s-]*decision(?:[_\s-]*id)?|decision[_\s-]*id)[:#\s]+(\d+)", text)
    batch_id_match = re.search(r"(?:batch[_\s-]*id|batch)[:#\s]+(\d+)", text)
    reference_match = re.search(r"reference_id[:：]\s*([A-Za-z0-9_\-]+)", message)
    if reference_match is None:
        reference_match = re.search(r"参考[:：]?\s*([A-Za-z0-9_\-]+)", message)

    policy = "rule_based"
    for candidate in ("risk_minimizing", "growth_optimized", "conservative", "rule_based"):
        if candidate in text:
            policy = candidate
            break

    product_category = "insect_dry_matter"
    if "insect oil" in text or "oil" in text:
        product_category = "insect_oil"
    elif "frass" in text or "fertilizer" in text:
        product_category = "frass_organic_fertilizer"
    elif "residue" in text:
        product_category = "residue_handling"

    value_proof_requested = "value proof" in text or "sustainability proof" in text
    compliance_requested = "compliance" in text or "release gate" in text or "quality gate" in text
    lca_requested = "lca" in text or "co2e" in text or "carbon" in text or value_proof_requested
    tea_requested = "tea" in text or "techno-economic" in text or "margin" in text or value_proof_requested

    return {
        "mode": "simulation_lab",
        "scenario": scenario,
        "cycles": int(cycles_match.group(1)) if cycles_match else 8,
        "seed": int(seed_match.group(1)) if seed_match else 17,
        "policy": policy,
        "compare_policies": "compare" in text or "比较策略" in message or "对比策略" in message,
        "export_appendix": "export appendix" in text or "release appendix" in text or "appendix" in text,
        "attach_release_packet": "attach release packet" in text
        or "attach appendix" in text
        or "attach simulation appendix" in text
        or "release packet" in text,
        "run_benchmark": "run benchmark" in text or "benchmark" in text,
        "request_model_review": "request model review" in text
        or "model review" in text
        or "governance review" in text,
        "request_compliance": compliance_requested,
        "request_lca": lca_requested,
        "request_tea": tea_requested,
        "batch_id": int(batch_id_match.group(1)) if batch_id_match else None,
        "jurisdiction": "CN",
        "product_category": product_category,
        "reference_id": reference_match.group(1) if reference_match else None,
        "simulation_id": simulation_match.group(1) if simulation_match else None,
        "run_id": run_match.group(1) if run_match else None,
        "release_decision_id": int(release_decision_match.group(1)) if release_decision_match else None,
    }


def _build_execution_plan(intent: dict[str, Any]) -> list[dict[str, str]]:
    plan = [
        {
            "step": "import_reference" if intent.get("reference_id") else "create_scenario",
            "tool": "simulation_lab.import_reference" if intent.get("reference_id") else "simulation_lab.create_run_compare",
            "policy": "auto_allowed",
            "status": "planned",
        },
        {
            "step": "run_virtual_loop",
            "tool": "simulation_lab.create_run_compare",
            "policy": "auto_allowed",
            "status": "planned",
        },
        {
            "step": "export_appendix_draft",
            "tool": "simulation_lab.create_run_compare",
            "policy": "auto_allowed",
            "status": "planned",
        },
    ]
    if intent.get("compare_policies"):
        plan.insert(
            2,
            {
                "step": "compare_policies",
                "tool": "simulation_lab.create_run_compare",
                "policy": "auto_allowed",
                "status": "planned",
            },
        )
    if intent.get("attach_release_packet"):
        plan.append(
            {
                "step": "attach_release_appendix",
                "tool": "release.attach_appendix",
                "policy": "auto_allowed",
                "status": "planned",
            }
        )
    if intent.get("run_benchmark") or intent.get("request_model_review"):
        plan.append(
            {
                "step": "run_benchmark_suite",
                "tool": "benchmark.run_suite",
                "policy": "auto_allowed",
                "status": "planned",
            }
        )
    if intent.get("request_compliance"):
        plan.append(
            {
                "step": "evaluate_compliance_gate",
                "tool": "compliance.evaluate",
                "policy": "auto_allowed",
                "status": "planned",
            }
        )
    if intent.get("request_lca"):
        plan.append(
            {
                "step": "compare_lca_value_proof",
                "tool": "lca.compare",
                "policy": "auto_allowed",
                "status": "planned",
            }
        )
    if intent.get("request_tea"):
        plan.append(
            {
                "step": "estimate_tea_value_proof",
                "tool": "tea.estimate",
                "policy": "auto_allowed",
                "status": "planned",
            }
        )
    if intent.get("request_model_review"):
        plan.append(
            {
                "step": "request_model_review",
                "tool": "model.request_review",
                "policy": "requires_confirmation",
                "status": "planned",
            }
        )
    return plan


def _executed_plan(execution_plan: list[dict[str, str]], completed_tool_names: set[str]) -> list[dict[str, str]]:
    registry = assistant_tool_registry_contract()["tools"]
    canonical_by_registry = {item["name"]: item["canonical_tool"] for item in registry}
    executed: list[dict[str, str]] = []
    for step in execution_plan:
        canonical_tool = canonical_by_registry.get(step["tool"], step["tool"])
        status = "completed" if canonical_tool in completed_tool_names else step["status"]
        if step["tool"] == "simulation_lab.create_run_compare" and "simulation_lab.run_scenario" in completed_tool_names:
            status = "completed"
        executed.append({**step, "status": status})
    return executed


def _input_snapshot(intent: dict[str, Any], *, simulation_id: str | None, run_id: str | None) -> dict[str, Any]:
    return {
        "mode": intent.get("mode"),
        "scenario": intent.get("scenario"),
        "cycles": intent.get("cycles"),
        "seed": intent.get("seed"),
        "policy": intent.get("policy"),
        "reference_id": intent.get("reference_id"),
        "simulation_id": simulation_id,
        "run_id": run_id,
        "requested_outputs": {
            "compare_policies": bool(intent.get("compare_policies")),
            "export_appendix": True,
            "attach_release_packet": bool(intent.get("attach_release_packet")),
            "run_benchmark": bool(intent.get("run_benchmark") or intent.get("request_model_review")),
            "request_model_review": bool(intent.get("request_model_review")),
            "evaluate_compliance": bool(intent.get("request_compliance")),
            "compare_lca": bool(intent.get("request_lca")),
            "estimate_tea": bool(intent.get("request_tea")),
        },
        "batch_id": intent.get("batch_id"),
        "jurisdiction": intent.get("jurisdiction"),
        "product_category": intent.get("product_category"),
    }


def _risk_value_drivers(
    *,
    comparison: Any,
    benchmark: dict[str, Any] | None,
    model_review: dict[str, Any] | None,
    release_attachment: Any,
    compliance_gate: Any | None = None,
    lca_result: Any | None = None,
    tea_result: Any | None = None,
    uncertainty_warnings: list[str] | None = None,
) -> dict[str, list[str]]:
    drivers = {
        "risk_drivers": ["Release decision remains unchanged until human review."],
        "value_drivers": ["Simulation appendix and evidence pack make the recommendation reviewable."],
    }
    comparison_payload = jsonable_encoder(comparison) if comparison is not None else None
    if isinstance(comparison_payload, dict):
        winner = comparison_payload.get("winner") or {}
        if winner.get("lowest_risk"):
            drivers["risk_drivers"].append(f"Lowest-risk policy candidate: {winner['lowest_risk']}.")
        if winner.get("highest_margin"):
            drivers["value_drivers"].append(f"Highest-margin policy candidate: {winner['highest_margin']}.")
    if benchmark:
        scorecard = benchmark.get("scorecard") or {}
        drivers["risk_drivers"].append(
            f"Benchmark gate is {scorecard.get('status', 'review_required')} with {scorecard.get('failed_count', 0)} failed cases."
        )
    if model_review:
        drivers["risk_drivers"].append("Model version is ready_for_review, not active.")
    if release_attachment is not None:
        drivers["value_drivers"].append("Release Center can display the attached appendix for internal review.")
    compliance_payload = jsonable_encoder(compliance_gate) if compliance_gate is not None else None
    if isinstance(compliance_payload, dict):
        status = compliance_payload.get("status", "review_required")
        drivers["risk_drivers"].append(f"Compliance gate is {status}; release remains review-gated.")
        blocked_reasons = compliance_payload.get("blocked_reasons") or []
        if blocked_reasons:
            drivers["risk_drivers"].append(f"Compliance blocked reasons: {', '.join(str(item) for item in blocked_reasons)}.")
    lca_payload = jsonable_encoder(lca_result) if lca_result is not None else None
    if isinstance(lca_payload, dict):
        result = lca_payload.get("result") or {}
        if isinstance(result, dict) and "co2e_abatement_kg" in result:
            drivers["value_drivers"].append(f"LCA abatement proof: {result['co2e_abatement_kg']} kg CO2e.")
    tea_payload = jsonable_encoder(tea_result) if tea_result is not None else None
    if isinstance(tea_payload, dict):
        result = tea_payload.get("result") or {}
        if isinstance(result, dict) and "gross_margin_usd" in result:
            drivers["value_drivers"].append(f"TEA gross margin proof: {result['gross_margin_usd']} USD.")
    if uncertainty_warnings:
        drivers["risk_drivers"].append(f"Uncertainty warnings: {', '.join(uncertainty_warnings)}.")
    return drivers


def _human_review_requirement(
    *,
    model_review: dict[str, Any] | None,
    release_attachment: Any,
    compliance_gate: Any | None = None,
    uncertainty_warnings: list[str] | None = None,
) -> dict[str, Any]:
    required_for = ["release approval before external use"]
    if model_review:
        required_for.append("model governance review completion")
    if release_attachment is not None:
        required_for.append("release appendix acceptance")
    compliance_payload = jsonable_encoder(compliance_gate) if compliance_gate is not None else None
    if isinstance(compliance_payload, dict):
        required_for.append("compliance gate review")
        if compliance_payload.get("status") in {"blocked", "insufficient_evidence"}:
            required_for.append("compliance blocker resolution")
    if uncertainty_warnings:
        required_for.append("LCA/TEA uncertainty review")
    return {
        "required": True,
        "state": "review_required",
        "required_for": required_for,
        "forbidden_actions": sorted(FORBIDDEN_TOOLS),
    }


def _next_safe_actions(
    *,
    simulation_id: str,
    run_id: str | None,
    evidence_pack_id: str | None,
    compliance_gate: Any | None = None,
    lca_result: Any | None = None,
    tea_result: Any | None = None,
) -> list[dict[str, str]]:
    actions = [
        {
            "label": "Open Simulation Lab scenario",
            "target": f"/bos/simulation-lab?simulationId={simulation_id}",
            "requires_confirmation": "false",
        },
        {
            "label": "Review evidence pack",
            "target": evidence_pack_id or "pending_evidence_pack",
            "requires_confirmation": "false",
        },
        {
            "label": "Review release appendix draft",
            "target": run_id or simulation_id,
            "requires_confirmation": "true",
        },
    ]
    compliance_payload = jsonable_encoder(compliance_gate) if compliance_gate is not None else None
    if isinstance(compliance_payload, dict):
        actions.append(
            {
                "label": "Review compliance evidence",
                "target": str(compliance_payload.get("evidence_pack_id") or compliance_payload.get("gate_id") or "pending_compliance_gate"),
                "requires_confirmation": "true",
            }
        )
    for label, result_payload in (("Review LCA value proof", lca_result), ("Review TEA value proof", tea_result)):
        encoded = jsonable_encoder(result_payload) if result_payload is not None else None
        if isinstance(encoded, dict):
            actions.append(
                {
                    "label": label,
                    "target": str(encoded.get("evidence_pack_id") or encoded.get("result_id") or "pending_value_proof"),
                    "requires_confirmation": "true",
                }
            )
    return actions


def _confirmation_payloads_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    result_ids = summary.get("result_ids") if isinstance(summary.get("result_ids"), dict) else {}
    payloads: list[dict[str, Any]] = []
    release_attachment_id = result_ids.get("release_attachment_id")
    assistant_evidence_pack_id = result_ids.get("evidence_pack_id")
    if isinstance(release_attachment_id, str) and release_attachment_id:
        payloads.append(
            {
                "action_name": "release.request_human_approval",
                "action_payload": {
                    "release_attachment_id": release_attachment_id,
                    "simulation_id": result_ids.get("simulation_id"),
                    "run_id": result_ids.get("run_id"),
                    "evidence_pack_id": assistant_evidence_pack_id,
                    "release_decision_impact": "unchanged_until_separate_human_release_workflow",
                    "execution": "queue_only_no_auto_approval",
                },
            }
        )
        payloads.append(
            {
                "action_name": "external.share_release_packet",
                "action_payload": {
                    "release_attachment_id": release_attachment_id,
                    "evidence_pack_id": assistant_evidence_pack_id,
                    "share_scope": "external",
                    "execution": "forbidden_until_explicit_external_share_workflow",
                },
            }
        )
    model_review = summary.get("model_review") if isinstance(summary.get("model_review"), dict) else {}
    model_approval_request_id = result_ids.get("model_approval_request_id")
    if isinstance(model_approval_request_id, str) and model_approval_request_id:
        payloads.append(
            {
                "action_name": "model.complete_review",
                "action_payload": {
                    "approval_request_id": model_approval_request_id,
                    "model_id": model_review.get("model_id"),
                    "model_version_id": model_review.get("model_version_id"),
                    "benchmark_run_id": result_ids.get("benchmark_run_id"),
                    "evidence_pack_id": model_review.get("evidence_pack_id"),
                    "execution": "queue_only_no_model_activation",
                },
            }
        )
    return payloads


async def _sync_confirmation_requests_from_summary(
    db: AsyncSession,
    *,
    assistant_run: AssistantRunRecord,
    tenant_id: int,
    summary: dict[str, Any],
) -> list[str]:
    created: list[str] = []
    for item in _confirmation_payloads_from_summary(summary):
        action_name = item["action_name"]
        exists = await db.scalar(
            select(AssistantConfirmationRequestRecord.id).where(
                AssistantConfirmationRequestRecord.assistant_run_id == assistant_run.id,
                AssistantConfirmationRequestRecord.tenant_id == tenant_id,
                AssistantConfirmationRequestRecord.action_name == action_name,
            )
        )
        if exists is not None:
            continue
        confirmation = AssistantConfirmationRequestRecord(
            confirmation_id=_new_id("ACONF"),
            assistant_run_id=assistant_run.id,
            tenant_id=tenant_id,
            action_name=action_name,
            action_payload=jsonable_encoder(item.get("action_payload") or {}),
            status="pending",
        )
        db.add(confirmation)
        created.append(confirmation.confirmation_id)
    return created


def _tool_response(record: AssistantToolCallRecord) -> AssistantToolCallResponse:
    return AssistantToolCallResponse(
        call_id=record.call_id,
        tool_name=record.tool_name,
        input_payload=record.input_payload,
        output_payload=record.output_payload,
        status=record.status,
        error_message=record.error_message,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


def _confirmation_response(record: AssistantConfirmationRequestRecord) -> AssistantConfirmationRequestResponse:
    return AssistantConfirmationRequestResponse(
        confirmation_id=record.confirmation_id,
        action_name=record.action_name,
        action_payload=record.action_payload,
        status=record.status,
        reason=record.reason,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _summary_result_ids(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    result_ids = summary.get("result_ids")
    return result_ids if isinstance(result_ids, dict) else {}


def _confirmation_evidence_ids(record: AssistantConfirmationRequestRecord, run: AssistantRunRecord) -> list[str]:
    payload = record.action_payload if isinstance(record.action_payload, dict) else {}
    result_ids = _summary_result_ids(run.result_summary)
    return _dedupe_strings(
        [
            run.evidence_pack_id,
            payload.get("evidence_pack_id"),
            result_ids.get("evidence_pack_id"),
            result_ids.get("compliance_evidence_pack_id"),
            result_ids.get("lca_evidence_pack_id"),
            result_ids.get("tea_evidence_pack_id"),
        ]
    )


def _guardrails_for_action(action_name: str) -> list[str]:
    if action_name == "release.request_human_approval":
        return [
            "queue_only_no_auto_approval",
            "release_decision_remains_review_required",
            "separate_human_release_workflow_required",
        ]
    if action_name == "external.share_release_packet":
        return [
            "queue_only_no_external_sharing",
            "external_share_forbidden_until_explicit_workflow",
            "tenant_boundary_required",
        ]
    if action_name == "model.complete_review":
        return [
            "queue_only_no_model_activation",
            "human_approval_request_remains_pending",
            "separate_model_governance_workflow_required",
        ]
    return ["review_gated", "queue_only"]


def _human_approval_evidence_ids(record: HumanApprovalRequestRecord) -> list[str]:
    payload = record.payload if isinstance(record.payload, dict) else {}
    return _dedupe_strings([payload.get("evidence_pack_id"), payload.get("assistant_evidence_pack_id")])


def _human_approval_item(
    record: HumanApprovalRequestRecord,
    *,
    source_run_id: str | None = None,
    source_evidence_pack_id: str | None = None,
) -> AssistantReviewHumanApprovalItem:
    payload = record.payload if isinstance(record.payload, dict) else {}
    resolved_source_run_id = source_run_id
    resolved_source_evidence_pack_id = source_evidence_pack_id
    if resolved_source_run_id is None and isinstance(payload.get("assistant_run_id"), str):
        resolved_source_run_id = payload["assistant_run_id"]
    if resolved_source_evidence_pack_id is None and isinstance(payload.get("assistant_evidence_pack_id"), str):
        resolved_source_evidence_pack_id = payload["assistant_evidence_pack_id"]
    return AssistantReviewHumanApprovalItem(
        approval_request_id=record.approval_request_id,
        release_decision_id=record.release_decision_id,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        status=record.status,
        reason=record.reason,
        payload=record.payload,
        source_assistant_run_id=resolved_source_run_id,
        source_evidence_pack_id=resolved_source_evidence_pack_id,
        evidence_pack_ids=_human_approval_evidence_ids(record),
        risk_guardrails=[
            "pending_review_request_only" if record.status == "pending" else "resolved_review_request_only",
            "no_auto_release_approval",
            "no_auto_model_activation",
            "no_external_sharing",
        ],
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )


async def list_assistant_review_workbench(
    db: AsyncSession,
    *,
    tenant_id: int,
    status: str = "pending",
    limit: int = 50,
) -> AssistantReviewWorkbenchResponse:
    confirmation_result = await db.execute(
        select(AssistantConfirmationRequestRecord, AssistantRunRecord)
        .join(AssistantRunRecord, AssistantRunRecord.id == AssistantConfirmationRequestRecord.assistant_run_id)
        .where(
            AssistantConfirmationRequestRecord.tenant_id == tenant_id,
            AssistantConfirmationRequestRecord.status == status,
        )
        .order_by(desc(AssistantConfirmationRequestRecord.created_at), desc(AssistantConfirmationRequestRecord.id))
        .limit(limit)
    )
    confirmation_rows = confirmation_result.all()
    confirmation_items: list[AssistantReviewConfirmationItem] = []
    approval_source_by_id: dict[str, tuple[str, str | None]] = {}
    for confirmation, run in confirmation_rows:
        payload = confirmation.action_payload if isinstance(confirmation.action_payload, dict) else {}
        evidence_ids = _confirmation_evidence_ids(confirmation, run)
        confirmation_items.append(
            AssistantReviewConfirmationItem(
                confirmation_id=confirmation.confirmation_id,
                action_name=confirmation.action_name,
                action_payload=confirmation.action_payload,
                status=confirmation.status,
                reason=confirmation.reason,
                source_assistant_run_id=run.run_id,
                source_evidence_pack_id=run.evidence_pack_id,
                evidence_pack_ids=evidence_ids,
                risk_guardrails=_guardrails_for_action(confirmation.action_name),
                created_at=confirmation.created_at,
                resolved_at=confirmation.resolved_at,
            )
        )
        approval_request_id = payload.get("approval_request_id")
        if isinstance(approval_request_id, str) and approval_request_id:
            approval_source_by_id[approval_request_id] = (run.run_id, run.evidence_pack_id)

    approval_result = await db.execute(
        select(HumanApprovalRequestRecord)
        .where(
            HumanApprovalRequestRecord.tenant_id == tenant_id,
            HumanApprovalRequestRecord.status == status,
        )
        .order_by(desc(HumanApprovalRequestRecord.created_at), desc(HumanApprovalRequestRecord.id))
        .limit(limit)
    )
    approval_items: list[AssistantReviewHumanApprovalItem] = []
    for approval in approval_result.scalars().all():
        payload = approval.payload if isinstance(approval.payload, dict) else {}
        source_run_id = payload.get("assistant_run_id") if isinstance(payload.get("assistant_run_id"), str) else None
        source_evidence_pack_id = (
            payload.get("assistant_evidence_pack_id")
            if isinstance(payload.get("assistant_evidence_pack_id"), str)
            else None
        )
        if source_run_id is None and approval.approval_request_id in approval_source_by_id:
            source_run_id, source_evidence_pack_id = approval_source_by_id[approval.approval_request_id]
        approval_items.append(
            _human_approval_item(
                approval,
                source_run_id=source_run_id,
                source_evidence_pack_id=source_evidence_pack_id,
            )
        )

    return AssistantReviewWorkbenchResponse(
        assistant_confirmations=confirmation_items,
        human_approval_requests=approval_items,
        guardrails=[
            "tenant_scoped_read_model",
            "queue_only_confirmation_management",
            "release_decision_remains_review_required",
            "no_auto_model_activation",
            "no_external_sharing",
        ],
    )


REVIEW_WORKBENCH_AUDIT_STATUSES = ("pending", "approved", "rejected")


def _review_workbench_status_bucket(
    status: str,
    response: AssistantReviewWorkbenchResponse,
) -> dict[str, Any]:
    assistant_confirmations = jsonable_encoder(response.assistant_confirmations)
    human_approval_requests = jsonable_encoder(response.human_approval_requests)
    evidence_pack_ids = _dedupe_strings(
        [
            evidence_id
            for item in response.assistant_confirmations
            for evidence_id in [item.source_evidence_pack_id, *item.evidence_pack_ids]
        ]
        + [
            evidence_id
            for item in response.human_approval_requests
            for evidence_id in [item.source_evidence_pack_id, *item.evidence_pack_ids]
        ]
    )
    return {
        "status": status,
        "counts": {
            "assistant_confirmations": len(response.assistant_confirmations),
            "human_approval_requests": len(response.human_approval_requests),
            "total": len(response.assistant_confirmations) + len(response.human_approval_requests),
        },
        "assistant_confirmations": assistant_confirmations,
        "human_approval_requests": human_approval_requests,
        "evidence_pack_ids": evidence_pack_ids,
        "guardrails": response.guardrails,
    }


def _latest_resolved_timestamp(responses: list[AssistantReviewWorkbenchResponse]) -> str | None:
    resolved_at_values = [
        item.resolved_at
        for response in responses
        for item in [*response.assistant_confirmations, *response.human_approval_requests]
        if item.resolved_at is not None
    ]
    if not resolved_at_values:
        return None
    return max(resolved_at_values).isoformat()


async def build_review_workbench_audit_packet(
    db: AsyncSession,
    *,
    tenant_id: int,
    limit: int = 50,
) -> dict[str, Any]:
    responses_by_status: dict[str, AssistantReviewWorkbenchResponse] = {}
    for status_name in REVIEW_WORKBENCH_AUDIT_STATUSES:
        responses_by_status[status_name] = await list_assistant_review_workbench(
            db,
            tenant_id=tenant_id,
            status=status_name,
            limit=limit,
        )

    buckets = {
        status_name: _review_workbench_status_bucket(status_name, response)
        for status_name, response in responses_by_status.items()
    }
    guardrails = _dedupe_strings(
        [
            guardrail
            for response in responses_by_status.values()
            for guardrail in response.guardrails
        ]
        + [
            "review_only_export",
            "final_release_approval_not_executed",
            "model_activation_not_executed",
            "external_share_not_executed",
        ]
    )
    evidence_pack_ids = _dedupe_strings(
        [
            evidence_id
            for bucket in buckets.values()
            for evidence_id in bucket["evidence_pack_ids"]
        ]
    )
    pending_total = buckets["pending"]["counts"]["total"]
    approved_total = buckets["approved"]["counts"]["total"]
    rejected_total = buckets["rejected"]["counts"]["total"]

    return {
        "packet_type": "assistant_review_workbench_audit_packet",
        "schema_version": "assistant_review_workbench_audit_packet_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "tenant_id": tenant_id,
        "review_only": True,
        "status_order": list(REVIEW_WORKBENCH_AUDIT_STATUSES),
        "summary": {
            "pending_queue_count": pending_total,
            "resolved_approval_count": approved_total,
            "resolved_rejection_count": rejected_total,
            "resolved_total_count": approved_total + rejected_total,
            "latest_resolved_at": _latest_resolved_timestamp(list(responses_by_status.values())),
            "final_actions": "not_executed",
        },
        "final_actions": {
            "release_approval": "not_executed",
            "model_activation": "not_executed",
            "external_share": "not_executed",
        },
        "guardrails": guardrails,
        "evidence_pack_ids": evidence_pack_ids,
        "statuses": buckets,
    }


def render_review_workbench_audit_packet_json(packet: dict[str, Any]) -> str:
    return json.dumps(packet, indent=2, ensure_ascii=False, default=str)


def _item_evidence_ids(item: dict[str, Any]) -> str:
    evidence_ids = item.get("evidence_pack_ids")
    if isinstance(evidence_ids, list) and evidence_ids:
        return ", ".join(str(value) for value in evidence_ids)
    source_evidence = item.get("source_evidence_pack_id")
    return str(source_evidence) if source_evidence else "pending"


def _human_approval_side_effect_summary(item: dict[str, Any]) -> str:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    resolution = payload.get("workbench_resolution") if isinstance(payload.get("workbench_resolution"), dict) else {}
    side_effects = resolution.get("side_effects") if isinstance(resolution.get("side_effects"), dict) else {}
    if not side_effects:
        return "not recorded"
    return ", ".join(f"{key}={value}" for key, value in side_effects.items())


def render_review_workbench_audit_packet_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    final_actions = packet.get("final_actions") if isinstance(packet.get("final_actions"), dict) else {}
    statuses = packet.get("statuses") if isinstance(packet.get("statuses"), dict) else {}
    sections = [
        "# BOS Assistant Review Workbench Audit Packet",
        "",
        "## Summary",
        f"- Generated at: {packet.get('generated_at', 'N/A')}",
        f"- Tenant ID: {packet.get('tenant_id', 'N/A')}",
        f"- Review only: {packet.get('review_only', True)}",
        f"- Source review packet ID: {packet.get('source_review_packet_id') or 'not_persisted'}",
        f"- Pending queue: {summary.get('pending_queue_count', 0)}",
        f"- Resolved approvals: {summary.get('resolved_approval_count', 0)}",
        f"- Resolved rejections: {summary.get('resolved_rejection_count', 0)}",
        f"- Latest resolved timestamp: {summary.get('latest_resolved_at') or 'N/A'}",
        "",
        "## Final Actions",
        f"- Release approval: {final_actions.get('release_approval', 'not_executed')}",
        f"- Model activation: {final_actions.get('model_activation', 'not_executed')}",
        f"- External share: {final_actions.get('external_share', 'not_executed')}",
        "",
        "## Evidence Packs",
    ]
    evidence_pack_ids = packet.get("evidence_pack_ids")
    if isinstance(evidence_pack_ids, list) and evidence_pack_ids:
        sections.extend(f"- {evidence_id}" for evidence_id in evidence_pack_ids)
    else:
        sections.append("- None")

    sections.extend(["", "## Guardrails"])
    guardrails = packet.get("guardrails")
    if isinstance(guardrails, list) and guardrails:
        sections.extend(f"- {guardrail}" for guardrail in guardrails)
    else:
        sections.append("- None")

    for status_name in packet.get("status_order", REVIEW_WORKBENCH_AUDIT_STATUSES):
        bucket = statuses.get(status_name) if isinstance(statuses.get(status_name), dict) else {}
        counts = bucket.get("counts") if isinstance(bucket.get("counts"), dict) else {}
        sections.extend(
            [
                "",
                f"## {str(status_name).title()} Queue",
                f"- Assistant confirmations: {counts.get('assistant_confirmations', 0)}",
                f"- Human approval requests: {counts.get('human_approval_requests', 0)}",
            ]
        )

        confirmations = bucket.get("assistant_confirmations")
        sections.append("")
        sections.append("### Assistant Confirmations")
        if isinstance(confirmations, list) and confirmations:
            for item in confirmations:
                if not isinstance(item, dict):
                    continue
                sections.extend(
                    [
                        f"- {item.get('confirmation_id', 'N/A')} / {item.get('action_name', 'N/A')} / {item.get('status', status_name)}",
                        f"  - Source Assistant run: {item.get('source_assistant_run_id', 'N/A')}",
                        f"  - Evidence packs: {_item_evidence_ids(item)}",
                        f"  - Reason: {item.get('reason') or 'N/A'}",
                    ]
                )
        else:
            sections.append("- None")

        approvals = bucket.get("human_approval_requests")
        sections.append("")
        sections.append("### Human Approval Requests")
        if isinstance(approvals, list) and approvals:
            for item in approvals:
                if not isinstance(item, dict):
                    continue
                sections.extend(
                    [
                        f"- {item.get('approval_request_id', 'N/A')} / {item.get('subject_type', 'N/A')} / {item.get('status', status_name)}",
                        f"  - Subject ID: {item.get('subject_id', 'N/A')}",
                        f"  - Source Assistant run: {item.get('source_assistant_run_id') or 'manual review request'}",
                        f"  - Evidence packs: {_item_evidence_ids(item)}",
                        f"  - Side effects: {_human_approval_side_effect_summary(item)}",
                        f"  - Reason: {item.get('reason') or 'N/A'}",
                    ]
                )
        else:
            sections.append("- None")

    return "\n".join(sections) + "\n"


async def resolve_human_approval_request(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    approval_request_id: str,
    payload: HumanApprovalResolveRequest,
) -> AssistantReviewHumanApprovalItem | None:
    approval = await db.scalar(
        select(HumanApprovalRequestRecord).where(
            HumanApprovalRequestRecord.approval_request_id == approval_request_id,
            HumanApprovalRequestRecord.tenant_id == tenant_id,
        )
    )
    if approval is None:
        return None
    if approval.status == "pending":
        prior_payload = approval.payload if isinstance(approval.payload, dict) else {}
        approval.status = "approved" if payload.approved else "rejected"
        approval.reason = payload.reason
        approval.resolved_at = datetime.now(UTC)
        approval.payload = jsonable_encoder(
            {
                **prior_payload,
                "workbench_resolution": {
                    "approved": payload.approved,
                    "resolved_by_user_id": user_id,
                    "reason": payload.reason,
                    "scope": "human_approval_request_only",
                    "side_effects": {
                        "release_decision": "unchanged",
                        "model_activation": False,
                        "external_share": False,
                    },
                },
            }
        )
        await db.commit()
        await db.refresh(approval)
    return _human_approval_item(approval)


async def _run_response(db: AsyncSession, record: AssistantRunRecord) -> AssistantRunResponse:
    tool_result = await db.execute(
        select(AssistantToolCallRecord)
        .where(AssistantToolCallRecord.assistant_run_id == record.id)
        .order_by(AssistantToolCallRecord.id)
    )
    confirmation_result = await db.execute(
        select(AssistantConfirmationRequestRecord)
        .where(AssistantConfirmationRequestRecord.assistant_run_id == record.id)
        .order_by(AssistantConfirmationRequestRecord.id)
    )
    summary = record.result_summary if isinstance(record.result_summary, dict) else {}
    return AssistantRunResponse(
        run_id=record.run_id,
        tenant_id=record.tenant_id,
        user_id=record.user_id,
        user_message=record.user_message,
        parsed_intent=record.parsed_intent,
        status=record.status,
        result_summary=record.result_summary,
        evidence_pack_id=record.evidence_pack_id,
        tool_registry=assistant_tool_registry_contract(),
        team_plan=summary.get("team_plan") if isinstance(summary.get("team_plan"), list) else [],
        specialist_cards=summary.get("specialist_cards") if isinstance(summary.get("specialist_cards"), list) else [],
        handoff_records=summary.get("handoff_records") if isinstance(summary.get("handoff_records"), list) else [],
        review_verdicts=summary.get("review_verdicts") if isinstance(summary.get("review_verdicts"), list) else [],
        action_ledger=summary.get("action_ledger") if isinstance(summary.get("action_ledger"), list) else [],
        memory_tags=summary.get("memory_tags") if isinstance(summary.get("memory_tags"), list) else [],
        final_synthesis=summary.get("final_synthesis") if isinstance(summary.get("final_synthesis"), dict) else None,
        created_at=record.created_at,
        completed_at=record.completed_at,
        tool_calls=[_tool_response(item) for item in tool_result.scalars().all()],
        confirmation_requests=[_confirmation_response(item) for item in confirmation_result.scalars().all()],
    )


async def _record_tool_call(
    db: AsyncSession,
    *,
    assistant_run: AssistantRunRecord,
    tool_name: str,
    input_payload: dict[str, Any],
    callback: Callable[[], Awaitable[Any]],
) -> Any:
    if tool_name in FORBIDDEN_TOOLS or tool_name not in SAFE_TOOLS:
        raise RuntimeError(f"Tool is not allowed for automatic execution: {tool_name}")
    started = datetime.now(UTC)
    call = AssistantToolCallRecord(
        call_id=_new_id("ATC"),
        assistant_run_id=assistant_run.id,
        tenant_id=assistant_run.tenant_id,
        tool_name=tool_name,
        input_payload=jsonable_encoder(input_payload),
        status="running",
        started_at=started,
    )
    db.add(call)
    await db.flush()
    try:
        output = await callback()
        call.status = "completed"
        call.output_payload = jsonable_encoder(output)
        call.completed_at = datetime.now(UTC)
        await db.flush()
        return output
    except Exception as exc:
        call.status = "failed"
        call.error_message = str(exc)
        call.completed_at = datetime.now(UTC)
        await db.flush()
        raise


async def _latest_release_decision_id(db: AsyncSession, *, tenant_id: int) -> int | None:
    result = await db.execute(
        select(ReleaseDecision.id)
        .where(ReleaseDecision.tenant_id == tenant_id)
        .order_by(desc(ReleaseDecision.created_at), desc(ReleaseDecision.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_release_batch_id(db: AsyncSession, *, tenant_id: int) -> int | None:
    result = await db.execute(
        select(ReleaseDecision.batch_id)
        .where(ReleaseDecision.tenant_id == tenant_id)
        .order_by(desc(ReleaseDecision.created_at), desc(ReleaseDecision.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _default_lca_payload(intent: dict[str, Any], *, simulation_id: str, run_id: str | None) -> LCACompareRequest:
    return LCACompareRequest(
        functional_unit="tonne_substrate",
        system_boundary={
            "scope": "gate_to_gate",
            "source": "assistant_default",
            "simulation_id": simulation_id,
            "run_id": run_id,
        },
        baseline_scenario={"kind": "landfill", "scenario": intent.get("scenario")},
        alternative_scenario={"kind": "bsf_route", "policy": intent.get("policy"), "simulation_id": simulation_id},
        activity_data={"substrate_tonnes": 1.0, "electricity_kwh": 20.0},
        emission_factors={},
    )


def _default_tea_payload(intent: dict[str, Any], *, simulation_id: str, run_id: str | None) -> TEAEstimateRequest:
    return TEAEstimateRequest(
        functional_unit="kg_biomass",
        system_boundary={
            "scope": "pilot",
            "source": "assistant_default",
            "simulation_id": simulation_id,
            "run_id": run_id,
        },
        baseline_scenario={"kind": "composting", "scenario": intent.get("scenario")},
        alternative_scenario={"kind": "bsf_route", "policy": intent.get("policy"), "simulation_id": simulation_id},
        activity_data={"biomass_kg": 50.0, "energy_kwh": 20.0, "labor_hours": 1.0},
        cost_factors={},
    )


async def _run_benchmark_suite(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    suite_name: str = "simulation_lab_regression",
) -> dict[str, Any]:
    cases = await ensure_default_benchmark_cases(db)
    scored_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        payload = case.scenario_payload or {}
        scenario = await create_scenario(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=SimulationScenarioCreate(
                species=str(payload.get("species", "BSF")),
                feedstock=str(payload.get("feedstock", "mixed_food_waste")),
                scenario=payload.get("scenario", "normal"),
                cycles=int(payload.get("cycles", 8)),
                seed=int(payload.get("seed", 17 + index)),
                policy=payload.get("policy", "rule_based"),
            ),
        )
        run = await run_scenario(db, tenant_id=tenant_id, user_id=user_id, simulation_id=scenario.simulation_id)
        run_history = await list_runs(db, tenant_id=tenant_id, simulation_id=scenario.simulation_id)
        latest_run = run_history[0] if run_history else None
        expected = case.expected_metrics or {}
        ending_risk = float(run.summary.ending_risk) if run else 1.0
        audit_event_count = int(run.summary.audit_event_count) if run else 0
        cycle_count = int(run.summary.cycle_count) if run else 0
        assertions: list[dict[str, Any]] = []
        passed = run is not None
        if "max_ending_risk" in expected:
            expected_max = float(expected["max_ending_risk"])
            assertion_passed = ending_risk <= expected_max
            assertions.append(
                {
                    "metric": "ending_risk",
                    "actual": ending_risk,
                    "expected_max": expected_max,
                    "passed": assertion_passed,
                }
            )
            passed = passed and assertion_passed
        if expected.get("audit_required"):
            assertion_passed = audit_event_count >= cycle_count
            assertions.append(
                {
                    "metric": "audit_event_count",
                    "actual": audit_event_count,
                    "expected_min": cycle_count,
                    "passed": assertion_passed,
                }
            )
            passed = passed and assertion_passed
        scored_cases.append(
            {
                "case_id": case.case_id,
                "name": case.name,
                "status": "passed" if passed else "failed",
                "simulation_id": scenario.simulation_id,
                "run_id": latest_run.run_id if latest_run else None,
                "evidence_pack_id": latest_run.evidence_pack_id if latest_run else None,
                "metrics": {
                    "ending_risk": ending_risk,
                    "audit_event_count": audit_event_count,
                    "cycle_count": cycle_count,
                },
                "assertions": assertions,
                "expected_metrics": expected,
            }
        )
    passed_count = sum(1 for item in scored_cases if item["status"] == "passed")
    scorecard = {
        "status": "ready_for_review" if passed_count == len(scored_cases) else "blocked",
        "suite_gate": "human_review_required",
        "passed_count": passed_count,
        "failed_count": len(scored_cases) - passed_count,
        "case_count": len(scored_cases),
        "cases": scored_cases,
    }
    record = BenchmarkRunRecord(
        benchmark_run_id=_new_id("BMR"),
        tenant_id=tenant_id,
        user_id=user_id,
        suite_name=suite_name,
        scorecard=scorecard,
    )
    db.add(record)
    await db.flush()
    pack = await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type="benchmark_run",
            subject_id=record.benchmark_run_id,
            title=f"Benchmark evidence for {suite_name}",
            summary="Assistant generated benchmark evidence for human review.",
            verification_status="review_required",
            human_review_required=True,
            items=[
                EvidenceItemCreate(
                    kind="benchmark_scorecard",
                    source_kind="deterministic_model",
                    source_ref="assistant_dispatcher",
                    payload={"suite_name": suite_name, "scorecard": scorecard},
                    uncertainty_level="medium",
                )
            ],
        ),
    )
    record.evidence_pack_id = pack.evidence_pack_id
    await db.flush()
    return {
        "benchmark_run_id": record.benchmark_run_id,
        "suite_name": record.suite_name,
        "scorecard": record.scorecard,
        "evidence_pack_id": record.evidence_pack_id,
    }


async def _register_model_candidate_for_review(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    benchmark_run_id: str,
    reason: str,
) -> dict[str, Any]:
    benchmark_run = await db.scalar(
        select(BenchmarkRunRecord).where(
            BenchmarkRunRecord.benchmark_run_id == benchmark_run_id,
            BenchmarkRunRecord.tenant_id == tenant_id,
        )
    )
    if benchmark_run is None:
        raise RuntimeError("Benchmark run not found for model review")
    model = ModelRegistryRecord(
        model_id=_new_id("MOD"),
        tenant_id=tenant_id,
        user_id=user_id,
        name="chronos-risk-candidate",
        task_type="risk_forecast",
        status="candidate",
    )
    db.add(model)
    await db.flush()
    version = ModelVersionRecord(
        model_version_id=_new_id("MVN"),
        model_id=model.model_id,
        version="assistant-review-candidate",
        metadata_payload={
            "source": "assistant_dispatcher",
            "benchmark_run_id": benchmark_run.benchmark_run_id,
            "evidence_pack_id": benchmark_run.evidence_pack_id,
            "governance_status": "candidate",
            "source_ref": "assistant_dispatcher:model.request_review",
            "checked_date": datetime.now(UTC).date().isoformat(),
            "review_status": "pending_review",
            "human_review_required": True,
            "fallback_candidate": True,
        },
        status="candidate",
    )
    db.add(version)
    await db.flush()
    return {
        "model_id": model.model_id,
        "model_version_id": version.model_version_id,
        "status": model.status,
        "version_status": version.status,
        "benchmark_run_id": benchmark_run.benchmark_run_id,
        "evidence_pack_id": benchmark_run.evidence_pack_id,
        "reason": reason,
    }


async def _request_model_governance_review(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    model_id: str,
    model_version_id: str,
    benchmark_run_id: str,
    reason: str,
    source_assistant_run_id: str | None = None,
    source_assistant_evidence_pack_id: str | None = None,
) -> dict[str, Any]:
    model = await db.scalar(
        select(ModelRegistryRecord).where(
            ModelRegistryRecord.model_id == model_id,
            ModelRegistryRecord.tenant_id == tenant_id,
        )
    )
    version = await db.scalar(
        select(ModelVersionRecord).where(
            ModelVersionRecord.model_id == model_id,
            ModelVersionRecord.model_version_id == model_version_id,
        )
    )
    benchmark_run = await db.scalar(
        select(BenchmarkRunRecord).where(
            BenchmarkRunRecord.benchmark_run_id == benchmark_run_id,
            BenchmarkRunRecord.tenant_id == tenant_id,
        )
    )
    if model is None or version is None or benchmark_run is None:
        raise RuntimeError("Model version or benchmark run not found")
    version.status = "ready_for_review"
    version.metadata_payload = {
        **(version.metadata_payload or {}),
        "governance_status": "ready_for_review",
        "governance_reason": reason,
        "benchmark_run_id": benchmark_run.benchmark_run_id,
        "evidence_pack_id": benchmark_run.evidence_pack_id,
    }
    model.status = "review_required"
    approval_request = HumanApprovalRequestRecord(
        approval_request_id=_new_id("HAR"),
        release_decision_id=None,
        tenant_id=tenant_id,
        user_id=user_id,
        subject_type="model_version",
        subject_id=model_version_id,
        status="pending",
        reason=reason,
        payload={
            "model_id": model_id,
            "model_version_id": model_version_id,
            "benchmark_run_id": benchmark_run_id,
            "evidence_pack_id": benchmark_run.evidence_pack_id,
            "assistant_run_id": source_assistant_run_id,
            "assistant_evidence_pack_id": source_assistant_evidence_pack_id,
            "governance_decision": "request_review",
        },
    )
    db.add(approval_request)
    relation = KnowledgeRelationRecord(
        relation_id=_new_id("KREL"),
        tenant_id=tenant_id,
        subject_type="model_version",
        subject_id=model_version_id,
        predicate="evaluated_by",
        object_type="benchmark_run",
        object_id=benchmark_run_id,
        evidence_pack_id=benchmark_run.evidence_pack_id,
        payload={"decision": "request_review", "reason": reason},
    )
    db.add(relation)
    await db.flush()
    return {
        "model_id": model_id,
        "model_version_id": model_version_id,
        "model_status": model.status,
        "version_status": version.status,
        "knowledge_relation_id": relation.relation_id,
        "evidence_pack_id": benchmark_run.evidence_pack_id,
        "approval_request_id": approval_request.approval_request_id,
    }


async def create_assistant_run(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: AssistantRunCreate,
) -> AssistantRunResponse:
    if payload.mode == "research_review":
        record = await create_research_review_run_record(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=payload,
        )
        return await _run_response(db, record)

    intent = parse_simulation_lab_intent(payload.message)
    execution_plan = _build_execution_plan(intent)
    run_record = AssistantRunRecord(
        run_id=_new_id("ARUN"),
        tenant_id=tenant_id,
        user_id=user_id,
        user_message=payload.message,
        parsed_intent=intent,
        status="running",
    )
    db.add(run_record)
    await db.flush()

    try:
        if intent.get("simulation_id"):
            simulation_id = intent["simulation_id"]
        elif intent.get("reference_id"):
            import_payload = SimulationScenarioImportRequest(
                reference_id=intent["reference_id"],
                cycles=intent["cycles"],
                seed=intent["seed"],
                policy=intent["policy"],
            )
            imported = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="simulation_lab.import_scenario_from_reference",
                input_payload=import_payload.model_dump(),
                callback=lambda: import_scenario_from_reference(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=import_payload,
                ),
            )
            if imported is None:
                raise RuntimeError("Reference source not found")
            simulation_id = imported.scenario.simulation_id
        else:
            create_payload = SimulationScenarioCreate(
                scenario=intent["scenario"],
                cycles=intent["cycles"],
                seed=intent["seed"],
                policy=intent["policy"],
            )
            scenario = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="simulation_lab.create_scenario",
                input_payload=create_payload.model_dump(),
                callback=lambda: create_scenario(db, tenant_id=tenant_id, user_id=user_id, payload=create_payload),
            )
            simulation_id = scenario.simulation_id

        run = await _record_tool_call(
            db,
            assistant_run=run_record,
            tool_name="simulation_lab.run_scenario",
            input_payload={"simulation_id": simulation_id},
            callback=lambda: run_scenario(db, tenant_id=tenant_id, user_id=user_id, simulation_id=simulation_id),
        )
        comparison = None
        if intent.get("compare_policies"):
            compare_payload = SimulationPolicyCompareRequest()
            comparison = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="simulation_lab.compare_policies",
                input_payload={"simulation_id": simulation_id, **compare_payload.model_dump()},
                callback=lambda: compare_policies(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    simulation_id=simulation_id,
                    policies=compare_payload.policies,
                    baseline_policy=compare_payload.baseline_policy,
                ),
            )
        cycles = await _record_tool_call(
            db,
            assistant_run=run_record,
            tool_name="simulation_lab.get_cycles",
            input_payload={"simulation_id": simulation_id},
            callback=lambda: get_cycles(db, tenant_id=tenant_id, simulation_id=simulation_id),
        )
        audit = await _record_tool_call(
            db,
            assistant_run=run_record,
            tool_name="simulation_lab.get_audit_trace",
            input_payload={"simulation_id": simulation_id},
            callback=lambda: get_audit_trace(db, tenant_id=tenant_id, simulation_id=simulation_id),
        )
        exported = await _record_tool_call(
            db,
            assistant_run=run_record,
            tool_name="simulation_lab.export_release_appendix",
            input_payload={"simulation_id": simulation_id},
            callback=lambda: export_run(db, tenant_id=tenant_id, simulation_id=simulation_id),
        )
        run_history = await list_runs(db, tenant_id=tenant_id, simulation_id=simulation_id)
        selected_run_id = intent.get("run_id") or (run_history[0].run_id if run_history else None)
        release_attachment = None
        if intent.get("attach_release_packet"):
            release_decision_id = intent.get("release_decision_id") or await _latest_release_decision_id(
                db,
                tenant_id=tenant_id,
            )
            if release_decision_id is None:
                raise RuntimeError("No release decision is available for packet attachment")
            release_attachment = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="release.attach_simulation_appendix",
                input_payload={
                    "release_decision_id": release_decision_id,
                    "simulation_id": simulation_id,
                    "run_id": selected_run_id,
                    "release_decision_impact": "unchanged",
                },
                callback=lambda: attach_simulation_appendix(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    release_decision_id=release_decision_id,
                    simulation_id=simulation_id,
                    run_id=selected_run_id,
                ),
            )
            if release_attachment is None:
                raise RuntimeError("Release decision or simulation appendix not found")
        benchmark = None
        if intent.get("run_benchmark") or intent.get("request_model_review"):
            benchmark = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="benchmark.run_suite",
                input_payload={"suite_name": "simulation_lab_regression", "suite_gate": "human_review_required"},
                callback=lambda: _run_benchmark_suite(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                ),
            )
        model_candidate = None
        model_review = None
        if intent.get("request_model_review"):
            if benchmark is None:
                raise RuntimeError("Benchmark run is required before model review")
            model_candidate = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="model.register_candidate",
                input_payload={"benchmark_run_id": benchmark["benchmark_run_id"]},
                callback=lambda: _register_model_candidate_for_review(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    benchmark_run_id=benchmark["benchmark_run_id"],
                    reason="Assistant requested model governance review from benchmark evidence.",
                ),
            )
            model_review = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="model.request_governance_review",
                input_payload={
                    "model_id": model_candidate["model_id"],
                    "model_version_id": model_candidate["model_version_id"],
                    "benchmark_run_id": benchmark["benchmark_run_id"],
                    "decision": "request_review",
                    "auto_approval": False,
                },
                callback=lambda: _request_model_governance_review(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    model_id=model_candidate["model_id"],
                    model_version_id=model_candidate["model_version_id"],
                    benchmark_run_id=benchmark["benchmark_run_id"],
                    reason="Assistant requested model governance review from benchmark evidence.",
                    source_assistant_run_id=run_record.run_id,
                    source_assistant_evidence_pack_id=run_record.evidence_pack_id,
                ),
            )
        compliance_gate = None
        if intent.get("request_compliance"):
            compliance_batch_id = intent.get("batch_id") or await _latest_release_batch_id(db, tenant_id=tenant_id)
            if compliance_batch_id is None:
                raise RuntimeError("Compliance evaluation requires batch_id or an existing release decision batch")
            compliance_payload = ComplianceEvaluateRequest(
                batch_id=int(compliance_batch_id),
                jurisdiction=str(intent.get("jurisdiction") or "CN"),
                product_category=str(intent.get("product_category") or "insect_dry_matter"),  # type: ignore[arg-type]
            )
            compliance_gate = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="compliance.evaluate",
                input_payload=compliance_payload.model_dump(),
                callback=lambda: evaluate_compliance(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=compliance_payload,
                ),
            )
            if compliance_gate is None:
                raise RuntimeError("Compliance batch not found")
        lca_result = None
        if intent.get("request_lca"):
            lca_payload = _default_lca_payload(intent, simulation_id=simulation_id, run_id=selected_run_id)
            lca_result = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="lca.compare",
                input_payload=lca_payload.model_dump(),
                callback=lambda: compare_lca(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=lca_payload,
                ),
            )
        tea_result = None
        if intent.get("request_tea"):
            tea_payload = _default_tea_payload(intent, simulation_id=simulation_id, run_id=selected_run_id)
            tea_result = await _record_tool_call(
                db,
                assistant_run=run_record,
                tool_name="tea.estimate",
                input_payload=tea_payload.model_dump(),
                callback=lambda: estimate_tea(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    payload=tea_payload,
                ),
            )
        uncertainty_warnings = [
            *(
                list(getattr(lca_result, "uncertainty_warnings", []) or [])
                if lca_result is not None
                else []
            ),
            *(
                list(getattr(tea_result, "uncertainty_warnings", []) or [])
                if tea_result is not None
                else []
            ),
        ]
        completed_tool_names = {
            item.tool_name
            for item in (
                await db.execute(
                    select(AssistantToolCallRecord).where(AssistantToolCallRecord.assistant_run_id == run_record.id)
                )
            )
            .scalars()
            .all()
            if item.status == "completed"
        }
        summary = {
            "simulation_id": simulation_id,
            "run_id": selected_run_id,
            "scenario": intent["scenario"],
            "tool_registry_version": assistant_tool_registry_contract()["version"],
            "execution_plan": _executed_plan(execution_plan, completed_tool_names),
            "input_snapshot": _input_snapshot(intent, simulation_id=simulation_id, run_id=selected_run_id),
            "run_summary": jsonable_encoder(run.summary if run else None),
            "comparison": jsonable_encoder(comparison),
            "cycle_count": len(cycles.cycles) if cycles else 0,
            "audit_event_count": len(audit.audit_trace) if audit else 0,
            "export_ready": exported is not None,
            "release_attachment": jsonable_encoder(release_attachment),
            "benchmark": jsonable_encoder(benchmark),
            "model_candidate": jsonable_encoder(model_candidate),
            "model_review": jsonable_encoder(model_review),
            "compliance_gate": jsonable_encoder(compliance_gate),
            "lca_value_proof": jsonable_encoder(lca_result),
            "tea_value_proof": jsonable_encoder(tea_result),
            "uncertainty_warnings": uncertainty_warnings,
            "result_ids": {
                "assistant_run_id": run_record.run_id,
                "simulation_id": simulation_id,
                "run_id": selected_run_id,
                "evidence_pack_id": None,
                "release_attachment_id": getattr(release_attachment, "attachment_id", None),
                "benchmark_run_id": benchmark["benchmark_run_id"] if benchmark else None,
                "model_approval_request_id": model_review["approval_request_id"] if model_review else None,
                "compliance_gate_id": getattr(compliance_gate, "gate_id", None),
                "compliance_evidence_pack_id": getattr(compliance_gate, "evidence_pack_id", None),
                "lca_result_id": getattr(lca_result, "result_id", None),
                "lca_evidence_pack_id": getattr(lca_result, "evidence_pack_id", None),
                "tea_result_id": getattr(tea_result, "result_id", None),
                "tea_evidence_pack_id": getattr(tea_result, "evidence_pack_id", None),
            },
            "safety": {
                "hardware_execution": False,
                "production_batch_mutation": False,
                "release_decision_auto_pass": False,
                "release_decision_impact": "unchanged",
                "human_review_required": True,
            },
            "risk_value_drivers": _risk_value_drivers(
                comparison=comparison,
                benchmark=benchmark,
                model_review=model_review,
                release_attachment=release_attachment,
                compliance_gate=compliance_gate,
                lca_result=lca_result,
                tea_result=tea_result,
                uncertainty_warnings=uncertainty_warnings,
            ),
            "human_review_requirement": _human_review_requirement(
                model_review=model_review,
                release_attachment=release_attachment,
                compliance_gate=compliance_gate,
                uncertainty_warnings=uncertainty_warnings,
            ),
            "next_safe_actions": _next_safe_actions(
                simulation_id=simulation_id,
                run_id=selected_run_id,
                evidence_pack_id=None,
                compliance_gate=compliance_gate,
                lca_result=lca_result,
                tea_result=tea_result,
            ),
            "evidence_links": {
                "cycles": f"/bos/simulation-lab/scenarios/{simulation_id}/cycles",
                "audit_trace": f"/bos/simulation-lab/scenarios/{simulation_id}/audit-trace",
                "release_appendix": f"/bos/simulation-lab/scenarios/{simulation_id}/release-appendix",
                "compliance_gate": getattr(compliance_gate, "evidence_pack_id", None),
                "lca_value_proof": getattr(lca_result, "evidence_pack_id", None),
                "tea_value_proof": getattr(tea_result, "evidence_pack_id", None),
            },
        }
        pack = await create_evidence_pack(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            payload=EvidencePackCreate(
                subject_type="assistant_run",
                subject_id=run_record.run_id,
                title=f"Assistant Simulation Lab run {run_record.run_id}",
                summary=f"Assistant created and ran Simulation Lab scenario {simulation_id}.",
                verification_status="review_required",
                human_review_required=True,
                items=[
                    EvidenceItemCreate(
                        kind="assistant_intent",
                        source_kind="operator_input",
                        source_ref=run_record.run_id,
                        payload=intent,
                    ),
                    EvidenceItemCreate(
                        kind="tool_call_log",
                        source_kind="deterministic_model",
                        source_ref=run_record.run_id,
                        payload={
                            "tool_registry": assistant_tool_registry_contract(),
                            "safe_tools": sorted(SAFE_TOOLS),
                            "requires_confirmation": sorted(REQUIRES_CONFIRMATION),
                            "execution_plan": summary["execution_plan"],
                            "input_snapshot": summary["input_snapshot"],
                            "risk_value_drivers": summary["risk_value_drivers"],
                            "human_review_requirement": summary["human_review_requirement"],
                            "next_safe_actions": summary["next_safe_actions"],
                            "compliance_gate": summary["compliance_gate"],
                            "lca_value_proof": summary["lca_value_proof"],
                            "tea_value_proof": summary["tea_value_proof"],
                            "uncertainty_warnings": summary["uncertainty_warnings"],
                        },
                        uncertainty_level="medium",
                    ),
                ],
            ),
        )
        run_record.evidence_pack_id = pack.evidence_pack_id
        summary["result_ids"]["evidence_pack_id"] = pack.evidence_pack_id
        summary["next_safe_actions"] = _next_safe_actions(
            simulation_id=simulation_id,
            run_id=selected_run_id,
            evidence_pack_id=pack.evidence_pack_id,
            compliance_gate=compliance_gate,
            lca_result=lca_result,
            tea_result=tea_result,
        )
        confirmation_ids = await _sync_confirmation_requests_from_summary(
            db,
            assistant_run=run_record,
            tenant_id=tenant_id,
            summary=summary,
        )
        summary["confirmation_queue"] = {
            "status": "pending_human_confirmation" if confirmation_ids else "not_required",
            "confirmation_ids": confirmation_ids,
            "guardrails": {
                "release_decision_auto_pass": False,
                "model_auto_activation": False,
                "external_share_auto_send": False,
            },
        }
        run_record.result_summary = summary
        run_record.status = "completed"
        run_record.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run_record)
        return await _run_response(db, run_record)
    except Exception as exc:
        run_record.status = "failed"
        run_record.result_summary = {"error": str(exc), "parsed_intent": intent}
        run_record.completed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(run_record)
        return await _run_response(db, run_record)


async def get_assistant_run(
    db: AsyncSession,
    *,
    tenant_id: int,
    run_id: str,
) -> AssistantRunResponse | None:
    result = await db.execute(
        select(AssistantRunRecord).where(
            AssistantRunRecord.run_id == run_id,
            AssistantRunRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    return await _run_response(db, record) if record else None


async def list_assistant_runs(
    db: AsyncSession,
    *,
    tenant_id: int,
    limit: int = 10,
) -> list[AssistantRunResponse]:
    result = await db.execute(
        select(AssistantRunRecord)
        .where(AssistantRunRecord.tenant_id == tenant_id)
        .order_by(desc(AssistantRunRecord.created_at), desc(AssistantRunRecord.id))
        .limit(max(1, min(limit, 50)))
    )
    return [await _run_response(db, record) for record in result.scalars().all()]


async def list_assistant_tool_calls(
    db: AsyncSession,
    *,
    tenant_id: int,
    run_id: str,
) -> list[AssistantToolCallResponse] | None:
    run = await get_assistant_run(db, tenant_id=tenant_id, run_id=run_id)
    return run.tool_calls if run else None


async def confirm_assistant_action(
    db: AsyncSession,
    *,
    tenant_id: int,
    run_id: str,
    payload: AssistantConfirmRequest,
) -> AssistantRunResponse | None:
    result = await db.execute(
        select(AssistantRunRecord).where(
            AssistantRunRecord.run_id == run_id,
            AssistantRunRecord.tenant_id == tenant_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None
    confirmation_result = await db.execute(
        select(AssistantConfirmationRequestRecord).where(
            AssistantConfirmationRequestRecord.confirmation_id == payload.confirmation_id,
            AssistantConfirmationRequestRecord.assistant_run_id == run.id,
            AssistantConfirmationRequestRecord.tenant_id == tenant_id,
        )
    )
    confirmation = confirmation_result.scalar_one_or_none()
    if confirmation is None:
        return None
    if confirmation.status != "pending":
        return await _run_response(db, run)
    confirmation.status = "approved" if payload.approved else "rejected"
    confirmation.reason = payload.reason
    confirmation.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run)
    return await _run_response(db, run)
