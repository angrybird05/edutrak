import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base

class AuditLog(Base):
    """
    Tracks security-sensitive and administrative actions.
    """
    __table_args__ = (
        Index("ix_auditlog_action_created_at", "action", "created_at"),
        Index("ix_auditlog_user_created_at", "user_id", "created_at"),
        Index("ix_auditlog_school_created_at", "school_id", "created_at"),
        Index("ix_auditlog_student_created_at", "student_id", "created_at"),
        Index("ix_auditlog_trace_id_created_at", "trace_id", "created_at"),
    )

    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False) # e.g., "CREATE_STUDENT", "LOGIN_SUCCESS"
    resource_type: Mapped[str] = mapped_column(String, nullable=False) # e.g., "student", "user"
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    school_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=True)
    student_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
