from pathlib import Path
from typing import Any, List
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.core.rate_limit import enforce_heavy_rate_limit
from app.models.performance import ReportCard
from app.models.student import Student, parent_student
from app.models.user import User, UserRole
from app.models.performance import Mark
from app.models.academic import Class, Subject
from app.schemas.performance import ReportCardGenerate, ReportCardResponse
from app.services.idempotency_service import idempotency_service
from app.services.notification_service import notification_service
from app.services.report_service import REPORTS_DIR, report_card_service

router = APIRouter()
logger = logging.getLogger(__name__)


async def _check_student_access(db: AsyncSession, user: User, student_id: UUID) -> None:
    if user.role in (UserRole.ADMIN, UserRole.TEACHER):
        return

    if user.role == UserRole.STUDENT:
        student_result = await db.execute(select(Student).where(Student.user_id == user.id))
        student_obj = student_result.scalar_one_or_none()
        if student_obj and student_obj.id == student_id:
            return
        raise HTTPException(status_code=403, detail="You can only access your own report cards")

    if user.role == UserRole.PARENT:
        link_result = await db.execute(
            select(parent_student).where(
                parent_student.c.parent_id == user.id,
                parent_student.c.student_id == student_id,
            )
        )
        if link_result.first():
            return
        raise HTTPException(status_code=403, detail="You can only access your child's report cards")

    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/generate", response_model=ReportCardResponse)
async def generate_report_card(
    *,
    db: AsyncSession = Depends(get_db),
    request_ctx: Request,
    request: ReportCardGenerate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(deps.get_current_user),
    _rate_limit: None = Depends(enforce_heavy_rate_limit),
) -> Any:
    """
    Generate and store a PDF report card for a student.
    Accessible by admin/teacher and by student/parent for authorized student.
    """
    if idempotency_key:
        existing = await idempotency_service.check_existing(
            db,
            idempotency_key=idempotency_key,
            scope="reports.generate",
            request_payload=request.model_dump(mode="json"),
        )
        if existing:
            return existing

    await _check_student_access(db, current_user, request.student_id)
    try:
        report = await report_card_service.generate_report_card(db, request.student_id, request.term_name)
        recipients = await notification_service.recipients_for_student(db, student_id=request.student_id)
        if recipients:
            await notification_service.emit_event(
                db,
                event_type="report_generated",
                actor_id=current_user.id,
                student_id=request.student_id,
                school_id=current_user.school_id,
                payload_json={
                    "report_id": str(report.id),
                    "student_id": str(request.student_id),
                    "term_name": request.term_name,
                    "trace_id": getattr(request_ctx.state, "trace_id", None),
                },
                recipient_user_ids=recipients,
            )
        response_payload = {
            "id": str(report.id),
            "student_id": str(report.student_id),
            "term_name": report.term_name,
            "pdf_url": report.pdf_url,
            "generated_at": str(report.generated_at),
        }
        if idempotency_key:
            await idempotency_service.store_response(
                db,
                idempotency_key=idempotency_key,
                scope="reports.generate",
                request_payload=request.model_dump(mode="json"),
                response_payload=response_payload,
                status_code=200,
            )
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.exception("Report card runtime failure for student %s", request.student_id)
        raise HTTPException(status_code=500, detail="Report generation service is unavailable")
    except Exception:
        logger.exception("Unexpected report generation failure for student %s", request.student_id)
        raise HTTPException(status_code=500, detail="Failed to generate report card")


