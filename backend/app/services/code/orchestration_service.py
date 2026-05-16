"""
Derived orchestration snapshot for BOS Code task/worker lanes.
"""

from sqlalchemy import select

from app.code import (
    ACTION_ACCEPT_REVIEW,
    ACTION_ARCHITECT_PLAN,
    ACTION_ARCHITECT_ROUTE,
    ACTION_BEGIN_REVIEW,
    ACTION_INSPECT_CONTEXT,
    ACTION_INSPECT_DIFF,
    ACTION_MARK_EXECUTOR_BLOCKED,
    ACTION_MARK_EXECUTOR_READY,
    ACTION_MARK_ARCHITECT_READY,
    ACTION_MARK_REVIEWER_BLOCKED,
    ACTION_MARK_REVIEWER_READY,
    ACTION_PREPARE_MERGE,
    ACTION_REFRESH_BRANCH,
    ACTION_RESET_SESSION_READY,
    ACTION_REJECT_REVIEW,
    ACTION_REQUEST_REVIEW,
    ACTION_REVIEW_DIFF,
    ACTION_RUN_VERIFICATION,
    OPERATOR_POSTURE_BLOCKED,
    OPERATOR_POSTURE_COMPLETED,
    OPERATOR_POSTURE_DEGRADED,
    OPERATOR_POSTURE_EXECUTION_ACTIVE,
    OPERATOR_POSTURE_IDLE,
    OPERATOR_POSTURE_MERGE_READY,
    OPERATOR_POSTURE_PENDING,
    OPERATOR_POSTURE_PLANNING_REQUIRED,
    OPERATOR_POSTURE_RECOVERY_REQUIRED,
    OPERATOR_POSTURE_REVIEW_ACTIVE,
    OPERATOR_POSTURE_REVIEW_QUEUE,
    OPERATOR_POSTURE_VERIFICATION_GATE,
    control_action_policy,
)
from app.models import CodeAgentRuntimeState, CodeBranchState, CodeSession, CodeWorkspace
from app.services.code.branch_service import CodeBranchService
from app.schemas import (
    CodeOrchestrationLaneResponse,
    CodeOrchestrationSnapshotResponse,
    CodeOrchestrationTotalsResponse,
)
from app.services.code.task_service import CodeTaskService
from app.services.code.worker_event_service import CodeWorkerEventService


