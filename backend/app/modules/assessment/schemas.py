from datetime import date
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"


class AttendanceSectionOption(BaseModel):
    id: UUID
    name: str
    class_id: UUID
    class_name: str


class AttendanceSheetStudent(BaseModel):
    student_id: UUID
    full_name: Optional[str] = None
    admission_number: str
    roll_number: Optional[str] = None
    status: Optional[AttendanceStatus] = None


class AttendanceSheetTotals(BaseModel):
    total: int
    marked: int
    present: int
    absent: int
    late: int


class AttendanceSheetResponse(BaseModel):
    date: date
    class_id: UUID
    class_name: str
    section_id: UUID
    section_name: str
    students: List[AttendanceSheetStudent]
    totals: AttendanceSheetTotals


class AttendanceSheetUpsertItem(BaseModel):
    student_id: UUID
    status: AttendanceStatus


class AttendanceSheetUpsertRequest(BaseModel):
    date: date
    records: List[AttendanceSheetUpsertItem]


class GradebookSubjectOption(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None


class GradebookExamOption(BaseModel):
    id: UUID
    name: str
    exam_date: Optional[date] = None


class GradebookSectionContextResponse(BaseModel):
    class_id: UUID
    class_name: str
    section_id: UUID
    section_name: str
    subjects: List[GradebookSubjectOption]
    exams: List[GradebookExamOption]


class GradebookMatrixStudent(BaseModel):
    student_id: UUID
    full_name: Optional[str] = None
    admission_number: str
    roll_number: Optional[str] = None
    marks_obtained: Optional[float] = None
    max_marks: float = 100.0
    mark_status: str = "present"
    comments: Optional[str] = None
    percentage: Optional[float] = None


class GradebookMatrixSummary(BaseModel):
    total_students: int
    entered_marks: int
    average_percentage: float
    highest_percentage: float
    lowest_percentage: float


class GradebookMatrixResponse(BaseModel):
    class_id: UUID
    class_name: str
    section_id: UUID
    section_name: str
    subject_id: UUID
    exam_id: UUID
    students: List[GradebookMatrixStudent]
    summary: GradebookMatrixSummary


class GradebookMatrixUpsertItem(BaseModel):
    student_id: UUID
    marks_obtained: float
    max_marks: float = 100.0
    mark_status: str = "present"
    comments: Optional[str] = None


class GradebookMatrixUpsertRequest(BaseModel):
    exam_id: UUID
    subject_id: UUID
    records: List[GradebookMatrixUpsertItem]
