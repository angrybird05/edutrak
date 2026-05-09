from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.api import deps
from app.models.academic import Class, Section, Subject
from app.models.performance import AIInsight, Attendance, Mark, ReportCard
from app.models.user import User

router = APIRouter()


@router.get("/")
async def read_students(
    db: AsyncSession = Depends(deps.get_db),
    page: int = 1,
    page_size: int = 20,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve students (scoped to user's school) with secure pagination.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    count_stmt = select(func.count()).select_from(models.student.Student)
    if current_user.school_id:
        count_stmt = count_stmt.where(models.student.Student.school_id == current_user.school_id)
    total = (await db.execute(count_stmt)).scalar_one_or_none() or 0

    query = (
        select(models.student.Student)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if current_user.school_id:
        query = query.where(models.student.Student.school_id == current_user.school_id)
        
    result = await db.execute(query.options(selectinload(models.student.Student.user)))
    students = result.scalars().all()
    
    items = [schemas.student.Student.model_validate(student).model_dump(mode="json") for student in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/query")
async def query_students(
    db: AsyncSession = Depends(deps.get_db),
    search: Optional[str] = None,
    class_id: Optional[UUID] = None,
    section_id: Optional[UUID] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Search/filter students with paginated response.
    Returns: {items, total, page, page_size}
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    filters = []
    if current_user.school_id:
        filters.append(models.student.Student.school_id == current_user.school_id)
    if class_id:
        filters.append(models.student.Student.class_id == class_id)
    if section_id:
        filters.append(models.student.Student.section_id == section_id)
    if search:
        term = f"%{search.strip()}%"
        query_user_ids = select(User.id).where(or_(User.full_name.ilike(term), User.phone.ilike(term)))
        filters.append(
            or_(
                models.student.Student.admission_number.ilike(term),
                models.student.Student.roll_number.ilike(term),
                models.student.Student.user_id.in_(query_user_ids),
            )
        )

    count_stmt = select(func.count()).select_from(models.student.Student)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(models.student.Student)
        .options(selectinload(models.student.Student.user))
        .order_by(models.student.Student.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    result = await db.execute(stmt)
    students = result.scalars().all()

    items = [schemas.student.Student.model_validate(student).model_dump(mode="json") for student in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/", response_model=schemas.student.StudentCreateResponse)
async def create_student(
    *,
    db: AsyncSession = Depends(deps.get_db),
    student_in: schemas.student.StudentCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new student.
    """
    # Check if student with admission number already exists
    # (Admission number is unique in model)
    student = await crud.student.create_with_user(db, obj_in=student_in)

    return schemas.student.StudentCreateResponse.model_validate(student)


@router.get("/{id}/profile-summary")
async def read_student_profile_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Composite student profile for admin/student-detail UI.
    Includes identity, class/section, term performance, subject metrics, attendance, AI summary, latest report.
    """
    student_result = await db.execute(
        select(models.student.Student)
        .where(models.student.Student.id == id)
        .options(selectinload(models.student.Student.user))
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    class_name = (
        await db.execute(select(Class.name).where(Class.id == student.class_id))
    ).scalar_one_or_none()
    section_name = (
        await db.execute(select(Section.name).where(Section.id == student.section_id))
    ).scalar_one_or_none()

    subject_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained), func.count(Mark.id))
        .join(Mark, Mark.subject_id == Subject.id)
        .where(Mark.student_id == id, Mark.mark_status == "present")
        .group_by(Subject.name)
    )
    subject_performance = [
        {"subject": row[0], "average_marks": round(float(row[1]), 2), "records_count": row[2]}
        for row in subject_rows.all()
        if row[1] is not None
    ]

    term_rows = await db.execute(
        select(
            ReportCard.term_name,
            func.avg(Mark.marks_obtained).label("avg_marks"),
            func.max(ReportCard.generated_at).label("generated_at"),
        )
        .join(Mark, Mark.student_id == ReportCard.student_id)
        .where(ReportCard.student_id == id, Mark.mark_status == "present")
        .group_by(ReportCard.term_name)
        .order_by(func.max(ReportCard.generated_at).desc())
    )
    term_performance = [
        {
            "term_name": row.term_name,
            "average_marks": round(float(row.avg_marks), 2) if row.avg_marks is not None else None,
            "generated_at": row.generated_at,
        }
        for row in term_rows
    ]

    total_days = (
        await db.execute(select(func.count()).select_from(Attendance).where(Attendance.student_id == id))
    ).scalar_one()
    present_days = (
        await db.execute(
            select(func.count()).select_from(Attendance).where(
                Attendance.student_id == id, Attendance.status == "Present"
            )
        )
    ).scalar_one()

    insight = (await db.execute(select(AIInsight).where(AIInsight.student_id == id))).scalar_one_or_none()
    latest_report = (
        await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id == id)
            .order_by(ReportCard.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "profile": {
            "student_id": str(student.id),
            "full_name": student.user.full_name if student.user else None,
            "phone": student.user.phone if student.user else None,
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "class": class_name,
            "section": section_name,
        },
        "term_performance": term_performance,
        "subject_performance": subject_performance,
        "attendance": {
            "present_days": present_days,
            "total_days": total_days,
            "attendance_percentage": round((present_days / total_days) * 100, 2) if total_days else 0.0,
        },
        "ai_summary": {
            "insight_text": insight.insight_text if insight else None,
            "recommendations": insight.recommendations if insight else None,
            "last_updated": insight.last_updated if insight else None,
        },
        "latest_report": {
            "id": str(latest_report.id),
            "term_name": latest_report.term_name,
            "generated_at": latest_report.generated_at,
            "pdf_url": latest_report.pdf_url,
        }
        if latest_report
        else None,
    }


@router.get("/{id}", response_model=schemas.student.Student)
async def read_student(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get student by ID (scoped to user's school).
    """
    student = await crud.student.get(db, id=id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user.school_id and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    return student


@router.get("/school/{school_id}")
async def read_students_by_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    school_id: UUID,
    page: int = 1,
    page_size: int = 20,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all students in a school with pagination.
    """
    if current_user.school_id and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    limit = page_size
    skip = (page - 1) * page_size

    total = (await db.execute(
        select(func.count()).select_from(models.student.Student).where(models.student.Student.school_id == school_id)
    )).scalar_one_or_none() or 0
    
    result = await db.execute(
        select(models.student.Student)
        .where(models.student.Student.school_id == school_id)
        .options(selectinload(models.student.Student.user))
        .offset(skip).limit(limit)
    )
    students = result.scalars().all()
    
    items = [schemas.student.Student.model_validate(student).model_dump(mode="json") for student in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/class/{class_id}")
async def read_students_by_class(
    *,
    db: AsyncSession = Depends(deps.get_db),
    class_id: UUID,
    page: int = 1,
    page_size: int = 20,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all students in a class with pagination.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    limit = page_size
    skip = (page - 1) * page_size

    total = (await db.execute(
        select(func.count()).select_from(models.student.Student).where(models.student.Student.class_id == class_id)
    )).scalar_one_or_none() or 0
    
    result = await db.execute(
        select(models.student.Student)
        .where(models.student.Student.class_id == class_id)
        .options(selectinload(models.student.Student.user))
        .offset(skip).limit(limit)
    )
    students = result.scalars().all()
    
    items = [schemas.student.Student.model_validate(student).model_dump(mode="json") for student in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{student_id}/link-parent/{parent_id}", response_model=dict)
async def link_student_parent(
    *,
    db: AsyncSession = Depends(deps.get_db),
    student_id: UUID,
    parent_id: UUID,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Link a student to a parent.
    """
    await crud.student.link_parent(db, student_id=student_id, parent_id=parent_id)
    return {"message": "Parent linked successfully"}
