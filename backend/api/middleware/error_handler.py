"""
Global error handler — converts domain exceptions to clean HTTP responses.

No stack traces leak to the client; errors are logged server-side.
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from exceptions import (
    AuthenticationError,
    CareGuardError,
    ConflictError,
    FHIRAuthError,
    FHIRRequestError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


async def careguard_exception_handler(request: Request, exc: CareGuardError) -> JSONResponse:
    logger.exception("Domain error: %s", exc.message)

    if isinstance(exc, AuthenticationError):
        return JSONResponse(status_code=401, content=_error_body(exc.code, exc.message))
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content=_error_body(exc.code, exc.message))
    if isinstance(exc, ConflictError):
        return JSONResponse(status_code=409, content=_error_body(exc.code, exc.message))
    if isinstance(exc, ValidationError):
        return JSONResponse(status_code=422, content=_error_body(exc.code, exc.message))
    if isinstance(exc, FHIRAuthError):
        return JSONResponse(status_code=502, content=_error_body(exc.code, exc.message))
    if isinstance(exc, FHIRRequestError):
        return JSONResponse(status_code=502, content=_error_body(exc.code, exc.message))

    return JSONResponse(status_code=500, content=_error_body(exc.code, exc.message))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=_error_body("INTERNAL_ERROR", "An unexpected error occurred."),
    )
