"""Main module API router — replacing the old app/api/api_v1/api.py."""
from fastapi import APIRouter

from app.modules.auth.endpoints import router as auth_router
from app.modules.identity.endpoints import router as identity_router
from app.modules.academic.endpoints import router as academic_router
from app.modules.assessment.endpoints import router as assessment_router
from app.modules.analytics.endpoints import router as analytics_router
from app.modules.analytics.insights_v2.api.endpoints import (
    analytics_router as insights_v2_analytics_router,
    public_router as insights_v2_public_router,
)
from app.modules.notification.endpoints import router as notification_router
from app.modules.platform.endpoints import router as platform_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/user/auth", tags=["auth"])
api_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_router.include_router(academic_router, prefix="/academic", tags=["academic"])
api_router.include_router(assessment_router, prefix="/assessment", tags=["assessment"])
api_router.include_router(insights_v2_public_router)
api_router.include_router(insights_v2_analytics_router)
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(notification_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(platform_router, prefix="/platform", tags=["platform"])
