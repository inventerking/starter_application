"""Cross-cutting HTTP middleware."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


def register_middleware(app: FastAPI, *, enable_hsts: bool) -> None:
    @app.middleware("http")
    async def _security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        path = request.url.path
        if not (path.startswith("/docs") or path.startswith("/redoc")):
            response.headers["Content-Security-Policy"] = _API_CSP
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if enable_hsts:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Request-ID"] = request.state.request_id
        return response
