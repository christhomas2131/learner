"""Internal pipeline data contracts (Pydantic).

Every model response is parsed into these before the deterministic layer acts
on it. Validation failures are treated as errors, never silently coerced.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.enums import ClaimStatus


class RetrievedPassage(BaseModel):
    passage_id: str
    source_id: str
    source_title: str
    source_type: str
    text: str
    chunk_index: int
    retrieval_score: float
    approved: bool
    source_metadata: dict = Field(default_factory=dict)


class DraftClaim(BaseModel):
    claim_id: str
    text: str
    material: bool = True
    cited_passage_ids: list[str] = Field(default_factory=list)

    @field_validator("claim_id", "text")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be non-empty")
        return v


class DraftResponse(BaseModel):
    answer: str
    claims: list[DraftClaim]


class VerifierEvidence(BaseModel):
    passage_id: str
    quotation: str


class VerifierResult(BaseModel):
    claim_id: str
    status: ClaimStatus
    evidence: list[VerifierEvidence] = Field(default_factory=list)
    explanation: str = ""
