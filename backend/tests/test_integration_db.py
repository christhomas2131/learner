"""Integration tests against a real SQLite database with FTS5.

Exercises ingestion, the approval workflow, DB-backed FTS retrieval, and a full
pipeline run end-to-end (no-model provider), plus audit persistence.
"""

from __future__ import annotations

import io

import pytest

from app.core.enums import SourceState, SourceType, TopLevelStatus
from app.db.base import AsyncSessionLocal, new_uuid
from app.db.init_db import create_all, drop_all
from app.ingestion.service import (
    DuplicateSourceError,
    EmptyDocumentError,
    UnsupportedFileError,
    ingest_file,
    ingest_structured,
    set_source_state,
)
from app.pipeline.engine import VerifiedLearningPipeline
from app.providers.nomodel import NoModelProvider
from app.retrieval.fts import SqliteFtsRetriever
from app.services.audit import persist_result
from app.services.records import load_resolver_records
from app.services.user import get_or_create_demo_user

BIO = (
    b"# Biology\n\nPhotosynthesis converts light energy into chemical energy. "
    b"It occurs in the chloroplasts of plant cells.\n"
)


@pytest.fixture(autouse=True)
async def fresh_db():
    await drop_all()
    await create_all()
    yield
    await drop_all()


async def _user_session():
    session = AsyncSessionLocal()
    user = await get_or_create_demo_user(session)
    return session, user


async def test_ingest_approve_retrieve_and_verify():
    session, user = await _user_session()
    async with session:
        src = await ingest_file(session, user_id=user.id, filename="bio.md", data=BIO,
                                title="Biology", save_file=False)
        assert src.state == SourceState.PENDING_APPROVAL

        # Not retrievable until approved.
        retriever = SqliteFtsRetriever(session)
        assert await retriever.retrieve("photosynthesis", None, 5) == []

        await set_source_state(session, src, SourceState.APPROVED)
        passages = await retriever.retrieve("photosynthesis", None, 5)
        assert passages and all(p.approved for p in passages)

        pipeline = VerifiedLearningPipeline(retriever, NoModelProvider())
        result = await pipeline.run(request_id=new_uuid(), question="What is photosynthesis?")
        assert result.status == TopLevelStatus.VERIFIED

        answer_id, audit_id = await persist_result(session, user_id=user.id, result=result)
        assert answer_id and audit_id


async def test_duplicate_detection():
    session, user = await _user_session()
    async with session:
        await ingest_file(session, user_id=user.id, filename="bio.md", data=BIO, save_file=False)
        with pytest.raises(DuplicateSourceError):
            await ingest_file(session, user_id=user.id, filename="bio2.md", data=BIO, save_file=False)


async def test_empty_document_rejected():
    session, user = await _user_session()
    async with session:
        with pytest.raises(EmptyDocumentError):
            await ingest_file(session, user_id=user.id, filename="empty.md", data=b"   ",
                              save_file=False)


async def test_unsupported_file_rejected():
    session, user = await _user_session()
    async with session:
        with pytest.raises(UnsupportedFileError):
            await ingest_file(session, user_id=user.id, filename="malware.exe", data=b"MZ...",
                              save_file=False)


async def test_docx_extraction():
    import docx

    buf = io.BytesIO()
    document = docx.Document()
    document.add_paragraph("The mitochondria is the powerhouse of the cell.")
    document.save(buf)

    session, user = await _user_session()
    async with session:
        src = await ingest_file(session, user_id=user.id, filename="cell.docx",
                                data=buf.getvalue(), save_file=False)
        await set_source_state(session, src, SourceState.APPROVED)
        passages = await SqliteFtsRetriever(session).retrieve("mitochondria", None, 5)
        assert passages and "mitochondria" in passages[0].text.lower()


async def test_pdf_extraction():
    from pypdf import PdfWriter

    # Minimal PDF has no extractable text; assert extraction path doesn't crash
    # and empty text is rejected as an empty document.
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    session, user = await _user_session()
    async with session:
        with pytest.raises(EmptyDocumentError):
            await ingest_file(session, user_id=user.id, filename="blank.pdf",
                              data=buf.getvalue(), save_file=False)


async def test_structured_records_drive_definition_resolver():
    session, user = await _user_session()
    async with session:
        src = await ingest_structured(
            session, user_id=user.id, source_type=SourceType.STRUCTURED_RECORD,
            title="Glossary",
            records=[{"term": "osmosis",
                      "definition": "Osmosis is the movement of water across a membrane."}],
        )
        await set_source_state(session, src, SourceState.APPROVED)
        definitions, answer_keys = await load_resolver_records(session, user.id)
        assert any(d["term"] == "osmosis" for d in definitions)

        pipeline = VerifiedLearningPipeline(
            SqliteFtsRetriever(session), NoModelProvider(),
            definition_records=definitions, answer_key_records=answer_keys,
        )
        result = await pipeline.run(request_id=new_uuid(), question="what is osmosis?")
        assert result.status == TopLevelStatus.VERIFIED
        assert result.claims[0].citations
