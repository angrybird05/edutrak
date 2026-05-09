"""
AI Insights API — Endpoints for viewing and triggering AI-generated
student performance insights. Visible to parents, students, and teachers.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.db.session import get_db
from app.api import deps
from app.models.performance import AIInsight
from app.models.student import Student, parent_student
from pydantic import BaseModel
from pydantic import BaseModel
from app.models.user import User, UserRole
from app.schemas.performance import AIInsightResponse, AIInsightGenerate, AIInsightRate, AdminDigestResponse
from app.core.celery_app import celery_app
from app.services.ai_task_queue import ai_insight_task_queue
from app.services.ai_service import ai_insight_service
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/student/{student_id}", response_model=AIInsightResponse)
async def get_student_insight(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get AI insight for a specific student.
    Accessible by: Admin, Teacher, Parent (own child), Student (self).
    """
    # Access control
    await _check_insight_access(db, current_user, student_id)

    result = await db.execute(
        select(AIInsight)
        .where(AIInsight.student_id == student_id)
        .order_by(AIInsight.created_at.desc())
    )
    insight = result.scalars().first()

    if not insight:
        raise HTTPException(status_code=404, detail="No insight generated yet for this student")

    return insight


@router.get("/student/{student_id}/stream")
async def stream_student_insight(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Stream AI insight generation live for a student.
    Accessible by: Admin, Teacher, Parent (own child), Student (self).
    """
    await _check_insight_access(db, current_user, student_id)
    # The stream now natively calls generate_insight_stream which wraps the Study Coach logic
    return EventSourceResponse(ai_insight_service.generate_insight_stream(db, student_id))


@router.get("/student/{student_id}/plan")
async def get_study_plan(
    student_id: UUID,
    language: str = "English",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Generate a personalized study plan for a student (Markdown text)."""
    await _check_insight_access(db, current_user, student_id)
    plan = await ai_insight_service.generate_study_plan(db, student_id, language=language)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to generate study plan")
    return {"plan": plan, "language": language}


@router.get("/student/{student_id}/parent-report")
async def get_parent_report(
    student_id: UUID,
    language: str = "English",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Generate a comprehensive narrative report card for parents (Markdown text)."""
    await _check_insight_access(db, current_user, student_id)
    report = await ai_insight_service.generate_parent_report(db, student_id, language=language)
    if not report:
        raise HTTPException(status_code=500, detail="Failed to generate parent report")
    return {"report": report, "language": language}


@router.get("/section/{section_id}", response_model=List[AIInsightResponse])
async def get_section_insights(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_admin),
) -> Any:
    """
    Get AI insights for all students in a section. Admin/Teacher only.
    """
    students = await db.execute(
        select(Student.id).where(Student.section_id == section_id)
    )
    student_ids = students.scalars().all()

    result = await db.execute(
        select(AIInsight)
        .where(AIInsight.student_id.in_(student_ids))
        .order_by(AIInsight.created_at.desc())
    )
    all_insights = result.scalars().all()
    
    # Keep only the latest insight per student
    latest_insights = {}
    for insight in all_insights:
        if insight.student_id not in latest_insights:
            latest_insights[insight.student_id] = insight
            
    return list(latest_insights.values())


@router.post("/generate", response_model=dict)
async def trigger_insight_generation(
    *,
    db: AsyncSession = Depends(get_db),
    request: AIInsightGenerate,
    current_user: User = Depends(deps.requires_admin),
) -> Any:
    """
    Manually trigger AI insight generation for a student or section.
    Runs in the background so the request returns immediately.
    """
    if request.student_id:
        result = await ai_insight_task_queue.enqueue_students([request.student_id])
        return {
            "status": "accepted",
            "message": f"Insight generation queued for student {request.student_id}",
            "queue": result,
        }

    elif request.section_id:
        students_result = await db.execute(
            select(Student.id).where(Student.section_id == request.section_id)
        )
        student_ids = students_result.scalars().all()
        result = await ai_insight_task_queue.enqueue_students(student_ids)
        return {
            "status": "accepted",
            "message": f"Insight generation queued for section {request.section_id}",
            "queue": result,
        }

    raise HTTPException(status_code=400, detail="Provide either student_id or section_id")


class TaskStatusRequest(BaseModel):
    task_ids: List[str]

@router.post("/tasks/status")
async def get_task_statuses(
    request: TaskStatusRequest,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Poll the status of background AI insight generation tasks.
    """
    statuses = []
    for task_id in request.task_ids:
        # Fetch status dynamically from Celery Redis broker
        res = celery_app.AsyncResult(task_id)
        statuses.append({
            "task_id": task_id,
            "status": res.state,
        })
    return {"tasks": statuses}


@router.patch("/{insight_id}/rate", response_model=AIInsightResponse)
async def rate_insight(
    insight_id: UUID,
    rating: AIInsightRate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Submit a user rating and feedback for an AI insight.
    """
    insight = await db.get(AIInsight, insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
        
    # Security: Ensure person rating owns the student record or is an admin
    await _check_insight_access(db, current_user, insight.student_id)
    
    insight.user_rating = rating.user_rating
    insight.feedback_text = rating.feedback_text
    
    await db.commit()
    await db.refresh(insight)
    return insight


@router.get("/admin/digest", response_model=AdminDigestResponse)
async def get_admin_digest(
    school_id: Optional[UUID] = None,
    section_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_admin),
) -> Any:
    """
    Generate or retrieve the strategic school-wide AI summary.
    Only accessible by School Admins.
    """
    # If standard admin, force their school_id
    target_school_id = school_id
    if current_user.school_id:
        target_school_id = current_user.school_id
        
    digest_text = await ai_insight_service.generate_admin_digest(
        db, school_id=target_school_id, section_id=section_id
    )
    metrics = await ai_insight_service._calculate_admin_metrics(
        db, school_id=target_school_id, section_id=section_id
    )
    
    if not digest_text:
        raise HTTPException(status_code=500, detail="Failed to generate admin digest")
        
    return {
        "digest": digest_text,
        "generated_at": datetime.now(),
        "metrics": metrics
    }


async def _check_insight_access(db: AsyncSession, user: User, student_id: UUID):
    """Role-based access control for viewing insights."""
    if user.role == UserRole.ADMIN:
        return  # Admins see everything

    if user.role == UserRole.TEACHER:
        return  # Teachers can view any student's insight

    if user.role == UserRole.STUDENT:
        # Students can only see their own insight
        student = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student_obj = student.scalar_one_or_none()
        if student_obj and student_obj.id == student_id:
            return
        raise HTTPException(status_code=403, detail="You can only view your own insights")

    if user.role == UserRole.PARENT:
        # Parents can only see their children's insights
        result = await db.execute(
            select(parent_student).where(
                parent_student.c.parent_id == user.id,
                parent_student.c.student_id == student_id
            )
        )
        if result.first():
            return
        raise HTTPException(status_code=403, detail="You can only view your child's insights")

    raise HTTPException(status_code=403, detail="Insufficient permissions")
