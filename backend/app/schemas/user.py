from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from app.models.user import UserRole


class UserBase(BaseModel):
    phone: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = True
    school_id: Optional[UUID] = None


class UserCreate(UserBase):
    phone: str
    role: UserRole


class UserUpdate(UserBase):
    pass


class UserInDBBase(UserBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class User(UserInDBBase):
    pass
