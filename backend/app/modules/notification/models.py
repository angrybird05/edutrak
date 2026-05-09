"""
Notification module models.

Migrated from app/models/performance.py (Notification) and app/models/scale_foundation.py.
"""
import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Notification(Base):
    """Simple app/SMS notification for parents/teachers."""
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationEvent(Base):
    __tablename__ = "notification_event"
    __table_args__ = (
        Index("ix_notification_event_event_type_created_at", "event_type", "created_at"),
        Index("ix_notification_event_student_created_at", "student_id", "created_at"),
        Index("ix_notification_event_school_created_at", "school_id", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    student_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=True)
    school_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserNotification(Base):
    __tablename__ = "user_notification"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "channel", name="uq_user_notification_event_user_channel"),
        Index("ix_user_notification_user_read_at", "user_id", "read_at"),
        Index("ix_user_notification_user_created_at", "user_id", "created_at"),
        Index("ix_user_notification_status_created_at", "status", "created_at"),
    )

    event_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notification_event.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    read_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class DeviceToken(Base):
    __tablename__ = "device_token"
    __table_args__ = (
        Index("ix_device_token_user_active", "user_id", "is_active"),
    )

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_seen_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
