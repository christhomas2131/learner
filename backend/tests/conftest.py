"""Shared test fixtures: an in-memory retriever and passage builders.

These let the state machine be tested with zero database and zero real model.
"""

from __future__ import annotations

import os
import tempfile

# Point the whole test process at an isolated temp SQLite DB + dirs BEFORE any
# app module (and thus the settings singleton) is imported.
_TMP = tempfile.mkdtemp(prefix="learner-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/test.db")
os.environ.setdefault("UPLOAD_DIRECTORY", f"{_TMP}/uploads")
os.environ.setdefault("MODEL_PROVIDER", "none")
# Keep tests hermetic + fast: no embedding-model download. Hybrid tests opt in
# via a fake embedder.
os.environ.setdefault("RETRIEVAL_USE_EMBEDDINGS", "false")
# No network in tests: never auto-discover from the web. Discovery tests opt in
# by monkeypatching settings.AUTO_DISCOVERY_ENABLED + the discover() call.
os.environ.setdefault("AUTO_DISCOVERY_ENABLED", "false")

import pytest  # noqa: E402

from app.retrieval.base import Retriever  # noqa: E402
from app.schemas.pipeline import RetrievedPassage  # noqa: E402


def make_passage(
    passage_id: str,
    text: str,
    *,
    source_id: str = "src-bio",
    title: str = "Introduction to Biology",
    source_type: str = "CURATED_MARKDOWN",
    approved: bool = True,
    score: float = 0.9,
    chunk_index: int = 0,
) -> RetrievedPassage:
    return RetrievedPassage(
        passage_id=passage_id, source_id=source_id, source_title=title,
        source_type=source_type, text=text, chunk_index=chunk_index,
        retrieval_score=score, approved=approved,
    )


class FakeRetriever(Retriever):
    """Returns preset passages, honoring approval + source filtering."""

    def __init__(self, passages: list[RetrievedPassage]) -> None:
        self._passages = passages

    async def retrieve(self, question, approved_source_ids, limit):
        ps = [p for p in self._passages if p.approved]
        if approved_source_ids:
            ps = [p for p in ps if p.source_id in approved_source_ids]
        return ps[:limit]


@pytest.fixture
def bio_passages() -> list[RetrievedPassage]:
    return [
        make_passage(
            "p-photo",
            "Photosynthesis converts light energy into chemical energy. "
            "It occurs in the chloroplasts of plant cells.",
        ),
        make_passage(
            "p-resp",
            "Cellular respiration releases energy stored in glucose.",
        ),
    ]


class ExplodingProvider:
    """A provider that fails if any model method is called (used to prove
    deterministic questions never touch the model)."""

    name = "exploding"
    model_identifier = None

    async def draft(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("draft() must not be called for deterministic questions")

    async def verify(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("verify() must not be called for deterministic questions")
