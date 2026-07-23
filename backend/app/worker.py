"""Claude Code worker: drain the premium question queue.

This is how the user's Claude Code session powers premium answers WITHOUT an API
key. The worker runs the identical Python pipeline; at the draft and verify
steps the model is *you* (the Claude Code agent operating this CLI). The harness
still validates every quotation and applies the release gate — the model cannot
bypass it.

Flow (driven interactively from a Claude Code session):
  1. `learner worker-prep <id>`  -> claims the item, retrieves passages, prints
     the DRAFT prompt. If the question is deterministically resolvable it is
     finished immediately.
  2. You write the draft JSON and the verify JSON to files.
  3. `learner worker-finish <id> <draft.json> <verify.json>` -> runs the full
     pipeline with your JSON as the model output, persists, marks the item DONE.
"""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.enums import QueueStatus
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all
from app.pipeline.resolvers import (
    answer_key_resolver,
    definition_resolver,
    resolve_computational,
)
from app.prompts.drafting import build_draft_prompt
from app.providers.claude_code import ClaudeCodeProvider
from app.retrieval.fts import SqliteFtsRetriever
from app.schemas.pipeline import DraftResponse, VerifierResult
from app.services import queue as queue_svc
from app.services.audit import persist_result, to_response
from app.services.pipeline_runner import build_pipeline
from app.services.records import load_resolver_records
from app.services.user import get_or_create_demo_user


async def worker_list() -> None:
    await create_all()
    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        items, total = await queue_svc.list_items(s, user, QueueStatus.PENDING, limit=100)
        print(f"{total} pending premium question(s):")
        for i in items:
            print(f"  {i.id}  | {i.question}")
        if not items:
            print("  (none)")


async def worker_prep(item_id: str) -> None:
    await create_all()
    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        item = await queue_svc.get_item(s, user, item_id)
        if item is None:
            print(f"No queue item {item_id}")
            return
        if item.status not in (QueueStatus.PENDING, QueueStatus.PROCESSING):
            print(f"Item is {item.status}; nothing to do.")
            return
        item.status = QueueStatus.PROCESSING
        await s.commit()

        question = " ".join(item.question.split())
        definitions, answer_keys = await load_resolver_records(s, user.id)

        # Deterministic short-circuit: finish now, no drafting needed.
        if (resolve_computational(question)
                or definition_resolver(question, definitions)
                or answer_key_resolver(question, answer_keys)):
            provider = ClaudeCodeProvider()  # won't be called for deterministic
            pipeline = await build_pipeline(s, user.id, provider=provider)
            result = await pipeline.run(request_id=item.request_id, question=question,
                                        session_id=item.session_id,
                                        approved_source_ids=item.approved_source_ids)
            answer_id, _audit = await persist_result(s, user_id=user.id, result=result)
            await queue_svc.complete_item(s, item, answer_id)
            print(f"Deterministically resolved -> {result.status}. Item DONE.")
            return

        retriever = SqliteFtsRetriever(s, min_score=settings.RETRIEVAL_MIN_SCORE)
        passages = await retriever.retrieve(question, item.approved_source_ids,
                                            settings.RETRIEVAL_LIMIT)
        if not passages:
            result = await (await build_pipeline(s, user.id, provider=ClaudeCodeProvider())).run(
                request_id=item.request_id, question=question, session_id=item.session_id,
                approved_source_ids=item.approved_source_ids,
            )
            answer_id, _ = await persist_result(s, user_id=user.id, result=result)
            await queue_svc.complete_item(s, item, answer_id)
            print(f"No approved passages -> {result.status} (abstained). Item DONE.")
            return

        print("=" * 70)
        print("DRAFT PROMPT — produce draft JSON, then run worker-finish.")
        print("=" * 70)
        print(build_draft_prompt(question, passages))


async def worker_finish(item_id: str, draft_path: str, verify_path: str) -> None:
    await create_all()
    with open(draft_path) as f:
        draft_dict = json.load(f)
    with open(verify_path) as f:
        verify_list = json.load(f)

    draft = DraftResponse.model_validate(draft_dict)
    verifier_results = [VerifierResult.model_validate(v) for v in verify_list]

    async def draft_fn(_q, _p, _prev):  # noqa: ANN001, ANN202
        return draft

    async def verify_fn(_claims, _passages):  # noqa: ANN001, ANN202
        return verifier_results

    provider = ClaudeCodeProvider(draft_fn=draft_fn, verify_fn=verify_fn)

    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        item = await queue_svc.get_item(s, user, item_id)
        if item is None:
            print(f"No queue item {item_id}")
            return
        pipeline = await build_pipeline(s, user.id, provider=provider)
        result = await pipeline.run(
            request_id=item.request_id, question=" ".join(item.question.split()),
            session_id=item.session_id, approved_source_ids=item.approved_source_ids,
        )
        try:
            answer_id, audit_id = await persist_result(s, user_id=user.id, result=result)
            await queue_svc.complete_item(s, item, answer_id)
        except Exception as e:  # noqa: BLE001
            await queue_svc.fail_item(s, item, str(e))
            raise
        resp = to_response(result, audit_id=audit_id)
        print(f"=== STATUS: {resp.status} ===")
        print(resp.answer or "(no answer)")
        for c in resp.claims:
            print(f"  [{c.status}] {c.text}")
        print(f"Item {item_id} -> DONE (answer {answer_id})")
