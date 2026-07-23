"""Aggregate v1 routers."""

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    answers,
    health,
    queue,
    sessions,
    sources,
    subjects,
    worker,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(answers.router, tags=["answers"])
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(sources.router, tags=["sources"])
api_router.include_router(subjects.router, tags=["subjects"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(queue.router, tags=["queue"])
api_router.include_router(worker.router, tags=["worker"])
