from sqlalchemy import Column, String, ForeignKey, Integer, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

# Association table for Teachers assigned to Sections
teacher_section = Table(
    "teacher_section",
    Base.metadata,
    Column("teacher_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("section_id", UUID(as_uuid=True), ForeignKey("section.id"), primary_key=True),
)

class Class(Base):
    """
    Generic class level (e.g., 'Class 1', 'Class 2')
    """
    school_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False) # e.g. "Primary 1"
    class_number: Mapped[int] = mapped_column(Integer, nullable=False) # e.g. 1, 2, 3

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="classes")
    sections: Mapped[List["Section"]] = relationship("Section", back_populates="parent_class")

class Section(Base):
    """
    Sub-division of a class (e.g., 'Section A', 'Section B')
    """
    class_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False) # e.g. "A", "B"

    # Relationships
    parent_class: Mapped["Class"] = relationship("Class", back_populates="sections")
    teachers: Mapped[List["User"]] = relationship(
        "User", secondary=teacher_section, backref="assigned_sections"
    )

# Association table for Students and Subjects (to track who takes what)
student_subject = Table(
    "student_subject",
    Base.metadata,
    Column("student_id", UUID(as_uuid=True), ForeignKey("student.id"), primary_key=True),
    Column("subject_id", UUID(as_uuid=True), ForeignKey("subject.id"), primary_key=True),
)

class Subject(Base):
    """
    Academic subject (e.g., 'Maths', 'Science')
    """
    school_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    school: Mapped["School"] = relationship("School")

class Timetable(Base):
    """
    Weekly schedule for a section and subject.
    """
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False)
    teacher_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False) # 0-6 (Mon-Sun)
    start_time: Mapped[str] = mapped_column(String, nullable=False) # "HH:MM"
    end_time: Mapped[str] = mapped_column(String, nullable=False) # "HH:MM"
    room: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    section: Mapped["Section"] = relationship("Section")
    subject: Mapped["Subject"] = relationship("Subject")
    teacher: Mapped["User"] = relationship("User")
