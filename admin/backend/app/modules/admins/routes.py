"""Admin Management endpoints. Every endpoint requires its own admins.* permission."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, require_permission
from app.core.pagination import Page, PageParams
from app.core.request_context import RequestContext, get_request_context
from app.modules.admins import permissions as perms
from app.modules.admins.schemas import (
    AdminCreatedResponse,
    AdminCreateRequest,
    AdminResponse,
    AdminUpdateRequest,
    MfaStatusResponse,
    TemporaryPasswordResponse,
)
from app.modules.admins.service import AdminManagementService
from app.modules.audit.schemas import AuditLogResponse
from app.modules.permissions.schemas import (
    PermissionOverrideRequest,
    PermissionOverrideResponse,
    PermissionResponse,
)
from app.modules.roles.schemas import RoleAssignmentRequest, RoleSummaryResponse

router = APIRouter(prefix="/admins", tags=["admin management"])


def service_for(permission):
    """Authorize the request, then build the service for the authorized actor."""

    def _dependency(
        principal: Principal = Depends(require_permission(permission)),
        db: Session = Depends(get_db),
        context: RequestContext = Depends(get_request_context),
    ) -> AdminManagementService:
        return AdminManagementService(db, context, principal.user)

    return _dependency


@router.get("", response_model=Page[AdminResponse])
def list_admins(
    params: PageParams = Depends(),
    search: str | None = Query(default=None, max_length=128),
    service: AdminManagementService = Depends(service_for(perms.ADMINS_VIEW)),
) -> Page:
    items, total = service.list_page(params.page, params.page_size, search)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


@router.post("", response_model=AdminCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminCreateRequest,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_CREATE)),
) -> AdminCreatedResponse:
    admin, temporary_password = service.create(payload.email, payload.username, payload.full_name)
    return AdminCreatedResponse(
        **AdminResponse.model_validate(admin).model_dump(), temporary_password=temporary_password)


@router.get("/{admin_id}", response_model=AdminResponse)
def get_admin(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_VIEW))
):
    return service.get(admin_id)


@router.patch("/{admin_id}", response_model=AdminResponse)
def update_admin(
    admin_id: UUID,
    payload: AdminUpdateRequest,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_UPDATE)),
):
    return service.update(admin_id, payload.model_dump(exclude_unset=True))


@router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_DELETE))
) -> None:
    service.delete(admin_id)


@router.post("/{admin_id}/activate", response_model=AdminResponse)
def activate_admin(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_ACTIVATE))
):
    return service.activate(admin_id)


@router.post("/{admin_id}/deactivate", response_model=AdminResponse)
def deactivate_admin(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_DEACTIVATE))
):
    return service.deactivate(admin_id)


@router.get("/{admin_id}/roles", response_model=list[RoleSummaryResponse])
def list_admin_roles(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_VIEW))
) -> list:
    return [RoleSummaryResponse(id=r.id, name=r.name, description=r.description,
                                is_system=r.is_system, created_at=r.created_at)
            for r in service.roles_of(admin_id)]


@router.post("/{admin_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
def assign_admin_role(
    admin_id: UUID,
    payload: RoleAssignmentRequest,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_ROLES_MANAGE)),
) -> None:
    service.assign_role(admin_id, payload.role_id)


@router.delete("/{admin_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_admin_role(
    admin_id: UUID,
    role_id: UUID,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_ROLES_MANAGE)),
) -> None:
    service.remove_role(admin_id, role_id)


@router.get("/{admin_id}/permissions", response_model=list[PermissionOverrideResponse])
def list_admin_overrides(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_VIEW))
) -> list:
    return [PermissionOverrideResponse(
                permission=PermissionResponse.model_validate(permission), effect=override.effect,
                reason=override.reason, created_at=override.created_at)
            for override, permission in service.overrides_of(admin_id)]


@router.get("/{admin_id}/permissions/effective", response_model=list[str])
def effective_admin_permissions(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_VIEW))
) -> list[str]:
    return service.effective_permissions_of(admin_id)


@router.put("/{admin_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_admin_override(
    admin_id: UUID,
    permission_id: UUID,
    payload: PermissionOverrideRequest,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_PERMISSIONS_MANAGE)),
) -> None:
    service.set_override(admin_id, permission_id, payload.effect, payload.reason)


@router.delete("/{admin_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_admin_override(
    admin_id: UUID,
    permission_id: UUID,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_PERMISSIONS_MANAGE)),
) -> None:
    service.remove_override(admin_id, permission_id)


@router.get("/{admin_id}/mfa", response_model=MfaStatusResponse)
def admin_mfa_status(
    admin_id: UUID,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_MFA_VIEW_STATUS)),
) -> MfaStatusResponse:
    admin, remaining = service.mfa_status(admin_id)
    return MfaStatusResponse(
        enabled=admin.mfa_enabled, enrollment_required=admin.mfa_enrollment_required,
        confirmed_at=admin.mfa_confirmed_at, recovery_codes_remaining=remaining)


@router.post("/{admin_id}/mfa/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_admin_mfa(
    admin_id: UUID, service: AdminManagementService = Depends(service_for(perms.ADMINS_MFA_RESET))
) -> None:
    service.reset_mfa(admin_id)


@router.post("/{admin_id}/password/reset", response_model=TemporaryPasswordResponse)
def reset_admin_password(
    admin_id: UUID,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_PASSWORD_RESET)),
) -> TemporaryPasswordResponse:
    return TemporaryPasswordResponse(temporary_password=service.issue_temporary_password(admin_id))


@router.post("/{admin_id}/sessions/revoke")
def revoke_admin_sessions(
    admin_id: UUID,
    service: AdminManagementService = Depends(service_for(perms.ADMINS_SESSIONS_REVOKE)),
) -> dict[str, int]:
    return {"revoked": service.revoke_sessions(admin_id)}


@router.get("/{admin_id}/activity", response_model=Page[AuditLogResponse])
def admin_activity(
    admin_id: UUID,
    params: PageParams = Depends(),
    service: AdminManagementService = Depends(service_for(perms.ADMINS_ACTIVITY_VIEW)),
) -> Page:
    items, total = service.activity(admin_id, params.page, params.page_size)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
