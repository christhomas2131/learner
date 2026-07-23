"""Create schema + FTS index. Dev/test convenience alongside Alembic."""

from __future__ import annotations

from sqlalchemy import text

from app.db.base import Base, engine


async def create_all() -> None:
    from app.models import models  # noqa: F401 - register mappers

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts "
                "USING fts5(passage_id UNINDEXED, source_id UNINDEXED, text)"
            )
        )


async def drop_all() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS passage_fts"))
        await conn.run_sync(Base.metadata.drop_all)
