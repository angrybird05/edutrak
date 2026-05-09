"""
Assessment module endpoints — Exams, marks, attendance, bulk uploads.

Migrated from performance.py and bulk.py endpoints.
"""
from datetime import date
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user, requires_roles
from app.modules.auth.models import User, UserRole
from app.modules.assessment.models import Exam, Mark, Attendance, Homework
from app.modules.assessment.schemas import (
    AttendanceSectionOption,
    AttendanceSheetResponse,
    AttendanceSheetUpsertRequest,
    GradebookMatrixResponse,
    GradebookMatrixUpsertRequest,
    GradebookSectionContextResponse,
)
from app.modules.assessment.service import get_assessment_service
from app.modules.identity.models import Student
from app.modules.academic.models import Class, Section, Subject

router = APIRouter()


async def _get_authorized_section(
    db: AsyncSession,
    *,
    current_user: User,
    section_id: UUID,
) -> tuple[Section, Class]:
    result = await db.execute(
        select(Section, Class)
        .join(Class, Class.id == Section.class_id)
        .where(Section.id == section_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")

    section, found_class = row
    if current_user.school_id and found_class.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this section")

    if current_user.role == UserRole.TEACHER:
        teacher_access = await db.execute(
            select(Section.id)
            .join(Section.teachers)
            .where(Section.id == section_id, User.id == current_user.id)
        )
        if teacher_access.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Teacher is not assigned to this section")

    return section, found_class


async def _build_attendance_sheet(
    db: AsyncSession,
    *,
    section: Section,
    found_class: Class,
    attendance_date: date,
) -> dict[str, Any]:
    student_result = await db.execute(
        select(
            Student.id,
            Student.admission_number,
            Student.roll_number,
            User.full_name,
        )
        .join(User, User.id == Student.user_id)
        .where(Student.section_id == section.id)
        .order_by(Student.roll_number.asc().nulls_last(), Student.admission_number.asc())
    )
    students = student_result.all()

    student_ids = [student.id for student in students]
    attendance_map: dict[UUID, str] = {}
    if student_ids:
        attendance_rows = await db.execute(
            select(Attendance.student_id, Attendance.status)
            .where(Attendance.student_id.in_(student_ids), Attendance.date == attendance_date)
        )
        attendance_map = {row.student_id: row.status for row in attendance_rows.all()}

    student_items = [
        {
            "student_id": student.id,
            "full_name": student.full_name,
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "status": attendance_map.get(student.id),
        }
        for student in students
    ]

    totals = {
        "total": len(student_items),
        "marked": sum(1 for item in student_items if item["status"] is not None),
        "present": sum(1 for item in student_items if item["status"] == "Present"),
        "absent": sum(1 for item in student_items if item["status"] == "Absent"),
        "late": sum(1 for item in student_items if item["status"] == "Late"),
    }

    return {
        "date": attendance_date,
        "class_id": found_class.id,
        "class_name": found_class.name,
        "section_id": section.id,
        "section_name": section.name,
        "students": student_items,
        "totals": totals,
    }


async def _get_authorized_gradebook_subject(
    db: AsyncSession,
    *,
    current_user: User,
    section_id: UUID,
    subject_id: UUID,
) -> Subject:
    stmt = (
        select(Subject)
        .join(Subject.sections)
        .where(Section.id == section_id, Subject.id == subject_id)
    )
    if current_user.role == UserRole.TEACHER:
        stmt = stmt.join(Subject.teachers).where(User.id == current_user.id)

    subject = (await db.execute(stmt)).scalar_one_or_none()
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found for this section")
    return subject


async def _get_authorized_exam(
    db: AsyncSession,
    *,
    section_id: UUID,
    exam_id: UUID,
) -> Exam:
    exam = (
        await db.execute(
            select(Exam).where(Exam.id == exam_id, Exam.section_id == section_id)
        )
    ).scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found for this section")
    return exam


async def _build_gradebook_matrix(
    db: AsyncSession,
    *,
    section: Section,
    found_class: Class,
    exam_id: UUID,
    subject_id: UUID,
) -> dict[str, Any]:
    student_rows = await db.execute(
        select(
            Student.id,
            Student.admission_number,
            Student.roll_number,
            User.full_name,
        )
        .join(User, User.id == Student.user_id)
        .where(Student.section_id == section.id)
        .order_by(Student.roll_number.asc().nulls_last(), Student.admission_number.asc())
    )
    students = student_rows.all()
    student_ids = [student.id for student in students]

    mark_map: dict[UUID, Mark] = {}
    if student_ids:
        mark_rows = await db.execute(
            select(Mark).where(
                Mark.exam_id == exam_id,
                Mark.subject_id == subject_id,
                Mark.student_id.in_(student_ids),
            )
        )
        mark_map = {mark.student_id: mark for mark in mark_rows.scalars().all()}

    items = []
    percentages: list[float] = []
    for student in students:
        mark = mark_map.get(student.id)
        percentage = None
        if mark and mark.max_marks:
            percentage = round((mark.marks_obtained / mark.max_marks) * 100, 1)
            percentages.append(percentage)

        items.append(
            {
                "student_id": student.id,
                "full_name": student.full_name,
                "admission_number": student.admission_number,
                "roll_number": student.roll_number,
                "marks_obtained": mark.marks_obtained if mark else None,
                "max_marks": mark.max_marks if mark else 100.0,
                "mark_status": mark.mark_status if mark else "present",
                "comments": mark.comments if mark else None,
                "percentage": percentage,
            }
        )

    return {
        "class_id": found_class.id,
        "class_name": found_class.name,
        "section_id": section.id,
        "section_name": section.name,
        "subject_id": subject_id,
        "exam_id": exam_id,
        "students": items,
        "summary": {
            "total_students": len(items),
            "entered_marks": len(percentages),
            "average_percentage": round(sum(percentages) / len(percentages), 1) if percentages else 0.0,
            "highest_percentage": max(percentages) if percentages else 0.0,
            "lowest_percentage": min(percentages) if percentages else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Exams
# ---------------------------------------------------------------------------
@router.post("/exams")
async def create_exam(
    *,
    db: AsyncSession = Depends(get_db),
    name: str,
    section_id: UUID,
    exam_date: Optional[date] = None,
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    await _get_authorized_section(db, current_user=current_user, section_id=section_id)
    exam = Exam(name=name, section_id=section_id, exam_date=exam_date)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return {"id": str(exam.id), "name": exam.name, "section_id": str(exam.section_id)}


@router.get("/exams/{section_id}")
async def list_exams(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(Exam).where(Exam.section_id == section_id).order_by(Exam.exam_date.desc())
    )
    exams = result.scalars().all()
    return [{"id": str(e.id), "name": e.name, "exam_date": str(e.exam_date) if e.exam_date else None} for e in exams]


@router.get("/gradebook/sections/{section_id}", response_model=GradebookSectionContextResponse)
async def get_gradebook_section_context(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    section, found_class = await _get_authorized_section(db, current_user=current_user, section_id=section_id)

    subjects_stmt = (
        select(Subject.id, Subject.name, Subject.code)
        .join(Subject.sections)
        .where(Section.id == section_id)
        .order_by(Subject.name.asc())
    )
    if current_user.role == UserRole.TEACHER:
        subjects_stmt = subjects_stmt.join(Subject.teachers).where(User.id == current_user.id)

    exams_stmt = (
        select(Exam.id, Exam.name, Exam.exam_date)
        .where(Exam.section_id == section_id)
        .order_by(Exam.exam_date.desc().nulls_last(), Exam.name.asc())
    )

    subject_rows = (await db.execute(subjects_stmt)).all()
    exam_rows = (await db.execute(exams_stmt)).all()

    return {
        "class_id": found_class.id,
        "class_name": found_class.name,
        "section_id": section.id,
        "section_name": section.name,
        "subjects": [
            {"id": row.id, "name": row.name, "code": row.code}
            for row in subject_rows
        ],
        "exams": [
            {"id": row.id, "name": row.name, "exam_date": row.exam_date}
            for row in exam_rows
        ],
    }


@router.get("/gradebook/sections/{section_id}/matrix", response_model=GradebookMatrixResponse)
async def get_gradebook_matrix(
    *,
    section_id: UUID,
    exam_id: UUID,
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    section, found_class = await _get_authorized_section(db, current_user=current_user, section_id=section_id)
    await _get_authorized_exam(db, section_id=section_id, exam_id=exam_id)
    await _get_authorized_gradebook_subject(
        db,
        current_user=current_user,
        section_id=section_id,
        subject_id=subject_id,
    )
    return await _build_gradebook_matrix(
        db,
        section=section,
        found_class=found_class,
        exam_id=exam_id,
        subject_id=subject_id,
    )


@router.post("/gradebook/sections/{section_id}/matrix", response_model=GradebookMatrixResponse)
async def upsert_gradebook_matrix(
    *,
    section_id: UUID,
    body: GradebookMatrixUpsertRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    from app.core.event_bus import event_bus

    section, found_class = await _get_authorized_section(db, current_user=current_user, section_id=section_id)
    await _get_authorized_exam(db, section_id=section_id, exam_id=body.exam_id)
    await _get_authorized_gradebook_subject(
        db,
        current_user=current_user,
        section_id=section_id,
        subject_id=body.subject_id,
    )

    student_rows = await db.execute(select(Student.id).where(Student.section_id == section_id))
    valid_student_ids = {student_id for student_id in student_rows.scalars().all()}
    invalid_student_ids = [str(record.student_id) for record in body.records if record.student_id not in valid_student_ids]
    if invalid_student_ids:
        raise HTTPException(
            status_code=400,
            detail=f"One or more students do not belong to this section: {', '.join(invalid_student_ids)}",
        )

    payload_student_ids = [record.student_id for record in body.records]
    existing_map: dict[UUID, Mark] = {}
    if payload_student_ids:
        existing_rows = await db.execute(
            select(Mark).where(
                Mark.exam_id == body.exam_id,
                Mark.subject_id == body.subject_id,
                Mark.student_id.in_(payload_student_ids),
            )
        )
        existing_map = {record.student_id: record for record in existing_rows.scalars().all()}

    changed_student_ids: list[str] = []
    for record in body.records:
        existing = existing_map.get(record.student_id)
        if existing:
            existing.marks_obtained = record.marks_obtained
            existing.max_marks = record.max_marks
            existing.mark_status = record.mark_status
            existing.comments = record.comments
            db.add(existing)
        else:
            db.add(
                Mark(
                    exam_id=body.exam_id,
                    student_id=record.student_id,
                    subject_id=body.subject_id,
                    marks_obtained=record.marks_obtained,
                    max_marks=record.max_marks,
                    mark_status=record.mark_status,
                    comments=record.comments,
                )
            )
        changed_student_ids.append(str(record.student_id))

    await db.commit()

    if changed_student_ids:
        await event_bus.emit(
            "assessment.marks_recorded",
            {
                "student_ids": changed_student_ids,
                "exam_id": str(body.exam_id),
                "actor_id": str(current_user.id),
            },
        )

    return await _build_gradebook_matrix(
        db,
        section=section,
        found_class=found_class,
        exam_id=body.exam_id,
        subject_id=body.subject_id,
    )


# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------
@router.get("/marks/{student_id}")
async def get_student_marks(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    from app.modules.academic.models import Subject
    result = await db.execute(
        select(Mark, Subject.name.label("subject_name"), Exam.name.label("exam_name"))
        .join(Subject, Mark.subject_id == Subject.id)
        .join(Exam, Mark.exam_id == Exam.id)
        .where(Mark.student_id == student_id)
        .order_by(Exam.exam_date.desc())
    )
    rows = result.all()
    return [
        {
            "mark_id": str(mark.id),
            "subject": subject_name,
            "exam": exam_name,
            "marks_obtained": mark.marks_obtained,
            "max_marks": mark.max_marks,
            "percentage": round((mark.marks_obtained / mark.max_marks) * 100, 1) if mark.max_marks else 0,
            "status": mark.mark_status,
            "comments": mark.comments,
        }
        for mark, subject_name, exam_name in rows
    ]


@router.post("/marks/single")
async def record_single_mark(
    *,
    db: AsyncSession = Depends(get_db),
    exam_id: UUID,
    student_id: UUID,
    subject_id: UUID,
    marks_obtained: float,
    max_marks: float = 100.0,
    mark_status: str = "present",
    comments: Optional[str] = None,
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    from app.core.event_bus import event_bus
    mark = Mark(
        exam_id=exam_id, student_id=student_id, subject_id=subject_id,
        marks_obtained=marks_obtained, max_marks=max_marks,
        mark_status=mark_status, comments=comments,
    )
    db.add(mark)
    await db.commit()
    await db.refresh(mark)

    await event_bus.emit("assessment.marks_recorded", {
        "student_ids": [str(student_id)],
        "exam_id": str(exam_id),
        "actor_id": str(current_user.id),
    })

    return {"id": str(mark.id), "status": "recorded"}


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
@router.get("/attendance/sections", response_model=list[AttendanceSectionOption])
async def list_attendance_sections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    stmt = (
        select(
            Section.id,
            Section.name,
            Class.id.label("class_id"),
            Class.name.label("class_name"),
        )
        .join(Class, Class.id == Section.class_id)
        .order_by(Class.class_number, Class.name, Section.name)
    )

    if current_user.role == UserRole.ADMIN:
        if not current_user.school_id:
            return []
        stmt = stmt.where(Class.school_id == current_user.school_id)
    else:
        stmt = stmt.join(Section.teachers).where(User.id == current_user.id)

    result = await db.execute(stmt)
    return [
        {
            "id": row.id,
            "name": row.name,
            "class_id": row.class_id,
            "class_name": row.class_name,
        }
        for row in result.all()
    ]


@router.get("/attendance/{student_id}")
async def get_student_attendance(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    total = (await db.execute(
        select(func.count()).select_from(Attendance).where(Attendance.student_id == student_id)
    )).scalar_one()
    present = (await db.execute(
        select(func.count()).select_from(Attendance).where(
            and_(Attendance.student_id == student_id, Attendance.status.in_(["Present", "Late"]))
        )
    )).scalar_one()

    return {
        "student_id": str(student_id),
        "total_days": total,
        "present_days": present,
        "attendance_rate": round((present / total) * 100, 1) if total else 0.0,
    }


@router.get("/attendance/sections/{section_id}", response_model=AttendanceSheetResponse)
async def get_section_attendance_sheet(
    section_id: UUID,
    attendance_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    section, found_class = await _get_authorized_section(db, current_user=current_user, section_id=section_id)
    return await _build_attendance_sheet(
        db,
        section=section,
        found_class=found_class,
        attendance_date=attendance_date,
    )


@router.post("/attendance/sections/{section_id}", response_model=AttendanceSheetResponse)
async def upsert_section_attendance_sheet(
    *,
    section_id: UUID,
    body: AttendanceSheetUpsertRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    from app.core.event_bus import event_bus

    section, found_class = await _get_authorized_section(db, current_user=current_user, section_id=section_id)

    student_result = await db.execute(
        select(Student.id).where(Student.section_id == section_id)
    )
    valid_student_ids = {student_id for student_id in student_result.scalars().all()}

    payload_student_ids = [record.student_id for record in body.records]
    invalid_student_ids = [str(student_id) for student_id in payload_student_ids if student_id not in valid_student_ids]
    if invalid_student_ids:
        raise HTTPException(
            status_code=400,
            detail=f"One or more students do not belong to this section: {', '.join(invalid_student_ids)}",
        )

    existing_rows = await db.execute(
        select(Attendance).where(
            Attendance.student_id.in_(payload_student_ids),
            Attendance.date == body.date,
        )
    )
    existing_map = {record.student_id: record for record in existing_rows.scalars().all()}

    changed_student_ids: list[str] = []
    for record in body.records:
        existing = existing_map.get(record.student_id)
        if existing:
            existing.status = record.status.value
            db.add(existing)
        else:
            db.add(Attendance(student_id=record.student_id, date=body.date, status=record.status.value))
        changed_student_ids.append(str(record.student_id))

    await db.commit()

    if changed_student_ids:
        await event_bus.emit("assessment.attendance_recorded", {
            "student_ids": changed_student_ids,
            "date": str(body.date),
            "actor_id": str(current_user.id),
        })

    return await _build_attendance_sheet(
        db,
        section=section,
        found_class=found_class,
        attendance_date=body.date,
    )


@router.post("/attendance/single")
async def record_single_attendance(
    *,
    db: AsyncSession = Depends(get_db),
    student_id: UUID,
    attendance_date: date,
    status: str,
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    from app.core.event_bus import event_bus
    record = Attendance(student_id=student_id, date=attendance_date, status=status)
    db.add(record)
    await db.commit()

    await event_bus.emit("assessment.attendance_recorded", {
        "student_ids": [str(student_id)],
        "date": str(attendance_date),
        "actor_id": str(current_user.id),
    })

    return {"status": "recorded"}


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------
@router.post("/bulk/marks")
async def bulk_upload_marks(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    exam_id: UUID = Query(...),
    subject_id: UUID = Query(...),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    service = get_assessment_service(db)
    records = await service.record_marks_bulk(file, exam_id, subject_id, actor_id=current_user.id)
    return {"uploaded": len(records), "status": "success"}


@router.post("/bulk/attendance")
async def bulk_upload_attendance(
    *,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    attendance_date: date = Query(...),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    service = get_assessment_service(db)
    records = await service.record_attendance_bulk(file, attendance_date, actor_id=current_user.id)
    return {"uploaded": len(records), "status": "success"}


@router.post("/sections/{section_id}/exams/{exam_id}/complete")
async def mark_exam_complete(
    *,
    section_id: UUID,
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """Mark an exam as completed to trigger automated report card generation."""
    from app.core.event_bus import event_bus
    
    exam = await _get_authorized_exam(db, section_id=section_id, exam_id=exam_id)
    if exam.is_completed:
        return {"status": "already completed"}

    exam.is_completed = True
    db.add(exam)
    await db.commit()

    await event_bus.emit("assessment.exam_completed", {
        "exam_id": str(exam.id),
        "section_id": str(exam.section_id),
        "term_name": exam.name,
    })

    return {"status": "completed"}

