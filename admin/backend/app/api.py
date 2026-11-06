"""Aggregates every versioned API router of this application."""

from fastapi import APIRouter

from app.core.health import router as health_router
from app.modules.admins.routes import router as admins_router
from app.modules.audit.routes import router as audit_router
from app.modules.authentication.routes import router as authentication_router
from app.modules.client_roles.routes import router as client_roles_router
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.mfa.routes import router as mfa_router
from app.modules.permissions.routes import router as permissions_router
from app.modules.roles.routes import router as roles_router
from app.modules.users.routes import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(authentication_router)
api_router.include_router(mfa_router)
api_router.include_router(permissions_router)
api_router.include_router(roles_router)
api_router.include_router(admins_router)
api_router.include_router(audit_router)
api_router.include_router(users_router)
api_router.include_router(client_roles_router)
api_router.include_router(dashboard_router)
