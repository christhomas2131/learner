"""Verification prompt. The verifier judges claims independently of the drafter.

It is never told the draft is likely correct, never given the drafter's
reasoning, and may use only the cited passages.
"""

from __future__ import annotations

import json

from app.schemas.pipeline import DraftClaim, RetrievedPassage

VERIFY_SYSTEM = (
    "You independently verify factual claims for a verified-learning system. "
    "You are NOT told whether the claims are correct. Rules:\n"
    "- Judge each claim ONLY against its cited passages. No outside knowledge, "
    "no internet.\n"
    "- Classify each claim as exactly one of: SUPPORTED, CONTRADICTED, "
    "INSUFFICIENT_EVIDENCE.\n"
    "- For SUPPORTED or CONTRADICTED, provide an exact verbatim quotation copied "
    "character-for-character from the cited passage. Do not paraphrase.\n"
    "- Return exactly one result per claim, same claim_id. Add no extra claims.\n"
    "- Keep the explanation brief and evidence-based. No chain-of-thought.\n"
    "- Output ONLY valid JSON."
)

VERIFY_SCHEMA = [
    {
        "claim_id": "claim-1",
        "status": "SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE",
        "evidence": [{"passage_id": "<cited passage_id>", "quotation": "exact verbatim text"}],
        "explanation": "brief evidence-based explanation",
    }
]


def build_verify_prompt(claims: list[DraftClaim], passages: list[RetrievedPassage]) -> str:
    by_id = {p.passage_id: p for p in passages}
    items = []
    for c in claims:
        cited = [
            {"passage_id": pid, "text": by_id[pid].text}
            for pid in c.cited_passage_ids
            if pid in by_id
        ]
        items.append({"claim_id": c.claim_id, "text": c.text, "cited_passages": cited})
    return (
        f"{VERIFY_SYSTEM}\n\n"
        f"CLAIMS TO VERIFY:\n{json.dumps(items, indent=2)}\n\n"
        f"Respond with a JSON array of exactly this shape:\n{json.dumps(VERIFY_SCHEMA, indent=2)}"
    )
