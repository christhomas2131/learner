"""PostgreSQL full-text retriever (tsvector / ts_rank).

Queries source_passages directly using `to_tsvector('english', text)` (backed by
a GIN index) and `plainto_tsquery`. Only APPROVED sources are returned — the
filter lives in SQL. No separate FTS table is needed (unlike SQLite FTS5); the
GIN index is maintained automatically.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SourceState
from app.retrieval.base import Retriever
from app.schemas.pipeline import RetrievedPassage

_TSCONFIG = "english"


def _normalize(ranks: list[float]) -> list[float]:
    if not ranks:
        return []
    best, worst = max(ranks), min(ranks)  # ts_rank: higher is better
    if best == worst:
        return [0.9 for _ in ranks]
    return [round(0.5 + 0.49 * (r - worst) / (best - worst), 4) for r in ranks]


class PostgresFtsRetriever(Retriever):
    def __init__(self, session: AsyncSession, min_score: float = 0.0) -> None:
        self._session = session
        self._min_score = min_score

    async def retrieve(
        self, question: str, approved_source_ids: list[str] | None, limit: int
    ) -> list[RetrievedPassage]:
        params: dict[str, object] = {
            "q": question,
            "limit": limit,
            "approved": SourceState.APPROVED.value,
        }
        source_filter = ""
        if approved_source_ids:
            placeholders = ",".join(f":sid{i}" for i in range(len(approved_source_ids)))
            source_filter = f" AND s.id IN ({placeholders})"
            for i, sid in enumerate(approved_source_ids):
                params[f"sid{i}"] = sid

        # The text-search config ('english') is a constant regconfig, hardcoded
        # rather than bound — Postgres can't infer a regconfig from a bind param.
        sql = text(
            f"""
            SELECT p.id AS passage_id, p.source_id, s.title, s.source_type, p.text,
                   p.chunk_index,
                   ts_rank(to_tsvector('{_TSCONFIG}', p.text),
                           plainto_tsquery('{_TSCONFIG}', :q)) AS rank
            FROM source_passages p
            JOIN sources s ON s.id = p.source_id
            WHERE s.state = :approved{source_filter}
              AND to_tsvector('{_TSCONFIG}', p.text) @@ plainto_tsquery('{_TSCONFIG}', :q)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )
        rows = (await self._session.execute(sql, params)).all()
        if not rows:
            return []

        scores = _normalize([float(r.rank) for r in rows])
        out: list[RetrievedPassage] = []
        for row, score in zip(rows, scores, strict=False):
            if score < self._min_score:
                continue
            out.append(
                RetrievedPassage(
                    passage_id=row.passage_id, source_id=row.source_id,
                    source_title=row.title, source_type=row.source_type, text=row.text,
                    chunk_index=row.chunk_index, retrieval_score=score, approved=True,
                )
            )
        return out
