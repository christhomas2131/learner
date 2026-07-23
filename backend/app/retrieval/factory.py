"""Pick the FTS retriever backend by database dialect."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.base import Retriever


def dialect_name(session: AsyncSession) -> str:
    return session.get_bind().dialect.name


def make_fts_retriever(session: AsyncSession, min_score: float = 0.0) -> Retriever:
    if dialect_name(session).startswith("postgres"):
        from app.retrieval.fts_pg import PostgresFtsRetriever

        return PostgresFtsRetriever(session, min_score=min_score)
    from app.retrieval.fts import SqliteFtsRetriever

    return SqliteFtsRetriever(session, min_score=min_score)
