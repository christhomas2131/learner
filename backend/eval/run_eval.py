"""Hallucination scorecard — measures the core promise on a gold set.

Seeds a fresh temp DB from the demo corpus, runs each gold question through the
grounded (no-model) pipeline, and scores:
  - status accuracy : does the top-level verdict match the expected outcome
                      (VERIFIED / INSUFFICIENT_EVIDENCE / CONTRADICTION)?
  - retrieval hit   : for questions with an expected source, is that source in
                      the retrieved pool?

Hermetic + fast: no model, no embeddings (FTS-only), no network. Exits non-zero
if status accuracy is below EVAL_MIN_ACCURACY (default 1.0) so CI can gate on it.

    python eval/run_eval.py        # from the backend/ dir
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import tempfile

_TMP = tempfile.mkdtemp(prefix="learner-eval-")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/eval.db")
os.environ.setdefault("UPLOAD_DIRECTORY", f"{_TMP}/uploads")
os.environ.setdefault("MODEL_PROVIDER", "none")
os.environ.setdefault("RETRIEVAL_USE_EMBEDDINGS", "false")
os.environ.setdefault("AUTO_DISCOVERY_ENABLED", "false")  # hermetic: no web calls

from app.core.enums import ModelProviderKind  # noqa: E402
from app.db.base import AsyncSessionLocal, new_uuid  # noqa: E402
from app.providers.factory import get_provider  # noqa: E402
from app.seed import seed  # noqa: E402
from app.services.pipeline_runner import _build_retriever, build_pipeline  # noqa: E402
from app.services.user import get_or_create_demo_user  # noqa: E402

GOLD = json.loads((pathlib.Path(__file__).parent / "gold.json").read_text())
MIN_ACCURACY = float(os.environ.get("EVAL_MIN_ACCURACY", "1.0"))


async def run() -> int:
    await seed()
    rows = []
    async with AsyncSessionLocal() as session:
        user = await get_or_create_demo_user(session)
        for item in GOLD:
            q = item["question"]
            pipeline = await build_pipeline(
                session, user.id, provider=get_provider(ModelProviderKind.NONE)
            )
            result = await pipeline.run(request_id=new_uuid(), question=q)
            got = str(result.status)
            status_ok = got == item["expect_status"]

            hit: bool | None = None
            if item.get("expect_source"):
                passages = await _build_retriever(session).retrieve(q, None, 8)
                hit = any(
                    item["expect_source"].lower() in p.source_title.lower() for p in passages
                )
            rows.append({"q": q, "expect": item["expect_status"], "got": got,
                         "status_ok": status_ok, "hit": hit})

    _report(rows)
    status_acc = sum(r["status_ok"] for r in rows) / len(rows)
    return 0 if status_acc >= MIN_ACCURACY else 1


def _report(rows: list[dict]) -> None:
    print("\nHALLUCINATION SCORECARD")
    print("=" * 78)
    for r in rows:
        mark = "PASS" if r["status_ok"] else "FAIL"
        hit = "" if r["hit"] is None else ("  ret:hit" if r["hit"] else "  ret:MISS")
        print(f"  [{mark}] {r['expect']:<22} got {r['got']:<22}{hit}  {r['q'][:38]}")
    n = len(rows)
    status_acc = sum(r["status_ok"] for r in rows) / n
    hit_rows = [r for r in rows if r["hit"] is not None]
    hit_rate = (sum(r["hit"] for r in hit_rows) / len(hit_rows)) if hit_rows else 1.0
    print("-" * 78)
    print(f"  status accuracy : {status_acc:.0%}  ({sum(r['status_ok'] for r in rows)}/{n})")
    print(f"  retrieval hit   : {hit_rate:.0%}  ({sum(r['hit'] for r in hit_rows)}/{len(hit_rows)})")
    fails = [r for r in rows if not r["status_ok"]]
    if fails:
        print("  FAILURES:")
        for r in fails:
            print(f"    - {r['q']}  (expected {r['expect']}, got {r['got']})")
    print("=" * 78)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
