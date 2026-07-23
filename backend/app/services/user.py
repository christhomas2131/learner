"""Single local user helper (no auth in this personal deployment)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import User, UserSettings


async def get_or_create_demo_user(session: AsyncSession) -> User:
    user = await session.get(User, settings.DEMO_USER_ID)
    if user is None:
        user = User(
            id=settings.DEMO_USER_ID, display_name="Local User", is_local_demo=True,
            email=None,
        )
        session.add(user)
        session.add(UserSettings(user_id=user.id, preferences={}))
        await session.commit()
        await session.refresh(user)
    return user
