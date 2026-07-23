"""Postgres full-text GIN index (no-op on SQLite, which uses FTS5)

Revision ID: pgfts0001
Revises: e2e479408f46
Create Date: 2026-07-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "pgfts0001"
down_revision: Union[str, None] = "e2e479408f46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_passages_tsv "
            "ON source_passages USING gin (to_tsvector('english', text))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_passages_tsv")
