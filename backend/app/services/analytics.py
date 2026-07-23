"""Learning + operational analytics derived from persisted answers."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TopLevelStatus
from app.models import Answer, Claim, Session, Source, Subject, User


async def compute_analytics(session: AsyncSession, user: User) -> dict:
    answers = (
        await session.execute(
            select(Answer).join(Session, Answer.session_id == Session.id)
            .where(Session.user_id == user.id)
        )
    ).scalars().all()

    total = len(answers)
    status_breakdown: dict[str, int] = {s.value: 0 for s in TopLevelStatus}
    duration_sum = 0
    for a in answers:
        status_breakdown[a.status.value if hasattr(a.status, "value") else str(a.status)] += 1
        duration_sum += a.duration_ms

    def rate(status: TopLevelStatus) -> float:
        return round(status_breakdown[status.value] / total, 4) if total else 0.0

    # Average claim count per answer.
    claim_total = (
        await session.execute(
            select(func.count()).select_from(Claim).join(Answer, Claim.answer_id == Answer.id)
            .join(Session, Answer.session_id == Session.id).where(Session.user_id == user.id)
        )
    ).scalar_one()

    # Sessions over time (by day).
    sot_rows = (
        await session.execute(
            select(func.date(Session.created_at), func.count())
            .where(Session.user_id == user.id).group_by(func.date(Session.created_at))
        )
    ).all()
    sessions_over_time = [{"date": str(d), "count": c} for d, c in sot_rows]

    # Most studied subjects (by source count).
    subj_rows = (
        await session.execute(
            select(Subject.name, func.count(Source.id))
            .outerjoin(Source, Source.subject_id == Subject.id)
            .where(Subject.user_id == user.id).group_by(Subject.name)
        )
    ).all()
    most_studied = [{"subject": n, "count": c} for n, c in subj_rows]

    # Source usage by type.
    src_rows = (
        await session.execute(
            select(Source.source_type, func.count()).where(Source.user_id == user.id)
            .group_by(Source.source_type)
        )
    ).all()
    source_usage = [{"type": str(t), "count": c} for t, c in src_rows]

    recent = (
        await session.execute(
            select(Answer.question, Answer.status, Answer.created_at)
            .join(Session, Answer.session_id == Session.id).where(Session.user_id == user.id)
            .order_by(Answer.created_at.desc()).limit(10)
        )
    ).all()
    recent_activity = [
        {"question": q, "status": str(s), "created_at": c.isoformat()} for q, s, c in recent
    ]

    return {
        "questions_asked": total,
        "verified_rate": rate(TopLevelStatus.VERIFIED),
        "abstention_rate": rate(TopLevelStatus.INSUFFICIENT_EVIDENCE),
        "contradiction_rate": rate(TopLevelStatus.CONTRADICTION),
        "error_rate": rate(TopLevelStatus.ERROR),
        "average_duration_ms": round(duration_sum / total, 1) if total else 0.0,
        "average_claim_count": round(claim_total / total, 2) if total else 0.0,
        "status_breakdown": status_breakdown,
        "sessions_over_time": sessions_over_time,
        "most_studied_subjects": most_studied,
        "source_usage": source_usage,
        "recent_activity": recent_activity,
    }
