"""Deterministic resolver tests."""

from __future__ import annotations

from app.pipeline.resolvers import (
    answer_key_resolver,
    definition_resolver,
    resolve_computational,
)


def test_arithmetic_resolver():
    r = resolve_computational("What is 2 + 2?")
    assert r is not None and r.kind == "arithmetic" and "4" in r.answer


def test_arithmetic_precision():
    r = resolve_computational("0.1 + 0.2")
    assert r is not None and "0.3" in r.answer  # Decimal, not float 0.30000000004


def test_percentage_resolver():
    r = resolve_computational("what is 15% of 200")
    assert r is not None and r.kind == "percentage" and "30" in r.answer


def test_date_between_resolver():
    r = resolve_computational("how many days between 2020-01-01 and 2020-02-01")
    assert r is not None and "31" in r.answer


def test_date_offset_resolver():
    r = resolve_computational("30 days after 2021-01-01")
    assert r is not None and "2021-01-31" in r.answer


def test_unit_conversion_resolver():
    r = resolve_computational("convert 10 km to miles")
    assert r is not None and r.kind == "unit_conversion" and "6.21" in r.answer


def test_temperature_conversion():
    r = resolve_computational("convert 100 C to F")
    assert r is not None and "212" in r.answer


def test_non_arithmetic_returns_none():
    assert resolve_computational("What is the capital of France?") is None


def test_definition_resolver_exact_match():
    recs = [{"term": "photosynthesis", "definition": "Converts light to chemical energy.",
             "source_id": "s1", "passage_id": "p1"}]
    r = definition_resolver("what is photosynthesis?", recs)
    assert r is not None and r.source_backed and r.citation.source_id == "s1"


def test_definition_resolver_no_match():
    assert definition_resolver("what is mitosis?", []) is None


def test_answer_key_resolver():
    recs = [{"question": "What is the boiling point of water in Celsius?",
             "answer": "100 degrees Celsius", "source_id": "s2", "passage_id": "p2"}]
    r = answer_key_resolver("What is the boiling point of water in Celsius?", recs)
    assert r is not None and r.answer == "100 degrees Celsius"
