from sqlalchemy import String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from typing import List, Optional, TYPE_CHECKING
import datetime

if TYPE_CHECKING:
    from app.models.student import Student

class AIChatSession(Base):
    """
    Persistent chat session for the AI Student Coach.
    """
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, default="New Chat Session")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    student: Mapped["Student"] = relationship("Student")
    messages: Mapped[List["AIChatMessage"]] = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")

class AIChatMessage(Base):
    """
    Individual message in an AI Coach session.
    """
    session_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aichatsession.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False) # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session: Mapped["AIChatSession"] = relationship("AIChatSession", back_populates="messages")
