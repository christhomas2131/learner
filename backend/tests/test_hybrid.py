"""Hybrid retriever tests: deterministic fake embedder (no model download) +
graceful FTS fallback."""

from __future__ import annotations

import pytest

from app.core.enums import SourceState
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all, drop_all
from app.ingestion.service import ingest_file, set_source_state
from app.retrieval import embeddings
from app.retrieval.hybrid import HybridRetriever
from app.services.user import get_or_create_demo_user

PHOTO = b"# Biology\n\nPhotosynthesis converts light energy into chemical energy using chlorophyll.\n"
ROME = b"# Rome\n\nJulius Caesar was a Roman general and the Roman Republic preceded the Empire.\n"

_KEYWORDS = ["photosynthesis", "light", "energy", "chlorophyll", "rome", "caesar", "republic", "empire"]


class FakeEmbedder:
    """Deterministic keyword-count 'embedding' — enough to test fusion + ranking."""

    available = True

    def embed(self, texts: list[str]):
        out = []
        for t in texts:
            tl = t.lower()
            v = [float(tl.count(k)) for k in _KEYWORDS]
            if sum(v) == 0:
                v = [1.0] + [0.0] * (len(_KEYWORDS) - 1)
            out.append(v)
        return out


@pytest.fixture(autouse=True)
async def fresh_db():
    await drop_all()
    await create_all()
    yield
    await drop_all()


async def _ingest_both(session, user):
    a = await ingest_file(session, user_id=user.id, filename="bio.md", data=PHOTO, save_file=False)
    b = await ingest_file(session, user_id=user.id, filename="rome.md", data=ROME, save_file=False)
    await set_source_state(session, a, SourceState.APPROVED)
    await set_source_state(session, b, SourceState.APPROVED)


async def test_hybrid_falls_back_to_fts_when_no_vectors():
    # Embeddings disabled in tests → no vectors stored → FTS-only path.
    async with AsyncSessionLocal() as session:
        user = await get_or_create_demo_user(session)
        await _ingest_both(session, user)
        results = await HybridRetriever(session).retrieve("photosynthesis", None, 5)
        assert results and any("photosynthesis" in p.text.lower() for p in results)


async def test_hybrid_uses_vectors_and_ranks_semantically(monkeypatch):
    monkeypatch.setattr(embeddings, "_embedder", FakeEmbedder())
    async with AsyncSessionLocal() as session:
        user = await get_or_create_demo_user(session)
        await _ingest_both(session, user)  # stores fake vectors
        results = await HybridRetriever(session).retrieve(
            "photosynthesis light energy", None, 5
        )
        assert results
        # The photosynthesis passage should fuse to the top.
        assert "photosynthesis" in results[0].text.lower()
        assert results[0].retrieval_score > 0
