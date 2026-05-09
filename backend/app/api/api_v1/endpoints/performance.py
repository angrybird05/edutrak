import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, case, func
from uuid import UUID
from datetime import date

from app.db.session import get_db
from app.api import deps
from app.core.rate_limit import enforce_heavy_rate_limit
from app.models.performance import Attendance, Exam, Mark, LearningTask
from app.models.academic import Subject
from app.models.student import Student, parent_student
from app.models.user import User, UserRole
from app.schemas.performance import (
    Attendance as AttendanceSchema,
    AttendanceCreate,
    AttendanceBulkCreate,
    Exam as ExamSchema,
    ExamCreate,
    Mark as MarkSchema,
    MarkCreate,
    MarkBulkCreate
)
from app.services.ai_task_queue import ai_insight_task_queue
from app.services.idempotency_service import idempotency_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_MARK_STATUSES = {"present", "absent", "exempt"}


async def _get_allowed_student_ids(db: AsyncSession, current_user: User) -> Optional[set[UUID]]:
    if current_user.role in {UserRole.ADMIN, UserRole.TEACHER}:
        return None

    if current_user.role == UserRole.STUDENT:
        student_result = await db.execute(select(Student.id).where(Student.user_id == current_user.id))
        student_id = student_result.scalar_one_or_none()
        return {student_id} if student_id else set()

    if current_user.role == UserRole.PARENT:
        children_result = await db.execute(
            select(parent_student.c.student_id).where(parent_student.c.parent_id == current_user.id)
        )
        return set(children_result.scalars().all())

    return set()

# --- Attendance Endpoints ---

