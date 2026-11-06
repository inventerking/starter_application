"""Client role and Client permission registry endpoints, distinct from /admin-roles."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, require_permission
from app.core.request_context import RequestContext, get_request_context
from app.modules.client_domain.models import ClientRole
from app.modules.client_roles import permissions as perms
from app.modules.client_roles.schemas import (
    ClientRoleCreateRequest,
    ClientRolePermissionsRequest,
    ClientRoleResponse,
    ClientRoleUpdateRequest,
)
from app.modules.client_roles.service import ClientRoleManagementService
from app.modules.users.schemas import ClientPermissionResponse, ClientRoleSummaryResponse

router = APIRouter(tags=["client roles"])


def service_for(permission):
    def _dependency(
        principal: Principal = Depends(require_permission(permission)),
        db: Session = Depends(get_db),
        context: RequestContext = Depends(get_request_context),
    ) -> ClientRoleManagementService:
        return ClientRoleManagementService(db, context, principal.user)

    return _dependency


def _response(service: ClientRoleManagementService, role: ClientRole) -> ClientRoleResponse:
    return ClientRoleResponse(
        **ClientRoleSummaryResponse.model_validate(role).model_dump(),
        permissions=[ClientPermissionResponse.model_validate(row)
                     for row in service.permissions_of(role.id)])


@router.get("/client-permissions", response_model=list[ClientPermissionResponse])
def list_client_permissions(
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_PERMISSIONS_VIEW)),
):
    return service.list_permissions()


@router.get("/client-roles", response_model=list[ClientRoleSummaryResponse])
def list_client_roles(
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_VIEW)),
):
    return service.list_all()


@router.post("/client-roles", response_model=ClientRoleResponse,
             status_code=status.HTTP_201_CREATED)
def create_client_role(
    payload: ClientRoleCreateRequest,
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_CREATE)),
) -> ClientRoleResponse:
    return _response(service, service.create(
        payload.name, payload.description, payload.is_default, payload.permission_ids))


@router.get("/client-roles/{role_id}", response_model=ClientRoleResponse)
def get_client_role(
    role_id: UUID,
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_VIEW)),
) -> ClientRoleResponse:
    return _response(service, service.get(role_id))


@router.patch("/client-roles/{role_id}", response_model=ClientRoleResponse)
def update_client_role(
    role_id: UUID,
    payload: ClientRoleUpdateRequest,
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_UPDATE)),
) -> ClientRoleResponse:
    return _response(service, service.update(role_id, payload.model_dump(exclude_unset=True)))


@router.put("/client-roles/{role_id}/permissions", response_model=ClientRoleResponse)
def set_client_role_permissions(
    role_id: UUID,
    payload: ClientRolePermissionsRequest,
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_UPDATE)),
) -> ClientRoleResponse:
    return _response(service, service.set_permissions(role_id, payload.permission_ids))


@router.delete("/client-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_role(
    role_id: UUID,
    service: ClientRoleManagementService = Depends(service_for(perms.CLIENT_ROLES_DELETE)),
) -> None:
    service.delete(role_id)
