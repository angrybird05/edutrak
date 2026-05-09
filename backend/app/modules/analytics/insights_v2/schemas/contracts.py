"""
Pydantic contracts for AI Insights V2.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InsightStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InsightGenerateRequest(BaseModel):
    exam_id: UUID
    section_id: Optional[UUID] = None
    student_ids: Optional[list[UUID]] = None
    explicit_ai: bool = False
    force_regenerate: bool = False
    reprocess_failed: bool = False
    model_version: str = Field(default="v2.0", min_length=1, max_length=50)


class InsightResponse(BaseModel):
    student_id: UUID
    exam_id: UUID
    insight_text: str
    recommendations_json: dict[str, Any]
    performance_summary_json: dict[str, Any]
    model_version: str
    status: InsightStatus
    generated_at: Optional[datetime]


class InsightStatusResponse(BaseModel):
    student_id: UUID
    exam_id: UUID
    status: InsightStatus
    model_version: Optional[str] = None
    generated_at: Optional[datetime] = None
    detail: Optional[str] = None


class SubjectSnapshot(BaseModel):
    subject_id: UUID
    subject_name: str
    current_percentage: float
    history_percentages: list[float]


class StructuredPerformanceData(BaseModel):
    student_id: UUID
    exam_id: UUID
    overall_percentage: float
    attendance_percentage: float
    subject_snapshots: list[SubjectSnapshot]
    overall_trend: str
    meta: dict[str, Any] = Field(default_factory=dict)

