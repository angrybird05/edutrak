"""
Academic module models — School hierarchy, subjects, timetables.

Migrated from app/models/school.py and app/models/academic.py.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, Table, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.auth.models import User

# Association table for Teachers assigned to Sections
teacher_section = Table(
    "teacher_section",
    Base.metadata,
    Column("teacher_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("section_id", UUID(as_uuid=True), ForeignKey("section.id"), primary_key=True),
)

# Association table for Teachers and Subjects they are allowed to teach
teacher_subject = Table(
    "teacher_subject",
    Base.metadata,
    Column("teacher_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("subject_id", UUID(as_uuid=True), ForeignKey("subject.id"), primary_key=True),
)

# Association table for Sections and the Subjects taught in that section
section_subject = Table(
    "section_subject",
    Base.metadata,
    Column("section_id", UUID(as_uuid=True), ForeignKey("section.id"), primary_key=True),
    Column("subject_id", UUID(as_uuid=True), ForeignKey("subject.id"), primary_key=True),
)

# Association table for Students and Subjects
student_subject = Table(
    "student_subject",
    Base.metadata,
    Column("student_id", UUID(as_uuid=True), ForeignKey("student.id"), primary_key=True),
    Column("subject_id", UUID(as_uuid=True), ForeignKey("subject.id"), primary_key=True),
)


class Chain(Base):
    """Overarching organization (e.g., 'ABC School Group')."""
    name: Mapped[str] = mapped_column(String, nullable=False)
    schools: Mapped[List["School"]] = relationship("School", back_populates="chain")


class School(Base):
    """Individual school within a chain."""
    chain_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chain.id"), nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    village: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    mandal: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    district_city: Mapped[str] = mapped_column(String, nullable=False)
    pincode: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    chain: Mapped["Chain"] = relationship("Chain", back_populates="schools")
    users: Mapped[List["User"]] = relationship("User", back_populates="school")
    classes: Mapped[List["Class"]] = relationship("Class", back_populates="school")


class Class(Base):
    """Generic class level (e.g., 'Class 1', 'Class 2')."""
    school_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    class_number: Mapped[int] = mapped_column(Integer, nullable=False)

    school: Mapped["School"] = relationship("School", back_populates="classes")
    sections: Mapped[List["Section"]] = relationship("Section", back_populates="parent_class")


class Section(Base):
    """Sub-division of a class (e.g., 'Section A', 'Section B')."""
    class_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    parent_class: Mapped["Class"] = relationship("Class", back_populates="sections")
    teachers: Mapped[List["User"]] = relationship(
        "User", secondary=teacher_section, backref="assigned_sections"
    )
    subjects: Mapped[List["Subject"]] = relationship(
        "Subject", secondary=section_subject, back_populates="sections"
    )


class Subject(Base):
    """Academic subject (e.g., 'Maths', 'Science')."""
    school_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    school: Mapped["School"] = relationship("School")
    teachers: Mapped[List["User"]] = relationship(
        "User", secondary=teacher_subject, backref="assigned_subjects"
    )
    sections: Mapped[List["Section"]] = relationship(
        "Section", secondary=section_subject, back_populates="subjects"
    )


class Timetable(Base):
    """Weekly schedule for a section and subject."""
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subject.id"), nullable=False)
    teacher_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)

    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    room: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    section: Mapped["Section"] = relationship("Section")
    subject: Mapped["Subject"] = relationship("Subject")
    teacher: Mapped["User"] = relationship("User")
