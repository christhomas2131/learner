"""End-to-end state-machine tests using the in-memory retriever + mock provider.

Covers every required branch: verified, abstain, contradiction, invented
citation/quotation, verifier omission/unknown-claim, malformed retry + limit,
timeout, model error, no-sources abstain, and deterministic-avoids-model.
"""

from __future__ import annotations

from app.core.enums import TopLevelStatus
from app.pipeline.engine import VerifiedLearningPipeline
from app.providers import mock as mk
from app.providers.mock import MockProvider
from app.providers.nomodel import NoModelProvider
from tests.conftest import ExplodingProvider, FakeRetriever, make_passage

REQ = "req-1"


def _pipeline(passages, provider, **kw) -> VerifiedLearningPipeline:
    return VerifiedLearningPipeline(FakeRetriever(passages), provider, **kw)


async def test_supported_question_verified(bio_passages):
    p = _pipeline(bio_passages, NoModelProvider())
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.VERIFIED
    assert "photosynthesis" in r.answer.lower()
    assert any(c.evidence for c in r.claims)
    assert "[1]" in r.answer  # cited


async def test_no_sources_abstains():
    p = _pipeline([], NoModelProvider())
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.INSUFFICIENT_EVIDENCE
    assert "do not have enough verified information" in r.answer


async def test_unsupported_question_abstains(bio_passages):
    prov = MockProvider(default=mk.UNSUPPORTED)
    p = _pipeline(bio_passages, prov, max_pipeline_attempts=2)
    r = await p.run(request_id=REQ, question="What is the meaning of life?")
    assert r.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


async def test_contradiction_returns_contradiction(bio_passages):
    prov = MockProvider(default=mk.CONTRADICTION)
    p = _pipeline(bio_passages, prov)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.CONTRADICTION
    assert r.contradiction_detail


async def test_invented_citation_rejected(bio_passages):
    prov = MockProvider(default=mk.INVENTED_CITATION)
    p = _pipeline(bio_passages, prov, max_model_retries=1)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    # Draft cites an unknown passage -> validation fails every retry -> ERROR.
    assert r.status == TopLevelStatus.ERROR


async def test_invented_quotation_rejected(bio_passages):
    prov = MockProvider(default=mk.INVENTED_QUOTATION)
    p = _pipeline(bio_passages, prov)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    # Verifier claims SUPPORTED with a fabricated quotation -> downgraded -> abstain.
    assert r.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


async def test_verifier_omission_rejected(bio_passages):
    prov = MockProvider(default=mk.OMIT_CLAIM)
    p = _pipeline(bio_passages, prov, max_model_retries=1)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.ERROR


async def test_unknown_verifier_claim_rejected(bio_passages):
    prov = MockProvider(default=mk.UNKNOWN_CLAIM)
    p = _pipeline(bio_passages, prov, max_model_retries=1)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.ERROR


async def test_malformed_json_retries_then_succeeds(bio_passages):
    # Fails the first draft attempt, succeeds on retry.
    prov = MockProvider(default=mk.MALFORMED_JSON, malformed_recover_after=1)
    p = _pipeline(bio_passages, prov, max_model_retries=2)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.VERIFIED


async def test_max_retries_enforced(bio_passages):
    prov = MockProvider(default=mk.MAX_RETRIES)
    p = _pipeline(bio_passages, prov, max_model_retries=2)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.ERROR


async def test_timeout_is_error(bio_passages):
    prov = MockProvider(default=mk.TIMEOUT)
    p = _pipeline(bio_passages, prov)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.ERROR


async def test_model_error_is_error(bio_passages):
    prov = MockProvider(default=mk.MODEL_ERROR)
    p = _pipeline(bio_passages, prov)
    r = await p.run(request_id=REQ, question="What is photosynthesis?")
    assert r.status == TopLevelStatus.ERROR


async def test_empty_question_is_error(bio_passages):
    p = _pipeline(bio_passages, NoModelProvider())
    r = await p.run(request_id=REQ, question="   ")
    assert r.status == TopLevelStatus.ERROR


async def test_deterministic_arithmetic_skips_model(bio_passages):
    # ExplodingProvider raises if the model is touched.
    p = _pipeline(bio_passages, ExplodingProvider())
    r = await p.run(request_id=REQ, question="What is 2 + 2?")
    assert r.status == TopLevelStatus.VERIFIED
    assert "4" in r.answer


async def test_deterministic_definition_cites_source(bio_passages):
    records = [{"term": "photosynthesis",
                "definition": "Photosynthesis converts light energy into chemical energy.",
                "source_id": "src-bio", "passage_id": "p-photo"}]
    p = _pipeline(bio_passages, ExplodingProvider(), definition_records=records)
    r = await p.run(request_id=REQ, question="what is photosynthesis?")
    assert r.status == TopLevelStatus.VERIFIED
    assert r.claims[0].citations[0].source_id == "src-bio"


async def test_unapproved_passage_not_retrieved():
    passages = [make_passage("p-x", "Some approved-looking text about cells.", approved=False)]
    p = _pipeline(passages, NoModelProvider())
    r = await p.run(request_id=REQ, question="What are cells?")
    assert r.status == TopLevelStatus.INSUFFICIENT_EVIDENCE


async def test_source_filter_restricts_retrieval(bio_passages):
    p = _pipeline(bio_passages, NoModelProvider())
    r = await p.run(request_id=REQ, question="What is photosynthesis?",
                    approved_source_ids=["nonexistent-source"])
    assert r.status == TopLevelStatus.INSUFFICIENT_EVIDENCE
