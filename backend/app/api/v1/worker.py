"""Premium worker presence endpoint (client polls this to show online/offline)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.worker_status import worker_status

router = APIRouter()


class WorkerStatus(BaseModel):
    online: bool
    last_seen: str | None


@router.get("/worker/status", response_model=WorkerStatus)
async def get_worker_status() -> WorkerStatus:
    return WorkerStatus(**worker_status())
