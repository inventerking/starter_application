"""MFA endpoints."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal, get_restricted_principal
from app.core.http_security import require_csrf_protection
from app.core.request_context import RequestContext, get_request_context
from app.modules.authentication.routes import apply_tokens
from app.modules.authentication.schemas import AuthResponse
from app.modules.mfa.schemas import (
    MfaConfirmRequest,
    MfaDisableRequest,
    MfaRegenerateRequest,
    MfaSetupRequest,
    MfaSetupResponse,
    MfaStatusResponse,
    MfaVerifyLoginRequest,
    RecoveryCodesResponse,
)
from app.modules.mfa.service import MfaService

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


def get_mfa_service(
    db: Session = Depends(get_db), context: RequestContext = Depends(get_request_context)
) -> MfaService:
    return MfaService(db, context)


@router.get("/status", response_model=MfaStatusResponse)
def mfa_status(
    principal: Principal = Depends(get_restricted_principal),
    service: MfaService = Depends(get_mfa_service),
) -> MfaStatusResponse:
    enabled, remaining = service.status(principal.user)
    confirmed = principal.user.mfa_confirmed_at
    return MfaStatusResponse(
        enabled=enabled,
        confirmed_at=confirmed.isoformat() if confirmed else None,
        recovery_codes_remaining=remaining,
    )


@router.post("/setup", response_model=MfaSetupResponse)
def setup(
    payload: MfaSetupRequest,
    principal: Principal = Depends(get_restricted_principal),
    service: MfaService = Depends(get_mfa_service),
) -> MfaSetupResponse:
    result = service.setup(principal.user, payload.password)
    return MfaSetupResponse(
        secret=result.secret, provisioning_uri=result.provisioning_uri, qr_code=result.qr_code,
        issuer=result.issuer, account=result.account)


@router.post("/confirm", response_model=RecoveryCodesResponse)
def confirm(
    payload: MfaConfirmRequest,
    principal: Principal = Depends(get_restricted_principal),
    service: MfaService = Depends(get_mfa_service),
) -> RecoveryCodesResponse:
    codes = service.confirm(principal.user, principal.session, payload.code)
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/verify-login", response_model=AuthResponse,
             dependencies=[Depends(require_csrf_protection)])
def verify_login(
    payload: MfaVerifyLoginRequest,
    response: Response,
    service: MfaService = Depends(get_mfa_service),
) -> AuthResponse:
    tokens = service.verify_login(payload.challenge_token, payload.code, payload.recovery_code)
    return apply_tokens(response, tokens, "authenticated")


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable(
    payload: MfaDisableRequest,
    principal: Principal = Depends(get_current_principal),
    service: MfaService = Depends(get_mfa_service),
) -> None:
    service.disable(principal.user, principal.session, payload.password, payload.code)


@router.post("/recovery-codes/regenerate", response_model=RecoveryCodesResponse)
def regenerate_recovery_codes(
    payload: MfaRegenerateRequest,
    principal: Principal = Depends(get_current_principal),
    service: MfaService = Depends(get_mfa_service),
) -> RecoveryCodesResponse:
    return RecoveryCodesResponse(
        recovery_codes=service.regenerate_recovery_codes(principal.user, payload.code))
