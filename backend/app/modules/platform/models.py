"""
Platform module models — Audit, logging, idempotency, outbox, settings.

Migrated from app/models/audit.py, app/models/scale_foundation.py, app/models/settings.py.
"""
import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class AuditLog(Base):
    """Tracks security-sensitive and administrative actions."""
    __table_args__ = (
        Index("ix_auditlog_action_created_at", "action", "created_at"),
        Index("ix_auditlog_user_created_at", "user_id", "created_at"),
        Index("ix_auditlog_school_created_at", "school_id", "created_at"),
        Index("ix_auditlog_student_created_at", "student_id", "created_at"),
        Index("ix_auditlog_trace_id_created_at", "trace_id", "created_at"),
    )

    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    school_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=True)
    student_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class APIRequestLog(Base):
    __tablename__ = "api_request_log"
    __table_args__ = (
        Index("ix_api_request_log_trace_id_created_at", "trace_id", "created_at"),
        Index("ix_api_request_log_user_created_at", "user_id", "created_at"),
        Index("ix_api_request_log_path_method_created_at", "path", "method", "created_at"),
        Index("ix_api_request_log_status_created_at", "status_code", "created_at"),
    )

    trace_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_key"
    __table_args__ = (
        Index("ix_idempotency_key_scope", "idempotency_key", "scope"),
        Index("ix_idempotency_key_expires_at", "expires_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    request_hash: Mapped[str] = mapped_column(String, nullable=False)
    response_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class OutboxJob(Base):
    __tablename__ = "outbox_job"
    __table_args__ = (
        Index("ix_outbox_job_status_next_run_at", "status", "next_run_at"),
        Index("ix_outbox_job_job_type_created_at", "job_type", "created_at"),
    )

    job_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    next_run_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    locked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class UserSettings(Base):
    """User-specific UI preferences and notification settings."""
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), unique=True, nullable=False, index=True)

    theme: Mapped[str] = mapped_column(String, default="light")
    language: Mapped[str] = mapped_column(String, default="en")
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_prefs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User")

# Avoid circular import — only needed for type annotation
from app.modules.auth.models import User  # noqa: E402
