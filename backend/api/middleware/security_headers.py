"""
Security headers middleware (HIPAA transmission security / defense in depth).

Adds HSTS and standard hardening headers to every response. HSTS is only sent in
production (over real TLS) so local http dev isn't pinned to https.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import get_settings

settings = get_settings()

_STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _STATIC_HEADERS.items():
            response.headers.setdefault(header, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response
