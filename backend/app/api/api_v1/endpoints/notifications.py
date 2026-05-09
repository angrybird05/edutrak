from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.scale_foundation import NotificationEvent, UserNotification
from app.models.user import User
from app.schemas.notification import (
    NotificationItem,
    NotificationListResponse,
    NotificationMarkReadResponse,
    NotificationReadAllResponse,
)

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Any:
    filters = [UserNotification.user_id == current_user.id]
    if unread_only:
        filters.append(UserNotification.read_at.is_(None))

    count_query = (
        select(func.count())
        .select_from(UserNotification)
        .where(*filters)
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = (
        select(
            UserNotification.id,
            UserNotification.event_id,
            NotificationEvent.event_type,
            UserNotification.channel,
            UserNotification.status,
            NotificationEvent.payload_json,
            NotificationEvent.created_at.label("event_created_at"),
            UserNotification.created_at,
            UserNotification.read_at,
            UserNotification.sent_at,
            UserNotification.failed_at,
            UserNotification.error_message,
        )
        .join(NotificationEvent, NotificationEvent.id == UserNotification.event_id)
        .where(*filters)
        .order_by(UserNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)

    items = [
        NotificationItem(
            id=row.id,
            event_id=row.event_id,
            event_type=row.event_type,
            channel=row.channel,
            status=row.status,
            payload_json=row.payload_json or {},
            event_created_at=row.event_created_at,
            created_at=row.created_at,
            read_at=row.read_at,
            sent_at=row.sent_at,
            failed_at=row.failed_at,
            error_message=row.error_message,
        )
        for row in result
    ]

    return NotificationListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/{notification_id}/read", response_model=NotificationMarkReadResponse)
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    query = select(UserNotification).where(
        UserNotification.id == notification_id,
        UserNotification.user_id == current_user.id,
    )
    result = await db.execute(query)
    notification = result.scalars().first()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    now = _utcnow()
    notification.read_at = now
    notification.status = "read"
    await db.commit()
    await db.refresh(notification)

    return NotificationMarkReadResponse(
        id=notification.id,
        status=notification.status,
        read_at=notification.read_at,
    )


@router.patch("/mark-all-read", response_model=NotificationReadAllResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    now = _utcnow()
    stmt = (
        update(UserNotification)
        .where(
            UserNotification.user_id == current_user.id,
            UserNotification.read_at.is_(None),
        )
        .values(read_at=now, status="read")
    )
    result = await db.execute(stmt)
    await db.commit()
    return NotificationReadAllResponse(updated_count=result.rowcount or 0)
