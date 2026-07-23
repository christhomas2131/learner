"""Source library queries + mutations (ownership-scoped)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source, SourcePassage, User


async def get_owned_source(session: AsyncSession, user: User, source_id: str) -> Source | None:
    stmt = select(Source).where(Source.id == source_id, Source.user_id == user.id)
    return (await session.execute(stmt)).scalars().first()


async def list_sources(
    session: AsyncSession, user: User, *, limit: int, offset: int,
    state: str | None = None, subject_id: str | None = None, search: str | None = None,
) -> tuple[list[Source], int, dict[str, int]]:
    where = [Source.user_id == user.id]
    if state:
        where.append(Source.state == state)
    if subject_id:
        where.append(Source.subject_id == subject_id)
    if search:
        where.append(Source.title.ilike(f"%{search}%"))
    total = (await session.execute(select(func.count()).select_from(Source).where(*where))).scalar_one()
    stmt = select(Source).where(*where).order_by(Source.updated_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()

    counts_stmt = (
        select(Source.state, func.count()).where(Source.user_id == user.id).group_by(Source.state)
    )
    counts = {str(s): c for s, c in (await session.execute(counts_stmt)).all()}
    return list(rows), total, counts


async def passage_count(session: AsyncSession, source_id: str) -> int:
    stmt = select(func.count()).select_from(SourcePassage).where(SourcePassage.source_id == source_id)
    return (await session.execute(stmt)).scalar_one()


async def list_passages(session: AsyncSession, source_id: str) -> list[SourcePassage]:
    stmt = (
        select(SourcePassage).where(SourcePassage.source_id == source_id)
        .order_by(SourcePassage.chunk_index.asc())
    )
    return list((await session.execute(stmt)).scalars().all())
