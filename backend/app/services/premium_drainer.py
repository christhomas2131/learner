"""In-process premium queue drainer.

Runs inside the API when the `claude` CLI is available. It heartbeats (so the UI
shows the worker online) and auto-answers pending premium questions via
ClaudeCliProvider — hands-off, no separate terminal. The deterministic harness
still validates and gates every answer.
"""

from __future__ import annotations

import asyncio

from app.core.enums import QueueStatus
from app.core.logging import get_logger
from app.db.base import AsyncSessionLocal, utcnow
from app.providers.claude_cli import ClaudeCliProvider
from app.services import queue as queue_svc
from app.services.audit import persist_result
from app.services.pipeline_runner import build_pipeline
from app.services.user import get_or_create_demo_user
from app.services.worker_status import touch_heartbeat

log = get_logger("premium_drainer")


async def _process_one(session, user, item, provider) -> str:  # noqa: ANN001
    item.status = QueueStatus.PROCESSING
    item.claimed_at = utcnow()
    await session.commit()
    pipeline = await build_pipeline(session, user.id, provider=provider)
    result = await pipeline.run(
        request_id=item.request_id,
        question=" ".join(item.question.split()),
        session_id=item.session_id,
        approved_source_ids=item.approved_source_ids,
    )
    answer_id, _audit = await persist_result(session, user_id=user.id, result=result)
    await queue_svc.complete_item(session, item, answer_id)
    return str(result.status)


async def run_drainer(interval: float, stop: asyncio.Event) -> None:
    provider = ClaudeCliProvider()
    log.info("premium_drainer_started", interval=interval)
    while not stop.is_set():
        try:
            touch_heartbeat()
            async with AsyncSessionLocal() as session:
                user = await get_or_create_demo_user(session)
                items, _ = await queue_svc.list_items(session, user, QueueStatus.PENDING, limit=20)
                for item in items:
                    try:
                        status = await _process_one(session, user, item, provider)
                        log.info("premium_drained", item=item.id, status=status)
                    except Exception as e:  # noqa: BLE001
                        await queue_svc.fail_item(session, item, str(e))
                        log.warning("premium_drain_failed", item=item.id, error=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("premium_drainer_error", error=str(e))
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
