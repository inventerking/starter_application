"""Admin role schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.permissions.schemas import PermissionResponse


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    permission_ids: list[UUID] = Field(default_factory=list, max_length=500)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)


class RolePermissionsRequest(BaseModel):
    permission_ids: list[UUID] = Field(max_length=500)


class RoleSummaryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_system: bool
    created_at: datetime


class RoleResponse(RoleSummaryResponse):
    permissions: list[PermissionResponse]


class RoleAssignmentRequest(BaseModel):
    role_id: UUID
