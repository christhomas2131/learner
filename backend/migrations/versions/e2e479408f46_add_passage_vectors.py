"""add passage_vectors

Revision ID: e2e479408f46
Revises: 4415af868d9c
Create Date: 2026-07-23 15:14:05.273653
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.db.base  # custom GUID / UTCDateTime types


revision: str = 'e2e479408f46'
down_revision: Union[str, None] = '4415af868d9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate also flagged the FTS5 shadow tables (passage_fts_*) as
    # "removed"; those are virtual-table internals and must not be dropped. Only
    # the passage_vectors table is applied here.
    op.create_table(
        'passage_vectors',
        sa.Column('passage_id', app.db.base.GUID(length=36), nullable=False),
        sa.Column('source_id', app.db.base.GUID(length=36), nullable=False),
        sa.Column('dim', sa.Integer(), nullable=False),
        sa.Column('vector', sa.JSON(), nullable=False),
        sa.Column('created_at', app.db.base.UTCDateTime(timezone=True), nullable=False),
        sa.Column('updated_at', app.db.base.UTCDateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['passage_id'], ['source_passages.id']),
        sa.PrimaryKeyConstraint('passage_id'),
    )
    with op.batch_alter_table('passage_vectors', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_passage_vectors_source_id'), ['source_id'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('passage_vectors', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_passage_vectors_source_id'))
    op.drop_table('passage_vectors')
