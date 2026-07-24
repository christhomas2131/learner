"""Conservative, deterministic question decomposition for multi-hop retrieval.

Splits a clearly-compound question into sub-questions so retrieval can gather
evidence for each part. Intentionally cautious: only splits on multiple explicit
questions ("...? ...?") or two-plus wh-clauses joined by "and"/commas, so single
topics ("black and white", "Newton's laws") are never split. The whole question
is always retrieved too, so decomposition is purely additive.
"""

from __future__ import annotations

import re

_WH = re.compile(r"(?i)\b(what|where|when|why|how|who|which)\b")
_TRAILING_CONJ = re.compile(r"(?i)[\s,]+(and|or)\s*$")


def decompose(question: str) -> list[str]:
    q = " ".join(question.split())
    if not q:
        return [q]

    # 1) Multiple explicit questions.
    parts = [p.strip() for p in re.split(r"\?+", q) if p.strip()]
    if len(parts) > 1:
        return [p if p.endswith("?") else p + "?" for p in parts]

    # 2) Two-or-more wh-clauses in one sentence.
    starters = [m.start() for m in _WH.finditer(q)]
    if len(starters) >= 2:
        clauses: list[str] = []
        for i, start in enumerate(starters):
            end = starters[i + 1] if i + 1 < len(starters) else len(q)
            clause = _TRAILING_CONJ.sub("", q[start:end].strip().rstrip(",")).strip(" ,")
            if len(clause.split()) >= 2:
                clauses.append(clause)
        if len(clauses) >= 2:
            return clauses

    return [q]
