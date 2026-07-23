"""Premium question queue: enqueue, claim, complete/fail, list.

The web UI enqueues; a Claude Code worker session drains the queue and produces
gate-verified answers. Everything is ownership-scoped to the single local user.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import QueueStatus
from app.db.base import new_uuid, utcnow
from app.models import QuestionQueue, User


async def enqueue(
    session: AsyncSession, user: User, *, session_id: str, question: str,
    approved_source_ids: list[str] | None,
) -> QuestionQueue:
    item = QuestionQueue(
        user_id=user.id, session_id=session_id, request_id=new_uuid(),
        question=question, approved_source_ids=approved_source_ids,
        status=QueueStatus.PENDING,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def get_item(session: AsyncSession, user: User, item_id: str) -> QuestionQueue | None:
    stmt = select(QuestionQueue).where(
        QuestionQueue.id == item_id, QuestionQueue.user_id == user.id
    )
    return (await session.execute(stmt)).scalars().first()


async def list_items(
    session: AsyncSession, user: User, status: QueueStatus | None = None,
    limit: int = 50, offset: int = 0,
) -> tuple[list[QuestionQueue], int]:
    where = [QuestionQueue.user_id == user.id]
    if status is not None:
        where.append(QuestionQueue.status == status)
    total = (
        await session.execute(select(func.count()).select_from(QuestionQueue).where(*where))
    ).scalar_one()
    stmt = (
        select(QuestionQueue).where(*where)
        .order_by(QuestionQueue.created_at.asc()).limit(limit).offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def claim_next(session: AsyncSession) -> QuestionQueue | None:
    """Worker: claim the oldest PENDING item (any user, single-tenant)."""
    stmt = (
        select(QuestionQueue).where(QuestionQueue.status == QueueStatus.PENDING)
        .order_by(QuestionQueue.created_at.asc()).limit(1)
    )
    item = (await session.execute(stmt)).scalars().first()
    if item is None:
        return None
    item.status = QueueStatus.PROCESSING
    item.claimed_at = utcnow()
    await session.commit()
    await session.refresh(item)
    return item


async def complete_item(session: AsyncSession, item: QuestionQueue, answer_id: str) -> None:
    item.status = QueueStatus.DONE
    item.answer_id = answer_id
    await session.commit()


async def fail_item(session: AsyncSession, item: QuestionQueue, error: str) -> None:
    item.status = QueueStatus.FAILED
    item.error = error[:2000]
    await session.commit()
