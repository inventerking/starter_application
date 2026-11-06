"""Authentication dependencies. Every token is checked against the database on every request."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db, utcnow
from app.core.exceptions import AuthenticationRequired, PermissionDenied
from app.core.request_context import RequestContext, get_request_context
from app.core.security import hash_token
from app.modules.admins.models import AdminUser
from app.modules.admins.repository import AdminRepository
from app.modules.authentication.exceptions import MfaEnrollmentRequired, PasswordChangeRequired
from app.modules.authentication.models import SCOPE_FULL, UserSession
from app.modules.authentication.repository import SessionRepository
from app.modules.authentication.service import AuthenticationService, mfa_enrollment_needed
from app.modules.permissions.registry import PermissionDefinition
from app.modules.permissions.service import PermissionService

_bearer = HTTPBearer(auto_error=False)
_LAST_SEEN_RESOLUTION = timedelta(minutes=1)


@dataclass(frozen=True)
class Principal:
    user: AdminUser
    session: UserSession


def resolve_session(db: Session, token: str) -> UserSession | None:
    digest = hash_token(token)
    session = SessionRepository(db).get_by_access_hash(digest)
    if session is None or session.revoked_at:
        return None
    now = utcnow()
    if session.expires_at <= now:
        return None
    if session.access_token_hash == digest:
        return session if session.access_expires_at > now else None
    previous_expiry = session.previous_access_expires_at
    return session if previous_expiry and previous_expiry > now else None


def get_restricted_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Principal:
    """A valid session of any scope. Only for /me, password change, logout and MFA enrollment."""
    if credentials is None:
        raise AuthenticationRequired
    session = resolve_session(db, credentials.credentials)
    if session is None:
        raise AuthenticationRequired
    user = AdminRepository(db).get(session.user_id)
    if user is None or not user.is_active:
        raise AuthenticationRequired
    now = utcnow()
    if session.last_seen_at is None or now - session.last_seen_at > _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
        db.commit()
    return Principal(user=user, session=session)


def get_current_principal(principal: Principal = Depends(get_restricted_principal)) -> Principal:
    """A fully authenticated session. This is the default for protected endpoints."""
    if principal.session.scope != SCOPE_FULL or mfa_enrollment_needed(principal.user):
        raise MfaEnrollmentRequired
    if principal.user.must_change_password:
        raise PasswordChangeRequired
    return principal


def get_authentication_service(
    db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)
) -> AuthenticationService:
    return AuthenticationService(db, context)


def require_permission(permission: PermissionDefinition) -> Callable[..., Principal]:
    """Route guard. It accepts only registered definitions, never free-form strings."""
    if not isinstance(permission, PermissionDefinition):
        raise TypeError("require_permission needs a PermissionDefinition")

    def _guard(
        principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)
    ) -> Principal:
        if not PermissionService(db).has(principal.user, permission):
            raise PermissionDenied
        return principal

    return _guard
