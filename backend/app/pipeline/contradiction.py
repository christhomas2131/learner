"""Deterministic cross-source contradiction detection (no model).

Conservative heuristic: a supported claim is flagged CONTRADICTED when a
*different* approved source contains a sentence that (a) negates and (b) shares
enough content with the claim. Singularized token overlap handles plural/singular
(planet/planets). This is intentionally cautious — better to miss a subtle
conflict than to raise a false one. Subtler semantic conflicts are caught by the
model verifier in premium mode.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.text_utils import clean_markdown, content_tokens, split_sentences, tokens

# Explicit negation cues (checked on raw tokens, which keep stopwords like "not").
_NEG_CUES = {"not", "no", "never", "cannot", "without", "neither", "nor", "none"}


def _singular(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") else t


def _norm(toks: list[str]) -> set[str]:
    return {_singular(t) for t in toks}


def _has_negation(sentence: str) -> bool:
    raw = tokens(sentence)
    if any(t in _NEG_CUES for t in raw):
        return True
    low = f" {sentence.lower()} "
    return "n't" in low


@dataclass
class ContradictionHit:
    quotation: str
    source_id: str
    passage_id: str
    retrieval_score: float


def find_contradiction(
    claim_text: str,
    claim_source_ids: set[str],
    passages,  # list[RetrievedPassage]
    *,
    min_shared: int = 2,
) -> ContradictionHit | None:
    """Return a cross-source negating sentence that conflicts with the claim."""
    claim_norm = _norm(content_tokens(claim_text))
    if len(claim_norm) < 2:
        return None

    for p in passages:
        if p.source_id in claim_source_ids:
            continue  # cross-source disagreement only
        for sentence in split_sentences(p.text):
            if not _has_negation(sentence):
                continue
            shared = _norm(content_tokens(sentence)) & claim_norm
            if len(shared) >= min_shared:
                return ContradictionHit(
                    quotation=clean_markdown(sentence).strip(),
                    source_id=p.source_id,
                    passage_id=p.passage_id,
                    retrieval_score=p.retrieval_score,
                )
    return None
