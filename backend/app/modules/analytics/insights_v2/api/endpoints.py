"""
Public and backward-compatible API endpoints for AI Insights V2.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.analytics.insights_v2.core import metrics
from app.modules.analytics.insights_v2.models.insight import AIInsightV2
from app.modules.analytics.insights_v2.schemas import InsightGenerateRequest
from app.modules.analytics.insights_v2.tasks.celery_tasks import ai_insights_v2_task_queue
from app.modules.assessment.models import Exam
from app.modules.auth.models import User, UserRole
from app.modules.identity.models import Student, parent_student
from app.shared.api.deps import get_current_user, requires_roles
from app.shared.db.session import get_db

public_router = APIRouter(prefix="/insights", tags=["insights-v2"])
analytics_router = APIRouter(prefix="/analytics/insights", tags=["analytics"])


async def _check_student_access(db: AsyncSession, current_user: User, student_id: UUID) -> None:
    if current_user.role in (UserRole.ADMIN, UserRole.TEACHER):
        return

    if current_user.role == UserRole.STUDENT:
        student = (
            await db.execute(select(Student).where(Student.user_id == current_user.id))
        ).scalar_one_or_none()
        if student and student.id == student_id:
            return
        raise HTTPException(status_code=403, detail="You can only access your own insights")

    if current_user.role == UserRole.PARENT:
        linked = await db.execute(
            select(parent_student).where(
                parent_student.c.parent_id == current_user.id,
                parent_student.c.student_id == student_id,
            )
        )
        if linked.first():
            return
        raise HTTPException(status_code=403, detail="You can only access your child's insights")

    raise HTTPException(status_code=403, detail="Insufficient permissions")


@public_router.get("/status/{student_id}/{exam_id}")
@analytics_router.get("/status/{student_id}/{exam_id}")
async def get_insight_status(
    student_id: UUID,
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _check_student_access(db, current_user, student_id)
    row = (
        await db.execute(
            select(AIInsightV2).where(
                AIInsightV2.student_id == student_id,
                AIInsightV2.exam_id == exam_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return {
            "student_id": str(student_id),
            "exam_id": str(exam_id),
            "status": "pending",
            "detail": "generating",
        }
    return {
        "student_id": str(row.student_id),
        "exam_id": str(row.exam_id),
        "status": row.status,
        "model_version": row.model_version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "detail": "generating" if row.status != "completed" else None,
    }


@public_router.get("/{student_id}/{exam_id}")
@analytics_router.get("/{student_id}/{exam_id}")
async def get_insight(
    student_id: UUID,
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _check_student_access(db, current_user, student_id)
    row = (
        await db.execute(
            select(AIInsightV2).where(
                AIInsightV2.student_id == student_id,
                AIInsightV2.exam_id == exam_id,
            )
        )
    ).scalar_one_or_none()
    if not row or row.status != "completed":
        return {
            "student_id": str(student_id),
            "exam_id": str(exam_id),
            "status": "generating",
        }

    return {
        "student_id": str(row.student_id),
        "exam_id": str(row.exam_id),
        "status": row.status,
        "insight_text": row.insight_text,
        "recommendations_json": row.recommendations_json or {},
        "performance_summary_json": row.performance_summary_json or {},
        "model_version": row.model_version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


@public_router.post("/generate")
@analytics_router.post("/generate")
async def generate_insights(
    request: InsightGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    # Kept for backward compatibility; automation pipeline is event-driven.
    from app.modules.analytics.insights_v2.services.data_service import insight_data_service

    student_ids = await insight_data_service.resolve_student_ids(
        db,
        exam_id=request.exam_id,
        section_id=request.section_id,
        student_ids=request.student_ids,
    )
    if not student_ids:
        return {"status": "queued", "enqueued": 0, "task_ids": []}

    result = await ai_insights_v2_task_queue.enqueue_exam(
        exam_id=request.exam_id,
        section_id=request.section_id,
        student_ids=student_ids,
        model_version=request.model_version,
        explicit_ai=request.explicit_ai,
        force_regenerate=request.force_regenerate,
        reprocess_failed=request.reprocess_failed,
    )
    return {
        **result,
        "exam_id": str(request.exam_id),
        "enqueued_students": len(student_ids),
    }


@public_router.get("/metrics")
@analytics_router.get("/metrics")
async def get_insight_metrics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    return await metrics.snapshot(db)


@public_router.get("/overview")
@analytics_router.get("/overview")
async def get_insight_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    """Cross-exam overview for global dashboard cards."""
    overall_status_rows = (
        await db.execute(
            select(
                AIInsightV2.status,
                func.count(AIInsightV2.id).label("count"),
            ).group_by(AIInsightV2.status)
        )
    ).all()

    counts: dict[str, int] = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
    for row in overall_status_rows:
        if row.status in counts:
            counts[row.status] = row.count

    exam_rows = (
        await db.execute(
            select(
                AIInsightV2.exam_id,
                func.count(AIInsightV2.id).label("total"),
                func.count(AIInsightV2.id).filter(AIInsightV2.status == "completed").label("completed"),
                func.count(AIInsightV2.id).filter(AIInsightV2.status.in_(["pending", "processing"])).label("in_progress"),
                func.count(AIInsightV2.id).filter(AIInsightV2.status == "failed").label("failed"),
            )
            .group_by(AIInsightV2.exam_id)
            .order_by(func.count(AIInsightV2.id).desc())
            .limit(10)
        )
    ).all()

    metrics_snapshot = await metrics.snapshot(db)
    total = sum(counts.values())
    completed = counts["completed"]

    return {
        "total": total,
        "generated": completed,
        "in_progress": counts["pending"] + counts["processing"],
        "failed": counts["failed"],
        "completion_pct": round((completed / total) * 100, 1) if total else 0.0,
        "task_processing_time_ms_avg": metrics_snapshot.get("task_processing_time_ms_avg", 0.0),
        "task_processing_time_ms_last": metrics_snapshot.get("task_processing_time_ms_last", 0.0),
        "top_exams": [
            {
                "exam_id": str(row.exam_id),
                "total": int(row.total or 0),
                "completed": int(row.completed or 0),
                "in_progress": int(row.in_progress or 0),
                "failed": int(row.failed or 0),
            }
            for row in exam_rows
        ],
    }


@public_router.get("/list")
@analytics_router.get("/list")
async def list_exam_insights(
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    """Return per-student rows for an exam, including not-yet-generated students."""
    exam = await db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    insight_rows = (
        await db.execute(select(AIInsightV2).where(AIInsightV2.exam_id == exam_id))
    ).scalars().all()
    insight_by_student = {row.student_id: row for row in insight_rows}

    student_rows = (
        await db.execute(
            select(Student.id, Student.admission_number, User.full_name)
            .join(User, User.id == Student.user_id)
            .where(Student.section_id == exam.section_id)
            .order_by(Student.created_at.asc())
        )
    ).all()

    response = []
    for student in student_rows:
        row = insight_by_student.get(student.id)
        response.append(
            {
                "student_id": str(student.id),
                "admission_number": student.admission_number,
                "full_name": student.full_name,
                "exam_id": str(exam_id),
                "status": row.status if row else "pending",
                "model_version": row.model_version if row else None,
                "generated_at": row.generated_at.isoformat() if row and row.generated_at else None,
            }
        )
    return response


@public_router.get("/batch-status")
@analytics_router.get("/batch-status")
async def get_batch_insight_status(
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    """Return automatic generation progress and ETA for all students in exam section."""
    exam = await db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")

    status_rows = (
        await db.execute(
            select(
                AIInsightV2.status,
                func.count(AIInsightV2.id).label("count"),
            )
            .where(AIInsightV2.exam_id == exam_id)
            .group_by(AIInsightV2.status)
        )
    ).all()

    counts: dict[str, int] = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
    for row in status_rows:
        if row.status in counts:
            counts[row.status] = row.count

    total_students = int(
        (
            await db.execute(
                select(func.count(Student.id)).where(Student.section_id == exam.section_id)
            )
        ).scalar_one_or_none()
        or 0
    )

    tracked_total = sum(counts.values())
    implicit_pending = max(total_students - tracked_total, 0)
    pending = counts["pending"] + implicit_pending
    processing = counts["processing"]
    completed = counts["completed"]
    failed = counts["failed"]

    in_progress = pending + processing
    remaining = max(total_students - completed, 0)
    progress_pct = round((completed / total_students) * 100, 1) if total_students else 0.0

    avg_task_ms = await metrics.average_task_duration_ms()
    eta_seconds: int | None = None
    if remaining <= 0:
        eta_seconds = 0
    elif avg_task_ms > 0:
        concurrency = max(settings.AI_INSIGHTS_V2_WORKER_CONCURRENCY, 1)
        eta_seconds = ceil((remaining * (avg_task_ms / 1000.0)) / concurrency)

    eta_completed_at = (
        (datetime.now(timezone.utc) + timedelta(seconds=eta_seconds)).isoformat()
        if eta_seconds is not None and eta_seconds > 0
        else None
    )

    is_complete = total_students > 0 and completed >= total_students and in_progress == 0 and failed == 0

    return {
        "exam_id": str(exam_id),
        "total": total_students,
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "generated": completed,
        "in_progress": in_progress,
        "remaining": remaining,
        "progress_pct": progress_pct,
        "eta_seconds": eta_seconds,
        "eta_completed_at": eta_completed_at,
        "is_complete": is_complete,
        "auto_mode": True,
    }
