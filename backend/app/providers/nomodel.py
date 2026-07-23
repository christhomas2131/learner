"""Deterministic no-model provider (extractive).

Produces answers assembled entirely from exact sentences of approved passages.
Every claim it emits is a verbatim substring of its cited passage, so the
verify step confirms it by pure substring matching. Blunt prose, zero
hallucination, no external dependency. This is the always-on baseline.
"""

from __future__ import annotations

from app.core.enums import ClaimStatus
from app.providers.base import ModelProvider
from app.providers.text_utils import (
    best_sentence,
    content_tokens,
    normalize_text,
    quotation_in_passage,
)
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

    def __init__(self, max_claims: int = 4) -> None:
        self._max_claims = max_claims

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        # Gather the most relevant sentence from each passage that shares topical
        # content with the question, then order by relevance and drop near-
        # duplicates so the grounded answer reads as clean prose rather than
        # repeating the same fact. Every sentence stays a verbatim substring, so
        # the verifier still confirms it — this is synthesis, never generation.
        # Relevance guard for extractive answers: a sentence is relevant when it
        # shares 2+ content words with the question, OR shares one *substantive*
        # word (length >= 6, e.g. "photosynthesis"). A single short common word
        # ("world", "cup") is never enough. Single-content-word questions
        # ("What is DNA?") only need that one word.
        q_content = set(content_tokens(question))
        single = len(q_content) <= 1

        def _relevant(overlap: set[str]) -> bool:
            if single:
                return len(overlap) >= 1
            return len(overlap) >= 2 or any(len(t) >= 6 for t in overlap)

        candidates: list[tuple[int, str, RetrievedPassage]] = []
        for p in passages:
            sentence = best_sentence(p.text, question).strip()
            if not sentence:
                continue
            overlap = q_content & set(content_tokens(sentence))
            if not _relevant(overlap):
                continue
            candidates.append((len(overlap), sentence, p))

        candidates.sort(key=lambda c: c[0], reverse=True)

        claims: list[DraftClaim] = []
        answer_parts: list[str] = []
        seen: list[str] = []
        for _score, sentence, p in candidates:
            if len(claims) >= self._max_claims:
                break
            norm = normalize_text(sentence)
            # Skip if this sentence is contained in (or contains) one already used.
            if any(norm in s or s in norm for s in seen):
                continue
            seen.append(norm)
            n = len(claims) + 1
            claims.append(
                DraftClaim(
                    claim_id=f"claim-{n}",
                    text=sentence,
                    material=True,
                    cited_passage_ids=[p.passage_id],
                )
            )
            answer_parts.append(f"{sentence} [{n}]")
        return DraftResponse(answer=" ".join(answer_parts), claims=claims)

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
