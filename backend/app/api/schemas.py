"""Request/response bodies for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.enums import ClaimStatus, QueueStatus, SourceState, SourceType, TopLevelStatus

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# ---- Answers ---- #

AskMode = str  # "grounded" | "premium"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    subject_id: str | None = None
    approved_source_ids: list[str] | None = None
    mode: AskMode = "grounded"


# ---- Sessions ---- #


class CreateSessionRequest(BaseModel):
    title: str | None = None
    subject_id: str | None = None


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    saved: bool | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    subject_id: str | None
    saved: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class AnswerSummary(BaseModel):
    id: str
    question: str
    status: TopLevelStatus
    answer_text: str
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut] = Field(default_factory=list)
    answers: list[AnswerSummary] = Field(default_factory=list)


# ---- Subjects ---- #


class CreateSubjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class SubjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    source_count: int = 0


# ---- Sources ---- #


class UpdateSourceRequest(BaseModel):
    title: str | None = None
    subject_id: str | None = None
    collection_id: str | None = None
    author: str | None = None
    organization: str | None = None
    publication_date: str | None = None
    url: str | None = None


class SourceOut(BaseModel):
    id: str
    title: str
    source_type: SourceType
    state: SourceState
    is_demo: bool
    subject_id: str | None
    author: str | None
    organization: str | None
    publication_date: str | None
    url: str | None
    content_hash: str
    original_filename: str | None
    byte_size: int
    passage_count: int = 0
    created_at: datetime
    updated_at: datetime


class PassageOut(BaseModel):
    id: str
    chunk_index: int
    text: str


# ---- Queue (premium/Claude Code worker) ---- #


class QueueItemOut(BaseModel):
    id: str
    session_id: str
    request_id: str
    question: str
    status: QueueStatus
    answer_id: str | None
    error: str | None
    created_at: datetime


class EnqueueResponse(BaseModel):
    queue_id: str
    session_id: str
    request_id: str
    status: QueueStatus


# ---- Analytics ---- #


class Analytics(BaseModel):
    questions_asked: int
    verified_rate: float
    abstention_rate: float
    contradiction_rate: float
    error_rate: float
    average_duration_ms: float
    average_claim_count: float
    status_breakdown: dict[str, int]
    sessions_over_time: list[dict]
    most_studied_subjects: list[dict]
    source_usage: list[dict]
    recent_activity: list[dict]


# ---- Claim status re-export for typing convenience ---- #

__all__ = [
    "Analytics", "AnswerSummary", "AskRequest", "ClaimStatus", "CreateSessionRequest",
    "CreateSubjectRequest", "EnqueueResponse", "MessageOut", "Page", "PassageOut",
    "QueueItemOut", "SessionDetail", "SessionOut", "SourceOut", "SubjectOut",
    "UpdateSessionRequest", "UpdateSourceRequest",
]
