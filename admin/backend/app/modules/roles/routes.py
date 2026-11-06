"""Admin role endpoints. Client roles have their own, separate endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, require_permission
from app.core.request_context import RequestContext, get_request_context
from app.modules.permissions.schemas import PermissionResponse
from app.modules.roles.models import Role
from app.modules.roles.permissions import (
    ADMIN_ROLES_CREATE,
    ADMIN_ROLES_DELETE,
    ADMIN_ROLES_UPDATE,
    ADMIN_ROLES_VIEW,
)
from app.modules.roles.schemas import (
    RoleCreateRequest,
    RolePermissionsRequest,
    RoleResponse,
    RoleSummaryResponse,
    RoleUpdateRequest,
)
from app.modules.roles.service import AdminRoleService

router = APIRouter(prefix="/admin-roles", tags=["admin roles"])


def _service(
    db: Session, context: RequestContext, principal: Principal
) -> AdminRoleService:
    return AdminRoleService(db, context, principal.user)


def _response(service: AdminRoleService, role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id, name=role.name, description=role.description, is_system=role.is_system,
        created_at=role.created_at,
        permissions=[PermissionResponse.model_validate(row)
                     for row in service.permissions_of(role.id)])


@router.get("", response_model=list[RoleSummaryResponse])
def list_roles(
    principal: Principal = Depends(require_permission(ADMIN_ROLES_VIEW)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list:
    roles = _service(db, context, principal).list_all()
    return [RoleSummaryResponse(id=r.id, name=r.name, description=r.description,
                                is_system=r.is_system, created_at=r.created_at) for r in roles]


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    principal: Principal = Depends(require_permission(ADMIN_ROLES_CREATE)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RoleResponse:
    service = _service(db, context, principal)
    return _response(service, service.create(
        payload.name, payload.description, payload.permission_ids))


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: UUID,
    principal: Principal = Depends(require_permission(ADMIN_ROLES_VIEW)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RoleResponse:
    service = _service(db, context, principal)
    return _response(service, service.get(role_id))


@router.patch("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    payload: RoleUpdateRequest,
    principal: Principal = Depends(require_permission(ADMIN_ROLES_UPDATE)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RoleResponse:
    service = _service(db, context, principal)
    return _response(service, service.update(role_id, payload.model_dump(exclude_unset=True)))


@router.put("/{role_id}/permissions", response_model=RoleResponse)
def set_role_permissions(
    role_id: UUID,
    payload: RolePermissionsRequest,
    principal: Principal = Depends(require_permission(ADMIN_ROLES_UPDATE)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RoleResponse:
    service = _service(db, context, principal)
    return _response(service, service.set_permissions(role_id, payload.permission_ids))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    principal: Principal = Depends(require_permission(ADMIN_ROLES_DELETE)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> None:
    _service(db, context, principal).delete(role_id)
