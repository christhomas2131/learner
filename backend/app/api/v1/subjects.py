"""Subjects."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.schemas import CreateSubjectRequest, SubjectOut
from app.models import Source, Subject, User

router = APIRouter()


@router.get("/subjects", response_model=list[SubjectOut])
async def list_subjects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SubjectOut]:
    rows = (
        await session.execute(select(Subject).where(Subject.user_id == user.id).order_by(Subject.name))
    ).scalars().all()
    count_rows = (
        await session.execute(
            select(Source.subject_id, func.count()).where(Source.user_id == user.id)
            .group_by(Source.subject_id)
        )
    ).all()
    counts: dict[str | None, int] = {sid: c for sid, c in count_rows}
    return [
        SubjectOut(id=s.id, name=s.name, description=s.description,
                   source_count=counts.get(s.id, 0))
        for s in rows
    ]


@router.post("/subjects", response_model=SubjectOut, status_code=201)
async def create_subject(
    body: CreateSubjectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubjectOut:
    subj = Subject(user_id=user.id, name=body.name, description=body.description)
    session.add(subj)
    await session.commit()
    await session.refresh(subj)
    return SubjectOut(id=subj.id, name=subj.name, description=subj.description, source_count=0)
