"""Premium question queue endpoints (client polls these; worker drains via CLI)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, get_session, pagination
from app.api.errors import NotFoundError
from app.api.schemas import Page, QueueItemOut
from app.core.enums import QueueStatus
from app.models import QuestionQueue, User
from app.services import queue as svc

router = APIRouter()


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
