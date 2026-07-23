"""Public API response contracts.

The final answer schema is strict and stable — the frontend validates against
it with Zod. Keep field names in sync with the TypeScript types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ClaimStatus, TopLevelStatus


class CitationOut(BaseModel):
    citation_number: int
    source_id: str
    passage_id: str


class EvidenceOut(BaseModel):
    source_id: str
    passage_id: str
    quotation: str
    retrieval_score: float


class ClaimOut(BaseModel):
    claim_id: str
    text: str
    material: bool
    status: ClaimStatus
    citations: list[CitationOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    verifier_explanation: str = ""


class SourceOut(BaseModel):
    source_id: str
    title: str
    source_type: str
    approved: bool
    author: str | None = None
    organization: str | None = None
    publication_date: str | None = None
    url: str | None = None


class PipelineInfo(BaseModel):
    attempts: int
    duration_ms: int
    completed_stages: list[str]
    provider: str
    model_identifier: str | None = None


class AnswerResponse(BaseModel):
    request_id: str
    audit_id: str | None
    session_id: str | None
    status: TopLevelStatus
    question: str
    answer: str
    claims: list[ClaimOut] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)
    pipeline: PipelineInfo
    contradiction_detail: str | None = None
    created_at: datetime
