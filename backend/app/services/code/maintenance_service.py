"""
Cross-session autonomy maintenance for BOS Code.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.models import (
    CodeAgentRuntimeState,
    CodeReflectionRun,
    CodeSession,
    CodeSkill,
    CodeTask,
    CodeVerificationRun,
    CodeWorkerEvent,
)
from app.services.brain_runtime import build_structured_runtime_document
from app.services.code.session_search_service import CodeSessionSearchService
from app.services.code.workflow_orchestrator_service import CodeWorkflowOrchestratorService


class CodeMaintenanceService:
    REPO_ROOT = Path(__file__).resolve().parents[4]
    RUNTIME_DIR = REPO_ROOT / ".agents" / "runtime"
    STAGING_DIR = REPO_ROOT / "reports" / "runtime-staging"
    REPORT_MARKDOWN_PATH = STAGING_DIR / "autonomy-maintenance-latest.md"
    REPORT_JSON_PATH = STAGING_DIR / "autonomy-maintenance-latest.json"

    @classmethod
    def _ensure_directories(cls) -> None:
        cls.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        cls.STAGING_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _display_path(cls, path: Path) -> str:
        try:
            return path.relative_to(cls.REPO_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _read_document(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @classmethod
    def _document_excerpt(cls, path: Path, *, max_chars: int = 900) -> str:
        content = cls._read_document(path).strip()
        if not content:
            return ""
        return content[:max_chars].strip()

    @staticmethod
    def _section_map(content: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        for raw_line in content.replace("\r\n", "\n").splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("## "):
                current_section = stripped[3:].strip()
                sections.setdefault(current_section, [])
                continue
            if current_section and stripped.startswith("- "):
                sections.setdefault(current_section, []).append(stripped)
        return sections

    @classmethod
    def _write_document(
        cls,
        *,
        document_key: str,
        path: Path,
        updates: dict[str, list[str]],
    ) -> str:
        structured = build_structured_runtime_document(document_key, cls._read_document(path))
        sections = cls._section_map(structured)
        for heading, lines in updates.items():
            sections[heading] = lines

        title_map = {
            "project_brain": "Project Brain",
            "decision_journal": "Decision Journal",
            "evolution_log": "Evolution Log",
            "run_ledger": "Autonomy Run Ledger",
        }
        order_map = {
            "project_brain": [
                "Mission",
                "Current Focus",
                "Next Slices",
                "Stable Facts",
                "Constraints",
                "Known Good Commands",
                "Repeated Pitfalls",
            ],
            "decision_journal": [
                "Recent Decisions",
                "Plan Changes",
            ],
            "evolution_log": [
                "Active Heuristics",
                "Recent Learnings",
            ],
        }
        order = order_map[document_key]
        output = [f"# {title_map[document_key]}", ""]
        for heading in order:
            output.append(f"## {heading}")
            output.append("")
            output.extend(sections.get(heading) or [f"- Record {heading.lower()} here."])
            output.append("")
        text = "\n".join(output).rstrip() + "\n"
        path.write_text(text, encoding="utf-8")
        return text

    @staticmethod
    def _task_label(task: CodeTask) -> str:
        return f"#{task.id} {task.title} ({task.task_status})"

    @classmethod
    def _build_project_brain_updates(
        cls,
        *,
        open_tasks: list[CodeTask],
        completed_tasks: list[CodeTask],
        runtime: CodeAgentRuntimeState,
        latest_session: CodeSession | None,
    ) -> dict[str, list[str]]:
        focus = open_tasks[0] if open_tasks else None
        focus_line = (
            f"- Current autonomy focus: {cls._task_label(focus)}."
            if focus is not None
            else "- Current autonomy focus: no active task; maintenance mode is active."
        )
        next_lines = [
            f"- Keep progressing {cls._task_label(task)} without waiting for a manual continue prompt."
            for task in open_tasks[:3]
        ] or [
            "- Keep the workspace in maintenance mode and wait for the next task or thread event.",
            "- Refresh branch posture and verification state during idle windows.",
        ]
        stable_facts = [
            "- BOS Code already has heartbeat, reflection, memory snapshot, skill draft, and subagent runtime primitives.",
            "- Celery beat is available and already runs BOS Code due automation jobs every minute.",
            "- The operator cockpit exposes Always-On Runtime, task orchestration, memory, reflections, and skill feedback surfaces.",
        ]
        constraints = [
            "- Automation-safe actions may refresh branch posture, run verification, reset prompt delivery, and move worker lanes.",
            "- Review-gated or human-only actions must stay visible instead of being silently auto-approved.",
            "- Autonomous repair should remain isolated to the tenant worktree and must not assume mainline merge authority.",
        ]
        commands = [
            r"- `.\scripts\p0_preflight.ps1` remains the strongest local readiness sweep.",
            r"- `C:\bos v9\bos v9\.venv\Scripts\python.exe -m pytest backend\tests\unit\test_code_runtime_services.py -q` is the primary runtime service slice.",
            r"- `npm exec vitest run src/components/code/CodeRuntimeComponents.test.tsx` is the primary runtime UI slice.",
        ]
        pitfalls = [
            "- Heartbeat summaries alone are not enough; continuation prompts must carry the active task and next gate explicitly.",
            "- Reflection-only memory is too local; autonomy maintenance must also compress cross-session task and verification evidence.",
            "- Idle time should not become dead time; the runtime needs a maintenance lane when no foreground task is active.",
        ]
        if latest_session is not None:
            focus_line += f" Latest session: #{latest_session.id} ({latest_session.session_status})."
        if completed_tasks:
            stable_facts.append(
                f"- Recently completed tasks remain available for reuse and verification evidence: {', '.join(cls._task_label(task) for task in completed_tasks[:2])}."
            )
        if runtime.runtime_metrics and runtime.runtime_metrics.get("policy_learning"):
            stable_facts.append("- Runtime policy learning is already persisted in runtime metrics and can be folded into heuristics.")
        return {
            "Mission": [
                "- Build a company-style BOS autonomy layer that keeps working across threads, keeps learning, and keeps the operator in control of risky gates.",
            ],
            "Current Focus": [focus_line],
            "Next Slices": next_lines,
            "Stable Facts": stable_facts,
            "Constraints": constraints,
            "Known Good Commands": commands,
            "Repeated Pitfalls": pitfalls,
        }

    @staticmethod
    def _build_decision_updates(
        *,
        generated_at: datetime,
        open_tasks: list[CodeTask],
        latest_session: CodeSession | None,
    ) -> dict[str, list[str]]:
        timestamp = generated_at.isoformat(timespec="minutes")
        recent = [
            f"- {timestamp}: Maintenance run updated cross-thread project memory and runtime staging artifacts.",
            "- Heartbeat continuation should continue active work when the session is ready-for-prompt instead of stopping at a passive summary.",
            "- A dedicated maintenance job should own idle-time upkeep every three hours.",
        ]
        if latest_session is not None:
            recent.append(
                f"- Latest active session during maintenance: #{latest_session.id} with status `{latest_session.session_status}`."
            )
        if open_tasks:
            recent.append(
                f"- Open task pressure during maintenance: {', '.join(f'#{task.id}:{task.task_status}' for task in open_tasks[:3])}."
            )
        plan_changes = [
            "- Shift from isolated autonomy primitives toward an always-on operating layer with explicit maintenance reporting.",
            "- Use `.agents/runtime` as the durable brain and mirror it into `reports/runtime-staging/` for operator-facing review.",
        ]
        return {
            "Recent Decisions": recent,
            "Plan Changes": plan_changes,
        }

    @staticmethod
    def _build_evolution_updates(
        *,
        runtime: CodeAgentRuntimeState,
        recent_reflections: list[CodeReflectionRun],
        recent_verifications: list[CodeVerificationRun],
        recent_events: list[CodeWorkerEvent],
    ) -> dict[str, list[str]]:
        policy_learning = dict((runtime.runtime_metrics or {}).get("policy_learning") or {})
        heuristics: list[str] = [
            "- Prefer automation-safe continuation when a session is ready-for-prompt and an active task still exists.",
            "- Treat verification failures and blocked subagent aggregates as stronger signals than optimistic task summaries.",
        ]
        for category, outcomes in list(policy_learning.items())[:4]:
            top = sorted(outcomes.items(), key=lambda item: (-int(item[1]), item[0]))[:2]
            rendered = ", ".join(f"{label}={count}" for label, count in top)
            heuristics.append(f"- Policy learning snapshot suggests `{category}` is currently driven by {rendered}.")

        learnings: list[str] = []
        if recent_reflections:
            output_counts = Counter(reflection.output_kind for reflection in recent_reflections)
            learnings.append(
                "- Recent reflections favored "
                + ", ".join(f"{kind} ({count})" for kind, count in output_counts.items())
                + "."
            )
        if recent_verifications:
            status_counts = Counter(run.verification_status for run in recent_verifications)
            learnings.append(
                "- Recent verification outcomes: "
                + ", ".join(f"{status} ({count})" for status, count in status_counts.items())
                + "."
            )
        if recent_events:
            blocked_events = sum(1 for event in recent_events if (event.payload or {}).get("blocking"))
            if blocked_events:
                learnings.append(f"- Recent worker events contained {blocked_events} blocking signals that should bias future recovery-first routing.")
        if not learnings:
            learnings.append("- Maintenance did not find enough new evidence to change heuristics in this run.")
        return {
            "Active Heuristics": heuristics,
            "Recent Learnings": learnings,
        }

    @classmethod
    def _build_report_markdown(
        cls,
        *,
        generated_at: datetime,
        runtime: CodeAgentRuntimeState,
        open_tasks: list[CodeTask],
        completed_tasks: list[CodeTask],
        latest_session: CodeSession | None,
        active_skills: list[CodeSkill],
        recent_reflections: list[CodeReflectionRun],
        recent_verifications: list[CodeVerificationRun],
    ) -> str:
        metrics = dict(runtime.runtime_metrics or {})
        loop_budget = metrics.get("last_heartbeat_loop_budget")
        convergence_signal = metrics.get("last_heartbeat_convergence_signal")
        difficulty_signals = list(metrics.get("last_heartbeat_difficulty_signals") or [])
        reflection_verified_signal = metrics.get("last_reflection_verified_signal")
        reflection_verification_signals = list(metrics.get("last_reflection_verification_signals") or [])
        lines = [
            "# BOS Autonomy Maintenance Report",
            "",
            f"- Generated At: {generated_at.isoformat()}",
            f"- Open Tasks: {len(open_tasks)}",
            f"- Recently Completed Tasks: {len(completed_tasks)}",
            f"- Active Skills: {len(active_skills)}",
            f"- Recent Reflections: {len(recent_reflections)}",
            f"- Recent Verification Runs: {len(recent_verifications)}",
        ]
        if latest_session is not None:
            lines.append(
                f"- Latest Session: #{latest_session.id} ({latest_session.session_status} / {latest_session.verification_status})"
            )
        lines.extend(
            [
                "",
                "## Autonomy Loop Posture",
                "",
            ]
        )
        if loop_budget or convergence_signal or difficulty_signals:
            if loop_budget:
                lines.append(f"- Loop budget: {loop_budget}")
            if convergence_signal:
                lines.append(f"- Convergence signal: {convergence_signal}")
            if difficulty_signals:
                lines.append("- Difficulty signals: " + ", ".join(str(signal) for signal in difficulty_signals[:6]))
        else:
            lines.append("- No heartbeat loop posture has been recorded yet.")
        lines.extend(
            [
                "",
                "## Reflection Learning Gate",
                "",
            ]
        )
        if isinstance(reflection_verified_signal, bool):
            lines.append(
                "- Reflection mode: "
                + ("verified skill promotion is allowed." if reflection_verified_signal else "memory only; skill promotion is currently blocked.")
            )
            if reflection_verification_signals:
                lines.append(
                    "- Verification signals: "
                    + ", ".join(str(signal) for signal in reflection_verification_signals[:6])
                )
        else:
            lines.append("- No reflection verification gate has been recorded yet.")
        lines.extend(
            [
                "",
                "## Open Task Queue",
                "",
            ]
        )
        if open_tasks:
            lines.extend(f"- {cls._task_label(task)}" for task in open_tasks[:5])
        else:
            lines.append("- No active BOS Code tasks. The workspace is currently in maintenance posture.")
        lines.extend(
            [
                "",
                "## Active Skill Signals",
                "",
            ]
        )
        if active_skills:
            lines.extend(
                f"- {skill.name} ({skill.skill_status}) +{skill.positive_feedback_count} / -{skill.negative_feedback_count}"
                for skill in active_skills[:5]
            )
        else:
            lines.append("- No active or draft skills are available yet.")
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _experience_quality(
        *,
        project_brain: str,
        decision_journal: str,
        evolution_log: str,
        recent_reflections: list[CodeReflectionRun],
        recent_verifications: list[CodeVerificationRun],
    ) -> dict[str, Any]:
        score = 0
        notes: list[str] = []
        if len(project_brain) > 200:
            score += 1
            notes.append("Project brain contains durable context beyond the default scaffold.")
        else:
            notes.append("Project brain still looks sparse; maintenance should keep enriching it.")
        if len(decision_journal) > 120:
            score += 1
            notes.append("Decision journal is recording planning changes and recent decisions.")
        else:
            notes.append("Decision journal still needs more decision-quality evidence.")
        if len(evolution_log) > 120:
            score += 1
            notes.append("Evolution log is capturing heuristics and recent learnings.")
        else:
            notes.append("Evolution log remains thin; long-run learning quality is still early.")
        if recent_reflections:
            score += 1
            notes.append(f"Recent reflections available: {len(recent_reflections)}.")
        if recent_verifications:
            score += 1
            notes.append(f"Recent verification evidence available: {len(recent_verifications)}.")
        posture = "strong" if score >= 4 else "emerging" if score >= 2 else "thin"
        return {"score": score, "posture": posture, "notes": notes}

    @classmethod
    def _build_next_autonomy_objective(
        cls,
        *,
        open_tasks: list[CodeTask],
        latest_session: CodeSession | None,
        recent_verifications: list[CodeVerificationRun],
        active_skills: list[CodeSkill],
    ) -> tuple[str, str]:
        if open_tasks:
            task = open_tasks[0]
            return (
                "continue_active",
                f"Continue task #{task.id} {task.title} and keep pushing it to the next gate without waiting for another manual continue prompt.",
            )
        failed_verification = next((run for run in recent_verifications if run.verification_status == "failed"), None)
        if failed_verification is not None:
            return (
                "recover_verification",
                f"Inspect recent verification failure in stage `{failed_verification.verification_stage}` and prepare the next safe corrective move.",
            )
        fragile_skill = next(
            (
                skill
                for skill in active_skills
                if int(skill.negative_feedback_count or 0) > int(skill.positive_feedback_count or 0)
            ),
            None,
        )
        if fragile_skill is not None:
            return (
                "repair_skill",
                f"Review skill `{fragile_skill.name}` and improve it using recent runtime evidence before it causes repeated weak handoffs.",
            )
        if latest_session is not None and latest_session.session_status == "blocked":
            return (
                "recover_session",
                f"Inspect blocked session #{latest_session.id} and restore it to a healthy ready-for-prompt posture if the blocker is recoverable.",
            )
        return (
            "idle_maintenance",
            "Run idle BOS maintenance: refresh branch posture, inspect readiness, and look for the highest-value optimization or verification sweep to perform next.",
        )

    @classmethod
    async def build_brain_context(
        cls,
        db,
        *,
        workspace_id: int,
        tenant_id: int,
        query: str,
        current_session_id: int | None = None,
    ) -> str:
        cls._ensure_directories()
        blocks: list[str] = []

        project_brain = cls._document_excerpt(cls.RUNTIME_DIR / "project-brain.md")
        if project_brain:
            blocks.append(f"## Project Brain\n{project_brain}")

        evolution_log = cls._document_excerpt(cls.RUNTIME_DIR / "evolution-log.md", max_chars=700)
        if evolution_log:
            blocks.append(f"## Evolution Heuristics\n{evolution_log}")

        run_ledger = cls._document_excerpt(cls.RUNTIME_DIR / "run-ledger.md", max_chars=700)
        if run_ledger:
            blocks.append(f"## Recent Autonomy Runs\n{run_ledger}")

        task_rows = await db.execute(
            select(CodeTask).where(CodeTask.workspace_id == workspace_id).order_by(CodeTask.updated_at.desc(), CodeTask.id.desc())
        )
        open_tasks = [
            task for task in list(task_rows.scalars().all())
            if task.task_status in {"created", "running", "review_pending", "in_review", "verification_pending", "blocked"}
        ]
        latest_session = await db.scalar(
            select(CodeSession).where(CodeSession.workspace_id == workspace_id).order_by(CodeSession.updated_at.desc(), CodeSession.id.desc())
        )
        recent_verifications = list(
            (
                await db.execute(
                    select(CodeVerificationRun)
                    .join(CodeSession, CodeVerificationRun.session_id == CodeSession.id)
                    .where(CodeSession.workspace_id == workspace_id)
                    .order_by(CodeVerificationRun.started_at.desc(), CodeVerificationRun.id.desc())
                    .limit(6)
                )
            ).scalars().all()
        )
        recent_events = list(
            (
                await db.execute(
                    select(CodeWorkerEvent)
                    .where(CodeWorkerEvent.workspace_id == workspace_id)
                    .order_by(CodeWorkerEvent.created_at.desc(), CodeWorkerEvent.id.desc())
                    .limit(10)
                )
            ).scalars().all()
        )
        skills = list(
            (
                await db.execute(
                    select(CodeSkill)
                    .where(CodeSkill.workspace_id == workspace_id)
                    .order_by(CodeSkill.updated_at.desc(), CodeSkill.id.desc())
                    .limit(10)
                )
            ).scalars().all()
        )
        workflow_plan = CodeWorkflowOrchestratorService.plan(
            query=query,
            open_tasks=open_tasks,
            latest_session=latest_session,
            recent_verifications=recent_verifications,
            recent_events=recent_events,
            skills=skills,
        )
        blocks.append(f"## Workflow Orchestrator\n{CodeWorkflowOrchestratorService.format_context(workflow_plan)}")

        related_sessions = await CodeSessionSearchService.search(
            db,
            tenant_id=tenant_id,
            query=query,
            limit=3,
        )
        filtered_sessions = [
            item for item in related_sessions if item["session_id"] != current_session_id
        ][:2]
        if filtered_sessions:
            blocks.append(
                "## Cross-Session Recall\n"
                + "\n".join(
                    f"- Session #{item['session_id']}: {item['headline']} | {item['summary'][:240]}"
                    for item in filtered_sessions
                )
            )

        if not blocks:
            return ""
        return (
            "Durable BOS autonomy context from prior threads and maintenance runs. "
            "Use this as background memory, not as a replacement for the current user request.\n\n"
            + "\n\n".join(blocks)
        )

    @classmethod
    async def run_maintenance(
        cls,
        db,
        *,
        workspace_id: int,
    ) -> dict[str, Any]:
        cls._ensure_directories()
        generated_at = datetime.now(UTC)

        runtime = await db.scalar(
            select(CodeAgentRuntimeState).where(CodeAgentRuntimeState.workspace_id == workspace_id)
        )
        if runtime is None:
            raise ValueError("runtime_state_missing")

        task_rows = await db.execute(
            select(CodeTask)
            .where(CodeTask.workspace_id == workspace_id)
            .order_by(CodeTask.updated_at.desc(), CodeTask.id.desc())
        )
        tasks = list(task_rows.scalars().all())
        open_tasks = [task for task in tasks if task.task_status in {"created", "running", "review_pending", "in_review", "verification_pending", "blocked"}]
        completed_tasks = [task for task in tasks if task.task_status == "completed"]

        latest_session = await db.scalar(
            select(CodeSession)
            .where(CodeSession.workspace_id == workspace_id)
            .order_by(CodeSession.updated_at.desc(), CodeSession.id.desc())
        )
        recent_reflections = list(
            (
                await db.execute(
                    select(CodeReflectionRun)
                    .where(CodeReflectionRun.workspace_id == workspace_id)
                    .order_by(CodeReflectionRun.created_at.desc(), CodeReflectionRun.id.desc())
                    .limit(5)
                )
            ).scalars().all()
        )
        recent_verifications = list(
            (
                await db.execute(
                    select(CodeVerificationRun)
                    .join(CodeSession, CodeVerificationRun.session_id == CodeSession.id)
                    .where(CodeSession.workspace_id == workspace_id)
                    .order_by(CodeVerificationRun.started_at.desc(), CodeVerificationRun.id.desc())
                    .limit(8)
                )
            ).scalars().all()
        )
        recent_events = list(
            (
                await db.execute(
                    select(CodeWorkerEvent)
                    .where(CodeWorkerEvent.workspace_id == workspace_id)
                    .order_by(CodeWorkerEvent.created_at.desc(), CodeWorkerEvent.id.desc())
                    .limit(12)
                )
            ).scalars().all()
        )
        active_skills = list(
            (
                await db.execute(
                    select(CodeSkill)
                    .where(CodeSkill.workspace_id == workspace_id)
                    .order_by(CodeSkill.last_feedback_at.desc(), CodeSkill.updated_at.desc(), CodeSkill.id.desc())
                    .limit(8)
                )
            ).scalars().all()
        )

        project_brain = cls._write_document(
            document_key="project_brain",
            path=cls.RUNTIME_DIR / "project-brain.md",
            updates=cls._build_project_brain_updates(
                open_tasks=open_tasks,
                completed_tasks=completed_tasks,
                runtime=runtime,
                latest_session=latest_session,
            ),
        )
        decision_journal = cls._write_document(
            document_key="decision_journal",
            path=cls.RUNTIME_DIR / "decision-journal.md",
            updates=cls._build_decision_updates(
                generated_at=generated_at,
                open_tasks=open_tasks,
                latest_session=latest_session,
            ),
        )
        evolution_log = cls._write_document(
            document_key="evolution_log",
            path=cls.RUNTIME_DIR / "evolution-log.md",
            updates=cls._build_evolution_updates(
                runtime=runtime,
                recent_reflections=recent_reflections,
                recent_verifications=recent_verifications,
                recent_events=recent_events,
            ),
        )

        for name, text in (
            ("project-brain.md", project_brain),
            ("decision-journal.md", decision_journal),
            ("evolution-log.md", evolution_log),
        ):
            (cls.STAGING_DIR / name).write_text(text, encoding="utf-8")

        workflow_plan = CodeWorkflowOrchestratorService.plan(
            query="maintenance autonomy review",
            open_tasks=open_tasks,
            latest_session=latest_session,
            recent_verifications=recent_verifications,
            recent_events=recent_events,
            skills=active_skills,
        )
        experience_quality = cls._experience_quality(
            project_brain=project_brain,
            decision_journal=decision_journal,
            evolution_log=evolution_log,
            recent_reflections=recent_reflections,
            recent_verifications=recent_verifications,
        )

        report_markdown = cls._build_report_markdown(
            generated_at=generated_at,
            runtime=runtime,
            open_tasks=open_tasks,
            completed_tasks=completed_tasks,
            latest_session=latest_session,
            active_skills=active_skills,
            recent_reflections=recent_reflections,
            recent_verifications=recent_verifications,
        )
        cls.REPORT_MARKDOWN_PATH.write_text(report_markdown, encoding="utf-8")
        report_payload = {
            "generated_at": generated_at.isoformat(),
            "workspace_id": workspace_id,
            "open_task_ids": [task.id for task in open_tasks[:10]],
            "completed_task_ids": [task.id for task in completed_tasks[:10]],
            "latest_session_id": latest_session.id if latest_session is not None else None,
            "latest_session_status": latest_session.session_status if latest_session is not None else None,
            "active_skill_ids": [skill.id for skill in active_skills[:10]],
            "recent_reflection_ids": [reflection.id for reflection in recent_reflections],
            "last_heartbeat_loop_budget": (runtime.runtime_metrics or {}).get("last_heartbeat_loop_budget"),
            "last_heartbeat_convergence_signal": (runtime.runtime_metrics or {}).get("last_heartbeat_convergence_signal"),
            "last_heartbeat_difficulty_signals": (runtime.runtime_metrics or {}).get("last_heartbeat_difficulty_signals") or [],
            "last_reflection_verified_signal": (runtime.runtime_metrics or {}).get("last_reflection_verified_signal"),
            "last_reflection_verification_signals": (runtime.runtime_metrics or {}).get("last_reflection_verification_signals") or [],
        }
        cls.REPORT_JSON_PATH.write_text(json.dumps(report_payload, ensure_ascii=True, indent=2), encoding="utf-8")

        summary = (
            f"Maintenance refreshed project memory and staged autonomy reports. "
            f"Open tasks: {len(open_tasks)}. "
            f"Latest session: #{latest_session.id}." if latest_session is not None else
            f"Maintenance refreshed project memory and staged autonomy reports. Open tasks: {len(open_tasks)}."
        )
        next_autonomy_mode, next_autonomy_objective = cls._build_next_autonomy_objective(
            open_tasks=open_tasks,
            latest_session=latest_session,
            recent_verifications=recent_verifications,
            active_skills=active_skills,
        )
        return {
            "summary": summary,
            "generated_at": generated_at.isoformat(),
            "report_markdown_path": cls._display_path(cls.REPORT_MARKDOWN_PATH),
            "report_json_path": cls._display_path(cls.REPORT_JSON_PATH),
            "project_brain_path": cls._display_path(cls.STAGING_DIR / "project-brain.md"),
            "decision_journal_path": cls._display_path(cls.STAGING_DIR / "decision-journal.md"),
            "evolution_log_path": cls._display_path(cls.STAGING_DIR / "evolution-log.md"),
            "next_autonomy_mode": next_autonomy_mode,
            "next_autonomy_objective": next_autonomy_objective,
            "workflow_mode": workflow_plan.mode,
            "workflow_skills": workflow_plan.recommended_skills,
            "workflow_rationale": workflow_plan.rationale,
            "experience_quality": experience_quality,
            "open_task_count": len(open_tasks),
            "completed_task_count": len(completed_tasks),
        }
