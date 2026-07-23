"""Consistent error schema + exception handlers.

User-facing errors never leak stack traces; details are logged server-side with
the request id.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.logging import get_logger

log = get_logger("api.errors")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class APIError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND)


class ValidationError(APIError):
    def __init__(self, message: str) -> None:
        super().__init__("validation_error", message, 422)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _payload(code: str, message: str, request_id: str | None) -> dict:
    return ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id)).model_dump()


def register_error_handlers(app) -> None:  # noqa: ANN001
    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status,
                            content=_payload(exc.code, exc.message, _request_id(request)))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload("validation_error", "Request validation failed.", _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", error=str(exc), request_id=_request_id(request),
                  exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload("internal_error", "An unexpected error occurred.", _request_id(request)),
        )
