"""Dashboard endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal
from app.modules.dashboard.schemas import DashboardResponse
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardResponse)
def summary(
    principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)
) -> DashboardResponse:
    return DashboardService(db).summary(principal.user)
