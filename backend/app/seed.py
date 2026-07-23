"""Development seed data. Everything created here is marked is_demo=True."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.enums import SourceState, SourceType
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all
from app.ingestion.service import ingest_file, ingest_structured, set_source_state
from app.models import Session, Subject
from app.services.user import get_or_create_demo_user

KNOWLEDGE = settings.KNOWLEDGE_DIRECTORY


async def seed() -> dict[str, int]:
    await create_all()
    counts = {"subjects": 0, "sources": 0, "sessions": 0}

    async with AsyncSessionLocal() as session:
        user = await get_or_create_demo_user(session)

        # Subjects
        subject_ids: dict[str, str] = {}
        for name in ("Biology", "History", "Mathematics"):
            existing = (
                await session.execute(
                    select(Subject).where(Subject.user_id == user.id, Subject.name == name)
                )
            ).scalars().first()
            if existing is None:
                subj = Subject(user_id=user.id, name=name, description=f"{name} materials")
                session.add(subj)
                await session.flush()
                subject_ids[name] = subj.id
                counts["subjects"] += 1
            else:
                subject_ids[name] = existing.id
        await session.commit()

        async def ingest_md(fname: str, title: str, subject: str, approve: bool) -> None:
            path = KNOWLEDGE / fname
            if not path.exists():
                return
            data = path.read_bytes()
            try:
                src = await ingest_file(
                    session, user_id=user.id, filename=fname, data=data, title=title,
                    subject_id=subject_ids.get(subject), is_demo=True, save_file=False,
                )
            except Exception:  # noqa: BLE001 - duplicate on re-seed is fine
                return
            if approve:
                await set_source_state(session, src, SourceState.APPROVED)
            counts["sources"] += 1

        await ingest_md("biology_intro.md", "Introduction to Biology", "Biology", approve=True)
        await ingest_md("history_rome.md", "A Short History of Rome", "History", approve=True)
        # Contradictory pair (both approved on purpose to demonstrate CONTRADICTION).
        await ingest_md("pluto_v1_2005.md", "Solar System Reference (2005)", "Biology", approve=True)
        await ingest_md("pluto_v2_2006.md", "Solar System Reference (2006)", "Biology", approve=True)
        # A source left pending approval, to show the approval workflow.
        await ingest_md("history_rome.md", "Rome (pending copy)", "History", approve=False)

        # Structured definitions + answer key (drive deterministic resolvers).
        try:
            defs = await ingest_structured(
                session, user_id=user.id, source_type=SourceType.STRUCTURED_RECORD,
                title="Biology Glossary", subject_id=subject_ids["Biology"], is_demo=True,
                records=[
                    {"term": "photosynthesis",
                     "definition": "Photosynthesis converts light energy into chemical energy."},
                    {"term": "mitochondria",
                     "definition": "Mitochondria are the organelles where most cellular respiration occurs."},
                ],
            )
            await set_source_state(session, defs, SourceState.APPROVED)
            counts["sources"] += 1
        except Exception:  # noqa: BLE001
            pass

        try:
            key = await ingest_structured(
                session, user_id=user.id, source_type=SourceType.ANSWER_KEY,
                title="Sample Answer Key", subject_id=subject_ids["Mathematics"], is_demo=True,
                records=[{"question": "What year was the Roman Republic established?",
                          "answer": "509 BC"}],
            )
            await set_source_state(session, key, SourceState.APPROVED)
            counts["sources"] += 1
        except Exception:  # noqa: BLE001
            pass

        # Example session
        existing_session = (
            await session.execute(select(Session).where(Session.user_id == user.id))
        ).scalars().first()
        if existing_session is None:
            session.add(Session(
                user_id=user.id, title="Getting started with Biology",
                subject_id=subject_ids["Biology"], saved=True, is_demo=True,
            ))
            counts["sessions"] += 1
        await session.commit()

    return counts
