"""Deterministic no-model provider (extractive).

Produces answers assembled entirely from exact sentences of approved passages.
Every claim it emits is a verbatim substring of its cited passage, so the
verify step confirms it by pure substring matching. Blunt prose, zero
hallucination, no external dependency. This is the always-on baseline.
"""

from __future__ import annotations

from app.core.enums import ClaimStatus
from app.providers.base import ModelProvider
from app.providers.text_utils import best_sentence, quotation_in_passage, sentence_relevance
from app.schemas.pipeline import (
    DraftClaim,
    DraftResponse,
    RetrievedPassage,
    VerifierEvidence,
    VerifierResult,
)


class NoModelProvider(ModelProvider):
    name = "none"
    model_identifier = None

    def __init__(self, max_claims: int = 3) -> None:
        self._max_claims = max_claims

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        # Scan ALL retrieved passages (not just the first few) and assert a claim
        # only when a passage shares topical content with the question. This keeps
        # grounded answers conservative even if a hybrid retriever reorders the
        # pool so that a lexical match sits below a semantic-only one.
        claims: list[DraftClaim] = []
        answer_parts: list[str] = []
        n = 0
        for p in passages:
            if len(claims) >= self._max_claims:
                break
            sentence = best_sentence(p.text, question).strip()
            if not sentence or sentence_relevance(p.text, question) < 1:
                continue
            n += 1
            claims.append(
                DraftClaim(
                    claim_id=f"claim-{n}",
                    text=sentence,
                    material=True,
                    cited_passage_ids=[p.passage_id],
                )
            )
            answer_parts.append(f"{sentence} [{n}]")
        answer = " ".join(answer_parts)
        return DraftResponse(answer=answer, claims=claims)

    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        by_id = {p.passage_id: p for p in passages}
        results: list[VerifierResult] = []
        for claim in claims:
            evidence: list[VerifierEvidence] = []
            for pid in claim.cited_passage_ids:
                passage = by_id.get(pid)
                if passage and quotation_in_passage(claim.text, passage.text):
                    evidence.append(VerifierEvidence(passage_id=pid, quotation=claim.text))
            if evidence:
                results.append(
                    VerifierResult(
                        claim_id=claim.claim_id,
                        status=ClaimStatus.SUPPORTED,
                        evidence=evidence,
                        explanation="Claim text is a verbatim substring of the cited approved passage.",
                    )
                )
            else:
                results.append(
                    VerifierResult(
                        claim_id=claim.claim_id,
                        status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                        evidence=[],
                        explanation="No cited approved passage contains this text.",
                    )
                )
        return results
