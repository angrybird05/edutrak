from sqlalchemy import Column, String, ForeignKey, Table, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.academic import Class, Section
    from app.models.school import School

# Many-to-Many link between Parents (Users) and Students
parent_student = Table(
    "parent_student",
    Base.metadata,
    Column("parent_id", UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True),
    Column("student_id", UUID(as_uuid=True), ForeignKey("student.id"), primary_key=True),
)

class Student(Base):
    """
    Detailed student record, linked to a User account and Academic structure.
    """
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, unique=True)
    school_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("school.id"), nullable=False)
    class_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class.id"), nullable=False)
    section_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("section.id"), nullable=False)
    
    admission_number: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    roll_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dob: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    parent_joining_code: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    parents: Mapped[List["User"]] = relationship(
        "User", secondary=parent_student, backref="children"
    )
    # academic_class: Mapped["Class"] = relationship("Class")
    # academic_section: Mapped["Section"] = relationship("Section")
