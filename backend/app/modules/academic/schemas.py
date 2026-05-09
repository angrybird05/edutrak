"""
Academic module schemas.
"""
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class ChainBase(BaseModel):
    name: str

class ChainCreate(ChainBase):
    pass

class ChainUpdate(BaseModel):
    name: Optional[str] = None

class Chain(ChainBase):
    id: UUID
    model_config = {"from_attributes": True}


class SchoolBase(BaseModel):
    name: str
    email: Optional[str] = None
    address: Optional[str] = None
    village: Optional[str] = None
    mandal: Optional[str] = None
    district_city: str
    pincode: str

class SchoolCreate(SchoolBase):
    chain_id: Optional[UUID] = None

class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    village: Optional[str] = None
    mandal: Optional[str] = None
    district_city: Optional[str] = None
    pincode: Optional[str] = None

class School(SchoolBase):
    id: UUID
    chain_id: Optional[UUID] = None
    is_active: bool = True
    model_config = {"from_attributes": True}


class ClassBase(BaseModel):
    name: str
    class_number: int

class ClassCreate(ClassBase):
    school_id: UUID

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    class_number: Optional[int] = None

class Class(ClassBase):
    id: UUID
    school_id: UUID
    model_config = {"from_attributes": True}


class SectionBase(BaseModel):
    name: str

class SectionCreate(SectionBase):
    class_id: UUID

class SectionUpdate(BaseModel):
    name: Optional[str] = None

class Section(SectionBase):
    id: UUID
    class_id: UUID
    model_config = {"from_attributes": True}


class SubjectBase(BaseModel):
    name: str
    code: Optional[str] = None

class SubjectCreate(SubjectBase):
    school_id: UUID

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

class Subject(SubjectBase):
    id: UUID
    school_id: UUID
    model_config = {"from_attributes": True}


class SectionSubjectAssignmentUpdate(BaseModel):
    subject_ids: List[UUID]


class AcademicStructureSubject(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None


class AcademicStructureSection(BaseModel):
    id: UUID
    name: str
    class_id: UUID
    subjects: List[AcademicStructureSubject]


class AcademicStructureClass(BaseModel):
    id: UUID
    name: str
    class_number: int
    school_id: UUID
    sections: List[AcademicStructureSection]


class AcademicStructureResponse(BaseModel):
    classes: List[AcademicStructureClass]
    subjects: List[AcademicStructureSubject]


class TimetableEntry(BaseModel):
    id: UUID
    section_id: UUID
    subject_id: UUID
    teacher_id: UUID
    day_of_week: int
    start_time: str
    end_time: str
    room: Optional[str] = None
    model_config = {"from_attributes": True}


class TeacherSectionAssignmentUpdate(BaseModel):
    section_ids: List[UUID]


class TeacherSubjectAssignmentUpdate(BaseModel):
    subject_ids: List[UUID]


class TimetableEntryCreate(BaseModel):
    section_id: UUID
    subject_id: UUID
    teacher_id: UUID
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    room: Optional[str] = None


class TimetableEntryUpdate(BaseModel):
    subject_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


class TeacherAssignmentSection(BaseModel):
    id: UUID
    name: str
    class_id: UUID
    class_name: str


class TeacherAssignmentSubject(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None


class TeacherTimetableEntry(BaseModel):
    id: UUID
    section_id: UUID
    section_name: str
    class_id: UUID
    class_name: str
    subject_id: UUID
    subject_name: str
    teacher_id: UUID
    day_of_week: int
    start_time: str
    end_time: str
    room: Optional[str] = None


class TeacherAssignmentsResponse(BaseModel):
    teacher_id: UUID
    section_ids: List[UUID]
    subject_ids: List[UUID]
    sections: List[TeacherAssignmentSection]
    subjects: List[TeacherAssignmentSubject]
    timetable: List[TeacherTimetableEntry]
