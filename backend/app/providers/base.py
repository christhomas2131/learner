"""Model provider interface and error types.

A provider does exactly two things: draft a candidate answer from retrieved
passages, and verify claims against their cited passages. It never decides
pipeline flow and never sees its own prior reasoning as evidence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.pipeline import DraftClaim, DraftResponse, RetrievedPassage, VerifierResult


class ModelError(Exception):
    """Generic provider failure."""


class ModelTimeoutError(ModelError):
    """Provider timed out."""


class MalformedResponseError(ModelError):
    """Provider returned output that failed schema/JSON validation."""


class ModelProvider(ABC):
    name: str = "base"
    model_identifier: str | None = None

    @abstractmethod
    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        """Produce a candidate answer using ONLY the provided passages."""
        raise NotImplementedError

    @abstractmethod
    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        """Independently classify each claim against its cited passages.

        Must return exactly one result per input claim (same claim_ids).
        """
        raise NotImplementedError
