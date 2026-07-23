"""Analytics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.schemas import Analytics
from app.models import User
from app.services.analytics import compute_analytics

router = APIRouter()


@router.get("/analytics", response_model=Analytics)
async def analytics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Analytics:
    return Analytics(**await compute_analytics(session, user))
