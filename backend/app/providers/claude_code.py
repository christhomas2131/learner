"""Claude Code worker provider.

The "premium" path: drafting and verification are performed by a running Claude
Code session (the user's subscription), not by an API call. The pipeline stays
identical; this provider is fed the model's JSON via injected async callables
that the Phase-2 worker supplies (file-RPC or staged CLI submission).

If no transport is attached, draft/verify fail loudly rather than fabricating —
consistent with the whole design: never invent verification.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.providers.base import ModelError, ModelProvider
from app.schemas.pipeline import DraftClaim, DraftResponse, RetrievedPassage, VerifierResult

DraftFn = Callable[[str, list[RetrievedPassage], list[str] | None], Awaitable[DraftResponse]]
VerifyFn = Callable[[list[DraftClaim], list[RetrievedPassage]], Awaitable[list[VerifierResult]]]


class ClaudeCodeProvider(ModelProvider):
    name = "claude_code"
    model_identifier = "claude-code-session"

    def __init__(self, draft_fn: DraftFn | None = None, verify_fn: VerifyFn | None = None) -> None:
        self._draft_fn = draft_fn
        self._verify_fn = verify_fn

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        if self._draft_fn is None:
            raise ModelError(
                "No Claude Code worker attached. Start a worker session (premium mode) "
                "or use MODEL_PROVIDER=none for deterministic answers."
            )
        return await self._draft_fn(question, passages, previous_unsupported)

    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        if self._verify_fn is None:
            raise ModelError("No Claude Code worker attached for verification.")
        return await self._verify_fn(claims, passages)
