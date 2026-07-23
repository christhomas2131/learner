"""Deterministic text helpers used for evidence validation.

Quotation matching is normalized-substring matching — never a model's word that
a quotation exists. This is the mechanical heart of the anti-hallucination gate.
"""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[A-Za-z0-9]+")
_SENT = re.compile(r"(?<=[.!?])\s+")

# Common words that must not drive retrieval or relevance scoring.
STOPWORDS = frozenset(
    """a an the of to in on at for and or but is are was were be been being this that
    these those it its as by with from into about what which who whom whose when where
    why how do does did done have has had can could should would will shall may might
    i you he she we they them his her their our your my me us if then than there here
    not no yes so such very more most many much some any all each every""".split()
)


def normalize_text(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


def quotation_in_passage(quotation: str, passage_text: str) -> bool:
    """True iff `quotation` appears in `passage_text` (whitespace/case-normalized)."""
    nq = normalize_text(quotation)
    if not nq:
        return False
    return nq in normalize_text(passage_text)


def tokens(s: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(s)]


def content_tokens(s: str) -> list[str]:
    """Tokens with stopwords and 1-char tokens removed."""
    return [t for t in tokens(s) if len(t) > 1 and t not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT.split(text.strip()) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def best_sentence(passage_text: str, question: str) -> str:
    """Pick the passage sentence with the most content-word overlap."""
    return _best_sentence_scored(passage_text, question)[0]


def _best_sentence_scored(passage_text: str, question: str) -> tuple[str, int]:
    q_tokens = set(content_tokens(question))
    sentences = split_sentences(passage_text)
    if not sentences:
        return passage_text.strip(), 0
    best = max(sentences, key=lambda s: len(q_tokens & set(content_tokens(s))))
    overlap = len(q_tokens & set(content_tokens(best)))
    return best, overlap


def sentence_relevance(passage_text: str, question: str) -> int:
    """How many question content-words the best sentence shares (0 = irrelevant)."""
    return _best_sentence_scored(passage_text, question)[1]
