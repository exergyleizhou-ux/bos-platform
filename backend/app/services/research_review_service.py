"""Deterministic Research Review assistant mode.

This mode is an Assistant control-plane workflow. It writes review-gated
evidence and packet snapshots, but does not approve, execute, share, or mutate
release/runtime state.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_bos import AssistantRunRecord, HumanApprovalRequestRecord
from app.schemas.assistant import AssistantRunCreate
from app.schemas.evidence import EvidenceItemCreate, EvidencePackCreate
from app.services.evidence_service import create_evidence_pack
from app.services.final_action_review_packet_service import persist_review_packet_snapshot

RESEARCH_REVIEW_MODE = "research_review"
RESEARCH_REVIEW_REGISTRY_VERSION = "research-review-registry-v1"
RESEARCH_REVIEW_APPROVAL_STATES = {
    "draft",
    "review_required",
    "scientific_review_passed",
    "evidence_audit_passed",
    "ready_for_human_decision",
}
DISALLOWED_FINAL_STATES = {"approved", "executable", "auto_approved"}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _language_for(message: str) -> str:
    return "zh-CN" if _is_chinese(message) else "en-US"


def parse_research_review_intent(message: str) -> dict[str, Any]:
    text = message.strip()
    language = _language_for(text)
    constraints = []
    for keyword, label in (
        ("预算", "budget_constraint"),
        ("budget", "budget_constraint"),
        ("周期", "timeline_constraint"),
        ("timeline", "timeline_constraint"),
        ("已有数据", "existing_data"),
        ("existing data", "existing_data"),
        ("文献", "literature_context"),
        ("literature", "literature_context"),
        ("标准", "standard_context"),
        ("standard", "standard_context"),
    ):
        if keyword.lower() in text.lower() and label not in constraints:
            constraints.append(label)
    return {
        "mode": RESEARCH_REVIEW_MODE,
        "language": language,
        "research_goal": text,
        "review_type": "research_protocol_review",
        "requested_outputs": [
            "team_plan",
            "specialist_cards",
            "handoff_records",
            "review_verdicts",
            "action_ledger",
            "final_synthesis",
        ],
        "constraints_detected": constraints,
        "safety_scope": {
            "external_materials": "review_required",
            "candidate_data": "review_required",
            "experiment_suggestions": "review_required",
            "final_decision": "human_only",
        },
        "requested_specialist": _requested_specialist(text),
        "follow_up_kind": _follow_up_kind(text),
    }


def _topic_from_message(message: str) -> str:
    normalized = re.sub(r"\s+", " ", message.strip())
    if not normalized:
        return "Research protocol review"
    return normalized[:180]


def _requested_specialist(message: str) -> str | None:
    text = message.lower()
    if "mechanistic analyst" in text or "mechanism" in text or "counterexample" in text or "failure mode" in text:
        return "mechanistic_analyst"
    if "机制" in message or "反证" in message or "失效" in message:
        return "mechanistic_analyst"
    if "protocol designer" in text or "实验路径" in message or "protocol" in text:
        return "protocol_designer"
    if "evidence auditor" in text or "traceability" in text or "证据" in message or "审计" in message:
        return "evidence_auditor"
    if "scientific reviewer" in text or "rigor" in text or "科学" in message:
        return "scientific_reviewer"
    if "digital twin" in text or "simulation" in text or "仿真" in message:
        return "digital_twin_analyst"
    if "data integrity" in text or "数据完整" in message:
        return "data_integrity_reviewer"
    return None


def _follow_up_kind(message: str) -> str:
    text = message.lower()
    if any(token in text for token in ("continue", "deeper", "follow up", "counterexample", "failure mode")):
        return "specialist_continuation"
    if any(token in message for token in ("继续", "深挖", "追问", "反证", "失效")):
        return "specialist_continuation"
    return "new_review"


def _continuity_context(parent_record: AssistantRunRecord | None) -> dict[str, Any] | None:
    if parent_record is None:
        return None
    parent_summary = parent_record.result_summary if isinstance(parent_record.result_summary, dict) else {}
    parent_final = parent_summary.get("final_synthesis") if isinstance(parent_summary.get("final_synthesis"), dict) else {}
    return {
        "parent_run_id": parent_record.run_id,
        "parent_evidence_pack_id": parent_record.evidence_pack_id,
        "parent_review_packet_snapshot_id": parent_final.get("review_packet_snapshot_id"),
        "recalled_team_plan": parent_summary.get("team_plan") if isinstance(parent_summary.get("team_plan"), list) else [],
        "recalled_memory_tags": parent_summary.get("memory_tags") if isinstance(parent_summary.get("memory_tags"), list) else [],
        "continuity_policy": "tenant_scoped_parent_run_only",
        "approval_state": parent_final.get("approval_state") or "review_required",
    }


def _localize_team_step(step: dict[str, Any], language: str) -> dict[str, Any]:
    if language != "zh-CN":
        return step
    title_map = {
        "Chief Scientist": "首席科学家",
        "Protocol Designer": "方案设计专家",
        "Mechanistic Analyst": "机制分析专家",
        "Reference Evidence Curator": "证据文献策展专家",
        "Digital Twin Analyst": "数字孪生分析专家",
        "Data Integrity Reviewer": "数据完整性审查专家",
        "Scientific Reviewer": "科学审查专家",
        "Evidence Auditor": "证据审计专家",
    }
    objective_map = {
        "chief_scientist_intake": "界定研究目标、判断语境与评审标尺。",
        "protocol_designer": "把问题拆成可执行的试验路径，并设置阶段性审查点。",
        "mechanistic_analyst": "追问因果机制、反例和失效模式。",
        "reference_evidence_curator": "整理文献、标准、外部资料和来源缺口。",
        "digital_twin_analyst": "建议仿真情景和数字孪生敏感性检查。",
        "data_integrity_reviewer": "检查输入质量、数据完整性、可追溯性和缺失对照。",
        "scientific_reviewer": "把关科学严谨性、可证伪性、对照和解释风险。",
        "evidence_auditor": "把关证据链、来源质量、出处和审计完整性。",
        "chief_scientist_synthesis": "产出统一综合判断和下一步 review-gated 行动。",
    }
    specialist_id = str(step["specialist_id"])
    return {
        **step,
        "title": title_map.get(str(step["title"]), str(step["title"])),
        "objective": objective_map.get(specialist_id, str(step["objective"])),
    }


def _team_plan(language: str = "en-US") -> list[dict[str, Any]]:
    plan = [
        {
            "stage": 1,
            "specialist_id": "chief_scientist_intake",
            "title": "Chief Scientist",
            "objective": "Frame the research objective, decision context, and review rubric.",
            "lane": "intake",
        },
        {
            "stage": 2,
            "specialist_id": "protocol_designer",
            "title": "Protocol Designer",
            "objective": "Draft the research and experiment path with staged review checkpoints.",
            "lane": "protocol",
        },
        {
            "stage": 3,
            "specialist_id": "mechanistic_analyst",
            "title": "Mechanistic Analyst",
            "objective": "Map causal mechanisms, counterexamples, and failure modes.",
            "lane": "mechanism",
        },
        {
            "stage": 4,
            "specialist_id": "reference_evidence_curator",
            "title": "Reference Evidence Curator",
            "objective": "Organize literature, standards, external references, and provenance gaps.",
            "lane": "evidence",
        },
        {
            "stage": 5,
            "specialist_id": "digital_twin_analyst",
            "title": "Digital Twin Analyst",
            "objective": "Recommend simulation scenarios and twin-based sensitivity checks.",
            "lane": "simulation",
        },
        {
            "stage": 6,
            "specialist_id": "data_integrity_reviewer",
            "title": "Data Integrity Reviewer",
            "objective": "Check input quality, data completeness, traceability, and missing controls.",
            "lane": "data_quality",
        },
        {
            "stage": 7,
            "specialist_id": "scientific_reviewer",
            "title": "Scientific Reviewer",
            "objective": "Gate scientific rigor, falsifiability, controls, and interpretation risk.",
            "lane": "scientific_gate",
        },
        {
            "stage": 8,
            "specialist_id": "evidence_auditor",
            "title": "Evidence Auditor",
            "objective": "Gate traceability, source quality, provenance, and audit completeness.",
            "lane": "evidence_gate",
        },
        {
            "stage": 9,
            "specialist_id": "chief_scientist_synthesis",
            "title": "Chief Scientist",
            "objective": "Produce the unified synthesis and next review-gated steps.",
            "lane": "synthesis",
        },
    ]
    return [_localize_team_step(step, language) for step in plan]


def _specific_unified_answer(topic: str, language: str) -> str | None:
    normalized = topic.lower()
    if language == "zh-CN" and all(token in topic for token in ("黄粉虫", "蛴螬")) and "酒糟" in topic:
        return (
            "在 review_required 前提下，默认更建议把黄粉虫作为酒糟处理的首选小试对象：它更适合干性或半干性粮食副产物，"
            "饲养体系和过程控制更成熟，污染与逃逸风险更容易管住。蛴螬可以作为反事实或补充路线，但白土蚕/金龟子幼虫类群"
            "在品系稳定性、病原与农田害虫风险、周期和合规边界上更难做成可审计的生产方案。"
        )
    if language == "en-US" and "mealworm" in normalized and ("grub" in normalized or "white grub" in normalized) and (
        "distiller" in normalized or "spent grain" in normalized
    ):
        return (
            "Under review_required gates, mealworm is the safer first pilot for distillers grains or spent grain: "
            "it has a more mature controlled-rearing base for dry or semi-dry cereal byproducts, while white grubs "
            "carry higher containment, pest, pathogen, cycle-time, and regulatory uncertainty."
        )
    return None


def _specialist_deliverables(topic: str, language: str = "en-US") -> dict[str, dict[str, Any]]:
    if language == "zh-CN":
        specific = _specific_unified_answer(topic, language)
        return {
            "chief_scientist_intake": {
                "reasoning_summary": "把用户问题视为科研判断题，不把任何路线自动升级为批准或执行。",
                "deliverable": f"评审框架：{topic}",
                "uncertainties": ["研究假设、成功指标和停止条件仍需人工确认。"],
            },
            "protocol_designer": {
                "reasoning_summary": "先把候选虫种、酒糟含水率、预处理方式、对照组和终点指标拆开，再进入小试。",
                "deliverable": "分阶段方案：桌面证据审查、基质预处理定义、黄粉虫优先小试、蛴螬作为受控反事实路线。",
                "uncertainties": ["样本量、酒糟批次差异、接种密度和验收阈值还没有锁定。"],
            },
            "mechanistic_analyst": {
                "reasoning_summary": "关键机制不是“能不能吃”，而是含水率、酒精残留、酸度、霉菌风险和虫种生态位是否匹配。",
                "deliverable": specific or "机制图：基质水分/发酵残留/微生物风险/取食效率/死亡率之间的因果链和反例。",
                "uncertainties": ["酒糟来源、干湿状态、灭菌或发酵预处理、实际虫种品系会改变优先级。"],
            },
            "reference_evidence_curator": {
                "reasoning_summary": "外部文献只能支持优先级排序，不能直接成为 validated defaults。",
                "deliverable": "证据收集计划：黄粉虫粮食副产物饲喂、蛴螬有机质处理、酒糟预处理、病原与合规边界。",
                "uncertainties": ["引用质量、适用物种、许可和边界条件需要人工审查。"],
            },
            "digital_twin_analyst": {
                "reasoning_summary": "仿真适合做敏感性排序，不替代真实饲养试验。",
                "deliverable": "仿真情景：酒糟含水率、预干燥、混配比例、死亡率、转化率和污染事件的压力测试。",
                "uncertainties": ["数字孪生需要校准数据，不能直接外推到未验证品系。"],
            },
            "data_integrity_reviewer": {
                "reasoning_summary": "当前问题足以启动评审，但不足以关闭证据门。",
                "deliverable": "数据完整性清单：酒糟来源、批次、含水率、pH、残酒精、霉菌、虫龄、密度、死亡率和残渣指标。",
                "uncertainties": ["原始数据、仪器校准和样品链路记录未知。"],
            },
            "scientific_reviewer": {
                "reasoning_summary": "可以给出研究优先级，但最终结论必须保留 review_required。",
                "deliverable": "科学门结论：黄粉虫优先进入受控小试；蛴螬保留为对照/探索路线，不作为默认生产首选。",
                "uncertainties": ["仍缺独立审查、重复实验和明确验收标准。"],
            },
            "evidence_auditor": {
                "reasoning_summary": "每个结论必须链接证据或显式标注不确定性。",
                "deliverable": "证据审计结论：review_required，外部资料和候选数据进入审查包，不写入 validated defaults。",
                "uncertainties": ["外部证据引用和内部源包还需要人工审核。"],
            },
            "chief_scientist_synthesis": {
                "reasoning_summary": "综合输出要先帮用户做判断，同时保留安全门。",
                "deliverable": specific or "统一结论：先做 review-gated 小试和证据包，再排队人工评审，不做自动批准。",
                "uncertainties": ["最终决策仍在自动 Assistant 工作流之外。"],
            },
        }
    return {
        "chief_scientist_intake": {
            "reasoning_summary": "The request is treated as a research protocol review, not a release or execution request.",
            "deliverable": f"Review framework for: {topic}",
            "uncertainties": ["Research hypothesis, success metrics, and stopping rules need human confirmation."],
        },
        "protocol_designer": {
            "reasoning_summary": "The protocol should move from hypothesis clarification to controlled pilot, then simulation-backed sensitivity checks.",
            "deliverable": "Staged protocol: clarify variables, define controls, run desk review, then prepare simulation scenarios before any lab execution.",
            "uncertainties": ["Experimental resources, sample size, and acceptance thresholds are not yet locked."],
        },
        "mechanistic_analyst": {
            "reasoning_summary": "Mechanism review should explicitly test causal chain breaks and counterexamples before interpreting positive results.",
            "deliverable": "Mechanism map with expected causal links, plausible confounders, and failure modes.",
            "uncertainties": ["Confounder priority depends on the user's actual substrate, species, equipment, and measurement cadence."],
        },
        "reference_evidence_curator": {
            "reasoning_summary": "External references can support prioritization but must remain candidate evidence until reviewed.",
            "deliverable": "Evidence collection plan for peer literature, standards, public datasets, and internal prior runs.",
            "uncertainties": ["Citation quality and licensing must be checked before material is promoted into validated defaults."],
        },
        "digital_twin_analyst": {
            "reasoning_summary": "Simulation is appropriate as scenario exploration and sensitivity ranking, not as physical execution.",
            "deliverable": "Candidate simulation lanes for baseline, stress, and counterfactual scenarios.",
            "uncertainties": ["Twin validity depends on calibration data and model boundary conditions."],
        },
        "data_integrity_reviewer": {
            "reasoning_summary": "The current operator prompt is enough to start review but not enough to close evidence gates.",
            "deliverable": "Data integrity checklist covering source provenance, measurement resolution, missing controls, and versioned inputs.",
            "uncertainties": ["Raw data availability, instrument calibration, and chain-of-custody records are unknown."],
        },
        "scientific_reviewer": {
            "reasoning_summary": "The plan can proceed as a draft review packet, but scientific rigor remains review-gated.",
            "deliverable": "Scientific gate verdict: review_required until hypothesis, controls, replication, and acceptance criteria are checked.",
            "uncertainties": ["No independent reviewer has accepted the protocol design yet."],
        },
        "evidence_auditor": {
            "reasoning_summary": "Traceability is not complete until every claim links to source evidence or an explicit uncertainty note.",
            "deliverable": "Evidence audit verdict: review_required with provenance checks required before human decision.",
            "uncertainties": ["External evidence references and internal source packets need explicit review."],
        },
        "chief_scientist_synthesis": {
            "reasoning_summary": "The unified answer should be useful immediately while preserving review-required gates.",
            "deliverable": "Proceed with a review-gated research plan, build an evidence packet, and queue human review before final decision.",
            "uncertainties": ["Final decision remains outside the automatic Assistant workflow."],
        },
    }


def _specialist_cards(topic: str, evidence_ref: str | None, language: str = "en-US") -> list[dict[str, Any]]:
    plan = _team_plan(language)
    deliverables = _specialist_deliverables(topic, language)
    cards: list[dict[str, Any]] = []
    for index, step in enumerate(plan):
        specialist_id = str(step["specialist_id"])
        details = deliverables[specialist_id]
        next_step = plan[index + 1]["specialist_id"] if index + 1 < len(plan) else None
        cards.append(
            {
                "specialist_id": specialist_id,
                "title": step["title"],
                "objective": step["objective"],
                "inputs_used": ["operator_prompt", "assistant_mode_contract"],
                "reasoning_summary": details["reasoning_summary"],
                "deliverable": details["deliverable"],
                "uncertainties": details["uncertainties"],
                "handoff_to": [next_step] if isinstance(next_step, str) else [],
                "review_required": True,
                "evidence_refs": [evidence_ref] if evidence_ref else ["pending_evidence_pack"],
            }
        )
    return cards


def _apply_specialist_continuation(
    cards: list[dict[str, Any]],
    *,
    requested_specialist: str | None,
    parent_run_id: str | None,
) -> list[dict[str, Any]]:
    if not requested_specialist or not parent_run_id:
        return cards
    next_cards = []
    for card in cards:
        if card.get("specialist_id") != requested_specialist:
            next_cards.append(card)
            continue
        if _is_chinese(str(card.get("deliverable", ""))):
            next_cards.append(
                {
                    **card,
                    "inputs_used": [*list(card.get("inputs_used") or []), f"parent_run:{parent_run_id}"],
                    "reasoning_summary": f"承接上一轮 {parent_run_id}：继续深化该专家视角，同时保持 review_required 安全门。",
                    "deliverable": f"{card['deliverable']} 续问重点：补充反例、失效条件和下一轮人工科学审查问题。",
                    "handoff_to": ["scientific_reviewer", "evidence_auditor"],
                }
            )
            continue
        next_cards.append(
            {
                **card,
                "inputs_used": [*list(card.get("inputs_used") or []), f"parent_run:{parent_run_id}"],
                "reasoning_summary": (
                    f"Continuation from {parent_run_id}: deepen the prior specialist analysis while keeping "
                    "the same review-required gate."
                ),
                "deliverable": (
                    f"{card['deliverable']} Continuation focus: add counterexamples, failure conditions, "
                    "and review questions for the next human scientific review."
                ),
                "handoff_to": ["scientific_reviewer", "evidence_auditor"],
            }
        )
    return next_cards


def _handoff_records(cards: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for card in cards:
        for target in card.get("handoff_to", []):
            records.append(
                {
                    "handoff_id": _new_id("RHAND"),
                    "source_specialist": card["specialist_id"],
                    "target_specialist": target,
                    "source_run_id": run_id,
                    "handoff_summary": card["deliverable"],
                    "status": "recorded",
                    "review_required": True,
                }
            )
    return records


def _review_verdicts(evidence_pack_id: str | None) -> list[dict[str, Any]]:
    return [
        {
            "reviewer_id": "scientific_reviewer",
            "gate": "scientific_rigor",
            "verdict": "review_required",
            "required_before_state": "scientific_review_passed",
            "evidence_refs": [evidence_pack_id] if evidence_pack_id else ["pending_evidence_pack"],
            "blocking_reasons": [
                "Hypothesis, controls, replication, and acceptance criteria require human scientific review."
            ],
        },
        {
            "reviewer_id": "evidence_auditor",
            "gate": "evidence_traceability",
            "verdict": "review_required",
            "required_before_state": "evidence_audit_passed",
            "evidence_refs": [evidence_pack_id] if evidence_pack_id else ["pending_evidence_pack"],
            "blocking_reasons": [
                "External references, candidate data, and experimental suggestions require provenance audit."
            ],
        },
    ]


def _action_ledger(run_id: str, evidence_pack_id: str | None, review_packet_id: str | None) -> list[dict[str, Any]]:
    base = {
        "source_run_id": run_id,
        "source_specialist": "chief_scientist_synthesis",
    }
    return [
        {
            **base,
            "action_name": "evidence_pack.create_or_update",
            "action_policy": "auto_allowed",
            "requires_confirmation": False,
            "evidence_role": "research_review_evidence",
            "side_effects": ["internal_evidence_pack_written"],
            "status": "completed" if evidence_pack_id else "blocked",
            "target_id": evidence_pack_id,
        },
        {
            **base,
            "action_name": "review_packet_snapshot.create",
            "action_policy": "auto_allowed",
            "requires_confirmation": False,
            "evidence_role": "review_packet_snapshot",
            "side_effects": ["internal_snapshot_written"],
            "status": "completed" if review_packet_id else "blocked",
            "target_id": review_packet_id,
        },
        {
            **base,
            "action_name": "simulation_scenario.prepare",
            "action_policy": "auto_allowed",
            "requires_confirmation": False,
            "evidence_role": "scenario_recommendation",
            "side_effects": ["internal_simulation_recommendation_only"],
            "status": "queued_for_review",
            "target_id": None,
        },
        {
            **base,
            "action_name": "benchmark_suite.prepare",
            "action_policy": "auto_allowed",
            "requires_confirmation": False,
            "evidence_role": "benchmark_recommendation",
            "side_effects": ["internal_benchmark_recommendation_only"],
            "status": "queued_for_review",
            "target_id": None,
        },
        {
            **base,
            "action_name": "human_research_review_queue.create",
            "action_policy": "auto_allowed",
            "requires_confirmation": False,
            "evidence_role": "human_review_queue",
            "side_effects": ["internal_review_queue_item_written"],
            "status": "completed",
            "target_id": None,
        },
        {
            **base,
            "action_name": "release.final_decision",
            "action_policy": "forbidden",
            "requires_confirmation": True,
            "evidence_role": "forbidden_final_action",
            "side_effects": [],
            "status": "forbidden",
            "target_id": None,
        },
        {
            **base,
            "action_name": "external.share",
            "action_policy": "requires_confirmation",
            "requires_confirmation": True,
            "evidence_role": "external_share_review",
            "side_effects": [],
            "status": "requires_confirmation",
            "target_id": None,
        },
        {
            **base,
            "action_name": "tenant.cross_boundary",
            "action_policy": "forbidden",
            "requires_confirmation": True,
            "evidence_role": "tenant_boundary_guard",
            "side_effects": [],
            "status": "forbidden",
            "target_id": None,
        },
        {
            **base,
            "action_name": "hardware.run",
            "action_policy": "forbidden",
            "requires_confirmation": True,
            "evidence_role": "hardware_guard",
            "side_effects": [],
            "status": "forbidden",
            "target_id": None,
        },
    ]


def _reasoning_stages(language: str) -> list[dict[str, str]]:
    if language == "zh-CN":
        return [
            {
                "stage": "问题重构",
                "status": "complete",
                "readout": "把用户问题改写为：在 review_required 前提下，比较黄粉虫与蛴螬处理酒糟的受控小试优先级。",
            },
            {
                "stage": "专家分工",
                "status": "complete",
                "readout": "机制、方案、证据、数据完整性和科学审查专家分别接管基质边界、试验路径、来源质量和安全门。",
            },
            {
                "stage": "交锋收敛",
                "status": "complete",
                "readout": "专家组收敛到黄粉虫优先小试、蛴螬保留为反事实/探索路线；争议点转入含水率、残酒精、病原与合规边界。",
            },
            {
                "stage": "审查门",
                "status": "review_required",
                "readout": "所有外部证据、候选数据、实验建议和生产默认仍保持 review_required，不自动批准、不外发。",
            },
        ]
    return [
        {
            "stage": "Question reframing",
            "status": "complete",
            "readout": "Reframe the prompt as a review-gated research prioritization problem, not an approval workflow.",
        },
        {
            "stage": "Expert routing",
            "status": "complete",
            "readout": "Route mechanism, protocol, evidence, data integrity, and scientific rigor to distinct specialists.",
        },
        {
            "stage": "Debate convergence",
            "status": "complete",
            "readout": "Converge on a controlled pilot path while preserving counterfactual and uncertainty lanes.",
        },
        {
            "stage": "Gate posture",
            "status": "review_required",
            "readout": "External evidence, candidate data, experiment suggestions, and final decisions remain review_required.",
        },
    ]


def _evidence_status(evidence_pack_id: str | None, review_packet_id: str | None, language: str) -> list[dict[str, str | None]]:
    if language == "zh-CN":
        return [
            {
                "claim": "黄粉虫更适合作为酒糟处理首轮受控小试对象",
                "status": "candidate_evidence",
                "basis": "领域机制判断和可控饲养成熟度；仍需文献与内部数据审查。",
                "gate": "review_required",
                "source_ref": evidence_pack_id,
            },
            {
                "claim": "蛴螬保留为反事实/探索路线",
                "status": "uncertainty_lane",
                "basis": "虫种稳定性、病原、农田害虫风险和合规边界不确定性较高。",
                "gate": "review_required",
                "source_ref": evidence_pack_id,
            },
            {
                "claim": "任何外部文献或产业资料不得写入 validated defaults",
                "status": "audit_guardrail",
                "basis": "外部资料只能进入候选证据层，等待人工审查和来源许可确认。",
                "gate": "review_required",
                "source_ref": review_packet_id,
            },
        ]
    return [
        {
            "claim": "Preferred first controlled pilot",
            "status": "candidate_evidence",
            "basis": "Mechanism fit and operational controllability are plausible but still need source review.",
            "gate": "review_required",
            "source_ref": evidence_pack_id,
        },
        {
            "claim": "Counterfactual exploration lane",
            "status": "uncertainty_lane",
            "basis": "Containment, pathogen, pest, cycle-time, and regulatory boundaries remain uncertain.",
            "gate": "review_required",
            "source_ref": evidence_pack_id,
        },
        {
            "claim": "No validated-default promotion",
            "status": "audit_guardrail",
            "basis": "External material remains candidate evidence until human source review is complete.",
            "gate": "review_required",
            "source_ref": review_packet_id,
        },
    ]


def _experiment_plan(language: str) -> list[dict[str, Any]]:
    if language == "zh-CN":
        return [
            {
                "step": "P0 桌面证据审查",
                "design": "先收集黄粉虫、蛴螬、酒糟预处理、病原和合规边界资料，只进入候选证据层。",
                "controls": ["来源许可", "适用物种", "基质条件", "人工审查"],
                "stop_rule": "证据来源不可追溯或许可不清时停止进入小试。",
                "gate": "review_required",
            },
            {
                "step": "P1 黄粉虫受控小试",
                "design": "用干性/半干性酒糟设小批量重复组，记录虫龄、密度、含水率、pH、死亡率和残渣指标。",
                "controls": ["空白基质", "未处理酒糟", "预干燥酒糟", "批次重复"],
                "stop_rule": "霉菌、残酒精刺激、死亡率或逃逸风险超阈值即停止。",
                "gate": "review_required",
            },
            {
                "step": "P2 蛴螬反事实组",
                "design": "只在隔离条件下作为探索组比较取食、死亡率、污染和管理风险，不作为默认生产路线。",
                "controls": ["隔离容器", "同源酒糟批次", "病原观察", "农田害虫风险记录"],
                "stop_rule": "品系不可控、病原或合规风险无法关闭时终止。",
                "gate": "review_required",
            },
        ]
    return [
        {
            "step": "P0 desk evidence review",
            "design": "Collect literature, standards, and internal prior evidence only as review-gated candidate evidence.",
            "controls": ["source license", "species applicability", "substrate boundary", "human review"],
            "stop_rule": "Stop before pilot if provenance or licensing cannot be reviewed.",
            "gate": "review_required",
        },
        {
            "step": "P1 preferred controlled pilot",
            "design": "Run a small replicated pilot with explicit substrate, life-stage, density, moisture, mortality, and residue endpoints.",
            "controls": ["blank substrate", "untreated substrate", "preconditioned substrate", "batch replicate"],
            "stop_rule": "Stop on mold, toxicity, mortality, escape, or data-integrity threshold breach.",
            "gate": "review_required",
        },
        {
            "step": "P2 counterfactual lane",
            "design": "Keep the alternative species/path as isolated exploration, not a default production route.",
            "controls": ["isolated container", "matched substrate batch", "pathogen observation", "containment record"],
            "stop_rule": "Terminate if containment, pathogen, or regulatory risk cannot be closed.",
            "gate": "review_required",
        },
    ]


def _debate_turns(language: str) -> list[dict[str, str]]:
    if language == "zh-CN":
        return [
            {
                "speaker": "机制分析专家",
                "stance": "先质疑虫种与酒糟基质是否匹配，不把能取食等同于适合工业化处理。",
                "challenges": "要求方案设计专家补齐含水率、残酒精、酸度、霉菌和死亡率边界。",
                "reply": "方案侧同意把酒糟预处理和停止规则放在小试前置条件里。",
            },
            {
                "speaker": "方案设计专家",
                "stance": "支持黄粉虫优先做受控小试，蛴螬只作为反事实或探索组。",
                "challenges": "要求数据完整性审查专家定义批次、虫龄、密度和终点指标。",
                "reply": "数据完整性侧要求所有批次、仪器和终点指标进入审查包后再判断优先级。",
            },
            {
                "speaker": "证据文献策展专家",
                "stance": "同意黄粉虫优先级更高，但外部文献只能进入候选证据层。",
                "challenges": "要求证据审计专家确认来源质量、许可和边界条件。",
                "reply": "证据审计侧确认不写 validated defaults，只生成带来源的候选证据。",
            },
            {
                "speaker": "科学审查专家",
                "stance": "允许给出研究判断，不允许把结论升级成批准或生产默认。",
                "challenges": "所有路线保持 review_required，等待人工审查和证据审计。",
                "reply": "首席科学家收敛为黄粉虫优先小试、蛴螬反事实探索、人工评审后再推进。",
            },
        ]
    return [
        {
            "speaker": "Mechanistic Analyst",
            "stance": "Challenge substrate-species fit before treating feeding ability as operational suitability.",
            "challenges": "Ask Protocol Designer to lock moisture, residual alcohol, pH, mold risk, and mortality boundaries.",
            "reply": "Protocol accepts substrate conditioning and stopping rules as prerequisites before pilot interpretation.",
        },
        {
            "speaker": "Protocol Designer",
            "stance": "Prefer the lower-risk controlled pilot before any production recommendation.",
            "challenges": "Ask Data Integrity Reviewer to define batch, life-stage, density, and endpoint records.",
            "reply": "Data Integrity requires every batch, instrument, and endpoint to enter the review packet first.",
        },
        {
            "speaker": "Reference Evidence Curator",
            "stance": "Use external literature for prioritization only, not validated defaults.",
            "challenges": "Ask Evidence Auditor to check source quality, licensing, and boundary conditions.",
            "reply": "Evidence Audit confirms external sources remain candidate evidence with provenance.",
        },
        {
            "speaker": "Scientific Reviewer",
            "stance": "A research judgment is allowed; approval or production defaults are not.",
            "challenges": "Keep the result review_required until human scientific review and evidence audit close.",
            "reply": "Chief Scientist converges on a review-gated pilot, not a production default.",
        },
    ]


def _final_synthesis(topic: str, evidence_pack_id: str | None, review_packet_id: str | None, language: str) -> dict[str, Any]:
    state = "review_required"
    if state not in RESEARCH_REVIEW_APPROVAL_STATES or state in DISALLOWED_FINAL_STATES:
        raise RuntimeError("Invalid research review approval state")
    if language == "zh-CN":
        unified_answer = _specific_unified_answer(topic, language) or (
            "BOS 已组建固定专家评审团队，并产出 review-gated 科研方案评审。下一步不是自动批准，"
            "而是把目标改写成假设、对照、证据图谱、仿真情景和数据完整性清单，再进入人工最终判断。"
        )
        recommended_next_steps = [
            "确认假设、主要终点、阴性对照和停止规则。",
            "把文献、标准和外部资料作为带来源的候选证据附入审查包。",
            "仿真只作为内部敏感性检查，不作为批准依据。",
            "把科学严谨性和证据可追溯性送入人工评审。",
        ]
        gate_summary = {
            "scientific_review": "review_required",
            "evidence_audit": "review_required",
            "final_decision": "human_only",
        }
    else:
        unified_answer = _specific_unified_answer(topic, language) or (
            "BOS has formed a fixed expert review team and produced a review-gated protocol critique. "
            "The strongest next step is to turn the current objective into a hypothesis, controls, evidence map, "
            "simulation scenarios, and data integrity checklist before any final human decision."
        )
        recommended_next_steps = [
            "Confirm hypothesis, primary endpoint, negative controls, and stopping rules.",
            "Attach reviewed literature and standards as candidate evidence with provenance.",
            "Run simulation scenarios only as internal sensitivity checks.",
            "Route scientific rigor and evidence traceability gates to human reviewers.",
        ]
        gate_summary = {
            "scientific_review": "review_required",
            "evidence_audit": "review_required",
            "final_decision": "human_only",
        }
    return {
        "approval_state": state,
        "language": language,
        "unified_answer": unified_answer,
        "reasoning_stages": _reasoning_stages(language),
        "debate_turns": _debate_turns(language),
        "evidence_status": _evidence_status(evidence_pack_id, review_packet_id, language),
        "experiment_plan": _experiment_plan(language),
        "recommended_next_steps": recommended_next_steps,
        "gate_summary": gate_summary,
        "topic": topic,
        "evidence_pack_id": evidence_pack_id,
        "review_packet_snapshot_id": review_packet_id,
    }


def _continuation_synthesis_overlay(
    final_synthesis: dict[str, Any],
    *,
    requested_specialist: str | None,
    parent_run_id: str | None,
) -> dict[str, Any]:
    if not parent_run_id:
        return final_synthesis
    specialist_label = requested_specialist or "research_review_team"
    if final_synthesis.get("language") == "zh-CN":
        return {
            **final_synthesis,
            "unified_answer": (
                f"BOS 已沿用上一轮 Research Review {parent_run_id}，并让 {specialist_label} 继续深挖。"
                "这次只增加专家分析深度，结论仍保持 review_required，直到科学审查和证据审计完成。"
            ),
            "continuity": {
                "parent_run_id": parent_run_id,
                "requested_specialist": specialist_label,
                "team_context_reused": True,
                "approval_state_inherited": "review_required",
            },
        }
    return {
        **final_synthesis,
        "unified_answer": (
            f"BOS continued the prior Research Review run {parent_run_id} with {specialist_label}. "
            "The continuation adds deeper specialist analysis, but the result remains review_required "
            "until scientific review and evidence audit are completed."
        ),
        "continuity": {
            "parent_run_id": parent_run_id,
            "requested_specialist": specialist_label,
            "team_context_reused": True,
            "approval_state_inherited": "review_required",
        },
    }


def _memory_tags(topic: str) -> list[str]:
    tags = ["research_review", "protocol_review", "review_required", "evidence_audit", "scientific_review"]
    if "black soldier" in topic.lower() or "bsf" in topic.lower() or "黑水虻" in topic:
        tags.append("bsf")
    if "solid waste" in topic.lower() or "固废" in topic:
        tags.append("solid_waste")
    return tags


def build_research_review_summary(
    *,
    run_id: str,
    message: str,
    evidence_pack_id: str | None = None,
    review_packet_id: str | None = None,
    parent_record: AssistantRunRecord | None = None,
    requested_specialist: str | None = None,
) -> dict[str, Any]:
    topic = _topic_from_message(message)
    language = _language_for(message)
    continuity_context = _continuity_context(parent_record)
    recalled_team_plan = continuity_context.get("recalled_team_plan") if continuity_context else None
    team_plan = recalled_team_plan if isinstance(recalled_team_plan, list) and recalled_team_plan else _team_plan(language)
    specialist_cards = _apply_specialist_continuation(
        _specialist_cards(topic, evidence_pack_id, language),
        requested_specialist=requested_specialist,
        parent_run_id=parent_record.run_id if parent_record else None,
    )
    final_synthesis = _continuation_synthesis_overlay(
        _final_synthesis(topic, evidence_pack_id, review_packet_id, language),
        requested_specialist=requested_specialist,
        parent_run_id=parent_record.run_id if parent_record else None,
    )
    return {
        "mode": RESEARCH_REVIEW_MODE,
        "language": language,
        "tool_registry_version": RESEARCH_REVIEW_REGISTRY_VERSION,
        "team_plan": team_plan,
        "specialist_cards": specialist_cards,
        "handoff_records": _handoff_records(specialist_cards, run_id),
        "review_verdicts": _review_verdicts(evidence_pack_id),
        "action_ledger": _action_ledger(run_id, evidence_pack_id, review_packet_id),
        "memory_tags": _memory_tags(topic),
        "final_synthesis": final_synthesis,
        "continuity_context": continuity_context,
        "result_ids": {
            "assistant_run_id": run_id,
            "parent_run_id": parent_record.run_id if parent_record else None,
            "evidence_pack_id": evidence_pack_id,
            "review_packet_snapshot_id": review_packet_id,
        },
        "safety": {
            "external_materials": "review_required",
            "candidate_data": "review_required",
            "experiment_suggestions": "review_required",
            "release_decision_auto_pass": False,
            "external_share_auto_send": False,
            "cross_tenant_action": False,
            "hardware_execution": False,
            "final_action_execution": False,
        },
    }


async def create_research_review_run_record(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    payload: AssistantRunCreate,
) -> AssistantRunRecord:
    intent = parse_research_review_intent(payload.message)
    parent_record = None
    if payload.parent_run_id:
        parent_record = await db.scalar(
            select(AssistantRunRecord).where(
                AssistantRunRecord.run_id == payload.parent_run_id,
                AssistantRunRecord.tenant_id == tenant_id,
            )
        )
        if parent_record is not None:
            intent["parent_run_id"] = parent_record.run_id
            intent["thread_id"] = payload.thread_id
            intent["continuity_scope"] = "tenant_scoped_parent_run"
        else:
            intent["parent_run_id_requested"] = payload.parent_run_id
            intent["thread_id"] = payload.thread_id
            intent["continuity_scope"] = "not_recalled_missing_or_tenant_boundary"
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

    requested_specialist = intent.get("requested_specialist") if isinstance(intent.get("requested_specialist"), str) else None
    summary = build_research_review_summary(
        run_id=run_record.run_id,
        message=payload.message,
        parent_record=parent_record,
        requested_specialist=requested_specialist,
    )
    pack = await create_evidence_pack(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payload=EvidencePackCreate(
            subject_type="assistant_run",
            subject_id=run_record.run_id,
            title=f"Research Review run {run_record.run_id}",
            summary="Review-gated research protocol critique with fixed expert-team topology.",
            verification_status="review_required",
            human_review_required=True,
            items=[
                EvidenceItemCreate(
                    kind="research_review_intent",
                    source_kind="operator_input",
                    source_ref=run_record.run_id,
                    payload=intent,
                    uncertainty_level="medium",
                ),
                EvidenceItemCreate(
                    kind="research_review_team_trace",
                    source_kind="deterministic_model",
                    source_ref=run_record.run_id,
                    payload={
                        "team_plan": summary["team_plan"],
                        "specialist_cards": summary["specialist_cards"],
                        "handoff_records": summary["handoff_records"],
                            "review_verdicts": summary["review_verdicts"],
                            "action_ledger": summary["action_ledger"],
                            "continuity_context": summary["continuity_context"],
                        },
                        uncertainty_level="medium",
                    ),
            ],
        ),
    )
    run_record.evidence_pack_id = pack.evidence_pack_id

    summary = build_research_review_summary(
        run_id=run_record.run_id,
        message=payload.message,
        evidence_pack_id=pack.evidence_pack_id,
        parent_record=parent_record,
        requested_specialist=requested_specialist,
    )
    packet = {
        "packet_type": "research_review_packet",
        "assistant_run_id": run_record.run_id,
        "parent_run_id": parent_record.run_id if parent_record else None,
        "tenant_id": tenant_id,
        "generated_by_user_id": user_id,
        "evidence_pack_ids": [pack.evidence_pack_id],
        "team_plan": summary["team_plan"],
        "review_verdicts": summary["review_verdicts"],
        "final_synthesis": summary["final_synthesis"],
        "continuity_context": summary["continuity_context"],
        "guardrails": [
            "review_required",
            "human_final_decision_required",
            "no_external_share",
            "no_cross_tenant_action",
            "no_hardware_execution",
            "no_final_action_execution",
        ],
    }
    snapshot = await persist_review_packet_snapshot(
        db,
        tenant_id=tenant_id,
        generated_by_user_id=user_id,
        packet=packet,
    )
    review_packet_id = snapshot.source_review_packet_id
    summary = build_research_review_summary(
        run_id=run_record.run_id,
        message=payload.message,
        evidence_pack_id=pack.evidence_pack_id,
        review_packet_id=review_packet_id,
        parent_record=parent_record,
        requested_specialist=requested_specialist,
    )

    approval_request = HumanApprovalRequestRecord(
        approval_request_id=_new_id("HAR"),
        release_decision_id=None,
        tenant_id=tenant_id,
        user_id=user_id,
        subject_type="research_review",
        subject_id=run_record.run_id,
        status="pending",
        reason="Research Review requires scientific review and evidence audit before human final decision.",
        payload=jsonable_encoder(
            {
                "assistant_run_id": run_record.run_id,
                "assistant_evidence_pack_id": pack.evidence_pack_id,
                "evidence_pack_id": pack.evidence_pack_id,
                "source_review_packet_id": review_packet_id,
                "approval_state": summary["final_synthesis"]["approval_state"],
                "scope": "research_protocol_review",
                "side_effects": {
                    "release_decision": "unchanged",
                    "external_share": False,
                    "hardware_execution": False,
                    "final_action_execution": False,
                },
            }
        ),
    )
    db.add(approval_request)

    summary["human_review_queue"] = {
        "status": "pending",
        "approval_request_id": approval_request.approval_request_id,
        "source_review_packet_id": review_packet_id,
        "evidence_pack_id": pack.evidence_pack_id,
        "guardrails": ["review_required", "queue_only", "human_final_decision_required"],
    }
    run_record.result_summary = summary
    run_record.status = "completed"
    run_record.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run_record)
    return run_record
