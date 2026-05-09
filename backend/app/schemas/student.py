from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import date
from app.schemas.user import User


class StudentBase(BaseModel):
    admission_number: str
    roll_number: Optional[str] = None
    dob: Optional[date] = None
    school_id: UUID
    class_id: UUID
    section_id: UUID


class StudentCreate(StudentBase):
    phone: str  # Associated user's phone
    full_name: str


class StudentUpdate(BaseModel):
    roll_number: Optional[str] = None
    dob: Optional[date] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    full_name: Optional[str] = None


class StudentInDBBase(StudentBase):
    id: UUID
    user_id: UUID
    parent_joining_code: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class StudentCreateResponse(StudentInDBBase):
    pass


class Student(StudentInDBBase):
    user: User
