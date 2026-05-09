from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID


# --- Class Schemas ---
class ClassBase(BaseModel):
    name: str
    class_number: int
    school_id: UUID


class ClassCreate(ClassBase):
    pass


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    class_number: Optional[int] = None


class ClassInDBBase(ClassBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Class(ClassInDBBase):
    pass


# --- Section Schemas ---
class SectionBase(BaseModel):
    name: str
    class_id: UUID


class SectionCreate(SectionBase):
    pass


class SectionUpdate(BaseModel):
    name: Optional[str] = None


class SectionInDBBase(SectionBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Section(SectionInDBBase):
    pass


# --- Subject Schemas ---
class SubjectBase(BaseModel):
    name: str
    code: Optional[str] = None
    school_id: UUID


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


class SubjectInDBBase(SubjectBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)


class Subject(SubjectInDBBase):
    pass
