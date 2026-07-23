"""ORM models for the verified learning app.

Single-user personal deployment: a `User` still exists (ownership columns,
audit trail, future multi-user seam) but there is no auth — a fixed demo user
owns everything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ClaimStatus,
    QueueStatus,
    SourceState,
    SourceType,
    TopLevelStatus,
)
from app.db.base import GUID, Base, TimestampMixin, new_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Local User")
    is_local_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    settings: Mapped[UserSettings | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), unique=True, index=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    user: Mapped[User] = relationship(back_populates="settings")


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceCollection(Base, TimestampMixin):
    __tablename__ = "source_collections"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("subjects.id"), nullable=True, index=True
    )
    collection_id: Mapped[str | None] = mapped_column(
        GUID, ForeignKey("source_collections.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[SourceType] = mapped_column(String(40))
    state: Mapped[SourceState] = mapped_column(String(30), default=SourceState.UPLOADED, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    stored_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)

    # Version / supersession metadata (spec: never infer supersession from upload date).
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_source_id: Mapped[str | None] = mapped_column(GUID, nullable=True)

    # For STRUCTURED_RECORD / ANSWER_KEY / APPROVED_WEBSITE payloads.
    structured_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    passages: Mapped[list[SourcePassage]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    @property
    def is_retrievable(self) -> bool:
        return self.state == SourceState.APPROVED


class SourcePassage(Base, TimestampMixin):
    __tablename__ = "source_passages"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(GUID, ForeignKey("sources.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[Source] = relationship(back_populates="passages")


Index("ix_passage_source_chunk", SourcePassage.source_id, SourcePassage.chunk_index)


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("subjects.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="New session")
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


Index("ix_sessions_user_updated", Session.user_id, Session.updated_at)


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(GUID, ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)

    session: Mapped[Session] = relationship(back_populates="messages")


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(GUID, ForeignKey("sessions.id"), index=True)
    message_id: Mapped[str | None] = mapped_column(GUID, ForeignKey("messages.id"), nullable=True)
    request_id: Mapped[str] = mapped_column(GUID, index=True)
    audit_id: Mapped[str | None] = mapped_column(GUID, nullable=True)

    question: Mapped[str] = mapped_column(Text)
    status: Mapped[TopLevelStatus] = mapped_column(String(30), index=True)
    answer_text: Mapped[str] = mapped_column(Text, default="")

    attempts: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    completed_stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(30), default="none")
    model_identifier: Mapped[str | None] = mapped_column(String(80), nullable=True)

    claims: Mapped[list[Claim]] = relationship(
        back_populates="answer", cascade="all, delete-orphan"
    )


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    answer_id: Mapped[str] = mapped_column(GUID, ForeignKey("answers.id"), index=True)
    label: Mapped[str] = mapped_column(String(40))  # e.g. "claim-1"
    text: Mapped[str] = mapped_column(Text)
    material: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[ClaimStatus] = mapped_column(String(30), default=ClaimStatus.INSUFFICIENT_EVIDENCE)

    answer: Mapped[Answer] = relationship(back_populates="claims")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    verification: Mapped[VerificationResult | None] = relationship(
        back_populates="claim", uselist=False, cascade="all, delete-orphan"
    )


class Citation(Base, TimestampMixin):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    claim_id: Mapped[str] = mapped_column(GUID, ForeignKey("claims.id"), index=True)
    citation_number: Mapped[int] = mapped_column(Integer)
    source_id: Mapped[str] = mapped_column(GUID, ForeignKey("sources.id"))
    passage_id: Mapped[str] = mapped_column(GUID, ForeignKey("source_passages.id"))

    claim: Mapped[Claim] = relationship(back_populates="citations")


class VerificationResult(Base, TimestampMixin):
    __tablename__ = "verification_results"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    claim_id: Mapped[str] = mapped_column(GUID, ForeignKey("claims.id"), unique=True, index=True)
    status: Mapped[ClaimStatus] = mapped_column(String(30))
    explanation: Mapped[str] = mapped_column(Text, default="")
    # [{source_id, passage_id, quotation, retrieval_score}]
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    claim: Mapped[Claim] = relationship(back_populates="verification")


class AuditRecord(Base, TimestampMixin):
    __tablename__ = "audit_records"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    request_id: Mapped[str] = mapped_column(GUID, index=True)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    answer_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[TopLevelStatus] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(30), default="none")
    # Full immutable snapshot of the pipeline result for later inspection.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(GUID, ForeignKey("sources.id"), index=True)
    state: Mapped[str] = mapped_column(String(30), default="PENDING")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_count: Mapped[int] = mapped_column(Integer, default=0)


class QuestionQueue(Base, TimestampMixin):
    """Queue of questions awaiting a Claude Code worker (premium mode).

    The web UI enqueues a PENDING row; a running Claude Code session claims it
    (PROCESSING), runs the pipeline as the model, and writes back DONE/FAILED.
    """

    __tablename__ = "question_queue"

    id: Mapped[str] = mapped_column(GUID, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(GUID, ForeignKey("sessions.id"), index=True)
    request_id: Mapped[str] = mapped_column(GUID, index=True)
    question: Mapped[str] = mapped_column(Text)
    approved_source_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[QueueStatus] = mapped_column(String(20), default=QueueStatus.PENDING, index=True)
    answer_id: Mapped[str | None] = mapped_column(GUID, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(nullable=True)
