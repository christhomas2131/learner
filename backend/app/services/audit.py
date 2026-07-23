"""Persist a completed pipeline result: answer, claims, citations, verification,
and an immutable audit record."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import new_uuid, utcnow
from app.models import (
    Answer,
    AuditRecord,
    Citation,
    Claim,
    Message,
    Session,
    User,
    VerificationResult,
)
from app.pipeline.engine import PipelineResult
from app.schemas.api import AnswerResponse, PipelineInfo


async def persist_result(
    session: AsyncSession,
    *,
    user_id: str,
    result: PipelineResult,
    store_message: bool = True,
) -> tuple[str, str]:
    """Persist the result. Returns (answer_id, audit_id)."""
    answer = Answer(
        session_id=result.session_id or new_uuid(),
        request_id=result.request_id,
        question=result.question,
        status=result.status,
        answer_text=result.answer,
        attempts=result.attempts,
        duration_ms=result.duration_ms,
        completed_stages=result.completed_stages,
        provider=result.provider,
        model_identifier=result.model_identifier,
    )
    session.add(answer)
    await session.flush()

    for c in result.claims:
        claim = Claim(
            answer_id=answer.id, label=c.claim_id, text=c.text,
            material=c.material, status=c.status,
        )
        session.add(claim)
        await session.flush()
        for cit in c.citations:
            session.add(Citation(
                claim_id=claim.id, citation_number=cit.citation_number,
                source_id=cit.source_id, passage_id=cit.passage_id,
            ))
        session.add(VerificationResult(
            claim_id=claim.id, status=c.status, explanation=c.verifier_explanation,
            evidence=[e.model_dump() for e in c.evidence], verified_at=utcnow(),
        ))

    audit = AuditRecord(
        request_id=result.request_id, user_id=user_id,
        session_id=result.session_id, answer_id=answer.id,
        question=result.question, status=result.status, provider=result.provider,
        snapshot=_snapshot(result),
    )
    session.add(audit)
    await session.flush()
    answer.audit_id = audit.id

    if store_message and result.session_id:
        session.add(Message(session_id=result.session_id, role="assistant",
                            content=result.answer))

    await session.commit()
    return answer.id, audit.id


async def load_answer_response(
    session: AsyncSession, user: User, answer_id: str
) -> AnswerResponse | None:
    """Reconstruct the full AnswerResponse for a persisted answer (ownership-scoped)."""
    ans = (
        await session.execute(
            select(Answer).join(Session, Answer.session_id == Session.id)
            .where(Answer.id == answer_id, Session.user_id == user.id)
        )
    ).scalars().first()
    if ans is None:
        return None
    audit = (
        await session.execute(select(AuditRecord).where(AuditRecord.answer_id == answer_id))
    ).scalars().first()
    if audit and audit.snapshot:
        data = dict(audit.snapshot)
        data["audit_id"] = audit.id
        return AnswerResponse.model_validate(data)
    return None


def _snapshot(result: PipelineResult) -> dict:
    return to_response(result, audit_id=None).model_dump(mode="json")


def to_response(result: PipelineResult, *, audit_id: str | None) -> AnswerResponse:
    return AnswerResponse(
        request_id=result.request_id,
        audit_id=audit_id,
        session_id=result.session_id,
        status=result.status,
        question=result.question,
        answer=result.answer,
        claims=result.claims,
        sources=result.sources,
        pipeline=PipelineInfo(
            attempts=result.attempts, duration_ms=result.duration_ms,
            completed_stages=result.completed_stages, provider=result.provider,
            model_identifier=result.model_identifier,
        ),
        contradiction_detail=result.contradiction_detail,
        created_at=result.created_at,
    )
