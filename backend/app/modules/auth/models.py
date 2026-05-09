"""
Auth module models — User identity and OTP sessions.

The User model is the central identity record. The auth module owns the
authentication-related fields (phone, password_hash, role, is_active).
The identity module extends User with profile fields via relationships.
"""
from sqlalchemy import String, Enum, Boolean, ForeignKey, DateTime, Integer, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from typing import Optional, TYPE_CHECKING
import enum
import datetime

if TYPE_CHECKING:
    from app.modules.academic.models import School


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


class User(Base):
    __table_args__ = (
        UniqueConstraint("role", "phone", name="uq_user_role_phone"),
    )

    phone: Mapped[str] = mapped_column(String, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language_pref: Mapped[str] = mapped_column(String, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    school_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school.id"), nullable=True
    )

    # Relationships
    school: Mapped[Optional["School"]] = relationship("School", back_populates="users")


class OTPSession(Base):
    """Session for tracking OTP login requests."""
    phone: Mapped[str] = mapped_column(String, index=True, nullable=False)
    requested_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    otp_code: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    request_ip: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
