"""User Management endpoints. Every endpoint requires its own users.* Admin permission."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, require_permission
from app.core.pagination import Page, PageParams
from app.core.request_context import RequestContext, get_request_context
from app.modules.users import permissions as perms
from app.modules.users.schemas import (
    ClientActivityResponse,
    ClientMfaStatusResponse,
    ClientOverrideRequest,
    ClientOverrideResponse,
    ClientPermissionResponse,
    ClientRoleAssignmentRequest,
    ClientRoleSummaryResponse,
    ClientUserCreatedResponse,
    ClientUserCreateRequest,
    ClientUserResponse,
    ClientUserUpdateRequest,
    TemporaryPasswordResponse,
)
from app.modules.users.service import ClientUserManagementService

router = APIRouter(prefix="/users", tags=["user management"])


def service_for(permission):
    def _dependency(
        principal: Principal = Depends(require_permission(permission)),
        db: Session = Depends(get_db),
        context: RequestContext = Depends(get_request_context),
    ) -> ClientUserManagementService:
        return ClientUserManagementService(db, context, principal.user)

    return _dependency


@router.get("", response_model=Page[ClientUserResponse])
def list_users(
    params: PageParams = Depends(),
    search: str | None = Query(default=None, max_length=128),
    service: ClientUserManagementService = Depends(service_for(perms.USERS_VIEW)),
) -> Page:
    items, total = service.list_page(params.page, params.page_size, search)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


@router.post("", response_model=ClientUserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: ClientUserCreateRequest,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_CREATE)),
) -> ClientUserCreatedResponse:
    user, temporary_password = service.create(
        payload.email, payload.username, payload.full_name, payload.role_ids)
    return ClientUserCreatedResponse(
        **ClientUserResponse.model_validate(user).model_dump(),
        temporary_password=temporary_password)


@router.get("/{user_id}", response_model=ClientUserResponse)
def get_user(
    user_id: UUID, service: ClientUserManagementService = Depends(service_for(perms.USERS_VIEW))
):
    return service.get(user_id)


@router.patch("/{user_id}", response_model=ClientUserResponse)
def update_user(
    user_id: UUID,
    payload: ClientUserUpdateRequest,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_UPDATE)),
):
    return service.update(user_id, payload.model_dump(exclude_unset=True))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID, service: ClientUserManagementService = Depends(service_for(perms.USERS_DELETE))
) -> None:
    service.delete(user_id)


@router.post("/{user_id}/activate", response_model=ClientUserResponse)
def activate_user(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_ACTIVATE)),
):
    return service.activate(user_id)


@router.post("/{user_id}/deactivate", response_model=ClientUserResponse)
def deactivate_user(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_DEACTIVATE)),
):
    return service.deactivate(user_id)


@router.get("/{user_id}/roles", response_model=list[ClientRoleSummaryResponse])
def list_user_roles(
    user_id: UUID, service: ClientUserManagementService = Depends(service_for(perms.USERS_VIEW))
):
    return service.roles_of(user_id)


@router.post("/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
def assign_user_role(
    user_id: UUID,
    payload: ClientRoleAssignmentRequest,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_ROLES_MANAGE)),
) -> None:
    service.assign_role(user_id, payload.role_id)


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_role(
    user_id: UUID,
    role_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_ROLES_MANAGE)),
) -> None:
    service.remove_role(user_id, role_id)


@router.get("/{user_id}/permissions", response_model=list[ClientOverrideResponse])
def list_user_overrides(
    user_id: UUID, service: ClientUserManagementService = Depends(service_for(perms.USERS_VIEW))
) -> list:
    return [ClientOverrideResponse(
                permission=ClientPermissionResponse.model_validate(permission),
                effect=override.effect, reason=override.reason, created_at=override.created_at)
            for override, permission in service.overrides_of(user_id)]


@router.put("/{user_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_user_override(
    user_id: UUID,
    permission_id: UUID,
    payload: ClientOverrideRequest,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_PERMISSIONS_MANAGE)),
) -> None:
    service.set_override(user_id, permission_id, payload.effect, payload.reason)


@router.delete("/{user_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_override(
    user_id: UUID,
    permission_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_PERMISSIONS_MANAGE)),
) -> None:
    service.remove_override(user_id, permission_id)


@router.get("/{user_id}/mfa", response_model=ClientMfaStatusResponse)
def user_mfa_status(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_MFA_VIEW_STATUS)),
) -> ClientMfaStatusResponse:
    user, remaining = service.mfa_status(user_id)
    return ClientMfaStatusResponse(
        enabled=user.mfa_enabled, enrollment_required=user.mfa_enrollment_required,
        confirmed_at=user.mfa_confirmed_at, recovery_codes_remaining=remaining)


@router.post("/{user_id}/mfa/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_mfa(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_MFA_RESET)),
) -> None:
    service.reset_mfa(user_id)


@router.post("/{user_id}/password/reset", response_model=TemporaryPasswordResponse)
def reset_user_password(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_PASSWORD_RESET)),
) -> TemporaryPasswordResponse:
    return TemporaryPasswordResponse(temporary_password=service.issue_temporary_password(user_id))


@router.post("/{user_id}/sessions/revoke")
def revoke_user_sessions(
    user_id: UUID,
    service: ClientUserManagementService = Depends(service_for(perms.USERS_SESSIONS_REVOKE)),
) -> dict[str, int]:
    return {"revoked": service.revoke_sessions(user_id)}


@router.get("/{user_id}/activity", response_model=Page[ClientActivityResponse])
def user_activity(
    user_id: UUID,
    params: PageParams = Depends(),
    service: ClientUserManagementService = Depends(service_for(perms.USERS_ACTIVITY_VIEW)),
) -> Page:
    items, total = service.activity(user_id, params.page, params.page_size)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
