"""Profile endpoints, each guarded by a Client permission."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import Principal, require_permission
from app.core.pagination import Page, PageParams
from app.core.request_context import RequestContext, get_request_context
from app.modules.users.permissions import ACTIVITY_VIEW, PROFILE_UPDATE, PROFILE_VIEW
from app.modules.users.schemas import ActivityResponse, ProfileResponse, ProfileUpdateRequest
from app.modules.users.service import ProfileService

router = APIRouter(prefix="/users", tags=["profile"])


@router.get("/me", response_model=ProfileResponse)
def get_profile(principal: Principal = Depends(require_permission(PROFILE_VIEW))):
    return principal.user


@router.patch("/me", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    principal: Principal = Depends(require_permission(PROFILE_UPDATE)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    changes = payload.model_dump(exclude_unset=True)
    return ProfileService(db, context).update(principal.user, changes)


@router.get("/me/activity", response_model=Page[ActivityResponse])
def my_activity(
    params: PageParams = Depends(),
    principal: Principal = Depends(require_permission(ACTIVITY_VIEW)),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> Page:
    items, total = ProfileService(db, context).activity(
        principal.user, params.page, params.page_size)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
