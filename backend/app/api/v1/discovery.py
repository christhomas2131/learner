"""Auto source-discovery: confirm chosen candidates, ingest, and re-answer."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.errors import ValidationError
from app.api.schemas import ConfirmDiscoveryRequest
from app.discovery.service import ingest_and_approve
from app.models import User
from app.schemas.api import AnswerResponse
from app.services.answering import answer_and_persist
from app.services.audit import to_response

router = APIRouter()


@router.post("/discovery/confirm", response_model=AnswerResponse)
async def confirm_discovery(
    body: ConfirmDiscoveryRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnswerResponse:
    """Ingest the user-approved candidates as sources, then re-run the answer.

    Every chosen URL is re-fetched server-side (SSRF-guarded) and approved; the
    deterministic pipeline then answers over the enlarged corpus and still
    cites-or-abstains. Discovery does NOT re-trigger here (no loop).
    """
    approved, errors = await ingest_and_approve(
        session, user_id=user.id,
        sources=[(s.url, s.title) for s in body.sources],
        subject_id=body.subject_id,
    )
    if not approved:
        detail = "; ".join(errors) if errors else "the URLs could not be fetched."
        raise ValidationError(f"No sources could be added: {detail}")
    result, _answer_id, audit_id, _sid = await answer_and_persist(
        session, user, question=body.question, session_id=body.session_id,
        subject_id=body.subject_id, approved_source_ids=None,
    )
    return to_response(result, audit_id=audit_id)
