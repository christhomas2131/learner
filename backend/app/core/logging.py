"""Structured logging setup.

Emits key-value structured logs. Never log secrets, prompts, or raw model
chain-of-thought — callers pass only safe metadata.
"""

from __future__ import annotations

import logging

import structlog

from app.core.config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    configure_logging()
    return structlog.get_logger(name)
