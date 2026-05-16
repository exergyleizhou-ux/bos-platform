"""
Worker/lane event persistence for BOS Code v3 orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models import CodeWorkerEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeWorkerEventService:
    CONTRACT_VERSION = 1
    FAILURE_CLASS_BRANCH_DIVERGENCE = "branch_divergence"
    FAILURE_CLASS_INFRA = "infra"
    FAILURE_CLASS_MCP_HANDSHAKE = "mcp_handshake"
    FAILURE_CLASS_MCP_STARTUP = "mcp_startup"
    FAILURE_CLASS_PLUGIN_STARTUP = "plugin_startup"
    FAILURE_CLASS_PROMPT_DELIVERY = "prompt_delivery"
    FAILURE_CLASS_TEST = "test"
    FAILURE_CLASS_TOOL_RUNTIME = "tool_runtime"
    FAILURE_CLASS_TRUST_GATE = "trust_gate"

    @classmethod
    async def append_event(
        cls,
        db: AsyncSession,
        *,
        workspace_id: int,
        lane: str,
        event_name: str,
        status: str,
        summary: str | None = None,
        payload: dict | None = None,
        task_id: int | None = None,
        worker_id: int | None = None,
    ) -> CodeWorkerEvent:
        event = CodeWorkerEvent(
            workspace_id=workspace_id,
            task_id=task_id,
            worker_id=worker_id,
            lane=lane,
            event_name=event_name,
            status=status,
            summary=summary,
            payload=cls._normalize_payload(
                lane=lane,
                event_name=event_name,
                status=status,
                summary=summary,
                payload=payload,
            ),
        )
        db.add(event)
        await db.flush()
        return event

    @classmethod
    def _normalize_payload(
        cls,
        *,
        lane: str,
        event_name: str,
        status: str,
        summary: str | None,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = dict(payload or {})
        failure_class = cls._coerce_str(normalized.get("failure_class")) or cls._infer_failure_class(
            lane=lane,
            event_name=event_name,
            status=status,
            summary=summary,
            payload=normalized,
        )
        phase = cls._coerce_str(normalized.get("phase")) or cls._infer_phase(
            lane=lane,
            event_name=event_name,
            payload=normalized,
        )
        severity = cls._coerce_str(normalized.get("severity")) or cls._infer_severity(
            status=status,
            event_name=event_name,
            failure_class=failure_class,
        )
        headline = cls._coerce_str(normalized.get("headline")) or summary or cls._humanize_event_name(event_name)
        recommended_actions = cls._normalize_actions(
            normalized.get("recommended_actions"),
            normalized.get("recommended_action"),
        )
        if not recommended_actions:
            recommended_actions = cls._infer_recommended_actions(
                lane=lane,
                event_name=event_name,
                status=status,
                failure_class=failure_class,
            )
        recommended_action = cls._coerce_str(normalized.get("recommended_action")) or (
            recommended_actions[0] if recommended_actions else None
        )
        degraded_scope = cls._coerce_str(normalized.get("degraded_scope")) or cls._infer_degraded_scope(
            lane=lane,
            failure_class=failure_class,
            status=status,
        )
        blocking = normalized.get("blocking")
        if blocking is None:
            blocking = status in {"blocked", "failed"} or event_name.endswith(".failed")

        normalized["event_data_version"] = normalized.get("event_data_version", cls.CONTRACT_VERSION)
        normalized["phase"] = phase
        normalized["severity"] = severity
        normalized["headline"] = headline
        normalized["recommended_actions"] = recommended_actions
        normalized["recommended_action"] = recommended_action
        normalized["blocking"] = bool(blocking)
        if failure_class:
            normalized["failure_class"] = failure_class
        if degraded_scope:
            normalized["degraded_scope"] = degraded_scope
        return normalized

    @staticmethod
    def _coerce_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @classmethod
    def _normalize_actions(cls, actions: Any, single_action: Any) -> list[str]:
        normalized: list[str] = []
        if isinstance(actions, list):
            normalized.extend(
                item.strip() for item in actions if isinstance(item, str) and item.strip()
            )
        single = cls._coerce_str(single_action)
        if single and single not in normalized:
            normalized.insert(0, single)
        return normalized

    @classmethod
    def _infer_failure_class(
        cls,
        *,
        lane: str,
        event_name: str,
        status: str,
        summary: str | None,
        payload: dict[str, Any],
    ) -> str | None:
        text = " ".join(
            part.lower()
            for part in (event_name, status, summary or "", str(payload.get("reason") or ""))
            if part
        )
        if "stale" in text or "behind" in text or "branch" in text and "merge" in text:
            return cls.FAILURE_CLASS_BRANCH_DIVERGENCE
        if "verification" in text or payload.get("verification_status") == "failed":
            return cls.FAILURE_CLASS_TEST
        if "mcp" in text and "handshake" in text:
            return cls.FAILURE_CLASS_MCP_HANDSHAKE
        if "mcp" in text:
            return cls.FAILURE_CLASS_MCP_STARTUP
        if "plugin" in text:
            return cls.FAILURE_CLASS_PLUGIN_STARTUP
        if "trust" in text:
            return cls.FAILURE_CLASS_TRUST_GATE
        if "prompt" in text and "deliver" in text:
            return cls.FAILURE_CLASS_PROMPT_DELIVERY
        if status in {"blocked", "failed"} and lane in {"executor", "reviewer", "architect"}:
            return cls.FAILURE_CLASS_TOOL_RUNTIME
        if "automation" in text and status == "failed":
            return cls.FAILURE_CLASS_INFRA
        return None

    @staticmethod
    def _infer_phase(*, lane: str, event_name: str, payload: dict[str, Any]) -> str:
        payload_phase = payload.get("phase")
        if isinstance(payload_phase, str) and payload_phase.strip():
            return payload_phase.strip()
        if "verification" in event_name:
            return "verification"
        if "review" in event_name or lane == "reviewer":
            return "review"
        if lane == "architect":
            return "planning"
        if lane == "executor":
            return "execution"
        if lane == "tasking":
            return "tasking"
        if "automation" in event_name:
            return "automation"
        return "runtime"

    @staticmethod
    def _infer_severity(*, status: str, event_name: str, failure_class: str | None) -> str:
        if status in {"failed"} or event_name.endswith(".failed"):
            return "error"
        if status in {"blocked", "degraded"} or failure_class is not None:
            return "warning"
        if status in {"completed", "ready"} or event_name.endswith(".completed") or event_name.endswith(".accepted"):
            return "success"
        return "info"

    @classmethod
    def _infer_recommended_actions(
        cls,
        *,
        lane: str,
        event_name: str,
        status: str,
        failure_class: str | None,
    ) -> list[str]:
        if failure_class == cls.FAILURE_CLASS_BRANCH_DIVERGENCE:
            return [
                "Refresh the branch posture before trusting broad verification output.",
                "Merge forward from the base branch, then rerun readiness and verification.",
            ]
        if failure_class in {cls.FAILURE_CLASS_MCP_STARTUP, cls.FAILURE_CLASS_MCP_HANDSHAKE}:
            return [
                "Inspect the MCP server error details and reconnect the affected server.",
                "Treat unaffected servers as usable, but keep degraded mode visible.",
            ]
        if failure_class == cls.FAILURE_CLASS_TEST:
            return [
                "Inspect the failing verification evidence before resuming execution.",
                "Route corrective work back through executor, then rerun review and verification.",
            ]
        if failure_class in {cls.FAILURE_CLASS_TOOL_RUNTIME, cls.FAILURE_CLASS_INFRA}:
            return [
                "Inspect the latest lane evidence and last tool output before retrying.",
                "Keep the lane visible until the blocker is cleared or rerouted.",
            ]
        if status in {"blocked", "failed"}:
            return [
                f"Inspect the latest {lane} lane evidence before continuing.",
                "Avoid assuming the task can progress until the blocker is cleared.",
            ]
        if event_name.endswith(".accepted"):
            return ["Run or confirm the next verification gate before treating the task as complete."]
        return []

    @staticmethod
    def _infer_degraded_scope(*, lane: str, failure_class: str | None, status: str) -> str | None:
        if failure_class in {"mcp_startup", "mcp_handshake"}:
            return "mcp_server"
        if failure_class == "branch_divergence":
            return "branch_posture"
        if status in {"blocked", "failed"} and lane in {"architect", "executor", "reviewer"}:
            return f"{lane}_lane"
        return None

    @staticmethod
    def _humanize_event_name(event_name: str) -> str:
        return event_name.replace(".", " ").replace("_", " ").strip().title()

    @staticmethod
    async def list_events(
        db: AsyncSession,
        *,
        workspace_id: int,
        after_id: int | None = None,
        lane: str | None = None,
        task_id: int | None = None,
        worker_id: int | None = None,
        limit: int = 50,
    ) -> list[CodeWorkerEvent]:
        stmt = select(CodeWorkerEvent).where(CodeWorkerEvent.workspace_id == workspace_id)
        if after_id is not None:
            stmt = stmt.where(CodeWorkerEvent.id > after_id)
        if lane is not None:
            stmt = stmt.where(CodeWorkerEvent.lane == lane)
        if task_id is not None:
            stmt = stmt.where(CodeWorkerEvent.task_id == task_id)
        if worker_id is not None:
            stmt = stmt.where(CodeWorkerEvent.worker_id == worker_id)

        if after_id is not None:
            result = await db.execute(stmt.order_by(CodeWorkerEvent.id.asc()).limit(limit))
            return list(result.scalars().all())

        result = await db.execute(stmt.order_by(CodeWorkerEvent.id.desc()).limit(limit))
        return list(reversed(result.scalars().all()))

    @staticmethod
    async def get_latest_event_id(db: AsyncSession, *, workspace_id: int) -> int | None:
        result = await db.execute(
            select(CodeWorkerEvent.id)
            .where(CodeWorkerEvent.workspace_id == workspace_id)
            .order_by(CodeWorkerEvent.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
