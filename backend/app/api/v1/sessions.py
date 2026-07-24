"""Session CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, get_session, pagination
from app.api.errors import NotFoundError
from app.api.schemas import (
    AnswerSummary,
    CreateSessionRequest,
    MessageOut,
    Page,
    SessionDetail,
    SessionOut,
    UpdateSessionRequest,
)
from app.models import Session, User
from app.services import sessions as svc

router = APIRouter()


def _to_out(s: Session) -> SessionOut:
    return SessionOut(
        id=s.id, title=s.title, subject_id=s.subject_id, saved=s.saved,
        is_demo=s.is_demo, created_at=s.created_at, updated_at=s.updated_at,
    )


@router.get("/sessions", response_model=Page[SessionOut])
async def list_sessions(
    page: Pagination = Depends(pagination),
    saved: bool = Query(False),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[SessionOut]:
    rows, total = await svc.list_sessions(session, user, page.limit, page.offset, saved, search)
    return Page(items=[_to_out(s) for s in rows], total=total, limit=page.limit, offset=page.offset)


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionOut:
    obj = Session(user_id=user.id, title=body.title or "New session", subject_id=body.subject_id)
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionDetail:
    obj = await svc.get_owned_session(session, user, session_id)
    if obj is None:
        raise NotFoundError("Session not found.")
    messages = await svc.session_messages(session, session_id)
    answers = await svc.session_answers(session, session_id)
    return SessionDetail(
        **_to_out(obj).model_dump(),
        messages=[MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
                  for m in messages],
        answers=[AnswerSummary(id=a.id, question=a.question, status=a.status,
                               answer_text=a.answer_text, created_at=a.created_at) for a in answers],
    )


@router.get("/sessions/{session_id}/export.docx")
async def export_session(
    session_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    from app.services.export import export_session_docx

    filename, data = await export_session_docx(session, user, session_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionOut:
    obj = await svc.get_owned_session(session, user, session_id)
    if obj is None:
        raise NotFoundError("Session not found.")
    if body.title is not None:
        obj.title = body.title
    if body.saved is not None:
        obj.saved = body.saved
    await session.commit()
    await session.refresh(obj)
    return _to_out(obj)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    obj = await svc.get_owned_session(session, user, session_id)
    if obj is None:
        raise NotFoundError("Session not found.")
    await session.delete(obj)
    await session.commit()