@router.get("/attendance/", response_model=List[AttendanceSchema])
async def get_attendance(
    db: AsyncSession = Depends(get_db),
    student_id: Optional[UUID] = None,
    section_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get attendance records with optional filters. Paginated.
    """
    query = select(Attendance)
    filters = []
    allowed_student_ids = await _get_allowed_student_ids(db, current_user)

    if allowed_student_ids is not None:
        if student_id and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this student")
        if not student_id:
            if not allowed_student_ids:
                return []
            filters.append(Attendance.student_id.in_(list(allowed_student_ids)))
    
    if student_id:
        filters.append(Attendance.student_id == student_id)
    
    if section_id:
        query = query.join(Student).filter(Student.section_id == section_id)
        
    if start_date:
        filters.append(Attendance.date >= start_date)
    if end_date:
        filters.append(Attendance.date <= end_date)
        
    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(Attendance.date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/attendance/bulk", response_model=List[AttendanceSchema])
async def create_attendance_bulk(
    *,
    db: AsyncSession = Depends(get_db),
    attendance_in: AttendanceBulkCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: Any = Depends(deps.requires_admin),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    """
    Bulk record attendance for a section.
    """
    payload = attendance_in.model_dump(mode="json")
    if idempotency_key:
        existing = await idempotency_service.check_existing(
            db,
            idempotency_key=idempotency_key,
            scope="performance.attendance.bulk",
            request_payload=payload,
        )
        if existing:
            return existing["items"]

    new_records = []
    student_ids = []
    for att in attendance_in.attendances:
        db_obj = Attendance(
            student_id=att.student_id,
            date=attendance_in.date,
            status=att.status
        )
        db.add(db_obj)
        new_records.append(db_obj)
        student_ids.append(att.student_id)
    
    await db.commit()
    for rec in new_records:
        await db.refresh(rec)

    # Queue AI generation to avoid blocking this request.
    await ai_insight_task_queue.enqueue_students(student_ids)

    # Low attendance detection — batched query instead of per-student loop
    unique_sids = list(set(student_ids))
    att_stats = await db.execute(
        select(
            Attendance.student_id,
            func.count().label("total"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present"),
        )
        .where(Attendance.student_id.in_(unique_sids))
        .group_by(Attendance.student_id)
    )
    for row in att_stats:
        pct = (int(row.present) / int(row.total)) if int(row.total) else 1.0
        if pct < 0.75:
            recipients = await notification_service.recipients_for_student(db, student_id=row.student_id)
            if recipients:
                await notification_service.emit_event(
                    db,
                    event_type="low_attendance_detected",
                    actor_id=current_user.id,
                    student_id=row.student_id,
                    school_id=current_user.school_id,
                    payload_json={
                        "attendance_percentage": round(pct * 100, 2),
                        "present_days": int(row.present),
                        "total_days": int(row.total),
                    },
                    recipient_user_ids=recipients,
                )

    if idempotency_key:
        await idempotency_service.store_response(
            db,
            idempotency_key=idempotency_key,
            scope="performance.attendance.bulk",
            request_payload=payload,
            response_payload={"items": [AttendanceSchema.model_validate(r).model_dump(mode="json") for r in new_records]},
        )
    return new_records

# --- Exam Endpoints ---

@router.post("/exams/", response_model=ExamSchema)
async def create_exam(
    *,
    db: AsyncSession = Depends(get_db),
    exam_in: ExamCreate,
    current_user: Any = Depends(deps.requires_admin)
) -> Any:
    """
    Create a new exam definition.
    """
    db_obj = Exam(**exam_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.get("/exams/", response_model=List[ExamSchema])
async def get_exams(
    db: AsyncSession = Depends(get_db),
    section_id: Optional[UUID] = None,
    current_user: Any = Depends(deps.get_current_user)
) -> Any:
    """
    List exams.
    """
    query = select(Exam)
    if section_id:
        query = query.where(Exam.section_id == section_id)
    result = await db.execute(query)
    return result.scalars().all()

# --- Marks Endpoints ---

@router.post("/marks/bulk", response_model=List[MarkSchema])
async def create_marks_bulk(
    *,
    db: AsyncSession = Depends(get_db),
    marks_in: MarkBulkCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: Any = Depends(deps.requires_admin),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    """
    Bulk record marks for an exam and subject.
    Auto-triggers AI insight generation for each student.
    """
    payload = marks_in.model_dump(mode="json")
    if idempotency_key:
        existing = await idempotency_service.check_existing(
            db,
            idempotency_key=idempotency_key,
            scope="performance.marks.bulk",
            request_payload=payload,
        )
        if existing:
            return existing["items"]

    new_records = []
    student_ids = set()
    for m in marks_in.marks:
        raw_status = m.mark_status.value if hasattr(m.mark_status, "value") else m.mark_status
        status_value = (raw_status or "present").strip().lower()
        if status_value not in VALID_MARK_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid mark_status '{m.mark_status}'. Use present/absent/exempt")

        if status_value in {"absent", "exempt"}:
            marks_obtained = 0.0
        else:
            if m.marks_obtained is None:
                raise HTTPException(status_code=400, detail="marks_obtained is required when mark_status is present")
            marks_obtained = m.marks_obtained
            if marks_obtained > m.max_marks:
                raise HTTPException(status_code=400, detail="marks_obtained cannot exceed max_marks")

        db_obj = Mark(
            exam_id=marks_in.exam_id,
            subject_id=marks_in.subject_id,
            student_id=m.student_id,
            marks_obtained=marks_obtained,
            max_marks=m.max_marks,
            mark_status=status_value,
            comments=m.comments
        )
        db.add(db_obj)
        new_records.append(db_obj)
        student_ids.add(m.student_id)
    
    await db.commit()
    for rec in new_records:
        await db.refresh(rec)

    # Queue AI generation to avoid blocking this request.
    await ai_insight_task_queue.enqueue_students(list(student_ids))

    # Low grade detection
    for rec in new_records:
        if rec.mark_status != "present":
            continue
        pct = (rec.marks_obtained / rec.max_marks) if rec.max_marks else 0.0
        if pct < 0.4:
            recipients = await notification_service.recipients_for_student(db, student_id=rec.student_id)
            if recipients:
                await notification_service.emit_event(
                    db,
                    event_type="low_grade_detected",
                    actor_id=current_user.id,
                    student_id=rec.student_id,
                    school_id=current_user.school_id,
                    payload_json={
                        "exam_id": str(rec.exam_id),
                        "subject_id": str(rec.subject_id),
                        "marks_obtained": rec.marks_obtained,
                        "max_marks": rec.max_marks,
                        "percentage": round(pct * 100, 2),
                    },
                    recipient_user_ids=recipients,
                )

    if idempotency_key:
        await idempotency_service.store_response(
            db,
            idempotency_key=idempotency_key,
            scope="performance.marks.bulk",
            request_payload=payload,
            response_payload={"items": [MarkSchema.model_validate(r).model_dump(mode="json") for r in new_records]},
        )

    return new_records

@router.get("/marks/", response_model=List[MarkSchema])
async def get_marks(
    db: AsyncSession = Depends(get_db),
    student_id: Optional[UUID] = None,
    exam_id: Optional[UUID] = None,
    subject_id: Optional[UUID] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user)
) -> Any:
    """
    Get marks with filters. Paginated.
    """
    query = select(Mark)
    filters = []
    allowed_student_ids = await _get_allowed_student_ids(db, current_user)

    if allowed_student_ids is not None:
        if student_id and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this student")
        if not student_id:
            if not allowed_student_ids:
                return []
            filters.append(Mark.student_id.in_(list(allowed_student_ids)))
    if student_id:
        filters.append(Mark.student_id == student_id)
    if exam_id:
        filters.append(Mark.exam_id == exam_id)
    if subject_id:
        filters.append(Mark.subject_id == subject_id)
    
    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(Mark.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/marks/enriched")
async def get_marks_enriched(
    db: AsyncSession = Depends(get_db),
    student_id: Optional[UUID] = None,
    exam_id: Optional[UUID] = None,
    subject_id: Optional[UUID] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    UI-friendly marks endpoint with joined student/subject/exam metadata. Paginated.
    """
    allowed_student_ids = await _get_allowed_student_ids(db, current_user)
    filters = []
    if allowed_student_ids is not None:
        if student_id and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this student")
        if not student_id:
            if not allowed_student_ids:
                return {"items": [], "total": 0, "page": page, "page_size": page_size}
            filters.append(Mark.student_id.in_(list(allowed_student_ids)))

    if student_id:
        filters.append(Mark.student_id == student_id)
    if exam_id:
        filters.append(Mark.exam_id == exam_id)
    if subject_id:
        filters.append(Mark.subject_id == subject_id)

    # Count query
    count_stmt = (
        select(func.count())
        .select_from(Mark)
        .join(Student, Student.id == Mark.student_id)
    )
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(
            Mark.id,
            Mark.student_id,
            Mark.exam_id,
            Mark.subject_id,
            Mark.marks_obtained,
            Mark.max_marks,
            Mark.mark_status,
            Mark.comments,
            Mark.created_at,
            Student.roll_number,
            User.full_name.label("student_name"),
            Exam.name.label("exam_name"),
            Exam.exam_date,
            Subject.name.label("subject_name"),
        )
        .join(Student, Student.id == Mark.student_id)
        .join(User, User.id == Student.user_id)
        .join(Exam, Exam.id == Mark.exam_id)
        .join(Subject, Subject.id == Mark.subject_id)
        .order_by(Mark.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(and_(*filters))

    rows = (await db.execute(stmt)).all()
    items = [
        {
            "id": str(row.id),
            "student_id": str(row.student_id),
            "student_name": row.student_name,
            "roll_number": row.roll_number,
            "exam_id": str(row.exam_id),
            "exam_name": row.exam_name,
            "exam_date": row.exam_date,
            "subject_id": str(row.subject_id),
            "subject_name": row.subject_name,
            "marks_obtained": row.marks_obtained,
            "max_marks": row.max_marks,
            "mark_status": row.mark_status,
            "percentage": round((row.marks_obtained / row.max_marks) * 100, 2) if row.max_marks else 0.0,
            "comments": row.comments,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/attendance/summary")
async def get_attendance_summary(
    db: AsyncSession = Depends(get_db),
    student_id: Optional[UUID] = None,
    section_id: Optional[UUID] = None,
    months: int = Query(default=6, ge=1, le=24),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Attendance summary endpoint for charts/cards.
    Uses DB-level aggregation instead of loading all rows into Python.
    """
    allowed_student_ids = await _get_allowed_student_ids(db, current_user)
    filters = []
    needs_student_join = False

    if section_id:
        filters.append(Student.section_id == section_id)
        needs_student_join = True
    if student_id:
        filters.append(Attendance.student_id == student_id)

    if allowed_student_ids is not None:
        if student_id and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="Not authorized for this student")
        if not student_id:
            if not allowed_student_ids:
                return {"overall": {}, "monthly": []}
            filters.append(Attendance.student_id.in_(list(allowed_student_ids)))

    # --- FIX: DB-level aggregation instead of Python-side counting ---
    overall_stmt = select(
        func.count().label("total"),
        func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present"),
        func.sum(case((Attendance.status == "Absent", 1), else_=0)).label("absent"),
        func.sum(case((Attendance.status == "Late", 1), else_=0)).label("late"),
    ).select_from(Attendance)
    if needs_student_join:
        overall_stmt = overall_stmt.join(Student, Student.id == Attendance.student_id)
    if filters:
        overall_stmt = overall_stmt.where(and_(*filters))

    overall_row = (await db.execute(overall_stmt)).one()
    total = int(overall_row.total or 0)
    present = int(overall_row.present or 0)
    absent = int(overall_row.absent or 0)
    late = int(overall_row.late or 0)

    monthly_stmt = (
        select(
            func.date_trunc("month", Attendance.date).label("month"),
            func.count().label("total_days"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present_days"),
            func.sum(case((Attendance.status == "Absent", 1), else_=0)).label("absent_days"),
            func.sum(case((Attendance.status == "Late", 1), else_=0)).label("late_days"),
        )
        .group_by(func.date_trunc("month", Attendance.date))
        .order_by(func.date_trunc("month", Attendance.date).desc())
        .limit(months)
    )
    if needs_student_join:
        monthly_stmt = monthly_stmt.select_from(Attendance).join(Student, Student.id == Attendance.student_id)
    if filters:
        monthly_stmt = monthly_stmt.where(and_(*filters))

    monthly_rows = (await db.execute(monthly_stmt)).all()
    monthly = [
        {
            "month": str(row.month.date()),
            "total_days": int(row.total_days or 0),
            "present_days": int(row.present_days or 0),
            "absent_days": int(row.absent_days or 0),
            "late_days": int(row.late_days or 0),
            "attendance_percentage": round((int(row.present_days or 0) / int(row.total_days or 1)) * 100, 2)
            if int(row.total_days or 0)
            else 0.0,
        }
        for row in monthly_rows
    ]

    return {
        "overall": {
            "total_days": total,
            "present_days": present,
            "absent_days": absent,
            "late_days": late,
            "attendance_percentage": round((present / total) * 100, 2) if total else 0.0,
        },
        "monthly": monthly,
    }

# --- Learning Path & Weekly Tasks ---

class LearningTaskCreate(BaseModel):
    subject_id: UUID
    task_name: str
    description: Optional[str] = None
    due_date: date

@router.post("/learning-path", response_model=dict)
async def create_learning_task(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.TEACHER)),
    task_in: LearningTaskCreate,
    student_id: UUID
) -> Any:
    """Assign a learning task to a student (Teacher only)."""
    db_obj = LearningTask(**task_in.model_dump(), student_id=student_id)
    db.add(db_obj)
    await db.commit()
    return {"message": "Task created"}

@router.get("/learning-path", response_model=List[dict])
async def get_my_learning_path(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
) -> Any:
    """Get the weekly path tasks for the current student."""
    student_res = await db.execute(select(Student.id).where(Student.user_id == current_user.id))
    student_id = student_res.scalar_one_or_none()
    
    query = select(LearningTask).where(LearningTask.student_id == student_id).order_by(LearningTask.due_date.asc())
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    output = []
    for t in tasks:
        subj = await db.get(Subject, t.subject_id)
        output.append({
            "id": t.id,
            "task_name": t.task_name,
            "description": t.description,
            "due_date": t.due_date,
            "is_done": t.is_done,
            "subject_name": subj.name if subj else "General"
        })
    return output

@router.patch("/learning-path/{task_id}")
async def toggle_learning_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
) -> Any:
    """Toggle a task as done/undone."""
    task = await db.get(LearningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.is_done = not task.is_done
    await db.commit()
    return {"is_done": task.is_done}

# --- Specialized Analytics ---

@router.get("/exams/upcoming", response_model=List[dict])
async def get_upcoming_exams(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Get exams scheduled for the future."""
    today = date.today()
    query = select(Exam).where(Exam.exam_date >= today).order_by(Exam.exam_date.asc()).limit(5)
    result = await db.execute(query)
    return [
        {"id": e.id, "name": e.name, "exam_date": e.exam_date, "section_id": e.section_id}
        for e in result.scalars().all()
    ]

@router.get("/gradebook/summary")
async def get_gradebook_summary(
    db: AsyncSession = Depends(get_db),
    student_id: Optional[UUID] = None,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Provides a chart-ready response of performance averages over time."""
    allowed_ids = await _get_allowed_student_ids(db, current_user)
    if allowed_ids is not None and student_id and student_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    target_id = student_id or (list(allowed_ids)[0] if allowed_ids else None)
    if not target_id:
        return {"trends": []}
        
    # Group by Exam/Date
    stmt = (
        select(Exam.name, Exam.exam_date, func.avg(Mark.marks_obtained / Mark.max_marks * 100))
        .join(Mark, Mark.exam_id == Exam.id)
        .where(Mark.student_id == target_id, Mark.mark_status == "present")
        .group_by(Exam.name, Exam.exam_date)
        .order_by(Exam.exam_date.asc())
    )
    rows = (await db.execute(stmt)).all()
    
    return {
        "trends": [
            {"exam": r[0], "date": r[1], "score_pct": round(float(r[2]), 2)}
            for r in rows
        ]
    }


@router.get("/matrix")
async def get_gradebook_matrix(
    *,
    db: AsyncSession = Depends(get_db),
    exam_id: UUID,
    subject_id: UUID,
    section_id: UUID,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Fetch a list of students in a section and their current marks for a specific exam/subject.
    Used for the grid-based grade entry in the frontend.
    """
    # 1. Get all students in the section
    students_query = select(Student, User.full_name).join(User, Student.user_id == User.id).where(Student.section_id == section_id).order_by(Student.roll_number.asc())
    students_res = await db.execute(students_query)
    students_rows = students_res.all()
    
    # 2. Get existing marks for this exam/subject
    marks_query = select(Mark).where(Mark.exam_id == exam_id, Mark.subject_id == subject_id)
    marks_res = await db.execute(marks_query)
    existing_marks = {m.student_id: m for m in marks_res.scalars().all()}
    
    matrix = []
    for student, full_name in students_rows:
        mark = existing_marks.get(student.id)
        matrix.append({
            "student_id": str(student.id),
            "student_name": full_name,
            "roll_number": student.roll_number,
            "marks_obtained": mark.marks_obtained if mark else None,
            "max_marks": mark.max_marks if mark else 100.0,
            "mark_status": mark.mark_status if mark else "present",
            "comments": mark.comments if mark else None
        })
        
    return matrix


class MatrixSaveItem(BaseModel):
    student_id: UUID
    marks_obtained: float
    max_marks: float = 100.0
    mark_status: str = "present"
    comments: Optional[str] = None


class MatrixSaveRequest(BaseModel):
    exam_id: UUID
    subject_id: UUID
    marks: List[MatrixSaveItem]


@router.post("/matrix/save")
async def save_gradebook_matrix(
    *,
    db: AsyncSession = Depends(get_db),
    matrix_in: MatrixSaveRequest,
    current_user: User = Depends(deps.requires_role(UserRole.TEACHER)),
) -> Any:
    """
    Bulk update marks for a specific exam and subject.
    """
    student_ids = []
    for item in matrix_in.marks:
        # Check if mark exists
        existing_stmt = select(Mark).where(
            Mark.exam_id == matrix_in.exam_id,
            Mark.subject_id == matrix_in.subject_id,
            Mark.student_id == item.student_id
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        
        if existing:
            existing.marks_obtained = item.marks_obtained
            existing.max_marks = item.max_marks
            existing.mark_status = item.mark_status
            existing.comments = item.comments
        else:
            new_mark = Mark(
                exam_id=matrix_in.exam_id,
                subject_id=matrix_in.subject_id,
                student_id=item.student_id,
                marks_obtained=item.marks_obtained,
                max_marks=item.max_marks,
                mark_status=item.mark_status,
                comments=item.comments
            )
            db.add(new_mark)
        student_ids.append(item.student_id)
        
    await db.commit()
    
    # Trigger AI insights for all updated students
    await ai_insight_task_queue.enqueue_students(student_ids)
    
    return {"message": f"Successfully updated marks for {len(student_ids)} students"}
