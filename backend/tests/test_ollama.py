"""OllamaProvider JSON handling (no real Ollama server)."""

from __future__ import annotations

import pytest

from app.providers.base import MalformedResponseError
from app.providers.ollama import OllamaProvider
from app.schemas.pipeline import DraftClaim


async def test_ollama_draft_parses(monkeypatch):
    p = OllamaProvider()

    async def fake_chat(_prompt: str) -> str:
        return (
            '{"answer": "X [1]", "claims": [{"claim_id": "claim-1", "text": "X",'
            ' "material": true, "cited_passage_ids": ["p1"]}]}'
        )

    monkeypatch.setattr(p, "_chat", fake_chat)
    draft = await p.draft("q", [])
    assert draft.claims[0].claim_id == "claim-1"


async def test_ollama_verify_parses(monkeypatch):
    p = OllamaProvider()

    async def fake_chat(_prompt: str) -> str:
        return '[{"claim_id": "claim-1", "status": "SUPPORTED", "evidence": [], "explanation": "ok"}]'

    monkeypatch.setattr(p, "_chat", fake_chat)
    results = await p.verify([DraftClaim(claim_id="claim-1", text="X", cited_passage_ids=["p1"])], [])
    assert results[0].claim_id == "claim-1"


async def test_ollama_rejects_garbage(monkeypatch):
    p = OllamaProvider()

    async def fake_chat(_prompt: str) -> str:
        return "no json here"

    monkeypatch.setattr(p, "_chat", fake_chat)
    with pytest.raises(MalformedResponseError):
        await p.draft("q", [])
