"""Claude Code CLI provider — hands-off premium drafting via `claude -p`.

Shells out to the user's authenticated `claude` CLI in headless print mode
(subscription login, NO API key). The prompt is fed on stdin; the model's text
comes back in the JSON envelope's `result` field, which we parse as our draft /
verify JSON. The deterministic harness still validates every quotation and
applies the release gate — so even if the CLI fabricates, the gate catches it.

If the `claude` binary isn't present, `available()` is False and callers fall
back to the queue/manual worker.
"""

from __future__ import annotations

import asyncio
import json
import shutil

from app.core.config import settings
from app.core.logging import get_logger
from app.prompts.drafting import build_draft_prompt
from app.prompts.verification import build_verify_prompt
from app.providers.base import (
    MalformedResponseError,
    ModelError,
    ModelProvider,
    ModelTimeoutError,
)
from app.schemas.pipeline import DraftClaim, DraftResponse, RetrievedPassage, VerifierResult

log = get_logger("claude_cli")


def claude_cli_available() -> bool:
    return shutil.which("claude") is not None


def _extract_json(text: str, array: bool = False) -> str:
    """Pull the outermost JSON object/array out of a possibly-fenced string."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.startswith("json"):
            t = t[4:]
    open_c, close_c = ("[", "]") if array else ("{", "}")
    start, end = t.find(open_c), t.rfind(close_c)
    if start == -1 or end == -1 or end < start:
        raise MalformedResponseError("no JSON found in model output")
    return t[start : end + 1]


class ClaudeCliProvider(ModelProvider):
    name = "claude_code"
    model_identifier = "claude-code-cli"

    def __init__(self, timeout_seconds: int | None = None) -> None:
        self._timeout = timeout_seconds or max(30, settings.MODEL_TIMEOUT_SECONDS)

    async def _call(self, prompt: str) -> str:
        if not claude_cli_available():
            raise ModelError("`claude` CLI not found on PATH.")
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--output-format", "json", "--allowedTools", "",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(prompt.encode()), timeout=self._timeout
            )
        except TimeoutError as e:
            raise ModelTimeoutError("claude CLI timed out") from e
        except OSError as e:
            raise ModelError(f"claude CLI failed to start: {e}") from e
        if proc.returncode != 0:
            raise ModelError(f"claude CLI exited {proc.returncode}: {err.decode()[:200]}")
        try:
            envelope = json.loads(out.decode())
        except json.JSONDecodeError as e:
            raise MalformedResponseError("claude CLI returned non-JSON envelope") from e
        if envelope.get("is_error"):
            raise ModelError(f"claude CLI reported error: {envelope.get('result', '')[:200]}")
        result = envelope.get("result")
        if not isinstance(result, str):
            raise MalformedResponseError("claude CLI envelope missing 'result'")
        return result

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        result = await self._call(build_draft_prompt(question, passages))
        try:
            return DraftResponse.model_validate_json(_extract_json(result))
        except (ValueError, MalformedResponseError) as e:
            raise MalformedResponseError(f"invalid draft JSON: {e}") from e

    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        result = await self._call(build_verify_prompt(claims, passages))
        try:
            data = json.loads(_extract_json(result, array=True))
            return [VerifierResult.model_validate(v) for v in data]
        except (ValueError, MalformedResponseError) as e:
            raise MalformedResponseError(f"invalid verifier JSON: {e}") from e
