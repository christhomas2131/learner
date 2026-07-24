"""Provider selection."""

from __future__ import annotations

from app.core.enums import ModelProviderKind
from app.providers.base import ModelProvider
from app.providers.claude_code import ClaudeCodeProvider
from app.providers.nomodel import NoModelProvider


def get_provider(kind: ModelProviderKind) -> ModelProvider:
    if kind == ModelProviderKind.NONE:
        return NoModelProvider()
    if kind == ModelProviderKind.CLAUDE_CODE:
        # Unattached by default; the worker attaches transports at runtime.
        return ClaudeCodeProvider()
    if kind == ModelProviderKind.OLLAMA:
        from app.providers.ollama import OllamaProvider

        return OllamaProvider()
    if kind == ModelProviderKind.MOCK:
        from app.providers.mock import MockProvider

        return MockProvider()
    raise ValueError(f"Unsupported or unconfigured provider: {kind}")
