"""Read-only view of the Admin permission registry."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.modules.permissions.definitions import ADMIN_PERMISSIONS_VIEW
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.schemas import PermissionResponse

router = APIRouter(prefix="/admin-permissions", tags=["admin permissions"])


@router.get("", response_model=list[PermissionResponse],
            dependencies=[Depends(require_permission(ADMIN_PERMISSIONS_VIEW))])
def list_admin_permissions(db: Session = Depends(get_db)) -> list:
    return PermissionRepository(db).list_all()
