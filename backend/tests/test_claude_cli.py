"""ClaudeCliProvider JSON handling (no real `claude` invocation)."""

from __future__ import annotations

import pytest

from app.providers.base import MalformedResponseError
from app.providers.claude_cli import ClaudeCliProvider, _extract_json


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_json_fenced():
    fenced = '```json\n{"a": 1}\n```'
    assert '"a": 1' in _extract_json(fenced)


def test_extract_json_array():
    assert _extract_json('prefix [1,2,3] suffix', array=True) == "[1,2,3]"


def test_extract_json_none_raises():
    with pytest.raises(MalformedResponseError):
        _extract_json("no json here")


async def test_draft_parses_cli_output(monkeypatch):
    provider = ClaudeCliProvider()

    async def fake_call(_prompt: str) -> str:
        return (
            '{"answer": "X [1]", "claims": [{"claim_id": "claim-1", "text": "X",'
            ' "material": true, "cited_passage_ids": ["p1"]}]}'
        )

    monkeypatch.setattr(provider, "_call", fake_call)
    draft = await provider.draft("q", [])
    assert draft.claims[0].claim_id == "claim-1" and draft.claims[0].cited_passage_ids == ["p1"]


async def test_draft_rejects_garbage(monkeypatch):
    provider = ClaudeCliProvider()

    async def fake_call(_prompt: str) -> str:
        return "the model rambled without any json"

    monkeypatch.setattr(provider, "_call", fake_call)
    with pytest.raises(MalformedResponseError):
        await provider.draft("q", [])
