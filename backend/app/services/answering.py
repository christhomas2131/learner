"""Glue: run the grounded pipeline for a question and persist everything."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ModelProviderKind
from app.models import User
from app.pipeline.engine import PipelineResult
from app.pipeline.events import EventEmitter
from app.providers.base import ModelProvider
from app.services.audit import persist_result
from app.services.pipeline_runner import run_pipeline
from app.services.sessions import add_user_message, ensure_session, touch_session


async def answer_and_persist(
    session: AsyncSession, user: User, *, question: str, session_id: str | None,
    subject_id: str | None, approved_source_ids: list[str] | None,
    provider: ModelProvider | None = None,
    provider_kind: ModelProviderKind = ModelProviderKind.NONE,
    emitter: EventEmitter | None = None,
) -> tuple[PipelineResult, str, str, str]:
    """Returns (result, answer_id, audit_id, session_id)."""
    sess = await ensure_session(session, user, session_id, subject_id, question)
    await add_user_message(session, sess.id, question)
    result = await run_pipeline(
        session, user.id, question=question, session_id=sess.id,
        approved_source_ids=approved_source_ids, provider=provider,
        provider_kind=provider_kind, emitter=emitter,
    )
    answer_id, audit_id = await persist_result(session, user_id=user.id, result=result)
    await touch_session(session, sess)
    return result, answer_id, audit_id, sess.id
