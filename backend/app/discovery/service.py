"""Discovery orchestration: run enabled providers, fuse, and ingest on confirm."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import SourceState
from app.core.logging import get_logger
from app.db.base import new_uuid
from app.discovery.fusion import fuse_candidates
from app.discovery.models import Candidate
from app.discovery.providers import enabled_providers
from app.ingestion.service import (
    DuplicateSourceError,
    IngestionError,
    ingest_website,
    set_source_state,
)
from app.models import Source

log = get_logger("discovery")


async def discover(query: str, *, limit: int | None = None) -> tuple[str, list[Candidate]]:
    """Search all enabled providers concurrently and return (discovery_id, fused)."""
    cap = limit or settings.AUTO_DISCOVERY_MAX_CANDIDATES
    provs = enabled_providers()
    results = await asyncio.gather(
        *(p.search(query, limit=cap) for p in provs), return_exceptions=True
    )
    lists: list[list[Candidate]] = []
    for prov, res in zip(provs, results, strict=False):
        if isinstance(res, BaseException):
            log.warning("provider_raised", provider=prov.name, error=str(res))
            continue
        lists.append(res)
    fused = fuse_candidates(lists, k=settings.RRF_K, limit=cap)
    log.info("discovery_done", query=query, providers=len(provs), candidates=len(fused))
    return new_uuid(), fused


async def ingest_and_approve(
    session: AsyncSession, *, user_id: str,
    sources: list[tuple[str, str | None]], subject_id: str | None = None,
) -> tuple[list[Source], list[str]]:
    """Ingest each chosen (url, title) as an APPROVED website source.

    Re-fetches every URL server-side (SSRF-guarded). Returns
    (approved_sources, errors); a URL that fails to fetch is skipped rather than
    aborting the batch — the caller decides what to do if *all* fail.
    """
    approved: list[Source] = []
    errors: list[str] = []
    for url, title in sources:
        try:
            src = await ingest_website(
                session, user_id=user_id, url=url, title=title,
                subject_id=subject_id, discovered=True,
            )
        except DuplicateSourceError as e:
            existing = await session.get(Source, str(e.args[0])) if e.args else None
            if existing is None:
                errors.append(f"{url}: already ingested")
                continue
            src = existing
        except IngestionError as e:
            errors.append(f"{url}: {e}")
            continue
        await set_source_state(session, src, SourceState.APPROVED)
        approved.append(src)
    return approved, errors
