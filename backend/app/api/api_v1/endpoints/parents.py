from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app import crud, models, schemas
from app.api import deps
from app.models.performance import AIInsight, Attendance, Mark, ReportCard
from app.models.academic import Subject

from pydantic import BaseModel
router = APIRouter()

class LinkStudentBody(BaseModel):
    joining_code: str


@router.get("/my-children", response_model=List[schemas.student.Student])
async def get_my_children(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.user.User = Depends(deps.requires_role(models.user.UserRole.PARENT)),
) -> Any:
    """
    Get all students linked to the current parent.
    """
    # current_user.children is available via backref in Student.parents
    # But we need to make sure they are loaded.
    # We'll use a manual query for clarity in async.
    
    query = select(models.student.Student).join(
        models.student.parent_student
    ).where(
        models.student.parent_student.c.parent_id == current_user.id
    ).options(selectinload(models.student.Student.user))
    
    result = await db.execute(query)
    children = result.scalars().all()
    return children


@router.get("/child/{student_id}", response_model=schemas.student.Student)
async def get_child_details(
    *,
    db: AsyncSession = Depends(deps.get_db),
    student_id: UUID,
    current_user: models.user.User = Depends(deps.requires_role(models.user.UserRole.PARENT)),
) -> Any:
    """
    Get detailed information for a specific child, verifying linkage.
    """
    # Verify linkage
    query = select(models.student.parent_student).where(
        models.student.parent_student.c.parent_id == current_user.id,
        models.student.parent_student.c.student_id == student_id
    )
    link = await db.execute(query)
    if not link.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this student's data"
        )
        
    student = await crud.student.get(db, id=student_id)
    return student


@router.get("/child/{student_id}/performance-summary")
async def child_performance_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    student_id: UUID,
    current_user: models.user.User = Depends(deps.requires_role(models.user.UserRole.PARENT)),
) -> Any:
    """
    Composite performance summary for one linked child.
    Includes profile, subject metrics, attendance, AI summary, and latest report metadata.
    """
    link_query = select(models.student.parent_student).where(
        models.student.parent_student.c.parent_id == current_user.id,
        models.student.parent_student.c.student_id == student_id,
    )
    link = await db.execute(link_query)
    if not link.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this student's data",
        )

    student_query = (
        select(models.student.Student)
        .where(models.student.Student.id == student_id)
        .options(selectinload(models.student.Student.user))
    )
    student_result = await db.execute(student_query)
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    marks_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained), func.count(Mark.id))
        .join(Mark, Mark.subject_id == Subject.id)
        .where(Mark.student_id == student_id, Mark.mark_status == "present")
        .group_by(Subject.name)
    )
    subject_metrics = [
        {"subject": row[0], "average_marks": round(float(row[1]), 2), "records_count": row[2]}
        for row in marks_rows.all()
    ]

    total_days = (
        await db.execute(select(func.count()).select_from(Attendance).where(Attendance.student_id == student_id))
    ).scalar_one()
    present_days = (
        await db.execute(
            select(func.count()).select_from(Attendance).where(
                Attendance.student_id == student_id, Attendance.status == "Present"
            )
        )
    ).scalar_one()
    attendance_summary = {
        "present_days": present_days,
        "total_days": total_days,
        "attendance_percentage": round((present_days / total_days) * 100, 2) if total_days else 0.0,
    }

    insight = (
        await db.execute(select(AIInsight).where(AIInsight.student_id == student_id))
    ).scalar_one_or_none()
    latest_report = (
        await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id == student_id)
            .order_by(ReportCard.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "profile": {
            "student_id": student.id,
            "full_name": student.user.full_name if student.user else None,
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "class_id": student.class_id,
            "section_id": student.section_id,
        },
        "subject_metrics": subject_metrics,
        "attendance": attendance_summary,
        "ai_summary": {
            "insight_text": insight.insight_text if insight else None,
            "recommendations": insight.recommendations if insight else None,
            "last_updated": insight.created_at if insight else None,
        },
        "latest_report": {
            "id": latest_report.id,
            "term_name": latest_report.term_name,
            "generated_at": latest_report.generated_at,
            "pdf_url": latest_report.pdf_url,
        }
        if latest_report
        else None,
    }

@router.post("/link-student")
async def link_student(
    *,
    db: AsyncSession = Depends(deps.get_db),
    body: LinkStudentBody,
    current_user: models.user.User = Depends(deps.requires_role(models.user.UserRole.PARENT)),
) -> Any:
    """
    Connect a parent account to a student profile using a 6-digit joining code.
    """
    # Find student by joining code
    query = select(models.student.Student).where(models.student.Student.parent_joining_code == body.joining_code)
    result = await db.execute(query)
    student = result.scalars().first()
    
    if not student:
        raise HTTPException(status_code=404, detail="Invalid joining code")
    
    # Check if already linked
    check_query = select(models.student.parent_student).where(
        models.student.parent_student.c.parent_id == current_user.id,
        models.student.parent_student.c.student_id == student.id
    )
    existing = await db.execute(check_query)
    if existing.first():
        return {"message": "Already linked to this student"}
    
    # Create linkage
    stmt = models.student.parent_student.insert().values(
        parent_id=current_user.id,
        student_id=student.id
    )
    await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Successfully linked to {student.admission_number}"}
