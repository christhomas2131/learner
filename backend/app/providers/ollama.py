"""Ollama provider — keyless, offline, local fluent drafting/verification.

Talks to a local Ollama server (default http://localhost:11434) with JSON mode.
Same prompts as every other provider; the deterministic harness still validates
each quotation and applies the release gate. Selected via MODEL_PROVIDER=ollama.
"""

from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.prompts.drafting import build_draft_prompt
from app.prompts.verification import build_verify_prompt
from app.providers.base import (
    MalformedResponseError,
    ModelError,
    ModelProvider,
    ModelTimeoutError,
)
from app.providers.claude_cli import _extract_json
from app.schemas.pipeline import DraftClaim, DraftResponse, RetrievedPassage, VerifierResult


class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._host = settings.OLLAMA_HOST.rstrip("/")
        self._model = settings.OLLAMA_MODEL
        self.model_identifier = f"ollama:{self._model}"
        self._timeout = max(30, settings.MODEL_TIMEOUT_SECONDS)

    async def _chat(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._host}/api/chat", json=payload)
        except httpx.TimeoutException as e:
            raise ModelTimeoutError("Ollama timed out") from e
        except httpx.HTTPError as e:
            raise ModelError(f"Ollama unreachable at {self._host}: {e}") from e
        if resp.status_code >= 400:
            raise ModelError(f"Ollama HTTP {resp.status_code}: {resp.text[:200]}")
        content = resp.json().get("message", {}).get("content")
        if not isinstance(content, str):
            raise MalformedResponseError("Ollama response missing message.content")
        return content

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        result = await self._chat(build_draft_prompt(question, passages))
        try:
            return DraftResponse.model_validate_json(_extract_json(result))
        except (ValueError, MalformedResponseError) as e:
            raise MalformedResponseError(f"invalid draft JSON: {e}") from e

    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        result = await self._chat(build_verify_prompt(claims, passages))
        try:
            data = json.loads(_extract_json(result, array=True))
            return [VerifierResult.model_validate(v) for v in data]
        except (ValueError, MalformedResponseError) as e:
            raise MalformedResponseError(f"invalid verifier JSON: {e}") from e
