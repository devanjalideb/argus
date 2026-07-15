"""Domain exceptions + FastAPI handlers producing the standard error envelope.

Error handling is a first-class architectural concern: validation -> 422, missing
resource -> 404, business conflict -> 409, everything unexpected -> 500 with a
correlation id, never a leaked stack trace.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import get_logger
from .response import error

logger = get_logger(__name__)


class ArgusError(Exception):
    """Base class for expected, handled application errors."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ArgusError):
    status_code = 404
    code = "not_found"


class ConflictError(ArgusError):
    status_code = 409
    code = "conflict"


class ValidationFailure(ArgusError):
    status_code = 422
    code = "validation_error"


class ServiceUnavailable(ArgusError):
    status_code = 503
    code = "service_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ArgusError)
    async def _handle_argus(_: Request, exc: ArgusError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error("validation_error", "Request validation failed", exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 401: "unauthorized", 403: "forbidden"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(status_code=exc.status_code, content=error(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        correlation_id = str(uuid.uuid4())
        logger.exception("Unhandled error [%s] on %s %s", correlation_id,
                         request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error("internal_error",
                          "An unexpected error occurred. Reference the correlation id.",
                          correlation_id=correlation_id),
        )
