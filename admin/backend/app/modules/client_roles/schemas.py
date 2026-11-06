"""Client role schemas."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.users.schemas import ClientPermissionResponse, ClientRoleSummaryResponse


class ClientRoleCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool = False
    permission_ids: list[UUID] = Field(default_factory=list, max_length=500)


class ClientRoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool | None = None


class ClientRolePermissionsRequest(BaseModel):
    permission_ids: list[UUID] = Field(max_length=500)


class ClientRoleResponse(ClientRoleSummaryResponse):
    permissions: list[ClientPermissionResponse]
