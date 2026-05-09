from sqlalchemy import Column, String, ForeignKey, Integer, Table, Date, Float, DateTime, JSON, Boolean, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base
from typing import List, Optional, TYPE_CHECKING
import datetime

if TYPE_CHECKING:
    from app.models.academic import Section, Subject
    from app.models.student import Student

class Exam(Base):
    """
    Academic exam (e.g., 'Term 1 Final')
    """
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)

    # Relationships
    section: Mapped["Section"] = relationship("Section")
    marks: Mapped[List["Mark"]] = relationship("Mark", back_populates="exam")

class Mark(Base):
    """
    Standard marks record for a student in an exam/subject.
    """
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

    # Relationships
    exam: Mapped["Exam"] = relationship("Exam", back_populates="marks")
    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")

class Attendance(Base):
    """
    Daily attendance record for students.
    """
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, default=func.current_date())
    status: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Present", "Absent", "Late"

    # Relationships
    student: Mapped["Student"] = relationship("Student")

class AIInsight(Base):
    """
    AI-generated performance analysis for students.
    """
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False, index=True)
    insight_text: Mapped[str] = mapped_column(String, nullable=False)
    recommendations: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=True)
    context_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    user_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, default="v1.0", server_default="v1.0")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student: Mapped["Student"] = relationship("Student")

class ReportCard(Base):
    """
    Finalized terminal reports.
    """
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    term_name: Mapped[str] = mapped_column(String, nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    generated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student: Mapped["Student"] = relationship("Student")

class Notification(Base):
    """
    App or SMS notifications for parents/teachers.
    """
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

class LearningTask(Base):
    """
    Specific study task or homework for the AI-generated 'Weekly Path'.
    """
    student_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("student.id"), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False)
    
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    student: Mapped["Student"] = relationship("Student")
    subject: Mapped["Subject"] = relationship("Subject")

class Homework(Base):
    """
    Class-wide assignments/homework created by teachers.
    """
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False, index=True)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False, index=True)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    section: Mapped["Section"] = relationship("Section")
    subject: Mapped["Subject"] = relationship("Subject")
