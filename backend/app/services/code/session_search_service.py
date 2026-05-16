"""
Cross-session recall across BOS Code turns, events, and artifacts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from app.models import CodeArtifact, CodeEvent, CodeSession, CodeTurn

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CodeSessionSearchService:
    @staticmethod
    async def search(
        db: AsyncSession,
        *,
        tenant_id: int,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        like_query = f"%{query}%"
        results: dict[int, dict] = {}
        session_scores: dict[int, float] = defaultdict(float)

        turn_result = await db.execute(
            select(CodeTurn, CodeSession)
            .join(CodeSession, CodeTurn.session_id == CodeSession.id)
            .where(
                CodeSession.tenant_id == tenant_id,
                or_(
                    CodeTurn.user_message.ilike(like_query),
                    CodeTurn.assistant_summary.ilike(like_query),
                ),
            )
            .order_by(CodeTurn.created_at.desc())
            .limit(limit * 4)
        )
        for turn, session in turn_result.all():
            payload = results.setdefault(
                session.id,
                {
                    "session_id": session.id,
                    "score": 0.0,
                    "headline": turn.user_message[:120],
                    "summary_parts": [],
                    "matched_turn_ids": [],
                    "matched_artifact_ids": [],
                    "matched_event_ids": [],
                },
            )
            payload["matched_turn_ids"].append(turn.id)
            payload["summary_parts"].append(
                f"Turn {turn.turn_index}: {turn.user_message[:120]}"
                + (f" -> {turn.assistant_summary[:140]}" if turn.assistant_summary else "")
            )
            session_scores[session.id] += 3.0

        artifact_result = await db.execute(
            select(CodeArtifact, CodeSession)
            .join(CodeSession, CodeArtifact.session_id == CodeSession.id)
            .where(
                CodeSession.tenant_id == tenant_id,
                CodeArtifact.diff_summary.ilike(like_query),
            )
            .order_by(CodeArtifact.created_at.desc())
            .limit(limit * 3)
        )
        for artifact, session in artifact_result.all():
            payload = results.setdefault(
                session.id,
                {
                    "session_id": session.id,
                    "score": 0.0,
                    "headline": "Artifact match",
                    "summary_parts": [],
                    "matched_turn_ids": [],
                    "matched_artifact_ids": [],
                    "matched_event_ids": [],
                },
            )
            payload["matched_artifact_ids"].append(artifact.id)
            payload["summary_parts"].append(f"Artifact: {artifact.diff_summary[:180] if artifact.diff_summary else artifact.artifact_type}")
            session_scores[session.id] += 2.0

        event_result = await db.execute(
            select(CodeEvent, CodeSession)
            .join(CodeSession, CodeEvent.session_id == CodeSession.id)
            .where(
                CodeSession.tenant_id == tenant_id,
                CodeEvent.event_type.ilike(like_query),
            )
            .order_by(CodeEvent.created_at.desc())
            .limit(limit * 3)
        )
        for event, session in event_result.all():
            payload = results.setdefault(
                session.id,
                {
                    "session_id": session.id,
                    "score": 0.0,
                    "headline": event.event_type,
                    "summary_parts": [],
                    "matched_turn_ids": [],
                    "matched_artifact_ids": [],
                    "matched_event_ids": [],
                },
            )
            payload["matched_event_ids"].append(event.id)
            payload["summary_parts"].append(f"Event: {event.event_type}")
            session_scores[session.id] += 1.0

        ranked = []
        for session_id, payload in results.items():
            payload["score"] = session_scores[session_id]
            payload["summary"] = "\n".join(payload.pop("summary_parts")[:5])
            ranked.append(payload)

        ranked.sort(key=lambda item: (-item["score"], -item["session_id"]))
        return ranked[:limit]
