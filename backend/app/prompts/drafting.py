"""Drafting prompt. Used by the Claude Code worker and any future API provider."""

from __future__ import annotations

import json

from app.schemas.pipeline import RetrievedPassage

DRAFT_SYSTEM = (
    "You draft answers for a verified-learning system. Rules, without exception:\n"
    "- Use ONLY the provided evidence passages. Do not use prior knowledge.\n"
    "- Do not invent citations. Cite passages by their exact passage_id.\n"
    "- Do not conceal uncertainty. If the evidence does not answer the question, "
    "produce zero claims.\n"
    "- Keep every factual assertion atomic: one checkable fact per claim.\n"
    "- Every externally verifiable statement in the answer MUST appear as a claim.\n"
    "- Do not include unsupported explanatory filler.\n"
    "- Output ONLY valid JSON matching the schema. No prose outside the JSON."
)

DRAFT_SCHEMA = {
    "answer": "string — the candidate answer, each factual sentence ending with [n] citation markers",
    "claims": [
        {
            "claim_id": "claim-1",
            "text": "one atomic factual claim",
            "material": "boolean — true if the claim is essential to answering",
            "cited_passage_ids": ["<passage_id from the evidence>"],
        }
    ],
}


def build_draft_prompt(question: str, passages: list[RetrievedPassage]) -> str:
    evidence = [
        {"passage_id": p.passage_id, "source_title": p.source_title, "text": p.text}
        for p in passages
    ]
    return (
        f"{DRAFT_SYSTEM}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"EVIDENCE PASSAGES (the only permitted source of facts):\n"
        f"{json.dumps(evidence, indent=2)}\n\n"
        f"Respond with JSON of exactly this shape:\n{json.dumps(DRAFT_SCHEMA, indent=2)}"
    )
