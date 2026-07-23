"""The verification state machine.

Python owns stage order. The model never decides what runs next, never reaches
the release gate, and never treats its own prior output as evidence. Every model
response is schema-validated and every quotation is checked by substring match
against an approved passage before it can count as support.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.enums import (
    DEFAULT_ABSTENTION_MESSAGE,
    ClaimStatus,
    PipelineStage,
    TopLevelStatus,
)
from app.core.logging import get_logger
from app.pipeline import gate
from app.pipeline.events import (
    CLAIM_VERIFICATION,
    COMPLETED,
    DRAFT_CREATED,
    FAILED,
    PIPELINE_STAGE,
    RELEASE_GATE,
    REQUEST_STARTED,
    REVISION_STARTED,
    SOURCE_RETRIEVED,
    EventEmitter,
    PipelineEvent,
    noop_emitter,
)
from app.pipeline.resolvers import (
    ResolvedAnswer,
    answer_key_resolver,
    definition_resolver,
    resolve_computational,
)
from app.providers.base import (
    MalformedResponseError,
    ModelError,
    ModelProvider,
    ModelTimeoutError,
)
from app.providers.text_utils import quotation_in_passage
from app.retrieval.base import Retriever
from app.schemas.api import CitationOut, ClaimOut, EvidenceOut, PipelineInfo, SourceOut
from app.schemas.pipeline import DraftClaim, DraftResponse, RetrievedPassage, VerifierResult

log = get_logger("pipeline")

MAX_QUESTION_LENGTH = 4000


class InputValidationError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class _ClaimState:
    label: str
    text: str
    material: bool
    status: ClaimStatus = ClaimStatus.INSUFFICIENT_EVIDENCE
    evidence: list[EvidenceOut] = field(default_factory=list)


@dataclass
class PipelineResult:
    request_id: str
    session_id: str | None
    status: TopLevelStatus
    question: str
    answer: str
    claims: list[ClaimOut]
    sources: list[SourceOut]
    attempts: int
    duration_ms: int
    completed_stages: list[str]
    provider: str
    model_identifier: str | None
    contradiction_detail: str | None
    reasons: list[str]
    created_at: datetime


class VerifiedLearningPipeline:
    def __init__(
        self,
        retriever: Retriever,
        provider: ModelProvider,
        *,
        retrieval_limit: int = 8,
        max_model_retries: int = 2,
        max_pipeline_attempts: int = 2,
        definition_records: list[dict] | None = None,
        answer_key_records: list[dict] | None = None,
    ) -> None:
        self._retriever = retriever
        self._provider = provider
        self._retrieval_limit = retrieval_limit
        self._max_model_retries = max_model_retries
        self._max_pipeline_attempts = max_pipeline_attempts
        self._definition_records = definition_records or []
        self._answer_key_records = answer_key_records or []

    async def run(
        self,
        *,
        request_id: str,
        question: str,
        session_id: str | None = None,
        approved_source_ids: list[str] | None = None,
        emitter: EventEmitter | None = None,
    ) -> PipelineResult:
        emit = emitter or noop_emitter
        started = time.monotonic()
        completed: list[str] = []
        attempts = 1
        passages: list[RetrievedPassage] = []

        def result(
            status: TopLevelStatus,
            answer: str,
            claims: list[ClaimOut],
            reasons: list[str],
            contradiction_detail: str | None = None,
        ) -> PipelineResult:
            return PipelineResult(
                request_id=request_id,
                session_id=session_id,
                status=status,
                question=question,
                answer=answer,
                claims=claims,
                sources=_sources_from_passages(passages),
                attempts=attempts,
                duration_ms=int((time.monotonic() - started) * 1000),
                completed_stages=completed,
                provider=self._provider.name,
                model_identifier=self._provider.model_identifier,
                contradiction_detail=contradiction_detail,
                reasons=reasons,
                created_at=datetime.now(UTC),
            )

        await emit(PipelineEvent(REQUEST_STARTED, message="Request received"))

        # ---- Stage 1: VALIDATE_INPUT -------------------------------------- #
        await emit(PipelineEvent(PIPELINE_STAGE, PipelineStage.VALIDATE_INPUT, "Validating question"))
        try:
            question = self._validate_input(question)
        except InputValidationError as e:
            await emit(PipelineEvent(FAILED, PipelineStage.VALIDATE_INPUT, e.message))
            return result(TopLevelStatus.ERROR, _safe_error(e.message), [], [e.message])
        completed.append(PipelineStage.VALIDATE_INPUT)

        # ---- Stage 2: RESOLVE_DETERMINISTIC_QUESTION ---------------------- #
        await emit(
            PipelineEvent(PIPELINE_STAGE, PipelineStage.RESOLVE_DETERMINISTIC_QUESTION,
                          "Checking deterministic resolvers")
        )
        resolved = self._resolve_deterministic(question)
        completed.append(PipelineStage.RESOLVE_DETERMINISTIC_QUESTION)
        if resolved is not None:
            return await self._finish_deterministic(resolved, result, completed, emit)

        # ---- Stage 3: RETRIEVE -------------------------------------------- #
        await emit(PipelineEvent(PIPELINE_STAGE, PipelineStage.RETRIEVE, "Retrieving approved sources"))
        passages = await self._retriever.retrieve(question, approved_source_ids, self._retrieval_limit)
        completed.append(PipelineStage.RETRIEVE)
        await emit(
            PipelineEvent(SOURCE_RETRIEVED, PipelineStage.RETRIEVE,
                          f"Retrieved {len(passages)} approved passage(s)",
                          {"count": len(passages)})
        )
        if not passages:
            reasons = ["No approved passage was retrieved for this question."]
            await emit(PipelineEvent(RELEASE_GATE, PipelineStage.RELEASE_GATE, reasons[0]))
            return result(TopLevelStatus.INSUFFICIENT_EVIDENCE, DEFAULT_ABSTENTION_MESSAGE, [], reasons)

        passage_by_id = {p.passage_id: p for p in passages}

        # ---- Stages 4-7: DRAFT / VERIFY / REVISE (bounded loop) ----------- #
        previous_unsupported: list[str] = []
        claim_states: list[_ClaimState] = []
        draft: DraftResponse | None = None

        while True:
            # DRAFT (+ EXTRACT_CLAIMS)
            await emit(PipelineEvent(PIPELINE_STAGE, PipelineStage.DRAFT, "Drafting candidate answer"))
            try:
                draft = await self._draft_with_retries(question, passages, previous_unsupported)
            except ModelCallsExhausted as e:
                await emit(PipelineEvent(FAILED, PipelineStage.DRAFT, e.reason))
                return result(TopLevelStatus.ERROR, _safe_error(e.reason), [], [e.reason])
            except (ModelTimeoutError, ModelError) as e:
                msg = f"Model provider error during drafting: {type(e).__name__}"
                await emit(PipelineEvent(FAILED, PipelineStage.DRAFT, msg))
                return result(TopLevelStatus.ERROR, _safe_error(msg), [], [msg])
            if PipelineStage.DRAFT not in completed:
                completed.append(PipelineStage.DRAFT)
            if PipelineStage.EXTRACT_CLAIMS not in completed:
                completed.append(PipelineStage.EXTRACT_CLAIMS)
            await emit(
                PipelineEvent(DRAFT_CREATED, PipelineStage.DRAFT,
                              f"Draft with {len(draft.claims)} atomic claim(s)",
                              {"claim_count": len(draft.claims)})
            )

            # VERIFY_CLAIMS
            await emit(
                PipelineEvent(PIPELINE_STAGE, PipelineStage.VERIFY_CLAIMS,
                              f"Verifying {len(draft.claims)} claim(s)")
            )
            try:
                verifier_results = await self._verify_with_retries(draft.claims, passages)
            except ModelCallsExhausted as e:
                await emit(PipelineEvent(FAILED, PipelineStage.VERIFY_CLAIMS, e.reason))
                return result(TopLevelStatus.ERROR, _safe_error(e.reason), [], [e.reason])
            except (ModelTimeoutError, ModelError) as e:
                msg = f"Model provider error during verification: {type(e).__name__}"
                await emit(PipelineEvent(FAILED, PipelineStage.VERIFY_CLAIMS, msg))
                return result(TopLevelStatus.ERROR, _safe_error(msg), [], [msg])
            if PipelineStage.VERIFY_CLAIMS not in completed:
                completed.append(PipelineStage.VERIFY_CLAIMS)

            claim_states = self._resolve_claim_states(draft.claims, verifier_results, passage_by_id)
            for cs in claim_states:
                await emit(
                    PipelineEvent(CLAIM_VERIFICATION, PipelineStage.VERIFY_CLAIMS,
                                  f"{cs.label}: {cs.status}",
                                  {"claim_id": cs.label, "status": cs.status.value})
                )

            unsupported_material = [
                c for c in claim_states
                if c.material and c.status == ClaimStatus.INSUFFICIENT_EVIDENCE
            ]
            contradicted_material = [
                c for c in claim_states
                if c.material and c.status == ClaimStatus.CONTRADICTED
            ]

            # Contradiction short-circuits — never silently pick a side.
            if contradicted_material:
                break
            if not unsupported_material:
                break
            if attempts >= self._max_pipeline_attempts:
                break

            # REVISE
            attempts += 1
            previous_unsupported = [c.text for c in unsupported_material]
            await emit(
                PipelineEvent(REVISION_STARTED, PipelineStage.REVISE,
                              "Revising: dropping unsupported material")
            )
            if PipelineStage.REVISE not in completed:
                completed.append(PipelineStage.REVISE)

        # ---- Stage 8: RELEASE_GATE ---------------------------------------- #
        await emit(PipelineEvent(PIPELINE_STAGE, PipelineStage.RELEASE_GATE, "Applying release gate"))
        decision, answer_text, claim_outs, contradiction_detail = self._apply_gate(
            draft, claim_states, passages
        )
        completed.append(PipelineStage.RELEASE_GATE)
        await emit(
            PipelineEvent(RELEASE_GATE, PipelineStage.RELEASE_GATE,
                          f"Status: {decision.status}", {"status": decision.status.value})
        )

        await emit(PipelineEvent(COMPLETED, PipelineStage.COMPLETE, "Complete",
                                 {"status": decision.status.value}))
        return result(decision.status, answer_text, claim_outs, decision.reasons, contradiction_detail)

    # ------------------------------------------------------------------ #
    # Stage helpers
    # ------------------------------------------------------------------ #

    def _validate_input(self, question: str) -> str:
        if question is None:
            raise InputValidationError("Question is required.")
        normalized = " ".join(question.split())
        if not normalized:
            raise InputValidationError("Question must not be empty.")
        if len(normalized) > MAX_QUESTION_LENGTH:
            raise InputValidationError(
                f"Question exceeds the maximum length of {MAX_QUESTION_LENGTH} characters."
            )
        return normalized

    def _resolve_deterministic(self, question: str) -> ResolvedAnswer | None:
        computational = resolve_computational(question)
        if computational is not None:
            return computational
        definition = definition_resolver(question, self._definition_records)
        if definition is not None:
            return definition
        return answer_key_resolver(question, self._answer_key_records)

    async def _finish_deterministic(self, resolved, result, completed, emit):
        claim = ClaimOut(
            claim_id="claim-1",
            text=resolved.claim_text,
            material=True,
            status=ClaimStatus.SUPPORTED,
        )
        if resolved.source_backed and resolved.citation is not None:
            claim.citations = [
                CitationOut(citation_number=1, source_id=resolved.citation.source_id,
                            passage_id=resolved.citation.passage_id)
            ]
            claim.evidence = [
                EvidenceOut(source_id=resolved.citation.source_id,
                            passage_id=resolved.citation.passage_id,
                            quotation=resolved.citation.quotation, retrieval_score=1.0)
            ]
            claim.verifier_explanation = resolved.detail
        else:
            claim.verifier_explanation = resolved.detail
        gi = gate.GateInput(
            deterministic=True, approved_support_count=1 if resolved.source_backed else 0,
            material_claim_statuses=[ClaimStatus.SUPPORTED], all_quotations_valid=True,
            contradiction=False, model_calls_exhausted=False, stage_failed=False,
        )
        decision = gate.decide(gi)
        completed.append(PipelineStage.RELEASE_GATE)
        await emit(PipelineEvent(RELEASE_GATE, PipelineStage.RELEASE_GATE, f"Status: {decision.status}"))
        await emit(PipelineEvent(COMPLETED, PipelineStage.COMPLETE, "Complete"))
        return result(decision.status, resolved.answer, [claim], decision.reasons)

    async def _draft_with_retries(
        self, question: str, passages: list[RetrievedPassage], previous_unsupported: list[str]
    ) -> DraftResponse:
        last_error = ""
        for _ in range(self._max_model_retries + 1):
            try:
                draft = await self._provider.draft(question, passages, previous_unsupported or None)
            except MalformedResponseError as e:
                last_error = f"Malformed draft response: {e}"
                continue
            try:
                self._validate_draft(draft, passages)
            except MalformedResponseError as e:
                last_error = f"Invalid draft: {e}"
                continue
            return draft
        raise ModelCallsExhausted(last_error or "Draft retries exhausted.")

    def _validate_draft(self, draft: DraftResponse, passages: list[RetrievedPassage]) -> None:
        known = {p.passage_id for p in passages}
        seen: set[str] = set()
        for claim in draft.claims:
            if claim.claim_id in seen:
                raise MalformedResponseError(f"duplicate claim_id {claim.claim_id}")
            seen.add(claim.claim_id)
            if not claim.cited_passage_ids:
                raise MalformedResponseError(f"{claim.claim_id} cites no passage")
            for pid in claim.cited_passage_ids:
                if pid not in known:
                    raise MalformedResponseError(f"{claim.claim_id} cites unknown passage {pid}")

    async def _verify_with_retries(
        self, claims: list[DraftClaim], passages: list[RetrievedPassage]
    ) -> list[VerifierResult]:
        last_error = ""
        expected = {c.claim_id for c in claims}
        for _ in range(self._max_model_retries + 1):
            try:
                results = await self._provider.verify(claims, passages)
            except MalformedResponseError as e:
                last_error = f"Malformed verifier response: {e}"
                continue
            got = {r.claim_id for r in results}
            if got != expected:
                missing = expected - got
                unknown = got - expected
                last_error = f"verifier claim mismatch missing={missing} unknown={unknown}"
                continue
            return results
        raise ModelCallsExhausted(last_error or "Verify retries exhausted.")

    def _resolve_claim_states(
        self,
        claims: list[DraftClaim],
        results: list[VerifierResult],
        passage_by_id: dict[str, RetrievedPassage],
    ) -> list[_ClaimState]:
        result_by_id = {r.claim_id: r for r in results}
        states: list[_ClaimState] = []
        for claim in claims:
            r = result_by_id[claim.claim_id]
            cited = set(claim.cited_passage_ids)
            valid_evidence: list[EvidenceOut] = []
            for ev in r.evidence:
                passage = passage_by_id.get(ev.passage_id)
                # Quotation must exist, in a cited AND approved passage. Never trust
                # the verifier's assertion that a quotation exists.
                if (
                    passage is not None
                    and passage.approved
                    and ev.passage_id in cited
                    and quotation_in_passage(ev.quotation, passage.text)
                ):
                    valid_evidence.append(
                        EvidenceOut(
                            source_id=passage.source_id,
                            passage_id=passage.passage_id,
                            quotation=ev.quotation,
                            retrieval_score=passage.retrieval_score,
                        )
                    )

            status = r.status
            if status == ClaimStatus.SUPPORTED and not valid_evidence:
                # Verifier claimed support but no quotation validated -> downgrade.
                status = ClaimStatus.INSUFFICIENT_EVIDENCE
            if status == ClaimStatus.CONTRADICTED and not valid_evidence:
                # Contradiction must also be backed by a real quotation.
                status = ClaimStatus.INSUFFICIENT_EVIDENCE
            states.append(
                _ClaimState(
                    label=claim.claim_id, text=claim.text, material=claim.material,
                    status=status, evidence=valid_evidence,
                )
            )
        return states

    def _apply_gate(
        self,
        draft: DraftResponse | None,
        claim_states: list[_ClaimState],
        passages: list[RetrievedPassage],
    ) -> tuple[gate.GateDecision, str, list[ClaimOut], str | None]:
        material_statuses = [c.status for c in claim_states if c.material]
        contradiction = any(
            c.material and c.status == ClaimStatus.CONTRADICTED for c in claim_states
        )
        supported = [c for c in claim_states if c.status == ClaimStatus.SUPPORTED]
        all_quotations_valid = all(
            bool(c.evidence) for c in claim_states if c.status == ClaimStatus.SUPPORTED
        )
        approved_support = len({e.source_id for c in supported for e in c.evidence})

        gi = gate.GateInput(
            deterministic=False,
            approved_support_count=approved_support,
            material_claim_statuses=material_statuses,
            all_quotations_valid=all_quotations_valid,
            contradiction=contradiction,
            model_calls_exhausted=False,
            stage_failed=False,
        )
        decision = gate.decide(gi)

        # Assign citation numbers and build public claim objects.
        claim_outs, citation_map = _build_claim_outs(claim_states)

        if decision.status == TopLevelStatus.VERIFIED:
            answer_text = _render_answer(draft, claim_states, citation_map)
            return decision, answer_text, claim_outs, None
        if decision.status == TopLevelStatus.CONTRADICTION:
            detail = _contradiction_detail(claim_states)
            return decision, DEFAULT_ABSTENTION_MESSAGE, claim_outs, detail
        # INSUFFICIENT_EVIDENCE / ERROR
        return decision, DEFAULT_ABSTENTION_MESSAGE, claim_outs, None


class ModelCallsExhausted(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# --------------------------------------------------------------------------- #
# Assembly helpers
# --------------------------------------------------------------------------- #


def _sources_from_passages(passages: list[RetrievedPassage]) -> list[SourceOut]:
    seen: dict[str, SourceOut] = {}
    for p in passages:
        if p.source_id not in seen:
            seen[p.source_id] = SourceOut(
                source_id=p.source_id, title=p.source_title,
                source_type=p.source_type, approved=p.approved,
            )
    return list(seen.values())


def _build_claim_outs(
    claim_states: list[_ClaimState],
) -> tuple[list[ClaimOut], dict[str, int]]:
    claim_outs: list[ClaimOut] = []
    citation_map: dict[str, int] = {}
    counter = 1
    for cs in claim_states:
        citations: list[CitationOut] = []
        if cs.status in (ClaimStatus.SUPPORTED, ClaimStatus.CONTRADICTED) and cs.evidence:
            citation_map[cs.label] = counter
            for ev in cs.evidence:
                citations.append(
                    CitationOut(citation_number=counter, source_id=ev.source_id,
                                passage_id=ev.passage_id)
                )
            counter += 1
        claim_outs.append(
            ClaimOut(
                claim_id=cs.label, text=cs.text, material=cs.material, status=cs.status,
                citations=citations, evidence=cs.evidence,
            )
        )
    return claim_outs, citation_map


def _render_answer(
    draft: DraftResponse | None,
    claim_states: list[_ClaimState],
    citation_map: dict[str, int],
) -> str:
    """Build the released answer from SUPPORTED claims only, each cited.

    Guarantees the released text contains no uncited factual statement, because
    it is assembled purely from validated, cited claims.
    """
    parts: list[str] = []
    for cs in claim_states:
        if cs.status == ClaimStatus.SUPPORTED and cs.label in citation_map:
            n = citation_map[cs.label]
            text = cs.text.rstrip()
            parts.append(f"{text} [{n}]")
    return " ".join(parts)


def _contradiction_detail(claim_states: list[_ClaimState]) -> str:
    for cs in claim_states:
        if cs.status == ClaimStatus.CONTRADICTED:
            quotes = "; ".join(e.quotation for e in cs.evidence)
            return (
                f"The approved materials conflict regarding: \"{cs.text}\". "
                f"Contradicting evidence: {quotes}"
            )
    return "The approved sources conflict."


def _safe_error(message: str) -> str:
    return f"The request could not be completed safely: {message}"


def pipeline_info(result: PipelineResult) -> PipelineInfo:
    return PipelineInfo(
        attempts=result.attempts, duration_ms=result.duration_ms,
        completed_stages=result.completed_stages, provider=result.provider,
        model_identifier=result.model_identifier,
    )
