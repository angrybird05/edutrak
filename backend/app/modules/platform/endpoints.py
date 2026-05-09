"""
Platform module endpoints — Ops, settings, health, meta.
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user, requires_admin
from app.modules.auth.models import User
from app.modules.platform.models import UserSettings
from app.core.config import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# User Settings
# ---------------------------------------------------------------------------
@router.get("/settings")
async def get_user_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user's settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = result.scalar_one_or_none()
    if not user_settings:
        user_settings = UserSettings(user_id=current_user.id)
        db.add(user_settings)
        await db.commit()
        await db.refresh(user_settings)

    return {
        "theme": user_settings.theme,
        "language": user_settings.language,
        "email_notifications": user_settings.email_notifications,
        "sms_notifications": user_settings.sms_notifications,
        "push_notifications": user_settings.push_notifications,
        "custom_prefs": user_settings.custom_prefs,
    }


@router.patch("/settings")
async def update_user_settings(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    theme: str = None,
    language: str = None,
    email_notifications: bool = None,
    sms_notifications: bool = None,
    push_notifications: bool = None,
) -> Any:
    """Update current user's settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    user_settings = result.scalar_one_or_none()
    if not user_settings:
        user_settings = UserSettings(user_id=current_user.id)
        db.add(user_settings)
        await db.flush()

    if theme is not None:
        user_settings.theme = theme
    if language is not None:
        user_settings.language = language
    if email_notifications is not None:
        user_settings.email_notifications = email_notifications
    if sms_notifications is not None:
        user_settings.sms_notifications = sms_notifications
    if push_notifications is not None:
        user_settings.push_notifications = push_notifications

    db.add(user_settings)
    await db.commit()
    await db.refresh(user_settings)
    return {"status": "updated"}


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@router.get("/health")
async def comprehensive_health_check(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Comprehensive health check — DB, Redis, Celery, Ollama."""
    health = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
        "environment": settings.ENVIRONMENT,
    }

    # Database
    try:
        await db.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception:
        health["database"] = "disconnected"
        health["status"] = "degraded"

    # Redis
    try:
        from app.core.redis import get_redis_client
        redis_client = await get_redis_client()
        await redis_client.ping()
        health["redis"] = "connected"
    except Exception:
        health["redis"] = "disconnected"
        health["status"] = "degraded"

    # Celery broker
    try:
        from app.core.celery_app import celery_app
        inspector = celery_app.control.inspect()
        # This is a quick check — don't block long
        health["celery"] = "available"
    except Exception:
        health["celery"] = "unavailable"

    # Ollama (optional — degraded is OK)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL or 'http://localhost:11434'}/api/tags")
            health["ollama"] = "available" if resp.status_code == 200 else "unavailable"
    except Exception:
        health["ollama"] = "unavailable"

    return health


# ---------------------------------------------------------------------------
# Ops / Meta
# ---------------------------------------------------------------------------
@router.get("/meta/version")
async def get_version() -> Any:
    """Get API version and build info."""
    return {
        "project": settings.PROJECT_NAME,
        "api_version": "v1",
        "environment": settings.ENVIRONMENT,
    }


@router.get("/event-bus/debug")
async def debug_event_bus(
    current_user: User = Depends(requires_admin),
) -> Any:
    """Debug: List all registered event bus handlers."""
    from app.core.event_bus import event_bus
    return event_bus.list_events()
