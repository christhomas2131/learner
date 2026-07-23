"""Session + message helpers with ownership enforcement."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import Answer, Message, Session, User


def _title_from_question(question: str) -> str:
    q = " ".join(question.split())
    return (q[:60] + "…") if len(q) > 60 else q or "New session"


async def get_owned_session(session: AsyncSession, user: User, session_id: str) -> Session | None:
    stmt = select(Session).where(Session.id == session_id, Session.user_id == user.id)
    return (await session.execute(stmt)).scalars().first()


async def ensure_session(
    session: AsyncSession, user: User, session_id: str | None,
    subject_id: str | None, question: str,
) -> Session:
    if session_id:
        existing = await get_owned_session(session, user, session_id)
        if existing is None:
            from app.api.errors import NotFoundError

            raise NotFoundError("Session not found.")
        return existing
    obj = Session(user_id=user.id, title=_title_from_question(question), subject_id=subject_id)
    session.add(obj)
    await session.flush()
    return obj


async def touch_session(session: AsyncSession, session_obj: Session) -> None:
    session_obj.updated_at = utcnow()
    await session.commit()


async def add_user_message(session: AsyncSession, session_id: str, content: str) -> None:
    session.add(Message(session_id=session_id, role="user", content=content))
    await session.commit()


async def list_sessions(
    session: AsyncSession, user: User, limit: int, offset: int, saved_only: bool = False,
    search: str | None = None,
) -> tuple[list[Session], int]:
    where = [Session.user_id == user.id]
    if saved_only:
        where.append(Session.saved.is_(True))
    if search:
        where.append(Session.title.ilike(f"%{search}%"))
    total = (await session.execute(select(func.count()).select_from(Session).where(*where))).scalar_one()
    stmt = (
        select(Session).where(*where).order_by(Session.updated_at.desc()).limit(limit).offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows), total


async def session_answers(session: AsyncSession, session_id: str) -> list[Answer]:
    stmt = select(Answer).where(Answer.session_id == session_id).order_by(Answer.created_at.asc())
    return list((await session.execute(stmt)).scalars().all())


async def session_messages(session: AsyncSession, session_id: str) -> list[Message]:
    stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    return list((await session.execute(stmt)).scalars().all())
