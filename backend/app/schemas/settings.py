from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserSettingsBase(BaseModel):
    theme: Optional[str] = "light"
    language: Optional[str] = "en"
    email_notifications: Optional[bool] = True
    sms_notifications: Optional[bool] = True
    push_notifications: Optional[bool] = True
    custom_prefs: Optional[Dict[str, Any]] = None


class UserSettingsUpdate(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    custom_prefs: Optional[Dict[str, Any]] = None


class UserSettings(UserSettingsBase):
    user_id: UUID
    model_config = ConfigDict(from_attributes=True)
