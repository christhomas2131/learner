"""Multi-hop decomposition: conservative splitting + additive merged retrieval."""

from __future__ import annotations

from app.core.enums import TopLevelStatus
from app.pipeline.decompose import decompose
from app.pipeline.engine import VerifiedLearningPipeline
from app.providers.nomodel import NoModelProvider
from app.providers.text_utils import content_tokens
from app.retrieval.base import Retriever
from tests.conftest import make_passage


def test_splits_two_wh_clauses():
    subs = decompose("What is photosynthesis and where does it occur?")
    assert len(subs) == 2 and "photosynthesis" in subs[0].lower()


def test_splits_multiple_questions():
    assert len(decompose("What is X? What is Y?")) == 2


def test_does_not_split_single_topic():
    assert decompose("What is black and white?") == ["What is black and white?"]
    assert decompose("Is Pluto a planet?") == ["Is Pluto a planet?"]


class QueryAwareRetriever(Retriever):
    """Returns only passages whose text shares a content token with the query."""

    def __init__(self, passages):
        self._passages = passages

    async def retrieve(self, question, approved_source_ids, limit):
        q = set(content_tokens(question))
        hits = [p for p in self._passages if q & set(content_tokens(p.text))]
        return hits[:limit]


async def test_compound_question_merges_both_topics():
    passages = [
        make_passage("p-photo", "Photosynthesis converts light energy into chemical energy.",
                     source_id="s1"),
        make_passage("p-resp", "Cellular respiration releases energy stored in glucose.",
                     source_id="s2"),
    ]
    pipeline = VerifiedLearningPipeline(QueryAwareRetriever(passages), NoModelProvider())
    # A single retrieval for the whole string would match both here, but the point
    # is that decomposition gathers each part; assert both topics are covered.
    r = await pipeline.run(
        request_id="req-mh",
        question="What is photosynthesis and what is cellular respiration?",
    )
    assert r.status == TopLevelStatus.VERIFIED
    texts = " ".join(c.text.lower() for c in r.claims)
    assert "photosynthesis" in texts and "respiration" in texts
