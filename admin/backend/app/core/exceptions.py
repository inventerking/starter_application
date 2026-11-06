"""Application errors and handlers. Internal details never reach API responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that are safe to show to API callers."""

    status_code = 400
    code = "bad_request"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code


class AuthenticationRequired(AppError):
    status_code = 401
    code = "authentication_required"
    message = "Authentication is required."


class PermissionDenied(AppError):
    status_code = 403
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state."


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many attempts. Please wait and try again."

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__()
        self.retry_after = retry_after


def _error(status: int, code: str, message: str, **extra: object) -> JSONResponse:
    headers = extra.pop("headers", None)
    body = {"error": {"code": code, "message": message, **extra}}
    return JSONResponse(status_code=status, content=jsonable_encoder(body), headers=headers)  # type: ignore[arg-type]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if isinstance(exc, RateLimited):
            headers["Retry-After"] = str(exc.retry_after)
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return _error(exc.status_code, exc.code, exc.message, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Only field locations and messages: submitted values (possibly passwords) are dropped.
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                   for e in exc.errors()]
        return _error(422, "validation_error", "The request is invalid.", details=details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = NotFound.message if exc.status_code == 404 else "The request failed."
        return _error(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the exception type only: messages and tracebacks can embed bound SQL parameters.
        logger.error("Unhandled exception: %s", type(exc).__name__)
        return _error(500, "internal_error", "An unexpected error occurred.")
