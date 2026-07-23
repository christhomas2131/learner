"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import register_error_handlers
from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import create_all
from app.providers.claude_cli import claude_cli_available
from app.services.premium_drainer import run_drainer

log = get_logger("main")

SECURE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        request.state.request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        for key, value in SECURE_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    configure_logging()
    settings.validate_runtime()
    # Convenience for local/SQLite; production uses Alembic migrations.
    if settings.is_sqlite:
        await create_all()

    # Hands-off premium: auto-drain the premium queue via `claude -p` when the
    # CLI is present. No terminal, no API key. Falls back to the manual worker.
    stop = asyncio.Event()
    drainer_task: asyncio.Task | None = None
    autodrain = settings.PREMIUM_AUTODRAIN and claude_cli_available()
    if autodrain:
        drainer_task = asyncio.create_task(run_drainer(settings.PREMIUM_DRAIN_INTERVAL, stop))
    log.info("startup", provider=settings.MODEL_PROVIDER.value, env=settings.APP_ENV,
             premium_autodrain=autodrain)
    yield
    stop.set()
    if drainer_task is not None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(drainer_task, timeout=5)


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version="0.1.0",
        description="Verified learning app — a deterministic harness that forces low hallucination.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
