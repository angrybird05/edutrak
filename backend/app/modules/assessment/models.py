"""
Assessment module models — Exams, Marks, Attendance, Homework.

Migrated from app/models/performance.py (assessment-related models only).
"""
import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Float, Date, DateTime, Integer, JSON, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.modules.academic.models import Section, Subject
    from app.modules.identity.models import Student


class Exam(Base):
    """Academic exam (e.g., 'Term 1 Final')."""
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    section: Mapped["Section"] = relationship("Section")
    marks: Mapped[List["Mark"]] = relationship("Mark", back_populates="exam")


class Mark(Base):
    """Standard marks record for a student in an exam/subject."""
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "subject_id", name="uq_mark_exam_student_subject"),
        Index("ix_mark_student_subject", "student_id", "subject_id"),
        Index("ix_mark_exam_subject", "exam_id", "subject_id"),
    )

    exam_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("exam.id"), nullable=False)
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False)

    marks_obtained: Mapped[float] = mapped_column(Float, nullable=False)
    max_marks: Mapped[float] = mapped_column(Float, default=100.0)
    mark_status: Mapped[str] = mapped_column(String, default="present", server_default="present", nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="marks")
    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")


class Attendance(Base):
    """Daily attendance record for students."""
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, default=func.current_date())
    status: Mapped[str] = mapped_column(String, nullable=False)

    student: Mapped["Student"] = relationship("Student")


class Homework(Base):
    """Class-wide assignments/homework created by teachers."""
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    section: Mapped["Section"] = relationship("Section")
    subject: Mapped["Subject"] = relationship("Subject")


class LearningTask(Base):
    """AI-generated study task for a student's weekly path."""
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False)

    task_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")
