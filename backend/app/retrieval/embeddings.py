"""Local, keyless text embeddings (fastembed / ONNX).

Lazy singleton. If the model can't load (missing dep, no network for the
one-time download, disabled by setting), it reports unavailable and the
retriever degrades to FTS-only. Nothing here ever calls a paid API.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("embeddings")


class Embedder:
    def __init__(self) -> None:
        self._model: Any = None
        self._tried = False
        self._available = False

    def _ensure(self) -> None:
        if self._tried:
            return
        self._tried = True
        if not settings.RETRIEVAL_USE_EMBEDDINGS:
            return
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(settings.EMBEDDING_MODEL)
            self._available = True
            log.info("embeddings_ready", model=settings.EMBEDDING_MODEL)
        except Exception as e:  # noqa: BLE001 - degrade gracefully
            log.warning("embeddings_unavailable", error=str(e))
            self._available = False

    @property
    def available(self) -> bool:
        self._ensure()
        return self._available

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        self._ensure()
        if not self._available or not texts:
            return None
        try:
            return [list(map(float, v)) for v in self._model.embed(texts)]
        except Exception as e:  # noqa: BLE001
            log.warning("embed_failed", error=str(e))
            return None


_embedder = Embedder()


def get_embedder() -> Embedder:
    return _embedder
