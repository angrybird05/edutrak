"""
Analytics module — Event subscribers.

Subscribes to assessment events to trigger AI insight regeneration.
This is the key decoupling: the assessment module doesn't know about analytics.
"""
import logging
from uuid import UUID

from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)


@event_bus.on("assessment.marks_recorded")
async def on_marks_recorded(payload: dict) -> None:
    """Legacy handler retained for compatibility; V2 pipeline handles regeneration."""
    student_ids = payload.get("student_ids", [])
    if student_ids:
        logger.info(
            "Legacy AIInsight pipeline skipped for %d students; using V2 orchestration",
            len(student_ids),
        )


@event_bus.on("assessment.attendance_recorded")
async def on_attendance_recorded(payload: dict) -> None:
    """Legacy handler retained for compatibility; V2 pipeline handles regeneration."""
    student_ids = payload.get("student_ids", [])
    if student_ids:
        logger.info(
            "Legacy attendance-triggered AIInsight generation skipped; using V2 orchestration"
        )

@event_bus.on("assessment.exam_completed")
async def on_exam_completed(payload: dict) -> None:
    """When an exam is marked completed, automatically generate report cards."""
    import asyncio
    from app.shared.db.session import SessionLocal
    from sqlalchemy import select
    from app.modules.identity.models import Student
    from app.modules.analytics.models import ReportCard
    from app.modules.analytics.report_service import background_generate_report

    section_id = UUID(payload["section_id"])
    term_name = payload["term_name"]
    
    logger.info("Exam completed for section %s (Term: %s). Auto-generating reports...", section_id, term_name)

    async with SessionLocal() as db:
        student_ids = (
            await db.execute(select(Student.id).where(Student.section_id == section_id))
        ).scalars().all()

        for sid in student_ids:
            # Check existing pending/completed
            stmt = select(ReportCard).where(ReportCard.student_id == sid, ReportCard.term_name == term_name)
            existing = (await db.execute(stmt)).scalars().first()
            
            if existing and not existing.pdf_url:
                report_id = existing.id
            elif not existing:
                report = ReportCard(student_id=sid, term_name=term_name, pdf_url=None)
                db.add(report)
                await db.commit()
                await db.refresh(report)
                report_id = report.id
            else:
                continue # Already generated
                
            # Fire and forget background task
            asyncio.create_task(background_generate_report(report_id))
