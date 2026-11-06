"""CSRF defence and refresh cookie handling for cookie-authenticated endpoints.

The defence has three layers: a SameSite=Strict cookie, an Origin allowlist check, and a required
custom header that cross-site forms cannot send and that fetch cannot send without a CORS preflight.
"""

from fastapi import Request, Response

from app.core.config import get_settings
from app.core.exceptions import PermissionDenied

CSRF_HEADER = "x-requested-with"
COOKIE_PATH = "/api/v1/auth"
_COOKIE_BASE_NAME = "admin_refresh"


def refresh_cookie_name() -> str:
    # Cookies are not isolated by port, so the name keeps Admin and Client apart on localhost.
    prefix = "__Secure-" if get_settings().cookie_secure else ""
    return f"{prefix}{_COOKIE_BASE_NAME}"


def require_csrf_protection(request: Request) -> None:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin not in get_settings().cors_origins or not request.headers.get(CSRF_HEADER):
        raise PermissionDenied("The request failed the origin check.", code="csrf_rejected")


def set_refresh_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        refresh_cookie_name(),
        token,
        max_age=max_age_seconds,
        path=COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        refresh_cookie_name(),
        path=COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )
