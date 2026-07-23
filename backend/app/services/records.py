"""Load approved structured records for the deterministic resolvers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SourceState, SourceType
from app.models import Source


async def load_resolver_records(
    session: AsyncSession, user_id: str
) -> tuple[list[dict], list[dict]]:
    """Return (definition_records, answer_key_records) from APPROVED sources."""
    stmt = select(Source).where(
        Source.user_id == user_id,
        Source.state == SourceState.APPROVED,
        Source.source_type.in_([SourceType.STRUCTURED_RECORD, SourceType.ANSWER_KEY]),
    )
    sources = (await session.execute(stmt)).scalars().all()

    definitions: list[dict] = []
    answer_keys: list[dict] = []
    for src in sources:
        data = src.structured_data or {}
        for rec in data.get("records", []):
            if "passage_id" not in rec:
                continue
            enriched = dict(rec)
            enriched["source_id"] = src.id
            if src.source_type == SourceType.STRUCTURED_RECORD:
                definitions.append(enriched)
            else:
                answer_keys.append(enriched)
    return definitions, answer_keys
