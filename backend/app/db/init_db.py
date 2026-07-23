"""Create schema + full-text index. Dev/test convenience alongside Alembic."""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import settings
from app.db.base import Base, engine


async def create_all() -> None:
    from app.models import models  # noqa: F401 - register mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.is_sqlite:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts "
                    "USING fts5(passage_id UNINDEXED, source_id UNINDEXED, text)"
                )
            )
        else:
            # Postgres: GIN index backing to_tsvector full-text search.
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_passages_tsv "
                    "ON source_passages USING gin (to_tsvector('english', text))"
                )
            )


async def drop_all() -> None:
    async with engine.begin() as conn:
        if settings.is_sqlite:
            await conn.execute(text("DROP TABLE IF EXISTS passage_fts"))
        await conn.run_sync(Base.metadata.drop_all)
