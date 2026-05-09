from sqlalchemy import String, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

class UserSettings(Base):
    """
    User-specific UI preferences and notification settings.
    """
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), unique=True, nullable=False, index=True)
    
    # UI Preferences
    theme: Mapped[str] = mapped_column(String, default="light")
    language: Mapped[str] = mapped_column(String, default="en")
    
    # Notification Toggles
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Flexible field for future growth
    custom_prefs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
