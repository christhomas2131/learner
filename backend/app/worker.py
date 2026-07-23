"""Claude Code worker: drain the premium question queue.

This is how the user's Claude Code session powers premium answers WITHOUT an API
key. The worker runs the identical Python pipeline; at the draft and verify
steps the model is *you* (the Claude Code agent operating this CLI). The harness
still validates every quotation and applies the release gate.

Commands:
  learner worker-serve                 keep-alive loop: heartbeats (UI shows the
                                       worker online) + auto-finishes any
                                       deterministically-resolvable questions.
  learner worker-list                  show pending premium questions.
  learner worker-prep <id>             claim + retrieve; prints the DRAFT prompt.
  learner worker-finish <id> d.json v.json   run the pipeline with your JSON.
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.core.enums import QueueStatus
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all
from app.models import QuestionQueue, User
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
from app.services.worker_status import touch_heartbeat


async def _is_deterministic(session, user_id: str, question: str) -> bool:
    definitions, answer_keys = await load_resolver_records(session, user_id)
    return bool(
        resolve_computational(question)
        or definition_resolver(question, definitions)
        or answer_key_resolver(question, answer_keys)
    )


async def _finish(session, user: User, item: QuestionQueue, question: str) -> str:
    """Run the pipeline for `item` (deterministic or abstain) and mark it DONE."""
    pipeline = await build_pipeline(session, user.id, provider=ClaudeCodeProvider())
    result = await pipeline.run(
        request_id=item.request_id, question=question, session_id=item.session_id,
        approved_source_ids=item.approved_source_ids,
    )
    answer_id, _audit = await persist_result(session, user_id=user.id, result=result)
    await queue_svc.complete_item(session, item, answer_id)
    return str(result.status)


async def worker_list() -> None:
    await create_all()
    touch_heartbeat()
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
    touch_heartbeat()
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
        if await _is_deterministic(s, user.id, question):
            status = await _finish(s, user, item, question)
            print(f"Deterministically resolved -> {status}. Item DONE.")
            return

        retriever = SqliteFtsRetriever(s, min_score=settings.RETRIEVAL_MIN_SCORE)
        passages = await retriever.retrieve(question, item.approved_source_ids, settings.RETRIEVAL_LIMIT)
        if not passages:
            status = await _finish(s, user, item, question)
            print(f"No approved passages -> {status} (abstained). Item DONE.")
            return

        print("=" * 70)
        print("DRAFT PROMPT — produce draft JSON, then run worker-finish.")
        print("=" * 70)
        print(build_draft_prompt(question, passages))


async def worker_finish(item_id: str, draft_path: str, verify_path: str) -> None:
    await create_all()
    touch_heartbeat()
    with open(draft_path) as f:
        draft = DraftResponse.model_validate(json.load(f))
    with open(verify_path) as f:
        verifier_results = [VerifierResult.model_validate(v) for v in json.load(f)]

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
        print(f"Item {item_id} -> DONE (answer {answer_id})")


async def worker_serve(interval: int = 10) -> None:
    """Keep-alive loop: heartbeat + auto-finish deterministic items.

    Model-needing questions are left PENDING and reported so you can run
    worker-prep / worker-finish on them.
    """
    await create_all()
    print(f"Worker serving (heartbeat every {interval}s). Ctrl-C to stop.")
    while True:
        touch_heartbeat()
        async with AsyncSessionLocal() as s:
            user = await get_or_create_demo_user(s)
            items, _ = await queue_svc.list_items(s, user, QueueStatus.PENDING, limit=100)
            for item in items:
                question = " ".join(item.question.split())
                if await _is_deterministic(s, user.id, question):
                    status = await _finish(s, user, item, question)
                    print(f"[worker] auto-resolved {item.id} -> {status}")
                else:
                    print(f"[worker] needs drafting: {item.id} | {item.question}")
        await asyncio.sleep(interval)
