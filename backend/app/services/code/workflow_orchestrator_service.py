"""
Dynamic workflow-skill orchestration for BOS Code.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import CodeSession, CodeSkill, CodeTask, CodeVerificationRun, CodeWorkerEvent


@dataclass(slots=True)
class WorkflowPlan:
    mode: str
    recommended_skills: list[str]
    rationale: list[str]


class CodeWorkflowOrchestratorService:
    @staticmethod
    def _contains_any(text: str, *tokens: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in tokens)

    @classmethod
    def plan(
        cls,
        *,
        query: str,
        open_tasks: list[CodeTask],
        latest_session: CodeSession | None,
        recent_verifications: list[CodeVerificationRun],
        recent_events: list[CodeWorkerEvent],
        skills: list[CodeSkill],
    ) -> WorkflowPlan:
        text = query.strip().lower()
        rationale: list[str] = []
        recommended = ["gstack-bos-director", "tbc-autonomy-loop"]
        mode = "execution"

        failed_verification = next((run for run in recent_verifications if run.verification_status == "failed"), None)
        blocked_event = next((event for event in recent_events if (event.payload or {}).get("blocking")), None)
        active_recovery_task = next((task for task in open_tasks if (task.scope or "").lower() == "code/recovery"), None)

        if active_recovery_task is not None or failed_verification is not None or blocked_event is not None:
            mode = "recovery"
            recommended.extend(["bos-systematic-debugging", "bos-verification-gate"])
            rationale.append("Recovery evidence is active, so debugging and verification gating should lead.")
        elif cls._contains_any(text, "plan", "scope", "design", "strategy", "roadmap", "packet"):
            mode = "planning"
            recommended.append("bos-task-planning")
            rationale.append("The request reads like planning or packet-formation work.")
        elif cls._contains_any(text, "verify", "verification", "gate", "review", "done", "complete"):
            mode = "verification"
            recommended.append("bos-verification-gate")
            rationale.append("The request is completion- or gate-oriented, so verification discipline should lead.")
        elif cls._contains_any(text, "parallel", "slice", "subagent", "fan out", "dispatch"):
            mode = "subagent_execution"
            recommended.extend(["bos-task-planning", "bos-subagent-execution"])
            rationale.append("The request suggests splitting work into bounded executor slices.")
        else:
            if len(open_tasks) >= 2 or any(len(task.acceptance_criteria or []) >= 2 for task in open_tasks):
                recommended.append("bos-subagent-execution")
                rationale.append("Open task pressure suggests bounded slice dispatch will help.")

        if latest_session is not None and latest_session.session_status in {"blocked", "failed", "trust_required"}:
            if "bos-systematic-debugging" not in recommended:
                recommended.append("bos-systematic-debugging")
            rationale.append(f"Latest session status `{latest_session.session_status}` requires evidence-first routing.")

        if any(int(skill.negative_feedback_count or 0) > int(skill.positive_feedback_count or 0) for skill in skills):
            if "hermes-growth-loop" not in recommended:
                recommended.append("hermes-growth-loop")
            rationale.append("Recent skill feedback shows friction, so growth heuristics should stay in the loop.")

        if "gbrain-project-brain" not in recommended:
            recommended.append("gbrain-project-brain")
        if "hermes-growth-loop" not in recommended:
            recommended.append("hermes-growth-loop")

        deduped: list[str] = []
        for item in recommended:
            if item not in deduped:
                deduped.append(item)

        if not rationale:
            rationale.append("Defaulted to execution mode because no stronger planning or recovery signal won.")

        return WorkflowPlan(
            mode=mode,
            recommended_skills=deduped,
            rationale=rationale,
        )

    @staticmethod
    def format_context(plan: WorkflowPlan) -> str:
        return (
            "Recommended BOS workflow skills for this turn.\n\n"
            f"Mode: {plan.mode}\n"
            "Skills:\n"
            + "\n".join(f"- {skill}" for skill in plan.recommended_skills)
            + "\nRationale:\n"
            + "\n".join(f"- {line}" for line in plan.rationale)
        )
