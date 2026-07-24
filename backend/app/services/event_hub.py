"""In-process pub/sub for streaming premium pipeline events.

The drainer (producer) and the SSE endpoint (consumers) run in the same API
process, so a simple in-memory hub keyed by queue-item id is enough. Each
subscriber gets its own asyncio.Queue.
"""

from __future__ import annotations

import asyncio
from typing import Any


class EventHub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, key: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subs.setdefault(key, set()).add(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._subs.get(key)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(key, None)

    async def publish(self, key: str, event: dict[str, Any]) -> None:
        for q in list(self._subs.get(key, ())):
            q.put_nowait(event)


_hub = EventHub()


def get_hub() -> EventHub:
    return _hub
