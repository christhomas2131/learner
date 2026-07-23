"""Hybrid retriever: lexical FTS + semantic vectors fused by reciprocal rank
fusion (RRF).

Both signals are ownership/approval-filtered in SQL. If embeddings are
unavailable (model can't load) or no vectors are stored, this degrades cleanly
to FTS-only — the pipeline never breaks.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SourceState
from app.models import PassageVector, Source, SourcePassage
from app.retrieval.base import Retriever
from app.retrieval.embeddings import get_embedder
from app.retrieval.factory import make_fts_retriever
from app.schemas.pipeline import RetrievedPassage


def _cosine(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    q = query / (np.linalg.norm(query) + 1e-9)
    m = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    return m @ q


class HybridRetriever(Retriever):
    def __init__(self, session: AsyncSession, *, min_score: float = 0.0, rrf_k: int = 60) -> None:
        self._session = session
        self._min_score = min_score
        self._rrf_k = rrf_k
        self._fts = make_fts_retriever(session, min_score=0.0)

    async def retrieve(
        self, question: str, approved_source_ids: list[str] | None, limit: int
    ) -> list[RetrievedPassage]:
        pool = max(limit * 3, limit)
        fts = await self._fts.retrieve(question, approved_source_ids, pool)
        vec = await self._vector_search(question, approved_source_ids, pool)

        if not vec:
            return fts[:limit]
        if not fts:
            return vec[:limit]

        # Reciprocal rank fusion. A passage strong in both lists rises to the top.
        fused: dict[str, float] = {}
        by_id: dict[str, RetrievedPassage] = {}
        vec_by_id = {p.passage_id: p for p in vec}
        for lst in (fts, vec):
            for rank, p in enumerate(lst):
                by_id.setdefault(p.passage_id, p)
                fused[p.passage_id] = fused.get(p.passage_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)

        ordered = sorted(fused, key=lambda pid: fused[pid], reverse=True)
        # Prefer the vector object when present (carries the cosine score for display).
        return [vec_by_id.get(pid) or by_id[pid] for pid in ordered[:limit]]

    async def _vector_search(
        self, question: str, approved_source_ids: list[str] | None, limit: int
    ) -> list[RetrievedPassage]:
        embedder = get_embedder()
        qv = embedder.embed([question])
        if not qv:
            return []

        stmt = (
            select(PassageVector.vector, SourcePassage, Source.title, Source.source_type)
            .join(SourcePassage, SourcePassage.id == PassageVector.passage_id)
            .join(Source, Source.id == PassageVector.source_id)
            .where(Source.state == SourceState.APPROVED)
        )
        if approved_source_ids:
            stmt = stmt.where(Source.id.in_(approved_source_ids))
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return []

        matrix = np.array([r[0] for r in rows], dtype=float)
        sims = _cosine(np.array(qv[0], dtype=float), matrix)
        top = np.argsort(-sims)[:limit]

        out: list[RetrievedPassage] = []
        for i in top:
            _vector, passage, title, source_type = rows[int(i)]
            out.append(
                RetrievedPassage(
                    passage_id=passage.id,
                    source_id=passage.source_id,
                    source_title=title,
                    source_type=source_type,
                    text=passage.text,
                    chunk_index=passage.chunk_index,
                    retrieval_score=round(max(0.0, float(sims[int(i)])), 4),
                    approved=True,
                )
            )
        return out
