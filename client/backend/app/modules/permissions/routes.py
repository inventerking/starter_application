"""A user's own effective permissions, for showing or hiding UI. The backend still enforces them."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal
from app.modules.permissions.service import PermissionService

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me", response_model=list[str])
def my_permissions(
    principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)
) -> list[str]:
    return sorted(PermissionService(db).effective_codes(principal.user))
