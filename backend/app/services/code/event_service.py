"""
Append-only event persistence for BOS Code.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeEvent


class CodeEventService:
    @staticmethod
    async def append_event(
        db: AsyncSession,
        *,
        session_id: int,
        event_type: str,
        payload: dict,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CodeEvent:
        last_seq = await db.scalar(select(func.max(CodeEvent.seq_no)).where(CodeEvent.session_id == session_id))
        event = CodeEvent(
            session_id=session_id,
            seq_no=(last_seq or 0) + 1,
            event_type=event_type,
            payload=payload,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def list_events(
        db: AsyncSession,
        *,
        session_id: int,
        after_seq: int | None = None,
        limit: int = 500,
    ) -> list[CodeEvent]:
        stmt = select(CodeEvent).where(CodeEvent.session_id == session_id).order_by(CodeEvent.seq_no.asc()).limit(limit)
        if after_seq is not None:
            stmt = stmt.where(CodeEvent.seq_no > after_seq)
        result = await db.execute(stmt)
        return list(result.scalars().all())
