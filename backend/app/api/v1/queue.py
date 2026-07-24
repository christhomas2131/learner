"""Premium question queue endpoints (client polls these; worker drains via CLI)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, get_session, pagination
from app.api.errors import NotFoundError
from app.api.schemas import Page, QueueItemOut
from app.core.enums import QueueStatus
from app.db.base import AsyncSessionLocal
from app.models import QuestionQueue, User
from app.services import queue as svc
from app.services.audit import load_answer_response
from app.services.event_hub import get_hub
from app.services.user import get_or_create_demo_user

router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _to_out(item: QuestionQueue) -> QueueItemOut:
    return QueueItemOut(
        id=item.id, session_id=item.session_id, request_id=item.request_id,
        question=item.question, status=item.status, answer_id=item.answer_id,
        error=item.error, created_at=item.created_at,
    )


@router.get("/queue", response_model=Page[QueueItemOut])
async def list_queue(
    page: Pagination = Depends(pagination),
    status: QueueStatus | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[QueueItemOut]:
    rows, total = await svc.list_items(session, user, status, page.limit, page.offset)
    return Page(items=[_to_out(i) for i in rows], total=total, limit=page.limit, offset=page.offset)


@router.get("/queue/{item_id}/events")
async def stream_queue_events(
    item_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    item = await svc.get_item(session, user, item_id)
    if item is None:
        raise NotFoundError("Queue item not found.")

    async def emit_terminal_from_db() -> str | None:
        """Build the authoritative frame if the item already reached a terminal state."""
        async with AsyncSessionLocal() as s:
            u = await get_or_create_demo_user(s)
            it = await svc.get_item(s, u, item_id)
            if it is None:
                return None
            if it.status == QueueStatus.DONE and it.answer_id:
                resp = await load_answer_response(s, u, it.answer_id)
                if resp:
                    return _sse("completed", resp.model_dump(mode="json"))
            if it.status == QueueStatus.FAILED:
                return _sse("failed", {"message": it.error or "Worker failed"})
            return None

    async def gen() -> AsyncIterator[str]:
        hub = get_hub()
        q = hub.subscribe(item_id)
        try:
            # If it already finished before we subscribed, deliver immediately.
            terminal = await emit_terminal_from_db()
            if terminal:
                yield terminal
                return
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield _sse(ev["event"], ev.get("data", {}))
                    if ev.get("terminal"):
                        break
                except TimeoutError:
                    # Safety net: hub events can be missed on a subscribe race.
                    terminal = await emit_terminal_from_db()
                    if terminal:
                        yield terminal
                        break
                    # Keepalive comment so idle proxies don't cut a long premium wait.
                    yield ": keepalive\n\n"
        finally:
            hub.unsubscribe(item_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/queue/{item_id}", response_model=QueueItemOut)
async def get_queue_item(
    item_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> QueueItemOut:
    item = await svc.get_item(session, user, item_id)
    if item is None:
        raise NotFoundError("Queue item not found.")
    return _to_out(item)
