"""A user's own roles."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import RoleResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/me", response_model=list[RoleResponse])
def my_roles(
    principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)
) -> list:
    return RoleRepository(db).roles_of_user(principal.user.id)