@router.get("/student/{student_id}", response_model=List[ReportCardResponse])
async def list_student_report_cards(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all generated report cards for a student.
    """
    await _check_student_access(db, current_user, student_id)
    result = await db.execute(
        select(ReportCard).where(ReportCard.student_id == student_id).order_by(ReportCard.generated_at.desc())
    )
    return result.scalars().all()


@router.get("/me", response_model=List[ReportCardResponse])
async def list_my_report_cards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Convenience endpoint for current logged-in user.
    - student: own report cards
    - parent: all linked children's report cards
    - admin/teacher: requires student-scoped endpoints
    """
    if current_user.role == UserRole.STUDENT:
        student_obj = (
            await db.execute(select(Student).where(Student.user_id == current_user.id))
        ).scalar_one_or_none()
        if not student_obj:
            return []
        result = await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id == student_obj.id)
            .order_by(ReportCard.generated_at.desc())
        )
        return result.scalars().all()

    if current_user.role == UserRole.PARENT:
        linked_ids = (
            await db.execute(
                select(parent_student.c.student_id).where(parent_student.c.parent_id == current_user.id)
            )
        ).scalars().all()
        if not linked_ids:
            return []
        result = await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id.in_(linked_ids))
            .order_by(ReportCard.generated_at.desc())
        )
        return result.scalars().all()

    raise HTTPException(status_code=400, detail="Use /reports/student/{student_id} for this role")


@router.get("/{report_id}", response_model=ReportCardResponse)
async def get_report_card_metadata(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get metadata of a specific report card.
    """
    result = await db.execute(select(ReportCard).where(ReportCard.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report card not found")
    await _check_student_access(db, current_user, report.student_id)
    return report


@router.get("/{report_id}/download")
async def download_report_card(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Download report card PDF.
    Accessible by admin, teacher, student (self), parent (linked child).
    """
    result = await db.execute(select(ReportCard).where(ReportCard.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report card not found")

    await _check_student_access(db, current_user, report.student_id)

    if not report.pdf_url:
        raise HTTPException(status_code=404, detail="PDF path is missing for this report card")
    pdf_path = Path(report.pdf_url).resolve()
    reports_root = REPORTS_DIR.resolve()
    if reports_root != pdf_path and reports_root not in pdf_path.parents:
        raise HTTPException(status_code=400, detail="Invalid report card file path")
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Report card PDF file not found on server")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"report_card_{report.student_id}_{report.term_name}.pdf",
    )


@router.get("/analytics/school/{school_id}")
async def school_analytics(
    school_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    School-level analytics: trends, toppers, low performers, subject and class distributions.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.TEACHER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if current_user.school_id and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="You can only access your school analytics")

    trends_rows = await db.execute(
        select(
            func.date_trunc("month", ReportCard.generated_at).label("month"),
            func.count(ReportCard.id).label("reports_generated"),
        )
        .join(Student, Student.id == ReportCard.student_id)
        .where(Student.school_id == school_id)
        .group_by(func.date_trunc("month", ReportCard.generated_at))
        .order_by(func.date_trunc("month", ReportCard.generated_at))
    )
    trends = [{"month": str(row.month.date()), "reports_generated": row.reports_generated} for row in trends_rows]

    avg_by_student = await db.execute(
        select(Student.id, func.avg(Mark.marks_obtained).label("avg_marks"))
        .join(Mark, Mark.student_id == Student.id)
        .where(Student.school_id == school_id, Mark.mark_status == "present")
        .group_by(Student.id)
    )
    perf = [{"student_id": str(row.id), "avg_marks": float(row.avg_marks)} for row in avg_by_student if row.avg_marks is not None]
    perf_sorted = sorted(perf, key=lambda x: x["avg_marks"], reverse=True)

    subject_dist_rows = await db.execute(
        select(Subject.name, func.count(Mark.id))
        .join(Mark, Mark.subject_id == Subject.id)
        .join(Student, Student.id == Mark.student_id)
        .where(Student.school_id == school_id)
        .group_by(Subject.name)
    )
    subject_distribution = [{"subject": row[0], "records": row[1]} for row in subject_dist_rows]

    class_dist_rows = await db.execute(
        select(Class.name, func.count(Student.id))
        .join(Student, Student.class_id == Class.id)
        .where(Student.school_id == school_id)
        .group_by(Class.name)
    )
    class_distribution = [{"class_name": row[0], "students": row[1]} for row in class_dist_rows]

    return {
        "trends": trends,
        "toppers": perf_sorted[:10],
        "low_performers": list(reversed(perf_sorted[-10:])),
        "subject_distribution": subject_distribution,
        "class_distribution": class_distribution,
    }
