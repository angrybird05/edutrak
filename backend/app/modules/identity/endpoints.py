"""
Identity module endpoints — Users, Students, Parents, Admin.

Migrated from app/api/api_v1/endpoints/students.py, user.py, parents.py, admin.py.
"""
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user, requires_admin, requires_roles
from app.modules.auth.models import User, UserRole
from app.modules.identity.models import Student
from app.modules.identity.schemas import (
    StudentCreate, StudentCreateResponse, Student as StudentSchema,
    StudentListResponse,
    ParentChildSummary,
    ParentLinkByCodeRequest,
    UserProfile, UserProfileUpdate,
    Teacher as TeacherSchema,
    TeacherCreate,
    TeacherCredentialsUpdate,
    TeacherListResponse,
    TeacherUpdate,
)
from app.modules.identity.service import get_identity_service
from app.modules.academic.models import Class, Section
from app.modules.assessment.models import Mark, Attendance
from app.modules.analytics.models import AIInsight, ReportCard
from app.modules.analytics.insights_v2.models import AIInsightV2

router = APIRouter()


def _normalize_recommendations_from_v2(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    ordered_keys = ("improvement_suggestions", "study_plan", "strengths", "weaknesses", "recommendations")
    items: list[str] = []
    for key in ordered_keys:
        value = payload.get(key)
        if isinstance(value, list):
            items.extend([str(entry).strip() for entry in value if str(entry).strip()])
    return items


# ---------------------------------------------------------------------------
# User profile endpoints
# ---------------------------------------------------------------------------
@router.get("/me", response_model=UserProfile)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user's profile."""
    return current_user


@router.patch("/me", response_model=UserProfile)
async def update_my_profile(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    profile_in: UserProfileUpdate,
) -> Any:
    """Update current user's profile."""
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name
    if profile_in.language_pref is not None:
        current_user.language_pref = profile_in.language_pref
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# Teacher endpoints
# ---------------------------------------------------------------------------
@router.get("/teachers", response_model=TeacherListResponse)
async def read_teachers(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Retrieve teachers for the current admin's school."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    filters = [User.role == UserRole.TEACHER, User.school_id == current_user.school_id]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                User.full_name.ilike(term),
                User.username.ilike(term),
                User.phone.ilike(term),
            )
        )

    count_stmt = select(func.count()).select_from(User).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    teachers = result.scalars().all()
    return {
        "items": [TeacherSchema.model_validate(teacher) for teacher in teachers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/teachers/{teacher_id}", response_model=TeacherSchema)
async def read_teacher(
    *,
    db: AsyncSession = Depends(get_db),
    teacher_id: UUID,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Get a teacher by ID for the current admin's school."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    result = await db.execute(
        select(User).where(
            User.id == teacher_id,
            User.role == UserRole.TEACHER,
            User.school_id == current_user.school_id,
        )
    )
    teacher = result.scalars().first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher


@router.post("/teachers", response_model=TeacherSchema, status_code=201)
async def create_teacher(
    *,
    db: AsyncSession = Depends(get_db),
    teacher_in: TeacherCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Create a teacher account within the admin's school."""
    identity_service = get_identity_service(db)
    teacher = await identity_service.create_teacher(current_user, teacher_in)
    return teacher


@router.patch("/teachers/{teacher_id}", response_model=TeacherSchema)
async def update_teacher(
    *,
    db: AsyncSession = Depends(get_db),
    teacher_id: UUID,
    teacher_in: TeacherUpdate,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Update teacher profile fields."""
    identity_service = get_identity_service(db)
    teacher = await identity_service.update_teacher(current_user, teacher_id, teacher_in)
    return teacher


@router.patch("/teachers/{teacher_id}/credentials", response_model=TeacherSchema)
async def update_teacher_credentials(
    *,
    db: AsyncSession = Depends(get_db),
    teacher_id: UUID,
    credentials_in: TeacherCredentialsUpdate,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Update teacher username and/or password."""
    identity_service = get_identity_service(db)
    teacher = await identity_service.update_teacher_credentials(current_user, teacher_id, credentials_in)
    return teacher


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------
@router.get("/students", response_model=StudentListResponse)
async def read_students(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Retrieve students (scoped to user's school) with pagination."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    count_stmt = select(func.count()).select_from(Student)
    if current_user.school_id:
        count_stmt = count_stmt.where(Student.school_id == current_user.school_id)
    total = (await db.execute(count_stmt)).scalar_one_or_none() or 0

    query = select(Student).offset((page - 1) * page_size).limit(page_size)
    if current_user.school_id:
        query = query.where(Student.school_id == current_user.school_id)

    result = await db.execute(query.options(selectinload(Student.user)).order_by(Student.created_at.desc()))
    students = result.scalars().all()

    items = [StudentSchema.model_validate(s).model_dump(mode="json") for s in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/students/query", response_model=StudentListResponse)
async def query_students(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None,
    class_id: Optional[UUID] = None,
    section_id: Optional[UUID] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Search/filter students with paginated response."""
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    filters = []
    if current_user.school_id:
        filters.append(Student.school_id == current_user.school_id)
    if class_id:
        filters.append(Student.class_id == class_id)
    if section_id:
        filters.append(Student.section_id == section_id)
    if search:
        term = f"%{search.strip()}%"
        query_user_ids = select(User.id).where(or_(User.full_name.ilike(term), User.phone.ilike(term)))
        filters.append(
            or_(
                Student.admission_number.ilike(term),
                Student.roll_number.ilike(term),
                Student.guardian_name.ilike(term),
                Student.guardian_phone.ilike(term),
                Student.user_id.in_(query_user_ids),
            )
        )

    count_stmt = select(func.count()).select_from(Student)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Student)
        .options(selectinload(Student.user))
        .order_by(Student.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if filters:
        stmt = stmt.where(*filters)
    result = await db.execute(stmt)
    students = result.scalars().all()

    items = [StudentSchema.model_validate(s).model_dump(mode="json") for s in students]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/students", response_model=StudentCreateResponse)
async def create_student(
    *,
    db: AsyncSession = Depends(get_db),
    student_in: StudentCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Create new student."""
    identity_service = get_identity_service(db)
    student, parent_account_created = await identity_service.create_student(current_user, student_in)

    return {
        **StudentCreateResponse.model_validate(student).model_dump(),
        "parent_account_created": parent_account_created,
    }


@router.get("/students/{student_id}", response_model=StudentSchema)
async def read_student(
    *,
    db: AsyncSession = Depends(get_db),
    student_id: UUID,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get student by ID."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user.school_id and student.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    return student


@router.get("/students/{student_id}/profile-summary")
async def read_student_profile_summary(
    *,
    db: AsyncSession = Depends(get_db),
    student_id: UUID,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Composite student profile — identity, performance, attendance, AI summary."""
    student_result = await db.execute(
        select(Student).where(Student.id == student_id).options(selectinload(Student.user))
    )
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    class_name = (await db.execute(select(Class.name).where(Class.id == student.class_id))).scalar_one_or_none()
    section_name = (await db.execute(select(Section.name).where(Section.id == student.section_id))).scalar_one_or_none()

    from app.modules.academic.models import Subject
    subject_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained), func.count(Mark.id))
        .join(Mark, Mark.subject_id == Subject.id)
        .where(Mark.student_id == student_id, Mark.mark_status == "present")
        .group_by(Subject.name)
    )
    subject_performance = [
        {"subject": row[0], "average_marks": round(float(row[1]), 2), "records_count": row[2]}
        for row in subject_rows.all()
        if row[1] is not None
    ]

    total_days = (await db.execute(
        select(func.count()).select_from(Attendance).where(Attendance.student_id == student_id)
    )).scalar_one()
    present_days = (await db.execute(
        select(func.count()).select_from(Attendance).where(
            Attendance.student_id == student_id, Attendance.status == "Present"
        )
    )).scalar_one()

    insight_v2 = (
        await db.execute(
            select(AIInsightV2)
            .where(
                AIInsightV2.student_id == student_id,
                AIInsightV2.status == "completed",
            )
            .order_by(AIInsightV2.generated_at.desc().nullslast(), AIInsightV2.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    latest_report = (await db.execute(
        select(ReportCard).where(ReportCard.student_id == student_id)
        .order_by(ReportCard.generated_at.desc()).limit(1)
    )).scalar_one_or_none()

    return {
        "profile": {
            "student_id": str(student.id),
            "full_name": student.user.full_name if student.user else None,
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "guardian_name": student.guardian_name,
            "guardian_relation": student.guardian_relation,
            "guardian_phone": student.guardian_phone,
            "parent_joining_code": student.parent_joining_code,
            "class": class_name,
            "section": section_name,
        },
        "subject_performance": subject_performance,
        "attendance": {
            "present_days": present_days,
            "total_days": total_days,
            "attendance_percentage": round((present_days / total_days) * 100, 2) if total_days else 0.0,
        },
        "ai_summary": {
            "insight_text": insight_v2.insight_text if insight_v2 else None,
            "recommendations": _normalize_recommendations_from_v2(
                insight_v2.recommendations_json if insight_v2 else None
            ) or None,
        },
        "latest_report": {
            "id": str(latest_report.id),
            "term_name": latest_report.term_name,
            "generated_at": latest_report.generated_at,
            "pdf_url": latest_report.pdf_url,
        } if latest_report else None,
    }


@router.get("/parents/me/children", response_model=list[ParentChildSummary])
async def read_my_children(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.PARENT])),
) -> Any:
    identity_service = get_identity_service(db)
    return await identity_service.get_parent_children(current_user)


@router.post("/parents/link-by-code", response_model=ParentChildSummary)
async def link_child_by_code(
    *,
    db: AsyncSession = Depends(get_db),
    body: ParentLinkByCodeRequest,
    current_user: User = Depends(requires_roles([UserRole.PARENT])),
) -> Any:
    identity_service = get_identity_service(db)
    student = await identity_service.link_parent_by_code(current_user.id, body.joining_code.strip().upper())
    if not student:
        raise HTTPException(status_code=404, detail="Invalid joining code")

    children = await identity_service.get_parent_children(current_user)
    linked_child = next((child for child in children if child.id == student.id), None)
    if not linked_child:
        raise HTTPException(status_code=500, detail="Child was linked but could not be loaded")
    return linked_child


@router.post("/students/{student_id}/link-parent/{parent_id}", response_model=dict)
async def link_student_parent(
    *,
    db: AsyncSession = Depends(get_db),
    student_id: UUID,
    parent_id: UUID,
    current_user: User = Depends(requires_admin),
) -> Any:
    """Link a student to a parent."""
    identity_service = get_identity_service(db)
    await identity_service.link_parent(student_id, parent_id)
    return {"message": "Parent linked successfully"}
