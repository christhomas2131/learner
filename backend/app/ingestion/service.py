"""Source ingestion service.

Uploaded material is never trusted: every source lands in PENDING_APPROVAL and
must be explicitly approved before retrieval can use it. Files are stored under
a non-public uploads directory; content is hashed for dedup; empty documents are
rejected.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import SourceState, SourceType
from app.core.security import content_hash, sanitize_filename, source_type_for_extension
from app.ingestion.chunk import chunk_text
from app.ingestion.extract import ExtractionError, extract_text
from app.models import IngestionJob, PassageVector, Source, SourcePassage
from app.retrieval.embeddings import get_embedder
from app.retrieval.fts import index_passages, remove_source_from_index


async def _index_vectors(session: AsyncSession, rows: list[tuple[str, str, str]]) -> None:
    """Embed passages and store vectors (no-op if embeddings unavailable)."""
    embedder = get_embedder()
    if not embedder.available or not rows:
        return
    vectors = embedder.embed([text for _, _, text in rows])
    if not vectors:
        return
    for (pid, sid, _text), vec in zip(rows, vectors, strict=False):
        session.add(PassageVector(passage_id=pid, source_id=sid, dim=len(vec), vector=vec))


class IngestionError(Exception):
    pass


class DuplicateSourceError(IngestionError):
    def __init__(self, existing_id: str) -> None:
        super().__init__("Duplicate document (same content hash already ingested).")
        self.existing_id = existing_id


class UnsupportedFileError(IngestionError):
    pass


class EmptyDocumentError(IngestionError):
    pass


async def _find_duplicate(session: AsyncSession, user_id: str, digest: str) -> Source | None:
    stmt = select(Source).where(
        Source.user_id == user_id,
        Source.content_hash == digest,
        Source.state.notin_([SourceState.REJECTED, SourceState.ARCHIVED]),
    )
    return (await session.execute(stmt)).scalars().first()


async def ingest_file(
    session: AsyncSession,
    *,
    user_id: str,
    filename: str,
    data: bytes,
    title: str | None = None,
    subject_id: str | None = None,
    is_demo: bool = False,
    save_file: bool = True,
) -> Source:
    if len(data) > settings.max_upload_bytes:
        raise IngestionError(
            f"File exceeds the maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )
    source_type = source_type_for_extension(filename)
    if source_type is None:
        raise UnsupportedFileError(f"Unsupported file type: {filename}")

    digest = content_hash(data)
    dup = await _find_duplicate(session, user_id, digest)
    if dup is not None:
        raise DuplicateSourceError(dup.id)

    try:
        text = extract_text(data, source_type)
    except ExtractionError as e:
        raise IngestionError(str(e)) from e
    if not text.strip():
        raise EmptyDocumentError("Document contains no extractable text.")

    safe_name = sanitize_filename(filename)
    stored_path: str | None = None
    if save_file:
        settings.UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
        dest = settings.UPLOAD_DIRECTORY / f"{digest[:16]}_{safe_name}"
        Path(dest).write_bytes(data)
        stored_path = str(dest)

    source = Source(
        user_id=user_id, title=title or safe_name, source_type=source_type,
        state=SourceState.PROCESSING, is_demo=is_demo, content_hash=digest,
        original_filename=safe_name, stored_path=stored_path, byte_size=len(data),
        subject_id=subject_id,
    )
    session.add(source)
    await session.flush()

    passages = await _create_passages(session, source, text)
    fts_rows = [(p.id, source.id, p.text) for p in passages]
    await index_passages(session, fts_rows)
    await _index_vectors(session, fts_rows)

    session.add(IngestionJob(source_id=source.id, state="DONE", passage_count=len(passages)))
    source.state = SourceState.PENDING_APPROVAL
    await session.commit()
    await session.refresh(source)
    return source


async def ingest_structured(
    session: AsyncSession,
    *,
    user_id: str,
    source_type: SourceType,
    title: str,
    records: list[dict],
    subject_id: str | None = None,
    is_demo: bool = False,
) -> Source:
    """Ingest a STRUCTURED_RECORD (definitions) or ANSWER_KEY source.

    Each record becomes a citable passage. `records` for STRUCTURED_RECORD:
    [{term, definition}]; for ANSWER_KEY: [{question, answer}].
    """
    if source_type not in (SourceType.STRUCTURED_RECORD, SourceType.ANSWER_KEY):
        raise IngestionError("ingest_structured only supports STRUCTURED_RECORD / ANSWER_KEY.")
    if not records:
        raise EmptyDocumentError("No records provided.")

    digest = content_hash(repr(records).encode())
    dup = await _find_duplicate(session, user_id, digest)
    if dup is not None:
        raise DuplicateSourceError(dup.id)

    source = Source(
        user_id=user_id, title=title, source_type=source_type,
        state=SourceState.PROCESSING, is_demo=is_demo, content_hash=digest,
        subject_id=subject_id, structured_data=None,
    )
    session.add(source)
    await session.flush()

    passages: list[SourcePassage] = []
    fts_rows: list[tuple[str, str, str]] = []
    records_out: list[dict] = []
    for i, rec in enumerate(records):
        value = rec.get("definition") if source_type == SourceType.STRUCTURED_RECORD else rec.get("answer")
        # Passage text is the value only (no "term:" prefix) so it reads cleanly
        # and stays a valid substring for the verifier; the term/question lives in
        # structured_data for the deterministic resolver.
        passage_text = value or ""
        passage = SourcePassage(source_id=source.id, chunk_index=i, text=passage_text,
                                char_start=0, char_end=len(passage_text or ""))
        session.add(passage)
        await session.flush()
        passages.append(passage)
        fts_rows.append((passage.id, source.id, passage.text))
        entry = dict(rec)
        entry["passage_id"] = passage.id
        records_out.append(entry)

    # Assign a fresh dict so SQLAlchemy persists the change (JSON is not mutable-tracked).
    source.structured_data = {"records": records_out, "kind": source_type.value}
    await index_passages(session, fts_rows)
    await _index_vectors(session, fts_rows)
    session.add(IngestionJob(source_id=source.id, state="DONE", passage_count=len(passages)))
    source.state = SourceState.PENDING_APPROVAL
    await session.commit()
    await session.refresh(source)
    return source


async def ingest_website(
    session: AsyncSession,
    *,
    user_id: str,
    url: str,
    title: str | None = None,
    subject_id: str | None = None,
    is_demo: bool = False,
    discovered: bool = False,
) -> Source:
    """Fetch, snapshot, and ingest a web page as an APPROVED_WEBSITE source.

    The stored passages are the snapshot the pipeline will cite — never live
    page content.
    """
    from app.db.base import utcnow
    from app.ingestion.web import WebFetchError, fetch_and_extract

    try:
        page_title, text = await fetch_and_extract(url)
    except WebFetchError as e:
        raise IngestionError(str(e)) from e

    digest = content_hash(f"{url}\n{text}".encode())
    dup = await _find_duplicate(session, user_id, digest)
    if dup is not None:
        raise DuplicateSourceError(dup.id)

    source = Source(
        user_id=user_id, title=title or page_title, source_type=SourceType.APPROVED_WEBSITE,
        state=SourceState.PROCESSING, is_demo=is_demo, content_hash=digest, url=url,
        subject_id=subject_id, byte_size=len(text.encode()),
        structured_data={"kind": "APPROVED_WEBSITE", "url": url,
                         "fetched_at": utcnow().isoformat(), "discovered": discovered},
    )
    session.add(source)
    await session.flush()

    passages = await _create_passages(session, source, text)
    fts_rows = [(p.id, source.id, p.text) for p in passages]
    await index_passages(session, fts_rows)
    await _index_vectors(session, fts_rows)
    session.add(IngestionJob(source_id=source.id, state="DONE", passage_count=len(passages)))
    source.state = SourceState.PENDING_APPROVAL
    await session.commit()
    await session.refresh(source)
    return source


async def _create_passages(session: AsyncSession, source: Source, text: str) -> list[SourcePassage]:
    passages: list[SourcePassage] = []
    for chunk in chunk_text(text):
        passage = SourcePassage(
            source_id=source.id, chunk_index=chunk.index, text=chunk.text,
            char_start=chunk.char_start, char_end=chunk.char_end,
        )
        session.add(passage)
        await session.flush()
        passages.append(passage)
    return passages


async def set_source_state(session: AsyncSession, source: Source, state: SourceState) -> Source:
    source.state = state
    if state in (SourceState.REJECTED, SourceState.ARCHIVED):
        await remove_source_from_index(session, source.id)
    await session.commit()
    await session.refresh(source)
    return source


async def reindex_source(session: AsyncSession, source: Source) -> int:
    """Rebuild the FTS + vector entries for a source from its stored passages."""
    await remove_source_from_index(session, source.id)
    await session.execute(delete(PassageVector).where(PassageVector.source_id == source.id))
    rows = (
        await session.execute(
            select(SourcePassage).where(SourcePassage.source_id == source.id)
        )
    ).scalars().all()
    fts_rows = [(p.id, source.id, p.text) for p in rows]
    await index_passages(session, fts_rows)
    await _index_vectors(session, fts_rows)
    return len(rows)
