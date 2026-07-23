"""Answer endpoints: synchronous grounded answers, SSE streaming, premium queue.

- mode="grounded": run the deterministic pipeline inline (no model, always works).
- mode="premium": enqueue for a Claude Code worker; the client polls the queue
  or streams queue status. Premium answers never run inline (there is no model
  in the API process).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.errors import NotFoundError
from app.api.schemas import AskRequest, EnqueueResponse
from app.db.base import AsyncSessionLocal
from app.models import User
from app.pipeline.events import COMPLETED, PipelineEvent
from app.schemas.api import AnswerResponse
from app.services import queue as queue_svc
from app.services.answering import answer_and_persist
from app.services.audit import load_answer_response, to_response
from app.services.sessions import add_user_message, ensure_session, touch_session
from app.services.user import get_or_create_demo_user

router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/answers", response_model=AnswerResponse | EnqueueResponse)
async def create_answer(
    body: AskRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.mode == "premium":
        sess = await ensure_session(session, user, body.session_id, body.subject_id, body.question)
        await add_user_message(session, sess.id, body.question)
        await touch_session(session, sess)
        item = await queue_svc.enqueue(
            session, user, session_id=sess.id, question=body.question,
            approved_source_ids=body.approved_source_ids,
        )
        return EnqueueResponse(queue_id=item.id, session_id=sess.id,
                               request_id=item.request_id, status=item.status)

    result, answer_id, audit_id, _ = await answer_and_persist(
        session, user, question=body.question, session_id=body.session_id,
        subject_id=body.subject_id, approved_source_ids=body.approved_source_ids,
    )
    return to_response(result, audit_id=audit_id)


@router.get("/answers/{answer_id}", response_model=AnswerResponse)
async def get_answer(
    answer_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    resp = await load_answer_response(session, user, answer_id)
    if resp is None:
        raise NotFoundError("Answer not found.")
    return resp


@router.post("/answers/stream")
async def stream_answer(
    body: AskRequest,
    user: User = Depends(get_current_user),
):
    async def event_gen() -> AsyncIterator[str]:
        events: asyncio.Queue = asyncio.Queue()

        async def emitter(ev: PipelineEvent) -> None:
            await events.put(ev)

        async def runner() -> None:
            # Fresh session: this outlives the request-scoped dependency session.
            async with AsyncSessionLocal() as s:
                u = await get_or_create_demo_user(s)
                try:
                    if body.mode == "premium":
                        sess = await ensure_session(s, u, body.session_id, body.subject_id,
                                                    body.question)
                        await add_user_message(s, sess.id, body.question)
                        await touch_session(s, sess)
                        item = await queue_svc.enqueue(
                            s, u, session_id=sess.id, question=body.question,
                            approved_source_ids=body.approved_source_ids,
                        )
                        await events.put(("__enqueued__", {
                            "queue_id": item.id, "session_id": sess.id,
                            "request_id": item.request_id, "status": str(item.status),
                        }))
                    else:
                        result, _aid, audit_id, _sid = await answer_and_persist(
                            s, u, question=body.question, session_id=body.session_id,
                            subject_id=body.subject_id,
                            approved_source_ids=body.approved_source_ids, emitter=emitter,
                        )
                        resp = to_response(result, audit_id=audit_id)
                        await events.put(("__result__", resp.model_dump(mode="json")))
                except Exception as e:  # noqa: BLE001
                    await events.put(("__failed__", {"message": str(e)}))
                finally:
                    await events.put(None)

        task = asyncio.create_task(runner())
        try:
            while True:
                item = await events.get()
                if item is None:
                    break
                if isinstance(item, tuple):
                    kind, payload = item
                    if kind == "__result__":
                        yield _sse("completed", payload)
                    elif kind == "__enqueued__":
                        yield _sse("queued", payload)
                    elif kind == "__failed__":
                        yield _sse("failed", payload)
                    continue
                ev: PipelineEvent = item
                # The engine's own COMPLETED is superseded by the authoritative
                # "completed" event carrying the full response.
                if ev.event == COMPLETED:
                    continue
                yield _sse(ev.event, ev.to_dict())
        finally:
            await task

    return StreamingResponse(event_gen(), media_type="text/event-stream")
