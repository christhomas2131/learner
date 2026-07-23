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
from app.retrieval.fts import SqliteFtsRetriever
from app.services.audit import persist_result, to_response
from app.services.records import load_resolver_records
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
        retriever = SqliteFtsRetriever(session, min_score=settings.RETRIEVAL_MIN_SCORE)
        definitions, answer_keys = await load_resolver_records(session, user.id)
        from app.pipeline.engine import VerifiedLearningPipeline

        pipeline = VerifiedLearningPipeline(
            retriever, get_provider(kind),
            retrieval_limit=settings.RETRIEVAL_LIMIT,
            max_model_retries=settings.MAX_MODEL_RETRIES,
            max_pipeline_attempts=settings.MAX_PIPELINE_ATTEMPTS,
            definition_records=definitions, answer_key_records=answer_keys,
        )
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

    args = parser.parse_args()
    if args.command == "initdb":
        asyncio.run(_cmd_initdb())
    elif args.command == "seed":
        asyncio.run(_cmd_seed())
    elif args.command == "ask":
        asyncio.run(_cmd_ask(args.question, args.provider))


if __name__ == "__main__":
    main()
