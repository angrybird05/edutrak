import csv
import io
from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, UploadFile

from app import crud, models, schemas
from app.services.ai_task_queue import ai_insight_task_queue

VALID_MARK_STATUSES = {"present", "absent", "exempt"}
VALID_ATTENDANCE_STATUSES = {"Present", "Absent", "Late"}

class BulkService:
    @staticmethod
    async def process_student_csv(
        db: AsyncSession, 
        file: UploadFile, 
        school_id: UUID, 
        class_id: UUID, 
        section_id: UUID,
        content: Optional[bytes] = None,
    ) -> List[models.student.Student]:
        if content is None:
            content = await file.read()
        f = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(f)
        
        students = []
        for row in reader:
            student_in = schemas.student.StudentCreate(
                full_name=row['full_name'],
                phone=row['phone'],
                admission_number=row['admission_number'],
                roll_number=row.get('roll_number'),
                school_id=school_id,
                class_id=class_id,
                section_id=section_id
            )
            student = await crud.student.create_with_user(db, obj_in=student_in)
            students.append(student)
            
        return students

    @staticmethod
    async def process_attendance_csv(
        db: AsyncSession, 
        file: UploadFile, 
        attendance_date: date,
        content: Optional[bytes] = None,
    ) -> List[models.performance.Attendance]:
        if content is None:
            content = await file.read()
        f = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(f)
        
        records = []
        student_ids = []
        for row in reader:
            sid = UUID(row['student_id'])
            status_value = str(row.get("status", "")).strip()
            if status_value not in VALID_ATTENDANCE_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid attendance status '{status_value}' in CSV. Use Present/Absent/Late",
                )
            db_obj = models.performance.Attendance(
                student_id=sid,
                date=attendance_date,
                status=status_value
            )
            db.add(db_obj)
            records.append(db_obj)
            student_ids.append(sid)
            
        await db.commit()
        await ai_insight_task_queue.enqueue_students(student_ids)
        return records

    @staticmethod
    async def process_mark_csv(
        db: AsyncSession, 
        file: UploadFile, 
        exam_id: UUID, 
        subject_id: UUID,
        content: Optional[bytes] = None,
    ) -> List[models.performance.Mark]:
        if content is None:
            content = await file.read()
        f = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(f)
        
        records = []
        student_ids = []
        for row in reader:
            sid = UUID(row['student_id'])
            status_value = str(row.get('mark_status', 'present')).strip().lower() or "present"
            if status_value not in VALID_MARK_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid mark_status '{status_value}' in CSV. Use present/absent/exempt",
                )
            if status_value in {"absent", "exempt"}:
                marks_obtained = 0.0
            else:
                if row.get("marks_obtained") in (None, ""):
                    raise HTTPException(
                        status_code=400,
                        detail="marks_obtained is required in CSV when mark_status is present",
                    )
                marks_obtained = float(row["marks_obtained"])
                if marks_obtained < 0:
                    raise HTTPException(status_code=400, detail="marks_obtained cannot be negative")

            max_marks = float(row.get('max_marks', 100.0))
            if max_marks <= 0:
                raise HTTPException(status_code=400, detail="max_marks must be greater than 0")
            if status_value == "present" and marks_obtained > max_marks:
                raise HTTPException(status_code=400, detail="marks_obtained cannot exceed max_marks")

            db_obj = models.performance.Mark(
                exam_id=exam_id,
                subject_id=subject_id,
                student_id=sid,
                marks_obtained=marks_obtained,
                max_marks=max_marks,
                mark_status=status_value,
                comments=row.get('comments')
            )
            db.add(db_obj)
            records.append(db_obj)
            student_ids.append(sid)
            
        await db.commit()
        await ai_insight_task_queue.enqueue_students(student_ids)
        return records

bulk_service = BulkService()
