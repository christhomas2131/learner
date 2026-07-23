"""Build and run the pipeline for HTTP/CLI callers (grounded path)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ModelProviderKind
from app.db.base import new_uuid
from app.pipeline.engine import PipelineResult, VerifiedLearningPipeline
from app.pipeline.events import EventEmitter
from app.providers.base import ModelProvider
from app.providers.factory import get_provider
from app.retrieval.base import Retriever
from app.retrieval.embeddings import get_embedder
from app.retrieval.fts import SqliteFtsRetriever
from app.retrieval.hybrid import HybridRetriever
from app.services.records import load_resolver_records


def _build_retriever(session: AsyncSession) -> Retriever:
    # Hybrid (semantic + lexical) when embeddings are available; else FTS-only.
    if settings.RETRIEVAL_USE_EMBEDDINGS and get_embedder().available:
        return HybridRetriever(session, min_score=settings.RETRIEVAL_MIN_SCORE, rrf_k=settings.RRF_K)
    return SqliteFtsRetriever(session, min_score=settings.RETRIEVAL_MIN_SCORE)


async def build_pipeline(
    session: AsyncSession, user_id: str, provider: ModelProvider | None = None,
    provider_kind: ModelProviderKind = ModelProviderKind.NONE,
) -> VerifiedLearningPipeline:
    retriever = _build_retriever(session)
    definitions, answer_keys = await load_resolver_records(session, user_id)
    return VerifiedLearningPipeline(
        retriever, provider or get_provider(provider_kind),
        retrieval_limit=settings.RETRIEVAL_LIMIT,
        max_model_retries=settings.MAX_MODEL_RETRIES,
        max_pipeline_attempts=settings.MAX_PIPELINE_ATTEMPTS,
        definition_records=definitions, answer_key_records=answer_keys,
    )


async def run_pipeline(
    session: AsyncSession, user_id: str, *, question: str, session_id: str | None,
    approved_source_ids: list[str] | None, provider: ModelProvider | None = None,
    provider_kind: ModelProviderKind = ModelProviderKind.NONE,
    emitter: EventEmitter | None = None,
) -> PipelineResult:
    pipeline = await build_pipeline(session, user_id, provider, provider_kind)
    return await pipeline.run(
        request_id=new_uuid(), question=question, session_id=session_id,
        approved_source_ids=approved_source_ids, emitter=emitter,
    )
