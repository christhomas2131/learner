"""SQLite FTS5 full-text retriever + index maintenance.

The FTS index is a separate virtual table (`passage_fts`) kept in sync by the
ingestion layer. Retrieval joins back to `sources` so that ONLY passages whose
source is APPROVED can ever be returned — the approval filter lives in SQL, not
in the caller.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SourceState
from app.providers.text_utils import STOPWORDS
from app.retrieval.base import Retriever
from app.schemas.pipeline import RetrievedPassage

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


async def ensure_fts(session: AsyncSession) -> None:
    """Create the FTS5 virtual table if it does not exist."""
    await session.execute(
        text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts "
            "USING fts5(passage_id UNINDEXED, source_id UNINDEXED, text)"
        )
    )
    await session.commit()


async def index_passages(
    session: AsyncSession, rows: list[tuple[str, str, str]]
) -> None:
    """Insert (passage_id, source_id, text) rows into the FTS index."""
    await ensure_fts(session)
    for pid, sid, txt in rows:
        await session.execute(
            text("INSERT INTO passage_fts(passage_id, source_id, text) VALUES (:p, :s, :t)"),
            {"p": pid, "s": sid, "t": txt},
        )
    await session.commit()


async def remove_source_from_index(session: AsyncSession, source_id: str) -> None:
    await ensure_fts(session)
    await session.execute(
        text("DELETE FROM passage_fts WHERE source_id = :s"), {"s": source_id}
    )
    await session.commit()


def _build_match_query(question: str) -> str | None:
    all_tokens = [t for t in _TOKEN_RE.findall(question.lower()) if len(t) > 1]
    content = [t for t in all_tokens if t not in STOPWORDS]
    # Prefer content words; fall back to all tokens only if the question is
    # entirely stopwords. This stops "the"/"who" from matching everything.
    tokens = content or all_tokens
    if not tokens:
        return None
    # OR the quoted tokens so any term can match; FTS5 ranks by relevance.
    return " OR ".join(f'"{t}"' for t in tokens)


def _normalize_scores(raw: list[float]) -> list[float]:
    """Map bm25 distances (lower = better) to a monotonic [0,1] display score."""
    if not raw:
        return []
    # bm25 returns more-negative for better matches; use magnitude ascending.
    best, worst = min(raw), max(raw)
    if best == worst:
        return [0.9 for _ in raw]
    return [round(0.5 + 0.49 * (worst - r) / (worst - best), 4) for r in raw]


class SqliteFtsRetriever(Retriever):
    def __init__(self, session: AsyncSession, min_score: float = 0.0) -> None:
        self._session = session
        self._min_score = min_score

    async def retrieve(
        self,
        question: str,
        approved_source_ids: list[str] | None,
        limit: int,
    ) -> list[RetrievedPassage]:
        await ensure_fts(self._session)
        match = _build_match_query(question)
        if match is None:
            return []

        params: dict[str, object] = {"match": match, "limit": limit, "approved": SourceState.APPROVED.value}
        source_filter = ""
        if approved_source_ids:
            placeholders = ",".join(f":sid{i}" for i in range(len(approved_source_ids)))
            source_filter = f" AND s.id IN ({placeholders})"
            for i, sid in enumerate(approved_source_ids):
                params[f"sid{i}"] = sid

        sql = text(
            f"""
            SELECT f.passage_id, f.source_id, s.title, s.source_type, p.text,
                   p.chunk_index, bm25(passage_fts) AS rank
            FROM passage_fts f
            JOIN source_passages p ON p.id = f.passage_id
            JOIN sources s ON s.id = f.source_id
            WHERE passage_fts MATCH :match
              AND s.state = :approved{source_filter}
            ORDER BY rank
            LIMIT :limit
            """
        )
        result = await self._session.execute(sql, params)
        rows = result.all()
        if not rows:
            return []

        ranks = [float(r.rank) for r in rows]
        scores = _normalize_scores(ranks)
        passages: list[RetrievedPassage] = []
        for row, score in zip(rows, scores, strict=False):
            if score < self._min_score:
                continue
            passages.append(
                RetrievedPassage(
                    passage_id=row.passage_id,
                    source_id=row.source_id,
                    source_title=row.title,
                    source_type=row.source_type,
                    text=row.text,
                    chunk_index=row.chunk_index,
                    retrieval_score=score,
                    approved=True,
                )
            )
        return passages
