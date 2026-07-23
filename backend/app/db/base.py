"""Async SQLAlchemy engine, session factory, and declarative base.

UUID primary keys are stored as 36-char strings (portable across SQLite and
PostgreSQL). Timestamps are timezone-aware UTC.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, TypeDecorator, event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

if settings.is_sqlite:
    # WAL + a busy timeout so the API server and the Claude Code worker can share
    # the SQLite file without "database is locked" errors.
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class GUID(TypeDecorator):
    """Platform-independent UUID stored as a 36-char string."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: object, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: object, dialect: object) -> str | None:
        if value is None:
            return None
        return str(value)


class UTCDateTime(TypeDecorator):
    """DateTime that always returns timezone-aware UTC values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: UTCDateTime,
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
