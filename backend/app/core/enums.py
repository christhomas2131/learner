"""Canonical enums shared across the engine.

These are the single source of truth for every state the pipeline can express.
The frontend maps against these exact string values; do not rename casually.
"""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    CURATED_MARKDOWN = "CURATED_MARKDOWN"
    UPLOADED_TEXT = "UPLOADED_TEXT"
    UPLOADED_PDF = "UPLOADED_PDF"
    UPLOADED_DOCX = "UPLOADED_DOCX"
    APPROVED_WEBSITE = "APPROVED_WEBSITE"
    STRUCTURED_RECORD = "STRUCTURED_RECORD"
    ANSWER_KEY = "ANSWER_KEY"


class SourceState(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


# Only passages whose source is in one of these states may be used as evidence.
RETRIEVABLE_SOURCE_STATES = frozenset({SourceState.APPROVED})


class ClaimStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TopLevelStatus(StrEnum):
    VERIFIED = "VERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTRADICTION = "CONTRADICTION"
    ERROR = "ERROR"
    # Response-only: the deterministic release gate NEVER emits this. The
    # auto-discovery orchestration sets it when an abstention can be backed by
    # candidate web sources the user may approve. Never persisted as an Answer.
    NEEDS_SOURCES = "NEEDS_SOURCES"


class PipelineStage(StrEnum):
    VALIDATE_INPUT = "VALIDATE_INPUT"
    RESOLVE_DETERMINISTIC_QUESTION = "RESOLVE_DETERMINISTIC_QUESTION"
    RETRIEVE = "RETRIEVE"
    DRAFT = "DRAFT"
    EXTRACT_CLAIMS = "EXTRACT_CLAIMS"
    VERIFY_CLAIMS = "VERIFY_CLAIMS"
    REVISE = "REVISE"
    RELEASE_GATE = "RELEASE_GATE"
    PERSIST_AUDIT = "PERSIST_AUDIT"
    COMPLETE = "COMPLETE"


class QueueStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class ModelProviderKind(StrEnum):
    NONE = "none"          # deterministic extractive, no model
    CLAUDE_CODE = "claude_code"  # answered by a Claude Code worker session
    OLLAMA = "ollama"      # local Ollama server (keyless, offline)
    MOCK = "mock"          # fixture-driven, tests only
    ANTHROPIC = "anthropic"  # reserved for future API-key path


# The canonical default abstention message. Used verbatim by the release gate.
DEFAULT_ABSTENTION_MESSAGE = (
    "I do not have enough verified information in the approved learning "
    "materials to answer that reliably."
)
