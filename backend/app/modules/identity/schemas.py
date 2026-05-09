"""
Identity module schemas.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StudentBase(BaseModel):
    admission_number: str
    roll_number: Optional[str] = None
    dob: Optional[date] = None
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_phone: Optional[str] = None


class StudentCreate(BaseModel):
    full_name: str
    admission_number: str
    roll_number: Optional[str] = None
    dob: Optional[date] = None
    class_id: UUID
    section_id: UUID
    guardian_name: str
    guardian_relation: str
    guardian_phone: str


class StudentUpdate(BaseModel):
    roll_number: Optional[str] = None
    dob: Optional[date] = None
    class_id: Optional[UUID] = None
    section_id: Optional[UUID] = None
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_phone: Optional[str] = None


class Student(StudentBase):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    school_id: UUID
    class_id: UUID
    section_id: UUID
    parent_joining_code: Optional[str] = None

    @classmethod
    def model_validate(cls, obj, **kwargs):
        data = super().model_validate(obj, **kwargs)
        if hasattr(obj, "user") and obj.user:
            data.full_name = obj.user.full_name
        return data

    model_config = {"from_attributes": True}


class StudentCreateResponse(Student):
    parent_account_created: bool = False


class StudentListResponse(BaseModel):
    items: List[Student]
    total: int
    page: int
    page_size: int


class ParentLinkByCodeRequest(BaseModel):
    joining_code: str = Field(min_length=4, max_length=32)


class ParentChildSummary(BaseModel):
    id: UUID
    user_id: UUID
    full_name: Optional[str] = None
    admission_number: str
    roll_number: Optional[str] = None
    class_id: UUID
    section_id: UUID
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_phone: Optional[str] = None
    parent_joining_code: Optional[str] = None


class UserProfile(BaseModel):
    id: UUID
    phone: str
    full_name: Optional[str] = None
    role: str
    language_pref: str = "en"
    school_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    language_pref: Optional[str] = None


class TeacherBase(BaseModel):
    full_name: str
    username: str
    phone: Optional[str] = None
    language_pref: str = "en"
    is_active: bool = True


class TeacherCreate(TeacherBase):
    password: str = Field(min_length=8)


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    language_pref: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherCredentialsUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)


class Teacher(BaseModel):
    id: UUID
    full_name: Optional[str] = None
    username: Optional[str] = None
    phone: str
    role: str
    language_pref: str = "en"
    is_active: bool = True
    school_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class TeacherListResponse(BaseModel):
    items: List[Teacher]
    total: int
    page: int
    page_size: int
