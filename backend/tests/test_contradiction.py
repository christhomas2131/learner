"""Cross-source contradiction detection tests (deterministic, no model)."""

from __future__ import annotations

from app.core.enums import TopLevelStatus
from app.pipeline.contradiction import find_contradiction
from app.pipeline.engine import VerifiedLearningPipeline
from app.providers.nomodel import NoModelProvider
from tests.conftest import FakeRetriever, make_passage

PLUTO_2005 = make_passage(
    "p-2005",
    "Pluto is the ninth planet of the solar system. It orbits the Sun beyond "
    "Neptune and is counted among the classical planets.",
    source_id="src-2005", title="Solar System Reference (2005)",
)
PLUTO_2006 = make_passage(
    "p-2006",
    "Pluto is a dwarf planet. It is not classified as one of the eight planets "
    "of the solar system following the 2006 definition.",
    source_id="src-2006", title="Solar System Reference (2006)",
)


def test_find_contradiction_detects_cross_source_negation():
    hit = find_contradiction(
        "Pluto is the ninth planet of the solar system.", {"src-2005"},
        [PLUTO_2005, PLUTO_2006],
    )
    assert hit is not None and hit.source_id == "src-2006" and "not classified" in hit.quotation


def test_find_contradiction_ignores_same_source():
    # If the only negation is in the claim's own source, it is not a cross-source conflict.
    hit = find_contradiction(
        "Pluto is the ninth planet of the solar system.", {"src-2005", "src-2006"},
        [PLUTO_2005, PLUTO_2006],
    )
    assert hit is None


def test_no_false_positive_on_clean_content(bio_passages):
    hit = find_contradiction(
        "Photosynthesis converts light energy into chemical energy.", {"src-bio"},
        bio_passages,
    )
    assert hit is None


async def test_pipeline_returns_contradiction_for_conflicting_sources():
    pipeline = VerifiedLearningPipeline(
        FakeRetriever([PLUTO_2005, PLUTO_2006]), NoModelProvider()
    )
    r = await pipeline.run(request_id="req-c", question="Is Pluto a planet?")
    assert r.status == TopLevelStatus.CONTRADICTION
    assert r.contradiction_detail
    assert any(c.status == "CONTRADICTED" for c in r.claims)


async def test_pipeline_verified_when_no_conflict(bio_passages):
    pipeline = VerifiedLearningPipeline(FakeRetriever(bio_passages), NoModelProvider())
    r = await pipeline.run(request_id="req-v", question="What is photosynthesis?")
    assert r.status == TopLevelStatus.VERIFIED
