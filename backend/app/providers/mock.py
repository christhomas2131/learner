"""Deterministic mock provider for tests and offline fixtures.

Behavior is chosen per-question by matching a substring against a behavior map,
letting a single provider instance exercise every pipeline branch:
supported, unsupported/abstain, contradiction, malformed JSON, invented
citation, invented quotation, timeout, max-retries, model error, and
batch-integrity failures (omitted / unknown claim).
"""

from __future__ import annotations

from app.core.enums import ClaimStatus
from app.providers.base import (
    MalformedResponseError,
    ModelError,
    ModelProvider,
    ModelTimeoutError,
)
from app.providers.text_utils import best_sentence
from app.schemas.pipeline import (
    DraftClaim,
    DraftResponse,
    RetrievedPassage,
    VerifierEvidence,
    VerifierResult,
)

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
CONTRADICTION = "contradiction"
MALFORMED_JSON = "malformed_json"
INVENTED_CITATION = "invented_citation"
INVENTED_QUOTATION = "invented_quotation"
TIMEOUT = "timeout"
MODEL_ERROR = "model_error"
MAX_RETRIES = "max_retries"
OMIT_CLAIM = "omit_claim"
UNKNOWN_CLAIM = "unknown_claim"


class MockProvider(ModelProvider):
    name = "mock"
    model_identifier = "mock-1"

    def __init__(
        self,
        behaviors: dict[str, str] | None = None,
        default: str = SUPPORTED,
        malformed_recover_after: int = 1,
    ) -> None:
        self._behaviors = behaviors or {}
        self._default = default
        # For MALFORMED_JSON: succeed after this many failed draft attempts.
        self._malformed_recover_after = malformed_recover_after
        self._draft_calls = 0

    def _behavior_for(self, question: str) -> str:
        q = question.lower()
        for needle, behavior in self._behaviors.items():
            if needle.lower() in q:
                return behavior
        return self._default

    async def draft(
        self,
        question: str,
        passages: list[RetrievedPassage],
        previous_unsupported: list[str] | None = None,
    ) -> DraftResponse:
        self._draft_calls += 1
        behavior = self._behavior_for(question)

        if behavior == TIMEOUT:
            raise ModelTimeoutError("mock timeout")
        if behavior == MODEL_ERROR:
            raise ModelError("mock model error")
        if behavior == MAX_RETRIES:
            raise MalformedResponseError("mock always malformed")
        if behavior == MALFORMED_JSON and self._draft_calls <= self._malformed_recover_after:
            raise MalformedResponseError("mock malformed draft")

        first = passages[0] if passages else None
        if behavior == INVENTED_CITATION:
            return DraftResponse(
                answer="Fabricated. [1]",
                claims=[
                    DraftClaim(
                        claim_id="claim-1",
                        text="A claim citing a passage that does not exist.",
                        material=True,
                        cited_passage_ids=["passage-does-not-exist"],
                    )
                ],
            )

        if first is None:
            return DraftResponse(answer="", claims=[])

        text = best_sentence(first.text, question)
        if behavior == UNSUPPORTED:
            text = "This asserts something no approved passage actually states."
        return DraftResponse(
            answer=f"{text} [1]",
            claims=[
                DraftClaim(
                    claim_id="claim-1",
                    text=text,
                    material=True,
                    cited_passage_ids=[first.passage_id],
                )
            ],
        )

    async def verify(
        self,
        claims: list[DraftClaim],
        passages: list[RetrievedPassage],
    ) -> list[VerifierResult]:
        by_id = {p.passage_id: p for p in passages}
        results: list[VerifierResult] = []
        for claim in claims:
            behavior = self._behavior_for(claim.text)
            # Behavior may also be keyed off the original question via cited passage.
            if behavior == self._default and claim.cited_passage_ids:
                pass
            pid = claim.cited_passage_ids[0] if claim.cited_passage_ids else None
            passage = by_id.get(pid) if pid else None

            if behavior == CONTRADICTION:
                quote = best_sentence(passage.text, claim.text) if passage else "conflicting text"
                results.append(
                    VerifierResult(
                        claim_id=claim.claim_id,
                        status=ClaimStatus.CONTRADICTED,
                        evidence=[VerifierEvidence(passage_id=pid, quotation=quote)] if pid else [],
                        explanation="The cited approved passage contradicts this claim.",
                    )
                )
                continue
            if behavior == UNSUPPORTED:
                results.append(
                    VerifierResult(
                        claim_id=claim.claim_id,
                        status=ClaimStatus.INSUFFICIENT_EVIDENCE,
                        explanation="No approved passage supports this claim.",
                    )
                )
                continue
            if behavior == INVENTED_QUOTATION:
                results.append(
                    VerifierResult(
                        claim_id=claim.claim_id,
                        status=ClaimStatus.SUPPORTED,
                        evidence=[
                            VerifierEvidence(
                                passage_id=pid or "x",
                                quotation="a quotation that is not present in the passage at all",
                            )
                        ],
                        explanation="Claims support with a fabricated quotation.",
                    )
                )
                continue
            if behavior == OMIT_CLAIM:
                # Skip emitting a result for this claim entirely.
                continue
            if behavior == UNKNOWN_CLAIM:
                results.append(
                    VerifierResult(
                        claim_id="claim-999-unknown",
                        status=ClaimStatus.SUPPORTED,
                        evidence=[],
                        explanation="A claim id that was never drafted.",
                    )
                )
                continue

            quote = claim.text if passage else claim.text
            results.append(
                VerifierResult(
                    claim_id=claim.claim_id,
                    status=ClaimStatus.SUPPORTED,
                    evidence=[VerifierEvidence(passage_id=pid, quotation=quote)] if pid else [],
                    explanation="Supported by the cited approved passage.",
                )
            )
        return results
