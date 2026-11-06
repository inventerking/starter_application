"""Authentication endpoints. Rules live in AuthenticationService."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    Principal,
    get_authentication_service,
    get_current_principal,
    get_restricted_principal,
    resolve_session,
)
from app.core.http_security import (
    clear_refresh_cookie,
    refresh_cookie_name,
    require_csrf_protection,
    set_refresh_cookie,
)
from app.modules.authentication.password_reset_delivery import (
    PasswordResetDelivery,
    get_password_reset_delivery,
)
from app.modules.authentication.schemas import (
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    SessionResponse,
)
from app.modules.authentication.service import AuthenticationService, mfa_enrollment_needed
from app.modules.authentication.session_service import IssuedTokens
from app.modules.permissions.service import PermissionService

router = APIRouter(prefix="/auth", tags=["authentication"])
_optional_bearer = HTTPBearer(auto_error=False)
_csrf = [Depends(require_csrf_protection)]


def apply_tokens(response: Response, tokens: IssuedTokens, status_value: str) -> AuthResponse:
    set_refresh_cookie(response, tokens.refresh_token, tokens.refresh_max_age)
    return AuthResponse(
        status=status_value, access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/login", response_model=AuthResponse, dependencies=_csrf)
def login(
    payload: LoginRequest,
    response: Response,
    service: AuthenticationService = Depends(get_authentication_service),
) -> AuthResponse:
    result = service.login(payload.identifier, payload.password)
    if result.tokens:
        return apply_tokens(response, result.tokens, result.status)
    return AuthResponse(
        status=result.status,
        challenge_token=result.challenge_token,
        challenge_expires_in=result.challenge_expires_in,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=_csrf)
def register(
    payload: RegisterRequest,
    service: AuthenticationService = Depends(get_authentication_service),
) -> dict[str, str]:
    service.register(payload.email, payload.username, payload.full_name, payload.password)
    return {"status": "registered"}


@router.post("/refresh", response_model=AuthResponse, dependencies=_csrf)
def refresh(
    request: Request,
    response: Response,
    service: AuthenticationService = Depends(get_authentication_service),
) -> AuthResponse:
    tokens = service.refresh(request.cookies.get(refresh_cookie_name()))
    status_value = "authenticated" if tokens.session.scope == "full" else "mfa_enrollment_required"
    return apply_tokens(response, tokens, status_value)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=_csrf)
def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
    service: AuthenticationService = Depends(get_authentication_service),
) -> None:
    session = resolve_session(db, credentials.credentials) if credentials else None
    service.logout(session=session, raw_refresh_token=request.cookies.get(refresh_cookie_name()))
    clear_refresh_cookie(response)


@router.get("/me", response_model=CurrentUserResponse)
def me(
    principal: Principal = Depends(get_restricted_principal), db: Session = Depends(get_db)
) -> CurrentUserResponse:
    user = principal.user
    # A restricted session holds no permissions, whatever its roles say.
    restricted = principal.session.scope != "full" or user.must_change_password
    permissions = [] if restricted else sorted(PermissionService(db).effective_codes(user))
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        mfa_enabled=user.mfa_enabled,
        must_change_password=user.must_change_password,
        mfa_enrollment_required=mfa_enrollment_needed(user),
        session_scope=principal.session.scope,
        permissions=permissions,
    )


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    principal: Principal = Depends(get_restricted_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> None:
    service.change_password(
        principal.user, principal.session, payload.current_password, payload.new_password)


@router.post("/password/reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest,
    service: AuthenticationService = Depends(get_authentication_service),
    delivery: PasswordResetDelivery = Depends(get_password_reset_delivery),
) -> dict[str, str]:
    service.request_password_reset(payload.email, delivery)
    return {"status": "accepted"}


@router.post("/password/reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    service: AuthenticationService = Depends(get_authentication_service),
) -> None:
    service.confirm_password_reset(payload.token, payload.new_password)


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    principal: Principal = Depends(get_current_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> list[SessionResponse]:
    return [
        SessionResponse(
            id=item.id, ip_address=item.ip_address, user_agent=item.user_agent,
            created_at=item.created_at, last_seen_at=item.last_seen_at,
            expires_at=item.expires_at, current=item.id == principal.session.id)
        for item in service.list_sessions(principal.user.id)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: UUID,
    principal: Principal = Depends(get_current_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> None:
    service.revoke_session(principal.user.id, session_id)


@router.post("/sessions/revoke-others")
def revoke_other_sessions(
    principal: Principal = Depends(get_current_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> dict[str, int]:
    return {"revoked": service.revoke_other_sessions(principal.user.id, principal.session.id)}
