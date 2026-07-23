"""Command-line entry point: initdb, seed, ask.

`ask` runs the full verification pipeline against the database using the
configured provider (default: deterministic no-model), so the engine is
runnable end-to-end from a terminal with no server and no API key.
"""

from __future__ import annotations

import argparse
import asyncio

from app.core.config import settings
from app.core.enums import ModelProviderKind
from app.db.base import AsyncSessionLocal, new_uuid
from app.db.init_db import create_all
from app.providers.factory import get_provider
from app.services.audit import persist_result, to_response
from app.services.user import get_or_create_demo_user


async def _cmd_initdb() -> None:
    settings.validate_runtime()
    await create_all()
    print(f"Initialized database at {settings.DATABASE_URL}")


async def _cmd_seed() -> None:
    settings.validate_runtime()
    from app.seed import seed

    counts = await seed()
    print(f"Seeded demo data: {counts}")


async def _cmd_ask(question: str, provider_kind: str | None) -> None:
    settings.validate_runtime()
    await create_all()
    kind = ModelProviderKind(provider_kind) if provider_kind else settings.MODEL_PROVIDER
    async with AsyncSessionLocal() as session:
        user = await get_or_create_demo_user(session)
        from app.services.pipeline_runner import build_pipeline

        pipeline = await build_pipeline(session, user.id, provider=get_provider(kind))
        result = await pipeline.run(request_id=new_uuid(), question=question)
        answer_id, audit_id = await persist_result(session, user_id=user.id, result=result)
        resp = to_response(result, audit_id=audit_id)

    print(f"\n=== STATUS: {resp.status} ===")
    print(resp.answer or "(no answer)")
    if resp.claims:
        print("\nClaims:")
        for c in resp.claims:
            print(f"  [{c.status}] {c.text}")
            for e in c.evidence:
                print(f"       ↳ \"{e.quotation}\"  (score {e.retrieval_score})")
    if resp.contradiction_detail:
        print(f"\nContradiction: {resp.contradiction_detail}")
    print(f"\nprovider={resp.pipeline.provider} stages={resp.pipeline.completed_stages}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="learner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("initdb", help="Create database schema + FTS index")
    sub.add_parser("seed", help="Seed demo data")
    ask = sub.add_parser("ask", help="Ask a question through the pipeline")
    ask.add_argument("question")
    ask.add_argument("--provider", choices=[k.value for k in ModelProviderKind], default=None)

    ws = sub.add_parser("worker-serve", help="Keep-alive loop: heartbeat + auto-finish deterministic")
    ws.add_argument("--interval", type=int, default=10)
    sub.add_parser("worker-list", help="List pending premium (Claude Code) questions")
    wp = sub.add_parser("worker-prep", help="Claim + retrieve for a premium question")
    wp.add_argument("item_id")
    wf = sub.add_parser("worker-finish", help="Finish a premium question with draft+verify JSON")
    wf.add_argument("item_id")
    wf.add_argument("draft_json")
    wf.add_argument("verify_json")

    args = parser.parse_args()
    if args.command == "initdb":
        asyncio.run(_cmd_initdb())
    elif args.command == "seed":
        asyncio.run(_cmd_seed())
    elif args.command == "ask":
        asyncio.run(_cmd_ask(args.question, args.provider))
    elif args.command == "worker-serve":
        from app.worker import worker_serve

        asyncio.run(worker_serve(args.interval))
    elif args.command == "worker-list":
        from app.worker import worker_list

        asyncio.run(worker_list())
    elif args.command == "worker-prep":
        from app.worker import worker_prep

        asyncio.run(worker_prep(args.item_id))
    elif args.command == "worker-finish":
        from app.worker import worker_finish

        asyncio.run(worker_finish(args.item_id, args.draft_json, args.verify_json))


if __name__ == "__main__":
    main()
