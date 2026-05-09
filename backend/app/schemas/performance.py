from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator
from uuid import UUID
from datetime import date, datetime

class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    LATE = "Late"


class MarkStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXEMPT = "exempt"


# Attendance Schemas
class AttendanceBase(BaseModel):
    student_id: UUID
    date: date
    status: AttendanceStatus

class AttendanceCreate(AttendanceBase):
    pass

class AttendanceUpdate(BaseModel):
    status: Optional[str] = None
    date: Optional[date] = None

class AttendanceInDBBase(AttendanceBase):
    id: UUID
    
    model_config = ConfigDict(from_attributes=True)

class Attendance(AttendanceInDBBase):
    pass

class AttendanceBulkCreate(BaseModel):
    date: date
    section_id: UUID
    attendances: List[AttendanceCreate]

# Exam Schemas
class ExamBase(BaseModel):
    name: str
    section_id: UUID
    exam_date: Optional[date] = None

class ExamCreate(ExamBase):
    pass

class ExamUpdate(BaseModel):
    name: Optional[str] = None
    exam_date: Optional[date] = None

class ExamInDBBase(ExamBase):
    id: UUID
    
    model_config = ConfigDict(from_attributes=True)

class Exam(ExamInDBBase):
    pass

# Mark Schemas
class MarkBase(BaseModel):
    exam_id: UUID
    student_id: UUID
    subject_id: UUID
    marks_obtained: Optional[float] = Field(default=None, ge=0)
    max_marks: float = Field(default=100.0, gt=0)
    mark_status: MarkStatus = MarkStatus.PRESENT
    comments: Optional[str] = None

    @model_validator(mode="after")
    def validate_mark_values(self):
        if self.mark_status == MarkStatus.PRESENT and self.marks_obtained is None:
            raise ValueError("marks_obtained is required when mark_status is present")
        if (
            self.marks_obtained is not None
            and self.max_marks is not None
            and self.marks_obtained > self.max_marks
        ):
            raise ValueError("marks_obtained cannot exceed max_marks")
        return self

class MarkCreate(MarkBase):
    pass

class MarkUpdate(BaseModel):
    marks_obtained: Optional[float] = Field(default=None, ge=0)
    max_marks: Optional[float] = Field(default=None, gt=0)
    mark_status: Optional[MarkStatus] = None
    comments: Optional[str] = None

class MarkInDBBase(MarkBase):
    id: UUID
    
    model_config = ConfigDict(from_attributes=True)

class Mark(MarkInDBBase):
    pass

class MarkBulkCreate(BaseModel):
    exam_id: UUID
    subject_id: UUID
    marks: List[MarkCreate]

# AI Insight Schemas
class AIInsightBase(BaseModel):
    student_id: UUID
    insight_text: str
    recommendations: Optional[dict] = None
    context_hash: Optional[str] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_text: Optional[str] = None
    prompt_version: str = "v1.0"

class AIInsightResponse(AIInsightBase):
    id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class AIInsightGenerate(BaseModel):
    """Request to generate insight for a student or section."""
    student_id: Optional[UUID] = None
    section_id: Optional[UUID] = None

class AIInsightRate(BaseModel):
    """Request to rate an AI insight."""
    user_rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None

class AdminDigestResponse(BaseModel):
    """Response containing school-wide strategic AI summary."""
    digest: str
    generated_at: datetime
    metrics: dict


# Report Card Schemas
class ReportCardGenerate(BaseModel):
    student_id: UUID
    term_name: str = "Current Term"


class ReportCardResponse(BaseModel):
    id: UUID
    student_id: UUID
    term_name: str
    pdf_url: Optional[str] = None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)
