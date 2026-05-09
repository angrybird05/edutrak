"""
Assessment module service — Marks, attendance, bulk operations with event bus.

Migrated from app/services/bulk_service.py with event-driven AI queuing.
"""
import csv
import io
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import event_bus
from app.modules.assessment.models import Mark, Attendance, Exam
from app.modules.identity.models import Student
from app.modules.auth.models import User, UserRole

VALID_MARK_STATUSES = {"present", "absent", "exempt"}
VALID_ATTENDANCE_STATUSES = {"Present", "Absent", "Late"}


class AssessmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_marks_bulk(
        self,
        file: UploadFile,
        exam_id: UUID,
        subject_id: UUID,
        actor_id: Optional[UUID] = None,
        content: Optional[bytes] = None,
    ) -> List[Mark]:
        """Process CSV of marks and emit event for AI insight regeneration."""
        if content is None:
            content = await file.read()
        f = io.StringIO(content.decode("utf-8"))
        reader = csv.DictReader(f)

        records = []
        student_ids = []
        for row in reader:
            sid = UUID(row["student_id"])
            status_value = str(row.get("mark_status", "present")).strip().lower() or "present"
            if status_value not in VALID_MARK_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid mark_status '{status_value}' in CSV. Use present/absent/exempt",
                )
            if status_value in {"absent", "exempt"}:
                marks_obtained = 0.0
            else:
                if row.get("marks_obtained") in (None, ""):
                    raise HTTPException(status_code=400, detail="marks_obtained is required when mark_status is present")
                marks_obtained = float(row["marks_obtained"])
                if marks_obtained < 0:
                    raise HTTPException(status_code=400, detail="marks_obtained cannot be negative")

            max_marks = float(row.get("max_marks", 100.0))
            if max_marks <= 0:
                raise HTTPException(status_code=400, detail="max_marks must be greater than 0")
            if status_value == "present" and marks_obtained > max_marks:
                raise HTTPException(status_code=400, detail="marks_obtained cannot exceed max_marks")

            db_obj = Mark(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=sid,
                marks_obtained=marks_obtained,
                max_marks=max_marks,
                mark_status=status_value,
                comments=row.get("comments"),
            )
            self.db.add(db_obj)
            records.append(db_obj)
            student_ids.append(sid)

        await self.db.commit()

        # Emit event — analytics module subscribes to regenerate AI insights
        await event_bus.emit("assessment.marks_recorded", {
            "student_ids": [str(sid) for sid in student_ids],
            "exam_id": str(exam_id),
            "subject_id": str(subject_id),
            "actor_id": str(actor_id) if actor_id else None,
        })

        return records

    async def record_attendance_bulk(
        self,
        file: UploadFile,
        attendance_date: date,
        actor_id: Optional[UUID] = None,
        content: Optional[bytes] = None,
    ) -> List[Attendance]:
        """Process CSV of attendance and emit event."""
        if content is None:
            content = await file.read()
        f = io.StringIO(content.decode("utf-8"))
        reader = csv.DictReader(f)

        records = []
        student_ids = []
        for row in reader:
            sid = UUID(row["student_id"])
            status_value = str(row.get("status", "")).strip()
            if status_value not in VALID_ATTENDANCE_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid attendance status '{status_value}'. Use Present/Absent/Late",
                )
            db_obj = Attendance(student_id=sid, date=attendance_date, status=status_value)
            self.db.add(db_obj)
            records.append(db_obj)
            student_ids.append(sid)

        await self.db.commit()

        await event_bus.emit("assessment.attendance_recorded", {
            "student_ids": [str(sid) for sid in student_ids],
            "date": str(attendance_date),
            "actor_id": str(actor_id) if actor_id else None,
        })

        return records


def get_assessment_service(db: AsyncSession) -> AssessmentService:
    return AssessmentService(db)
