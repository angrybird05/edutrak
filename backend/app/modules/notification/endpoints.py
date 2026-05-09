"""
Notification module endpoints.

Migrated from app/api/api_v1/endpoints/notifications.py.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user
from app.modules.auth.models import User
from app.modules.notification.models import UserNotification, NotificationEvent

router = APIRouter()


@router.get("/")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
) -> Any:
    """List notifications for the current user."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 50))

    result = await db.execute(
        select(UserNotification, NotificationEvent)
        .join(NotificationEvent, UserNotification.event_id == NotificationEvent.id)
        .where(UserNotification.user_id == current_user.id)
        .order_by(UserNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()

    return [
        {
            "id": str(un.id),
            "event_type": event.event_type,
            "payload": event.payload_json,
            "channel": un.channel,
            "status": un.status,
            "read_at": str(un.read_at) if un.read_at else None,
            "created_at": str(un.created_at),
        }
        for un, event in rows
    ]


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Mark a notification as read."""
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.status = "read"
    notification.read_at = datetime.now(timezone.utc)
    db.add(notification)
    await db.commit()
    return {"status": "read"}


@router.patch("/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Mark all notifications as read."""
    await db.execute(
        update(UserNotification)
        .where(
            UserNotification.user_id == current_user.id,
            UserNotification.status == "unread",
        )
        .values(status="read", read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"status": "all_read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Delete a notification for the current user."""
    result = await db.execute(
        select(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.execute(
        delete(UserNotification).where(
            UserNotification.id == notification_id,
            UserNotification.user_id == current_user.id,
        )
    )
    await db.commit()
    return {"status": "deleted"}
