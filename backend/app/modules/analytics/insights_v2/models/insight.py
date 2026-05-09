"""
AI Insights V2 persistence model.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.modules.assessment.models import Exam
    from app.modules.identity.models import Student


class AIInsightV2(Base):
    """
    Exam-scoped AI insight record used by the precomputed V2 pipeline.
    """

    __tablename__ = "ai_insights"
    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_ai_insights_student_exam"),
        Index("ix_ai_insights_student_exam", "student_id", "exam_id"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_ai_insights_status",
        ),
    )

    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    exam_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam.id"), nullable=False)
    insight_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    recommendations_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    performance_summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="v2.0", server_default="v2.0")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending")
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped["Student"] = relationship("Student")
    exam: Mapped["Exam"] = relationship("Exam")
