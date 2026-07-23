"""Source library: upload, list, inspect, approve/reject, reindex, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Pagination, get_current_user, get_session, pagination
from app.api.errors import APIError, NotFoundError, ValidationError
from app.api.schemas import Page, PassageOut, SourceOut, UpdateSourceRequest
from app.core.enums import SourceState
from app.ingestion.service import (
    DuplicateSourceError,
    EmptyDocumentError,
    IngestionError,
    UnsupportedFileError,
    ingest_file,
    reindex_source,
    set_source_state,
)
from app.models import Source, User
from app.services import sources as svc

router = APIRouter()


async def _to_out(session: AsyncSession, s: Source) -> SourceOut:
    return SourceOut(
        id=s.id, title=s.title, source_type=s.source_type, state=s.state, is_demo=s.is_demo,
        subject_id=s.subject_id, author=s.author, organization=s.organization,
        publication_date=s.publication_date, url=s.url, content_hash=s.content_hash,
        original_filename=s.original_filename, byte_size=s.byte_size,
        passage_count=await svc.passage_count(session, s.id),
        created_at=s.created_at, updated_at=s.updated_at,
    )


@router.get("/sources", response_model=Page[SourceOut])
async def list_sources(
    page: Pagination = Depends(pagination),
    state: str | None = Query(None),
    subject_id: str | None = Query(None),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Page[SourceOut]:
    rows, total, _counts = await svc.list_sources(
        session, user, limit=page.limit, offset=page.offset, state=state,
        subject_id=subject_id, search=search,
    )
    items = [await _to_out(session, s) for s in rows]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.post("/sources/upload", response_model=SourceOut, status_code=201)
async def upload_source(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    subject_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    data = await file.read()
    try:
        src = await ingest_file(
            session, user_id=user.id, filename=file.filename or "upload",
            data=data, title=title, subject_id=subject_id,
        )
    except DuplicateSourceError as e:
        raise APIError("duplicate_source", str(e), 409) from e
    except (UnsupportedFileError, EmptyDocumentError) as e:
        raise ValidationError(str(e)) from e
    except IngestionError as e:
        raise ValidationError(str(e)) from e
    return await _to_out(session, src)


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    return await _to_out(session, src)


@router.get("/sources/{source_id}/passages", response_model=list[PassageOut])
async def get_passages(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PassageOut]:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    rows = await svc.list_passages(session, source_id)
    return [PassageOut(id=p.id, chunk_index=p.chunk_index, text=p.text) for p in rows]


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: str,
    body: UpdateSourceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(src, field, value)
    await session.commit()
    await session.refresh(src)
    return await _to_out(session, src)


@router.post("/sources/{source_id}/approve", response_model=SourceOut)
async def approve_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    await set_source_state(session, src, SourceState.APPROVED)
    return await _to_out(session, src)


@router.post("/sources/{source_id}/reject", response_model=SourceOut)
async def reject_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    await set_source_state(session, src, SourceState.REJECTED)
    return await _to_out(session, src)


@router.post("/sources/{source_id}/reindex", response_model=SourceOut)
async def reindex(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    await reindex_source(session, src)
    await session.commit()
    return await _to_out(session, src)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    src = await svc.get_owned_source(session, user, source_id)
    if src is None:
        raise NotFoundError("Source not found.")
    await set_source_state(session, src, SourceState.ARCHIVED)
    await session.delete(src)
    await session.commit()
