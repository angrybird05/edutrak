"""
Analytics module models — AI Insights, Report Cards, Chat Sessions.

Migrated from app/models/performance.py (analytics-related) and app/models/ai_history.py.
"""
import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Integer, DateTime, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.modules.identity.models import Student
    from app.modules.academic.models import School


class AIInsight(Base):
    """AI-generated performance analysis for students."""
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False, index=True)
    insight_text: Mapped[str] = mapped_column(String, nullable=False)
    recommendations: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=True)
    context_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    user_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, default="v1.0", server_default="v1.0")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["Student"] = relationship("Student")


class ReportCard(Base):
    """Finalized terminal reports."""
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    term_name: Mapped[str] = mapped_column(String, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    student: Mapped["Student"] = relationship("Student")


class InstitutionalInsight(Base):
    """Persisted school-wide AI insight history for admin dashboards."""
    school_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=True, index=True)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    insight_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, default="v1.0", server_default="v1.0")
    status: Mapped[str] = mapped_column(String, default="generated", server_default="generated")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    school: Mapped[Optional["School"]] = relationship("School")


class AIChatSession(Base):
    """Persistent chat session for the AI Student Coach."""
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, default="New Chat Session")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    student: Mapped["Student"] = relationship("Student")
    messages: Mapped[List["AIChatMessage"]] = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")


class AIChatMessage(Base):
    """Individual message in an AI Coach session."""
    session_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aichatsession.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["AIChatSession"] = relationship("AIChatSession", back_populates="messages")