class CodeOrchestrationService:
    LANE_ORDER = ("tasking", "architect", "executor", "reviewer")
    TASK_PRIORITY = ("in_review", "review_pending", "verification_pending", "running", "created", "blocked", "completed", "failed")

    @classmethod
    def _order_lane(cls, lane: str) -> tuple[int, str]:
        try:
            return (cls.LANE_ORDER.index(lane), lane)
        except ValueError:
            return (len(cls.LANE_ORDER), lane)

    @classmethod
    def _task_priority(cls, task) -> tuple[int, int]:
        try:
            index = cls.TASK_PRIORITY.index(task.task_status)
        except ValueError:
            index = len(cls.TASK_PRIORITY)
        return (index, -int(task.id))

    @classmethod
    def _pick_focus_task(cls, tasks):
        if not tasks:
            return None
        ordered = sorted(tasks, key=cls._task_priority)
        focus_task = ordered[0]

        task_packet = getattr(focus_task, "task_packet", None) or {}
        source_task_id = task_packet.get("source_task_id") if isinstance(task_packet, dict) else None
        if (getattr(focus_task, "scope", None) or "").lower() == "code/recovery" and source_task_id is not None:
            source_task = next((task for task in tasks if task.id == source_task_id), None)
            if source_task is not None:
                return source_task

        return focus_task

    @classmethod
    def _pick_focus_lane(cls, lanes, focus_task):
        if focus_task is None:
            return None

        matching = [lane for lane in lanes if lane.task_id == focus_task.id]
        if not matching:
            return None

        preferred_lane = {
            "created": "architect",
            "running": "executor",
            "review_pending": "reviewer",
            "in_review": "reviewer",
            "verification_pending": "tasking",
            "blocked": "tasking",
            "completed": "tasking",
            "failed": "tasking",
        }.get(focus_task.task_status, "tasking")

        for lane in matching:
            if lane.lane == preferred_lane:
                return lane

        for lane_name in ("reviewer", "executor", "architect", "tasking"):
            for lane in matching:
                if lane.lane == lane_name:
                    return lane

        return matching[0]

    @staticmethod
    def _to_tone(status: str | None) -> str:
        match status:
            case "ready" | "completed":
                return "success"
            case "merge_ready":
                return "success"
            case "in_review" | "review_pending" | "waiting_review":
                return "info"
            case "running" | "assigned" | "blocked" | "pending" | "needs_recovery":
                return "warning"
            case "failed":
                return "danger"
            case "created":
                return "brand"
            case _:
                return "neutral"

    @staticmethod
    def _is_blocked(status: str | None) -> bool:
        return status in {"failed", "blocked"}

    @staticmethod
    def _build_headline(
        *,
        lane: str,
        latest_event_name: str | None,
        latest_summary: str | None,
        task_title: str | None,
        worker_status: str | None,
        task_status: str | None,
    ) -> str:
        if lane == "tasking":
            match task_status:
                case "created":
                    return "Task created and waiting for architect planning."
                case "running":
                    return "Execution is in motion."
                case "review_pending":
                    return "Review requested and waiting for reviewer pickup."
                case "in_review":
                    return "Reviewer is actively evaluating the implementation."
                case "verification_pending":
                    return "Review accepted; verification is now the only remaining gate."
                case "completed":
                    return "Task completed after verification cleared."
                case "blocked":
                    return "Task is blocked and needs operator attention."
                case "failed":
                    return "Task failed and needs intervention."
                case _:
                    pass

        if lane == "architect":
            match worker_status:
                case "running":
                    return "Architect is drafting the route and acceptance bar."
                case "ready":
                    return "Architect lane is ready for the next planning request."
                case "completed":
                    return "Architect finished planning this slice."
                case _:
                    pass

        if lane == "executor":
            match worker_status:
                case "running":
                    return "Executor is implementing the approved scope."
                case "waiting_review":
                    return "Executor handed off work and is waiting for reviewer pickup."
                case "ready":
                    return "Executor lane is ready for the next implementation slice."
                case "blocked":
                    return "Executor is blocked and waiting for follow-up."
                case _:
                    pass

        if lane == "reviewer":
            if latest_event_name == "review.requested":
                return "Review requested and waiting for reviewer pickup."
            if latest_event_name == "review.accepted":
                return "Reviewer accepted the handoff; verification is next."
            if latest_event_name == "review.rejected":
                return "Reviewer asked for changes before verification."
            match worker_status:
                case "assigned":
                    return "Review is queued and waiting for reviewer pickup."
                case "running":
                    return "Reviewer is actively evaluating the implementation."
                case "completed":
                    return "Reviewer decision is complete."
                case "ready":
                    return "Reviewer lane is ready for the next handoff."
                case _:
                    pass

        if latest_summary and latest_event_name not in {"lane.started", "lane.progressed", "lane.completed"}:
            return latest_summary
        if task_title and worker_status:
            return f"{task_title} / {worker_status}"
        if task_title and task_status:
            return f"{task_title} / {task_status}"
        if latest_event_name:
            return latest_event_name.replace(".", " ")
        return f"{lane} lane awaiting activity"

    @staticmethod
    def _summarize_merge_posture(
        *,
        merge_readiness: str,
        verification_gate: str,
        merge_blockers: list[str],
        tasks,
        branch_state: CodeBranchState | None,
    ) -> tuple[str, str | None, list[str]]:
        open_tasks = [task for task in tasks if task.task_status in {"created", "running", "in_review", "verification_pending"}]
        blocked_tasks = [task for task in tasks if task.task_status == "blocked"]
        evidence = [
            f"Verification gate: {verification_gate}",
            f"Open tasks: {len(open_tasks)}",
            f"Blocked tasks: {len(blocked_tasks)}",
        ]
        if branch_state is not None:
            evidence.append(f"Branch posture: {branch_state.branch_status}")
        if merge_blockers:
            evidence.append(f"Blockers: {', '.join(merge_blockers)}")

        if merge_readiness == "merge_ready":
            return (
                "Merge is ready. Verification passed and there are no remaining merge blockers.",
                "Proceed to the next release or merge step.",
                evidence,
            )

        if merge_readiness == "blocked":
            if "verification_failed" in merge_blockers:
                return (
                    "Merge is blocked because the verification gate failed.",
                    "Inspect the failing verification stage and rerun the pipeline after fixes land.",
                    evidence,
                )
            return (
                "Merge is blocked by an unresolved execution issue.",
                "Clear the blocking task or failure state before attempting release.",
                evidence,
            )

        if merge_readiness == "needs_recovery":
            if "git_runtime_unavailable" in merge_blockers:
                return (
                    "Merge needs recovery because Git runtime evidence is unavailable.",
                    "Restore Git visibility, then refresh branch posture and readiness.",
                    evidence,
                )
            if "stale_branch" in merge_blockers:
                return (
                    "Merge needs recovery because the session branch is stale against its base.",
                    "Refresh the branch state and bring the branch up to date before trusting verification.",
                    evidence,
                )
            if "dirty_workspace" in merge_blockers:
                return (
                    "Merge needs recovery because the workspace is dirty.",
                    "Review local changes, stabilize the workspace, and refresh branch posture.",
                    evidence,
                )
            return (
                "Merge needs recovery before the release signal can be trusted.",
                "Resolve the recovery blockers, then rerun readiness.",
                evidence,
            )

        if merge_readiness == "pending":
            if "verification_pending" in merge_blockers:
                return (
                    "Merge is pending because verification has not cleared yet.",
                    "Run or finish the verification pipeline before treating the task as done.",
                    evidence,
                )
            if "tasks_not_complete" in merge_blockers:
                return (
                    "Merge is pending because work is still in flight.",
                    "Finish the active task flow through review and verification.",
                    evidence,
                )
            return (
                "Merge is pending while orchestration catches up to the latest task state.",
                "Refresh orchestration after the next task or verification transition.",
                evidence,
            )

        return (
            f"Merge posture is {merge_readiness}.",
            "Inspect orchestration state for the next concrete move.",
            evidence,
        )

    @staticmethod
    def _build_action_policies(actions: list[str]) -> dict[str, str]:
        return {action: control_action_policy(action) for action in actions}

    @staticmethod
    def _format_action_label(action: str | None) -> str | None:
        return action.replace("_", " ") if action else None

    @staticmethod
    def _partition_actions(action_policies: dict[str, str]) -> tuple[list[str], list[str], list[str], str | None, str | None]:
        automation_actions = [action for action, policy in action_policies.items() if policy == "automation_safe"]
        review_gated_actions = [action for action, policy in action_policies.items() if policy == "review_gated"]
        human_actions = [action for action, policy in action_policies.items() if policy == "human_only"]
        next_automation_action = automation_actions[0] if automation_actions else None
        next_human_action = (review_gated_actions + human_actions)[0] if (review_gated_actions or human_actions) else None
        return automation_actions, human_actions, review_gated_actions, next_automation_action, next_human_action

    @classmethod
    def _build_automation_gate(
        cls,
        *,
        automation_actions: list[str],
        human_actions: list[str],
        review_gated_actions: list[str],
        next_automation_action: str | None,
    ) -> tuple[bool, list[str], str]:
        if not automation_actions or next_automation_action is None:
            return (
                False,
                ["no_automation_safe_action"],
                "No automation-safe action is available right now.",
            )

        if review_gated_actions:
            return (
                False,
                ["review_gate_present"],
                f"Automation is paused because a review-gated action must be resolved before {cls._format_action_label(next_automation_action)} can run safely.",
            )

        if human_actions:
            return (
                False,
                ["human_gate_present"],
                f"Automation is paused because a human-only action must be resolved before {cls._format_action_label(next_automation_action)} can run safely.",
            )

        return (
            True,
            [],
            f"Automation can safely execute {cls._format_action_label(next_automation_action)} next.",
        )

    @staticmethod
    def _build_operator_control_plane(
        *,
        merge_readiness: str,
        merge_blockers: list[str],
        verification_gate: str,
        focus_task,
        session_status: str | None,
        recovery_failure_class: str | None,
        recovery_next_safe_action: str | None,
    ) -> tuple[str, list[str], dict[str, str]]:
        actions: list[str] = []
        posture = OPERATOR_POSTURE_IDLE

        task_status = focus_task.task_status if focus_task is not None else None

        if task_status == "created":
            posture = OPERATOR_POSTURE_PLANNING_REQUIRED
            actions.extend([ACTION_ARCHITECT_PLAN, ACTION_ARCHITECT_ROUTE])
        elif task_status == "running":
            posture = OPERATOR_POSTURE_EXECUTION_ACTIVE
            actions.extend([ACTION_REQUEST_REVIEW, ACTION_MARK_EXECUTOR_BLOCKED])
        elif task_status == "review_pending":
            posture = OPERATOR_POSTURE_REVIEW_QUEUE
            actions.extend([ACTION_BEGIN_REVIEW, ACTION_MARK_REVIEWER_BLOCKED])
        elif task_status == "in_review":
            posture = OPERATOR_POSTURE_REVIEW_ACTIVE
            actions.extend([ACTION_ACCEPT_REVIEW, ACTION_REJECT_REVIEW, ACTION_MARK_REVIEWER_READY])
        elif task_status == "verification_pending":
            posture = OPERATOR_POSTURE_VERIFICATION_GATE
            actions.extend([ACTION_RUN_VERIFICATION, ACTION_REFRESH_BRANCH])
        elif task_status == "blocked":
            posture = OPERATOR_POSTURE_BLOCKED
            actions.extend([ACTION_MARK_EXECUTOR_READY, ACTION_REFRESH_BRANCH])
        elif task_status == "completed":
            posture = OPERATOR_POSTURE_COMPLETED

        if "dirty_workspace" in merge_blockers:
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
            actions.extend([ACTION_INSPECT_DIFF, ACTION_REFRESH_BRANCH])
        if "stale_branch" in merge_blockers:
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
            actions.extend([ACTION_REFRESH_BRANCH])
        if "verification_failed" in merge_blockers:
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
            actions.extend([ACTION_RUN_VERIFICATION, ACTION_INSPECT_DIFF])
        if "git_runtime_unavailable" in merge_blockers:
            posture = OPERATOR_POSTURE_DEGRADED
            actions.extend([ACTION_REFRESH_BRANCH])

        if session_status == "blocked" and recovery_next_safe_action == ACTION_RESET_SESSION_READY:
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
            actions.insert(0, ACTION_RESET_SESSION_READY)
        elif session_status == "blocked" and recovery_failure_class == "prompt_delivery":
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
            actions.insert(0, ACTION_RESET_SESSION_READY)
        elif session_status == "trust_required":
            posture = OPERATOR_POSTURE_BLOCKED
            actions.insert(0, ACTION_INSPECT_CONTEXT)

        if merge_readiness == "merge_ready":
            posture = OPERATOR_POSTURE_MERGE_READY
            actions = [ACTION_REVIEW_DIFF, ACTION_PREPARE_MERGE]
        elif merge_readiness == "blocked" and posture == OPERATOR_POSTURE_IDLE:
            posture = OPERATOR_POSTURE_BLOCKED
        elif merge_readiness == "needs_recovery" and posture == OPERATOR_POSTURE_IDLE:
            posture = OPERATOR_POSTURE_RECOVERY_REQUIRED
        elif merge_readiness == "pending" and posture == OPERATOR_POSTURE_IDLE:
            posture = OPERATOR_POSTURE_PENDING

        if not actions and verification_gate == "pending":
            actions.append(ACTION_RUN_VERIFICATION)
        if not actions:
            actions.append(ACTION_INSPECT_CONTEXT)

        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)

        return posture, deduped, CodeOrchestrationService._build_action_policies(deduped)

    @staticmethod
    def _build_lane_control_plane(
        *,
        lane: str,
        worker_status: str | None,
        task_status: str | None,
        blocked: bool,
    ) -> tuple[list[str], dict[str, str], str | None, str | None]:
        actions: list[str] = []
        primary_action: str | None = None

        if lane == "architect":
            if task_status == "created":
                actions.extend([ACTION_ARCHITECT_PLAN, ACTION_ARCHITECT_ROUTE])
                primary_action = ACTION_ARCHITECT_PLAN
            if blocked:
                actions.append(ACTION_MARK_ARCHITECT_READY)

        elif lane == "executor":
            if task_status == "running":
                actions.extend([ACTION_REQUEST_REVIEW, ACTION_MARK_EXECUTOR_BLOCKED])
                primary_action = ACTION_REQUEST_REVIEW
            elif blocked:
                actions.append(ACTION_MARK_EXECUTOR_READY)
                primary_action = ACTION_MARK_EXECUTOR_READY
            elif worker_status == "ready" and task_status == "verification_pending":
                actions.append(ACTION_INSPECT_CONTEXT)

        elif lane == "reviewer":
            if task_status == "review_pending":
                actions.extend([ACTION_BEGIN_REVIEW, ACTION_MARK_REVIEWER_BLOCKED])
                primary_action = ACTION_BEGIN_REVIEW
            elif task_status == "in_review":
                actions.extend([ACTION_ACCEPT_REVIEW, ACTION_REJECT_REVIEW, ACTION_MARK_REVIEWER_READY])
                primary_action = ACTION_ACCEPT_REVIEW
            elif blocked:
                actions.append(ACTION_MARK_REVIEWER_READY)
                primary_action = ACTION_MARK_REVIEWER_READY

        elif lane == "tasking":
            if task_status == "verification_pending":
                actions.extend([ACTION_RUN_VERIFICATION, ACTION_REFRESH_BRANCH])
                primary_action = ACTION_RUN_VERIFICATION
            elif blocked:
                actions.extend([ACTION_INSPECT_DIFF, ACTION_REFRESH_BRANCH])
                primary_action = ACTION_INSPECT_DIFF

        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)

        if primary_action is None and deduped:
            primary_action = deduped[0]
        action_policies = CodeOrchestrationService._build_action_policies(deduped)
        primary_action_policy = control_action_policy(primary_action) if primary_action else None
        return deduped, action_policies, primary_action, primary_action_policy

    @classmethod
    async def build_snapshot(cls, db, *, workspace_id: int) -> CodeOrchestrationSnapshotResponse:
        workspace_result = await db.execute(
            select(CodeWorkspace).where(CodeWorkspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        if workspace is None:
            raise ValueError("workspace_not_found")

        runtime_result = await db.execute(
            select(CodeAgentRuntimeState).where(CodeAgentRuntimeState.workspace_id == workspace_id)
        )
        runtime = runtime_result.scalar_one_or_none()

        await CodeTaskService.ensure_default_workers(db, workspace=workspace)
        tasks = await CodeTaskService.list_tasks(db, workspace_id=workspace_id)
        workers = await CodeTaskService.list_workers(db, workspace_id=workspace_id)
        worker_events = await CodeWorkerEventService.list_events(
            db,
            workspace_id=workspace_id,
            limit=500,
        )

        task_by_id = {task.id: task for task in tasks}
        worker_by_id = {worker.id: worker for worker in workers}
        focus_task = cls._pick_focus_task(tasks)
        lane_names = {"tasking", *(worker.worker_name for worker in workers), *(event.lane for event in worker_events)}

        lanes: list[CodeOrchestrationLaneResponse] = []
        for lane_name in sorted(lane_names, key=cls._order_lane):
            lane_events = sorted(
                [event for event in worker_events if event.lane == lane_name],
                key=lambda event: event.id,
                reverse=True,
            )
            latest_event = lane_events[0] if lane_events else None

            worker = next((item for item in workers if item.worker_name == lane_name), None)
            if worker is None and latest_event and latest_event.worker_id is not None:
                worker = worker_by_id.get(latest_event.worker_id)

            task = None
            if worker and worker.task_id is not None:
                task = task_by_id.get(worker.task_id)
            if task is None and latest_event and latest_event.task_id is not None:
                task = task_by_id.get(latest_event.task_id)
            if task is None and lane_name == "tasking":
                task = focus_task

            latest_status = (
                latest_event.status if latest_event else worker.worker_status if worker else task.task_status if task else None
            )
            blocked = (
                cls._is_blocked(latest_status)
                or cls._is_blocked(worker.worker_status if worker else None)
                or cls._is_blocked(task.task_status if task else None)
            )
            lane_actions, lane_action_policies, primary_action, primary_action_policy = cls._build_lane_control_plane(
                lane=lane_name,
                worker_status=worker.worker_status if worker else None,
                task_status=task.task_status if task else None,
                blocked=blocked,
            )
            lane_automation_actions, lane_human_actions, lane_review_gated_actions, lane_next_automation_action, _lane_next_human_action = cls._partition_actions(
                lane_action_policies
            )
            lane_automation_ready, lane_automation_blockers, lane_automation_summary = cls._build_automation_gate(
                automation_actions=lane_automation_actions,
                human_actions=lane_human_actions,
                review_gated_actions=lane_review_gated_actions,
                next_automation_action=lane_next_automation_action,
            )

            lanes.append(
                CodeOrchestrationLaneResponse(
                    lane=lane_name,
                    worker_name=worker.worker_name if worker else None,
                    worker_role=worker.worker_role if worker else None,
                    worker_status=worker.worker_status if worker else None,
                    task_id=task.id if task else latest_event.task_id if latest_event else None,
                    task_title=task.title if task else None,
                    task_status=task.task_status if task else None,
                    latest_event_id=latest_event.id if latest_event else None,
                    latest_event_name=latest_event.event_name if latest_event else None,
                    latest_status=latest_status,
                    latest_summary=latest_event.summary if latest_event else None,
                    latest_event_at=latest_event.created_at if latest_event else None,
                    event_count=len(lane_events),
                    blocked=blocked,
                    tone="danger" if blocked else cls._to_tone(latest_status),
                    headline=cls._build_headline(
                        lane=lane_name,
                        latest_event_name=latest_event.event_name if latest_event else None,
                        latest_summary=latest_event.summary if latest_event else None,
                        task_title=task.title if task else None,
                        worker_status=worker.worker_status if worker else None,
                        task_status=task.task_status if task else None,
                    ),
                    lane_actions=lane_actions,
                    lane_action_policies=lane_action_policies,
                    automation_actions=lane_automation_actions,
                    human_actions=lane_human_actions,
                    review_gated_actions=lane_review_gated_actions,
                    automation_ready=lane_automation_ready,
                    automation_blockers=lane_automation_blockers,
                    automation_summary=lane_automation_summary,
                    next_automation_action=lane_next_automation_action,
                    primary_action=primary_action,
                    primary_action_policy=primary_action_policy,
                )
            )

        latest_event_time = lane_event_time = None
        if worker_events:
            lane_event_time = max(
                (event.created_at for event in worker_events if event.created_at is not None),
                default=None,
            )
        latest_event_time = lane_event_time

        session_result = await db.execute(
            select(CodeSession)
            .where(CodeSession.workspace_id == workspace_id)
            .order_by(CodeSession.created_at.desc())
        )
        session = session_result.scalars().first()
        verification_gate = session.verification_status if session else "not_required"
        recovery = None
        if session is not None:
            from app.services.code.recovery_service import CodeRecoveryService

            recovery = await CodeRecoveryService.suggest_recovery_actions(db, session=session)

        merge_blockers: list[str] = []
        if any(task.task_status in {"created", "running", "in_review", "verification_pending"} for task in tasks):
            merge_blockers.append("tasks_not_complete")
        if verification_gate == "failed":
            merge_blockers.append("verification_failed")
        elif verification_gate in {"pending", "running"} and any(task.task_status == "verification_pending" for task in tasks):
            merge_blockers.append("verification_pending")

        merge_readiness = "idle"
        branch_state = None
        if session is not None:
            branch_result = await db.execute(
                select(CodeBranchState)
                .where(
                    CodeBranchState.workspace_id == workspace_id,
                    CodeBranchState.branch_name == session.session_branch,
                )
                .order_by(CodeBranchState.updated_at.desc())
            )
            branch_state = branch_result.scalars().first()
            if branch_state is not None:
                branch_readiness = CodeBranchService.summarize_branch_readiness(branch_state)
                merge_blockers.extend(branch_readiness.blocking_reasons)
                merge_readiness = branch_readiness.readiness
            else:
                merge_readiness = "pending"

        if merge_blockers:
            if "verification_failed" in merge_blockers:
                merge_readiness = "blocked"
            elif any(blocker in {"dirty_workspace", "stale_branch", "git_runtime_unavailable"} for blocker in merge_blockers):
                merge_readiness = "needs_recovery"
            else:
                merge_readiness = "pending"
        elif session is not None and verification_gate == "passed":
            merge_readiness = "merge_ready"

        merge_summary, merge_next_action, merge_evidence = cls._summarize_merge_posture(
            merge_readiness=merge_readiness,
            verification_gate=verification_gate,
            merge_blockers=sorted(set(merge_blockers)),
            tasks=tasks,
            branch_state=branch_state,
        )
        operator_posture, operator_actions, operator_action_policies = cls._build_operator_control_plane(
            merge_readiness=merge_readiness,
            merge_blockers=sorted(set(merge_blockers)),
            verification_gate=verification_gate,
            focus_task=focus_task,
            session_status=session.session_status if session else None,
            recovery_failure_class=recovery.failure_class if recovery else None,
            recovery_next_safe_action=recovery.next_safe_action if recovery else None,
        )
        automation_actions, human_actions, review_gated_actions, next_automation_action, next_human_action = cls._partition_actions(
            operator_action_policies
        )
        automation_ready, automation_blockers, automation_summary = cls._build_automation_gate(
            automation_actions=automation_actions,
            human_actions=human_actions,
            review_gated_actions=review_gated_actions,
            next_automation_action=next_automation_action,
        )
        focus_lane = cls._pick_focus_lane(lanes, focus_task)
        focus_task_headline = (
            focus_lane.headline
            if focus_lane is not None
            else cls._build_headline(
                lane="tasking",
                latest_event_name=None,
                latest_summary=None,
                task_title=focus_task.title if focus_task is not None else None,
                worker_status=None,
                task_status=focus_task.task_status if focus_task is not None else None,
            )
            if focus_task is not None
            else None
        )

        return CodeOrchestrationSnapshotResponse(
            workspace_id=workspace_id,
            latest_event_time=latest_event_time,
            verification_gate=verification_gate,
            merge_readiness=merge_readiness,
            operator_posture=operator_posture,
            operator_actions=operator_actions,
            operator_action_policies=operator_action_policies,
            automation_actions=automation_actions,
            human_actions=human_actions,
            review_gated_actions=review_gated_actions,
            automation_ready=automation_ready,
            automation_blockers=automation_blockers,
            automation_summary=automation_summary,
            next_automation_action=next_automation_action,
            next_human_action=next_human_action,
            operator_action_classes=operator_action_policies,
            merge_blockers=sorted(set(merge_blockers)),
            merge_summary=merge_summary,
            merge_next_action=merge_next_action,
            merge_evidence=merge_evidence,
            heartbeat_status=(runtime.last_heartbeat_decision if runtime and runtime.last_heartbeat_decision else "idle"),
            heartbeat_summary=(
                f"Last heartbeat at {runtime.last_heartbeat_at.isoformat()}"
                if runtime and runtime.last_heartbeat_at
                else None
            ),
            reflection_posture=(
                "active"
                if runtime and runtime.last_reflection_at and runtime.reflections_enabled
                else "idle"
            ),
            focus_task_id=focus_task.id if focus_task is not None else None,
            focus_task_title=focus_task.title if focus_task is not None else None,
            focus_task_status=focus_task.task_status if focus_task is not None else None,
            focus_task_headline=focus_task_headline,
            totals=CodeOrchestrationTotalsResponse(
                tasks=len(tasks),
                workers=len(workers),
                running_tasks=sum(1 for task in tasks if task.task_status == "running"),
                blocked_tasks=sum(1 for task in tasks if task.task_status == "blocked"),
                completed_tasks=sum(1 for task in tasks if task.task_status == "completed"),
                active_lanes=sum(1 for lane in lanes if lane.latest_status == "running"),
                blocked_lanes=sum(1 for lane in lanes if lane.blocked),
            ),
            lanes=lanes,
        )
