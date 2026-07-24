"""Reciprocal-rank fusion for multi-provider candidate lists.

Same RRF formula the hybrid retriever uses (score += 1 / (k + rank)), here
generalized to fuse N provider result lists keyed on a normalized URL, merging
provenance (which providers surfaced each candidate).
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from app.discovery.models import Candidate


def normalize_url(url: str) -> str:
    """Canonicalize for dedupe: lowercase scheme+host, drop fragment + trailing slash."""
    raw = url.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.lower()
    if not parts.scheme or not parts.netloc:
        return raw.lower()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def fuse_candidates(lists: list[list[Candidate]], *, k: int, limit: int) -> list[Candidate]:
    """Fuse ranked candidate lists via RRF; dedupe by normalized URL, merge providers."""
    scores: dict[str, float] = {}
    merged: dict[str, Candidate] = {}
    for lst in lists:
        for rank, cand in enumerate(lst):
            key = normalize_url(cand.url)
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            existing = merged.get(key)
            if existing is None:
                merged[key] = Candidate(url=cand.url, title=cand.title,
                                        snippet=cand.snippet, providers=list(cand.providers))
                continue
            for provider in cand.providers:
                if provider not in existing.providers:
                    existing.providers.append(provider)
            if not existing.snippet and cand.snippet:
                existing.snippet = cand.snippet
    ordered = sorted(merged.values(), key=lambda c: scores[normalize_url(c.url)], reverse=True)
    return ordered[:limit]
