"""Pipeline event types for streaming (SSE) and diagnostics."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# Supported event names (mirrored by the frontend SSE client).
REQUEST_STARTED = "request_started"
PIPELINE_STAGE = "pipeline_stage"
SOURCE_RETRIEVED = "source_retrieved"
DRAFT_CREATED = "draft_created"
CLAIM_VERIFICATION = "claim_verification"
REVISION_STARTED = "revision_started"
RELEASE_GATE = "release_gate"
COMPLETED = "completed"
FAILED = "failed"


@dataclass
class PipelineEvent:
    event: str
    stage: str | None = None
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "stage": self.stage,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp,
        }


EventEmitter = Callable[[PipelineEvent], Awaitable[None]]


async def noop_emitter(_: PipelineEvent) -> None:
    return None
