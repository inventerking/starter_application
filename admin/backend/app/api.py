"""Aggregates every versioned API router of this application."""

from fastapi import APIRouter

from app.core.health import router as health_router
from app.modules.authentication.routes import router as authentication_router
from app.modules.mfa.routes import router as mfa_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(authentication_router)
api_router.include_router(mfa_router)
