"""Retriever abstraction.

The pipeline depends only on this interface, so a vector/embeddings backend can
be added later without touching the state machine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.pipeline import RetrievedPassage


class Retriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        question: str,
        approved_source_ids: list[str] | None,
        limit: int,
    ) -> list[RetrievedPassage]:
        """Return approved passages relevant to `question`, best first.

        Implementations MUST only return passages whose source is APPROVED.
        `approved_source_ids`, when provided, further restricts to that subset.
        """
        raise NotImplementedError
