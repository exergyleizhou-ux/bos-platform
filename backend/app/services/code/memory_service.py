"""
BOS Code memory snapshots, compaction, and prompt context helpers.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import CodeAgentRuntimeState, CodeMemorySnapshot, CodeSession, CodeToolCall, CodeTurn
from app.services.code.runtime_service import CodeRuntimeService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeMemoryService:
    MIN_TURNS_BEFORE_COMPACTION = 4
    KEEP_RECENT_TURNS = 2

    @staticmethod
    async def list_snapshots(db: AsyncSession, *, session_id: int) -> list[CodeMemorySnapshot]:
        result = await db.execute(
            select(CodeMemorySnapshot)
            .where(CodeMemorySnapshot.session_id == session_id)
            .order_by(CodeMemorySnapshot.created_at.desc(), CodeMemorySnapshot.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_latest_snapshot(db: AsyncSession, *, session_id: int) -> CodeMemorySnapshot | None:
        result = await db.execute(
            select(CodeMemorySnapshot)
            .where(CodeMemorySnapshot.session_id == session_id)
            .order_by(CodeMemorySnapshot.created_at.desc(), CodeMemorySnapshot.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _safe_boundary(turns: list[CodeTurn], last_snapshot: CodeMemorySnapshot | None) -> tuple[int, int] | None:
        if len(turns) < CodeMemoryService.MIN_TURNS_BEFORE_COMPACTION:
            return None

        latest_turn_index = turns[-1].turn_index
        boundary_end = latest_turn_index - CodeMemoryService.KEEP_RECENT_TURNS
        if boundary_end <= 0:
            return None

        start = 1
        if last_snapshot is not None and last_snapshot.source_turn_end is not None:
            start = last_snapshot.source_turn_end + 1

        if start > boundary_end:
            return None
        return start, boundary_end

    @staticmethod
    def _build_summary(turns: list[CodeTurn], tool_calls: list[CodeToolCall]) -> tuple[str, str, int]:
        tool_names_by_turn: dict[int, list[str]] = defaultdict(list)
        for call in tool_calls:
            if call.turn_id is None:
                continue
            tool_names_by_turn[int(call.turn_id)].append(call.tool_name)

        lines = ["## Memory Snapshot", "", "### Covered Turns"]
        history_parts: list[str] = []
        for turn in turns:
            tools = ", ".join(sorted(set(tool_names_by_turn.get(turn.id, []))))
            lines.append(f"- Turn {turn.turn_index}: {turn.user_message[:180]}")
            if turn.assistant_summary:
                lines.append(f"  Assistant: {turn.assistant_summary[:220]}")
            if tools:
                lines.append(f"  Tools: {tools}")
            history_parts.append(
                f"Turn {turn.turn_index}: {turn.user_message[:120]}"
                + (f" -> {turn.assistant_summary[:160]}" if turn.assistant_summary else "")
            )
        summary = "\n".join(lines).strip()
        history = "\n".join(history_parts).strip()
        token_estimate = max(1, len(summary) // 4)
        return summary, history, token_estimate

    @classmethod
    async def refresh_snapshot(
        cls,
        db: AsyncSession,
        *,
        session: CodeSession,
        force: bool = False,
    ) -> CodeMemorySnapshot | None:
        turns_result = await db.execute(
            select(CodeTurn).where(CodeTurn.session_id == session.id).order_by(CodeTurn.turn_index.asc())
        )
        turns = list(turns_result.scalars().all())
        last_snapshot = await cls.get_latest_snapshot(db, session_id=session.id)
        boundary = cls._safe_boundary(turns, last_snapshot)
        if boundary is None and not force:
            return last_snapshot

        if boundary is None and force and turns:
            boundary = (1, turns[-1].turn_index)
        if boundary is None:
            if not force:
                return None
            snapshot = CodeMemorySnapshot(
                workspace_id=session.workspace_id,
                session_id=session.id,
                snapshot_kind="summary",
                source_turn_start=None,
                source_turn_end=None,
                summary_markdown="## Memory Snapshot\n\n- No BOS Code turns available yet.",
                history_excerpt="",
                token_estimate=8,
            )
            db.add(snapshot)
            runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=session.workspace_id)
            runtime.last_memory_sync_at = datetime.now(UTC)
            await db.flush()
            return snapshot

        start, end = boundary
        covered_turns = [turn for turn in turns if start <= turn.turn_index <= end]
        if not covered_turns:
            return last_snapshot

        covered_turn_ids = [turn.id for turn in covered_turns]
        tools_result = await db.execute(
            select(CodeToolCall)
            .where(CodeToolCall.turn_id.in_(covered_turn_ids))
            .order_by(CodeToolCall.created_at.asc())
        )
        summary, history, token_estimate = cls._build_summary(covered_turns, list(tools_result.scalars().all()))
        snapshot = CodeMemorySnapshot(
            workspace_id=session.workspace_id,
            session_id=session.id,
            snapshot_kind="summary",
            source_turn_start=start,
            source_turn_end=end,
            summary_markdown=summary,
            history_excerpt=history,
            token_estimate=token_estimate,
        )
        db.add(snapshot)
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=session.workspace_id)
        runtime.last_memory_sync_at = datetime.now(UTC)
        runtime.last_compressed_turn_index = end
        metrics = dict(runtime.runtime_metrics or {})
        metrics["latest_memory_session_id"] = session.id
        metrics["latest_memory_turn_end"] = end
        runtime.runtime_metrics = metrics
        await db.flush()
        return snapshot

    @classmethod
    async def build_prompt_memory_context(cls, db: AsyncSession, *, session_id: int) -> str:
        latest = await cls.get_latest_snapshot(db, session_id=session_id)
        if latest is None:
            return ""
        return (
            "Memory context from earlier BOS Code work. Treat this as background state, "
            "not a new user request.\n\n"
            f"{latest.summary_markdown}"
        )

    @classmethod
    async def touch_runtime_on_turn(cls, db: AsyncSession, *, session: CodeSession) -> CodeAgentRuntimeState:
        runtime = await CodeRuntimeService.ensure_runtime_state(db, workspace_id=session.workspace_id)
        metrics = dict(runtime.runtime_metrics or {})
        metrics["latest_turn_session_id"] = session.id
        metrics["latest_turn_at"] = datetime.now(UTC).isoformat()
        runtime.runtime_metrics = metrics
        await db.flush()
        return runtime
