"""
Analytics module endpoints — Insights, reports, dashboard, AI coach.

Migrated from insights.py, reports.py, dashboard.py, ai_coach.py.
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import case, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user, requires_roles
from app.modules.auth.models import User, UserRole
from app.modules.analytics.models import AIInsight, InstitutionalInsight, ReportCard
from app.modules.analytics.insights_v2.models import AIInsightV2
from app.modules.analytics.service import ai_insight_service
from app.modules.analytics.task_queue import ai_insight_task_queue
from app.modules.identity.models import Student, parent_student
from app.modules.analytics.report_service import REPORTS_DIR, report_card_service
from app.modules.assessment.models import Attendance, LearningTask, Mark
from app.modules.notification.models import NotificationEvent, UserNotification
from app.modules.academic.models import Class, Section, Subject, Timetable

router = APIRouter()
logger = logging.getLogger(__name__)


class ReportGenerateRequest(BaseModel):
    student_id: UUID
    term_name: str


class ReportBulkRequest(BaseModel):
    term_name: str


class ReportStopRequest(BaseModel):
    term_name: Optional[str] = None


def _grade_bucket(score: float | None) -> str:
    if score is None:
        return "D/F"
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D/F"


def _relative_time(value: datetime | None) -> str:
    if not value:
        return "Recently"
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = now - value
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"{max(minutes, 1)} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


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


async def _check_student_access(db: AsyncSession, user: User, student_id: UUID) -> None:
    if user.role in (UserRole.ADMIN, UserRole.TEACHER):
        return

    if user.role == UserRole.STUDENT:
        student_obj = (
            await db.execute(select(Student).where(Student.user_id == user.id))
        ).scalar_one_or_none()
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


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------
@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Institutional-wide metrics for the executive dashboard."""
    from sqlalchemy import func
    from app.modules.identity.models import Student
    from app.modules.assessment.models import Mark, Attendance

    # Scoped to school if applicable
    school_id = current_user.school_id

    # 1. Total Students
    student_count_stmt = select(func.count(Student.id))
    if school_id:
        student_count_stmt = student_count_stmt.where(Student.school_id == school_id)
    total_students = (await db.execute(student_count_stmt)).scalar() or 0

    # 2. Avg Performance
    perf_stmt = select(func.avg(Mark.marks_obtained))
    if school_id:
        perf_stmt = perf_stmt.join(Student, Student.id == Mark.student_id).where(Student.school_id == school_id)
    avg_perf = (await db.execute(perf_stmt)).scalar() or 0.0

    # 3. Attendance Rate
    att_stmt = select(func.count(Attendance.id)).where(Attendance.status == "Present")
    total_att_stmt = select(func.count(Attendance.id))
    if school_id:
        att_stmt = att_stmt.join(Student, Student.id == Attendance.student_id).where(Student.school_id == school_id)
        total_att_stmt = total_att_stmt.join(Student, Student.id == Attendance.student_id).where(Student.school_id == school_id)
    
    present_count = (await db.execute(att_stmt)).scalar() or 0
    total_count = (await db.execute(total_att_stmt)).scalar() or 1 # Avoid div by zero
    attendance_rate = (present_count / total_count) * 100

    return {
        "total_students": total_students,
        "avg_performance": round(float(avg_perf), 2),
        "attendance_rate": round(attendance_rate, 2),
        "at_risk_count": 0, # Logic for this is complex, defaulting to 0 for now
        "performance_change": "+2.5%", # Mocked trend for now
    }


@router.get("/dashboard/admin/overview")
async def get_admin_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN])),
) -> Any:
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    mark_month = func.date_trunc(text("'month'"), Mark.created_at)
    attendance_month = func.date_trunc(text("'month'"), Attendance.date)

    monthly_marks = await db.execute(
        select(
            mark_month.label("month"),
            func.avg(Mark.marks_obtained).label("score"),
        )
        .join(Student, Student.id == Mark.student_id)
        .where(Student.school_id == school_id, Mark.mark_status == "present")
        .group_by(mark_month)
        .order_by(mark_month.asc())
        .limit(6)
    )
    performance_map = {
        row.month.strftime("%b"): {"month": row.month.strftime("%b"), "score": round(float(row.score or 0), 2), "attendance": 0.0}
        for row in monthly_marks
    }

    monthly_attendance = await db.execute(
        select(
            attendance_month.label("month"),
            func.count(Attendance.id).label("total"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present"),
        )
        .join(Student, Student.id == Attendance.student_id)
        .where(Student.school_id == school_id)
        .group_by(attendance_month)
        .order_by(attendance_month.asc())
        .limit(6)
    )
    for row in monthly_attendance:
        month_key = row.month.strftime("%b")
        attendance_rate = round((float(row.present or 0) / float(row.total or 1)) * 100, 2)
        if month_key in performance_map:
            performance_map[month_key]["attendance"] = attendance_rate
        else:
            performance_map[month_key] = {"month": month_key, "score": 0.0, "attendance": attendance_rate}

    subject_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained).label("avg_score"))
        .join(Mark, Mark.subject_id == Subject.id)
        .join(Student, Student.id == Mark.student_id)
        .where(Student.school_id == school_id, Mark.mark_status == "present")
        .group_by(Subject.name)
        .order_by(Subject.name.asc())
    )
    subject_performance = [
        {"subject": row.name, "avg": round(float(row.avg_score or 0), 2)}
        for row in subject_rows
    ]

    student_ids = (
        await db.execute(select(Student.id).where(Student.school_id == school_id))
    ).scalars().all()
    marks_map = {}
    if student_ids:
        mark_stats = await db.execute(
            select(Mark.student_id, func.avg(Mark.marks_obtained).label("avg_marks"))
            .where(Mark.student_id.in_(student_ids), Mark.mark_status == "present")
            .group_by(Mark.student_id)
        )
        marks_map = {row.student_id: float(row.avg_marks) if row.avg_marks is not None else None for row in mark_stats}

        attendance_stats = await db.execute(
            select(
                Attendance.student_id,
                func.count(Attendance.id).label("total_days"),
                func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present_days"),
            )
            .where(Attendance.student_id.in_(student_ids))
            .group_by(Attendance.student_id)
        )
        attendance_map = {
            row.student_id: (float(row.present_days or 0) / float(row.total_days or 1)) * 100
            for row in attendance_stats
        }
    else:
        attendance_map = {}

    risk_counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for student_id in student_ids:
        avg_marks = marks_map.get(student_id)
        attendance_percentage = attendance_map.get(student_id, 100.0)
        if (avg_marks is not None and avg_marks < 40) or attendance_percentage < 75:
            risk_counts["High Risk"] += 1
        elif (avg_marks is not None and avg_marks < 60) or attendance_percentage < 85:
            risk_counts["Medium Risk"] += 1
        else:
            risk_counts["Low Risk"] += 1

    recent_insights = await db.execute(
        select(InstitutionalInsight)
        .where(InstitutionalInsight.school_id == school_id)
        .order_by(InstitutionalInsight.created_at.desc())
        .limit(4)
    )
    recent_reports = await db.execute(
        select(ReportCard)
        .join(Student, Student.id == ReportCard.student_id)
        .where(Student.school_id == school_id)
        .order_by(ReportCard.generated_at.desc())
        .limit(4)
    )

    activity = [
        {
            "name": item.summary_text[:80],
            "status": item.status.title(),
            "time": _relative_time(item.created_at),
        }
        for item in recent_insights.scalars().all()
    ]
    activity.extend(
        {
            "name": f"Report card generated: {item.term_name}",
            "status": "Completed",
            "time": _relative_time(item.generated_at),
        }
        for item in recent_reports.scalars().all()
    )

    return {
        "performance_trend": list(performance_map.values()),
        "subject_performance": subject_performance,
        "risk_distribution": [
            {"name": name, "value": value}
            for name, value in risk_counts.items()
        ],
        "recent_activity": activity[:4],
    }


@router.get("/dashboard/teacher/me")
async def get_teacher_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.TEACHER])),
) -> Any:
    teacher_sections = await db.execute(
        select(Section.id, Section.name, Class.name.label("class_name"))
        .join(Class, Class.id == Section.class_id)
        .join(Section.teachers)
        .where(User.id == current_user.id)
        .order_by(Class.class_number, Section.name)
    )
    sections = teacher_sections.all()
    section_ids = [row.id for row in sections]

    student_count = 0
    avg_attendance = 0.0
    if section_ids:
        student_count = (
            await db.execute(select(func.count(Student.id)).where(Student.section_id.in_(section_ids)))
        ).scalar() or 0

        attendance_stats = await db.execute(
            select(
                func.count(Attendance.id).label("total"),
                func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present"),
            )
            .join(Student, Student.id == Attendance.student_id)
            .where(Student.section_id.in_(section_ids))
        )
        attendance_row = attendance_stats.one()
        avg_attendance = round((float(attendance_row.present or 0) / float(attendance_row.total or 1)) * 100, 2)

    weekday = datetime.now().weekday()
    today_schedule = await db.execute(
        select(Timetable.start_time, Class.name.label("class_name"), Section.name.label("section_name"), Subject.name.label("subject_name"), Timetable.room)
        .join(Section, Section.id == Timetable.section_id)
        .join(Class, Class.id == Section.class_id)
        .join(Subject, Subject.id == Timetable.subject_id)
        .where(Timetable.teacher_id == current_user.id, Timetable.day_of_week == weekday)
        .order_by(Timetable.start_time.asc())
    )

    section_student_rows = await db.execute(
        select(
            Section.id.label("section_id"),
            Section.name.label("section_name"),
            Class.name.label("class_name"),
            func.count(Student.id).label("student_count"),
            func.avg(Mark.marks_obtained).label("avg_score"),
        )
        .join(Class, Class.id == Section.class_id)
        .outerjoin(Student, Student.section_id == Section.id)
        .outerjoin(Mark, Mark.student_id == Student.id)
        .join(Section.teachers)
        .where(User.id == current_user.id)
        .group_by(Section.id, Section.name, Class.name)
        .order_by(Class.name.asc(), Section.name.asc())
    )
    my_classes = [
        {
            "name": f"{row.class_name} - {row.section_name}",
            "students": int(row.student_count or 0),
            "section": row.section_name,
            "avg_score": round(float(row.avg_score or 0), 2),
        }
        for row in section_student_rows
    ]

    risk_rows = await db.execute(
        select(
            Student.id,
            Student.roll_number,
            Student.admission_number,
            User.full_name,
            Class.name.label("class_name"),
            Section.name.label("section_name"),
            func.avg(Mark.marks_obtained).label("avg_marks"),
        )
        .join(User, User.id == Student.user_id)
        .join(Section, Section.id == Student.section_id)
        .join(Class, Class.id == Student.class_id)
        .outerjoin(Mark, Mark.student_id == Student.id)
        .where(Student.section_id.in_(section_ids))
        .group_by(Student.id, Student.roll_number, Student.admission_number, User.full_name, Class.name, Section.name)
    )

    risk_alerts = []
    for row in risk_rows:
        attendance_row = await db.execute(
            select(
                func.count(Attendance.id).label("total"),
                func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present"),
            )
            .where(Attendance.student_id == row.id)
        )
        att = attendance_row.one()
        attendance_percentage = (float(att.present or 0) / float(att.total or 1)) * 100 if att.total else 100.0
        avg_marks = float(row.avg_marks) if row.avg_marks is not None else None
        issue = None
        severity = "medium"
        if avg_marks is not None and avg_marks < 40:
            issue = f"Average marks are {round(avg_marks, 1)}%"
            severity = "high"
        elif attendance_percentage < 75:
            issue = f"Attendance is {round(attendance_percentage, 1)}%"
            severity = "high"
        elif avg_marks is not None and avg_marks < 60:
            issue = f"Average marks slipped to {round(avg_marks, 1)}%"
        if issue:
            risk_alerts.append(
                {
                    "student": row.full_name or row.admission_number,
                    "class": f"{row.class_name}-{row.section_name}",
                    "issue": issue,
                    "severity": severity,
                }
            )

    today_schedule_rows = today_schedule.all()

    return {
        "my_students": student_count,
        "today_classes": len(today_schedule_rows),
        "avg_attendance": avg_attendance,
        "at_risk_students": len(risk_alerts),
        "schedule": [
            {
                "time": row.start_time,
                "class": f"{row.class_name}-{row.section_name}",
                "subject": row.subject_name,
                "room": row.room or "Room not set",
            }
            for row in today_schedule_rows
        ],
        "risk_alerts": risk_alerts[:5],
        "my_classes": my_classes,
    }


@router.get("/performance/overview")
async def get_performance_overview(
    class_id: Optional[UUID] = None,
    subject_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    filters = []
    if current_user.school_id:
        filters.append(Student.school_id == current_user.school_id)
    if class_id:
        filters.append(Student.class_id == class_id)
    if subject_id:
        filters.append(Mark.subject_id == subject_id)
    mark_month = func.date_trunc(text("'month'"), Mark.created_at)

    monthly_rows = await db.execute(
        select(
            mark_month.label("month"),
            Subject.name.label("subject_name"),
            func.avg(Mark.marks_obtained).label("avg_marks"),
        )
        .join(Student, Student.id == Mark.student_id)
        .join(Subject, Subject.id == Mark.subject_id)
        .where(Mark.mark_status == "present", *filters)
        .group_by(mark_month, Subject.name)
        .order_by(mark_month.asc(), Subject.name.asc())
    )
    monthly_map: dict[str, dict[str, Any]] = {}
    for row in monthly_rows:
        key = row.month.strftime("%b")
        bucket = monthly_map.setdefault(key, {"month": key})
        bucket[row.subject_name.lower()] = round(float(row.avg_marks or 0), 2)

    class_rows = await db.execute(
        select(
            Class.name,
            Class.class_number,
            func.avg(Mark.marks_obtained).label("avg_marks"),
        )
        .join(Student, Student.class_id == Class.id)
        .join(Mark, Mark.student_id == Student.id)
        .where(Mark.mark_status == "present", *filters)
        .group_by(Class.name, Class.class_number)
        .order_by(Class.class_number.asc(), Class.name.asc())
    )

    grade_rows = await db.execute(
        select(Student.id, func.avg(Mark.marks_obtained).label("avg_marks"))
        .join(Mark, Mark.student_id == Student.id)
        .where(Mark.mark_status == "present", *filters)
        .group_by(Student.id)
    )
    grade_counts = {"A+": 0, "A": 0, "B": 0, "C": 0, "D/F": 0}
    for row in grade_rows:
        grade_counts[_grade_bucket(float(row.avg_marks) if row.avg_marks is not None else None)] += 1

    subject_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained).label("avg_marks"))
        .join(Mark, Mark.subject_id == Subject.id)
        .join(Student, Student.id == Mark.student_id)
        .where(Mark.mark_status == "present", *filters)
        .group_by(Subject.name)
        .order_by(Subject.name.asc())
    )

    return {
        "monthly_trend": list(monthly_map.values()),
        "class_averages": [
            {"name": row.name, "avg": round(float(row.avg_marks or 0), 2)}
            for row in class_rows
        ],
        "grade_distribution": [
            {"name": name, "value": value}
            for name, value in grade_counts.items()
        ],
        "subject_competency": [
            {"subject": row.name, "score": round(float(row.avg_marks or 0), 2)}
            for row in subject_rows
        ],
    }


@router.get("/reports/overview")
async def get_reports_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    student_stmt = (
        select(Student, User.full_name, Class.name.label("class_name"), Section.name.label("section_name"))
        .join(User, User.id == Student.user_id)
        .join(Class, Class.id == Student.class_id)
        .join(Section, Section.id == Student.section_id)
    )

    if current_user.role == UserRole.ADMIN:
        student_stmt = student_stmt.where(Student.school_id == current_user.school_id)
    else:
        teacher_sections = (
            await db.execute(
                select(Section.id).join(Section.teachers).where(User.id == current_user.id)
            )
        ).scalars().all()
        student_stmt = student_stmt.where(Student.section_id.in_(teacher_sections or [UUID(int=0)]))

    students = (await db.execute(student_stmt.order_by(User.full_name.asc()))).all()
    student_ids = [row[0].id for row in students]

    report_rows = await db.execute(
        select(ReportCard)
        .where(ReportCard.student_id.in_(student_ids or [UUID(int=0)]))
        .order_by(ReportCard.student_id, ReportCard.generated_at.desc())
        .distinct(ReportCard.student_id)
    )
    latest_report_map = {report.student_id: report for report in report_rows.scalars().all()}

    marks_rows = await db.execute(
        select(Mark.student_id, func.avg(Mark.marks_obtained).label("avg_marks"))
        .where(Mark.student_id.in_(student_ids or [UUID(int=0)]), Mark.mark_status == "present")
        .group_by(Mark.student_id)
    )
    marks_map = {row.student_id: float(row.avg_marks) if row.avg_marks is not None else None for row in marks_rows}

    items = []
    for row in students:
        student = row[0]
        latest_report = latest_report_map.get(student.id)
        avg_marks = marks_map.get(student.id)
        
        # Determine explicit status
        if latest_report:
            if latest_report.pdf_url:
                current_status = "ready"
            else:
                current_status = "pending"
        else:
            current_status = "not_started"
            
        items.append(
            {
                "id": str(student.id),
                "name": row.full_name or student.admission_number,
                "roll_number": student.roll_number,
                "admission_number": student.admission_number,
                "class": f"{row.class_name}-{row.section_name}",
                "generated": latest_report.generated_at.isoformat() if latest_report else None,
                "status": current_status,
                "grade": _grade_bucket(avg_marks) if avg_marks is not None else None,
                "report_id": str(latest_report.id) if latest_report else None,
                "term_name": latest_report.term_name if latest_report else None,
                "pdf_url": latest_report.pdf_url if latest_report else None,
            }
        )

    return {
        "terms": sorted({item["term_name"] for item in items if item["term_name"]}) or ["Current Term"],
        "items": items,
        "ready_count": len([i for i in items if i["status"] == "ready"]),
        "pending_count": len([i for i in items if i["status"] == "pending"]),
        "not_started_count": len([i for i in items if i["status"] == "not_started"]),
    }


@router.get("/dashboard/student/me")
async def get_student_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.STUDENT])),
) -> Any:
    student = (
        await db.execute(
            select(Student).where(Student.user_id == current_user.id).options(selectinload(Student.user))
        )
    ).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    avg_marks = (
        await db.execute(
            select(func.avg(Mark.marks_obtained)).where(Mark.student_id == student.id, Mark.mark_status == "present")
        )
    ).scalar()
    total_days = (
        await db.execute(select(func.count()).select_from(Attendance).where(Attendance.student_id == student.id))
    ).scalar_one()
    present_days = (
        await db.execute(
            select(func.count()).select_from(Attendance).where(
                Attendance.student_id == student.id,
                Attendance.status == "Present",
            )
        )
    ).scalar_one()
    attendance_percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0

    status_orb = "green"
    if (avg_marks is not None and avg_marks < 40) or attendance_percentage < 75:
        status_orb = "red"
    elif (avg_marks is not None and avg_marks < 60) or attendance_percentage < 85:
        status_orb = "yellow"
    mark_month = func.date_trunc(text("'month'"), Mark.created_at)

    subject_rows = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained))
        .join(Mark, Mark.subject_id == Subject.id)
        .where(Mark.student_id == student.id, Mark.mark_status == "present")
        .group_by(Subject.name)
        .order_by(Subject.name.asc())
    )
    subject_scores = [
        {"subject": row[0], "score": round(float(row[1]), 2) if row[1] is not None else 0.0}
        for row in subject_rows.all()
    ]

    trend_rows = await db.execute(
        select(
            mark_month.label("month"),
            func.avg(Mark.marks_obtained).label("average_score"),
        )
        .where(Mark.student_id == student.id, Mark.mark_status == "present")
        .group_by(mark_month)
        .order_by(mark_month.asc())
    )
    performance_trend = [
        {
            "month": row.month.strftime("%b") if row.month else "N/A",
            "average_score": round(float(row.average_score), 2) if row.average_score is not None else 0.0,
        }
        for row in trend_rows
    ]

    task_rows = await db.execute(
        select(LearningTask, Subject.name)
        .join(Subject, Subject.id == LearningTask.subject_id)
        .where(LearningTask.student_id == student.id)
        .order_by(LearningTask.due_date.asc())
        .limit(7)
    )
    weekly_tasks = [
        {
            "id": str(task.id),
            "task_name": task.task_name,
            "description": task.description,
            "subject": subject_name,
            "due_date": task.due_date.isoformat(),
            "is_done": task.is_done,
        }
        for task, subject_name in task_rows.all()
    ]

    insight_v2 = (
        await db.execute(
            select(AIInsightV2)
            .where(
                AIInsightV2.student_id == student.id,
                AIInsightV2.status == "completed",
            )
            .order_by(AIInsightV2.generated_at.desc().nullslast(), AIInsightV2.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    latest_report = (
        await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id == student.id)
            .order_by(ReportCard.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    class_name = (await db.execute(select(Class.name).where(Class.id == student.class_id))).scalar_one_or_none()
    section_name = (await db.execute(select(Section.name).where(Section.id == student.section_id))).scalar_one_or_none()

    best_subject = max(subject_scores, key=lambda item: item["score"], default=None)
    weakest_subject = min(subject_scores, key=lambda item: item["score"], default=None)

    return {
        "profile": {
            "student_id": str(student.id),
            "full_name": current_user.full_name,
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "class_name": class_name,
            "section_name": section_name,
        },
        "metrics": {
            "attendance_percentage": attendance_percentage,
            "average_marks": round(float(avg_marks), 2) if avg_marks is not None else None,
            "status_orb": status_orb,
            "assignments_done": len([task for task in weekly_tasks if task["is_done"]]),
            "assignments_total": len(weekly_tasks),
        },
        "best_subject": best_subject,
        "weakest_subject": weakest_subject,
        "subject_scores": subject_scores,
        "performance_trend": performance_trend,
        "weekly_tasks": weekly_tasks,
        "ai_summary": {
            "insight_text": insight_v2.insight_text if insight_v2 else None,
            "recommendations": _normalize_recommendations_from_v2(
                insight_v2.recommendations_json if insight_v2 else None
            ) or None,
        },
        "latest_report": {
            "id": str(latest_report.id),
            "term_name": latest_report.term_name,
            "generated_at": str(latest_report.generated_at),
            "pdf_url": latest_report.pdf_url,
        } if latest_report else None,
    }


@router.get("/dashboard/parent/me")
async def get_parent_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.PARENT])),
) -> Any:
    children = (
        await db.execute(
            select(Student)
            .join(parent_student, parent_student.c.student_id == Student.id)
            .where(parent_student.c.parent_id == current_user.id)
            .options(selectinload(Student.user))
            .order_by(Student.created_at.asc())
        )
    ).scalars().all()

    if not children:
        return {"children_count": 0, "children": [], "kpis": {}, "recent_alerts": []}

    child_ids = [child.id for child in children]
    class_ids = {child.class_id for child in children}
    section_ids = {child.section_id for child in children}

    class_rows = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids)))
    class_map = {row[0]: row[1] for row in class_rows.all()}
    section_rows = await db.execute(select(Section.id, Section.name).where(Section.id.in_(section_ids)))
    section_map = {row[0]: row[1] for row in section_rows.all()}

    marks_stats = await db.execute(
        select(Mark.student_id, func.avg(Mark.marks_obtained).label("avg_marks"))
        .where(Mark.student_id.in_(child_ids), Mark.mark_status == "present")
        .group_by(Mark.student_id)
    )
    marks_map = {row.student_id: float(row.avg_marks) if row.avg_marks is not None else None for row in marks_stats}

    attendance_stats = await db.execute(
        select(
            Attendance.student_id,
            func.count().label("total_days"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present_days"),
        )
        .where(Attendance.student_id.in_(child_ids))
        .group_by(Attendance.student_id)
    )
    attendance_map = {
        row.student_id: {"total": int(row.total_days or 0), "present": int(row.present_days or 0)}
        for row in attendance_stats
    }

    latest_reports_result = await db.execute(
        select(ReportCard)
        .where(ReportCard.student_id.in_(child_ids))
        .order_by(ReportCard.student_id, ReportCard.generated_at.desc())
        .distinct(ReportCard.student_id)
    )
    report_map = {report.student_id: report for report in latest_reports_result.scalars().all()}

    summaries = []
    low_grade_children = 0
    low_attendance_children = 0
    for child in children:
        avg_marks = marks_map.get(child.id)
        att = attendance_map.get(child.id, {"total": 0, "present": 0})
        attendance_percentage = round((att["present"] / att["total"]) * 100, 2) if att["total"] else 0.0
        if avg_marks is not None and avg_marks < 40:
            low_grade_children += 1
        if att["total"] and attendance_percentage < 75:
            low_attendance_children += 1

        status_orb = "green"
        if (avg_marks is not None and avg_marks < 40) or attendance_percentage < 75:
            status_orb = "red"
        elif (avg_marks is not None and avg_marks < 60) or attendance_percentage < 85:
            status_orb = "yellow"

        latest_report = report_map.get(child.id)
        summaries.append(
            {
                "student_id": str(child.id),
                "full_name": child.user.full_name if child.user else child.admission_number,
                "admission_number": child.admission_number,
                "roll_number": child.roll_number,
                "class_name": class_map.get(child.class_id),
                "section_name": section_map.get(child.section_id),
                "average_marks": round(avg_marks, 2) if avg_marks is not None else None,
                "attendance_percentage": attendance_percentage,
                "status_orb": status_orb,
                "guardian_relation": child.guardian_relation,
                "latest_report": {
                    "id": str(latest_report.id),
                    "term_name": latest_report.term_name,
                    "generated_at": str(latest_report.generated_at),
                    "pdf_url": latest_report.pdf_url,
                } if latest_report else None,
            }
        )

    alerts_rows = await db.execute(
        select(
            UserNotification.id,
            UserNotification.status,
            UserNotification.read_at,
            UserNotification.created_at,
            NotificationEvent.event_type,
            NotificationEvent.payload_json,
        )
        .join(NotificationEvent, NotificationEvent.id == UserNotification.event_id)
        .where(UserNotification.user_id == current_user.id)
        .order_by(UserNotification.created_at.desc())
        .limit(10)
    )
    recent_alerts = [
        {
            "notification_id": str(row.id),
            "event_type": row.event_type,
            "status": row.status,
            "read_at": row.read_at.isoformat() if row.read_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "payload": row.payload_json or {},
        }
        for row in alerts_rows
    ]
    unread_count = (
        await db.execute(
            select(func.count()).select_from(UserNotification).where(
                UserNotification.user_id == current_user.id,
                UserNotification.read_at.is_(None),
            )
        )
    ).scalar_one()

    return {
        "children_count": len(children),
        "children": summaries,
        "kpis": {
            "low_grade_children": low_grade_children,
            "low_attendance_children": low_attendance_children,
            "unread_alerts": unread_count,
        },
        "recent_alerts": recent_alerts,
    }


# ---------------------------------------------------------------------------
# AI Insights
# ---------------------------------------------------------------------------
@router.get("/insights/{student_id}")
async def get_insight(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get latest completed AI Insight V2 for a student (legacy-compatible contract)."""
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
    ).scalars().first()
    if not insight_v2:
        raise HTTPException(status_code=404, detail="No completed insight available yet.")

    recommendations = _normalize_recommendations_from_v2(insight_v2.recommendations_json)
    return {
        "id": str(insight_v2.id),
        "student_id": str(insight_v2.student_id),
        "exam_id": str(insight_v2.exam_id),
        "insight_text": insight_v2.insight_text,
        "recommendations": recommendations,
        "recommendations_json": insight_v2.recommendations_json or {},
        "model_version": insight_v2.model_version,
        "status": insight_v2.status,
        "created_at": str(insight_v2.created_at),
        "generated_at": str(insight_v2.generated_at) if insight_v2.generated_at else None,
    }


@router.post("/insights/{student_id}/generate")
async def generate_insight(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Generate a fresh AI insight for a student."""
    insight = await ai_insight_service.generate_insight(db, student_id)
    if not insight:
        raise HTTPException(status_code=500, detail="Failed to generate insight")
    return {
        "id": str(insight.id),
        "insight_text": insight.insight_text,
        "recommendations": insight.recommendations,
        "created_at": str(insight.created_at),
    }


@router.post("/insights/{student_id}/queue")
async def queue_insight_generation(
    student_id: UUID,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Queue background AI insight generation."""
    result = await ai_insight_task_queue.enqueue_students([student_id])
    return {"status": "queued", **result}


@router.post("/insights/global/generate")
async def generate_global_insight(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Generate institutional-wide AI insight."""
    insight = await ai_insight_service.generate_global_insight(db, school_id=current_user.school_id)
    if not insight:
        raise HTTPException(status_code=500, detail="Failed to generate global insight")

    summary = insight["insight_text"].split("\n", 1)[0].strip() or "Institutional insight generated."
    history_entry = InstitutionalInsight(
        school_id=current_user.school_id,
        summary_text=summary[:255],
        insight_text=insight["insight_text"],
        metadata_json=insight.get("metadata"),
        prompt_version="v1.0",
        status="generated",
    )
    db.add(history_entry)
    await db.commit()
    await db.refresh(history_entry)

    return {
        **insight,
        "id": str(history_entry.id),
        "summary": history_entry.summary_text,
        "prompt_version": history_entry.prompt_version,
        "status": history_entry.status,
    }


@router.get("/insights/global/history")
async def list_global_insight_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List persisted institutional AI insights for the current school."""
    limit = max(1, min(limit, 100))
    stmt = (
        select(InstitutionalInsight)
        .order_by(InstitutionalInsight.created_at.desc())
        .limit(limit)
    )
    if current_user.school_id:
        stmt = stmt.where(InstitutionalInsight.school_id == current_user.school_id)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return [
        {
            "id": str(item.id),
            "summary": item.summary_text,
            "insight_text": item.insight_text,
            "metadata": item.metadata_json,
            "version": item.prompt_version,
            "status": item.status,
            "timestamp": str(item.created_at),
        }
        for item in items
    ]


# ---------------------------------------------------------------------------
# Study Plan
# ---------------------------------------------------------------------------
@router.post("/study-plan/{student_id}")
async def generate_study_plan(
    student_id: UUID,
    language: str = "English",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Generate AI-powered personalized study plan."""
    plan = await ai_insight_service.generate_study_plan(db, student_id, language)
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to generate study plan")
    return {"student_id": str(student_id), "study_plan": plan}


# ---------------------------------------------------------------------------
# Risk Prediction
# ---------------------------------------------------------------------------
@router.post("/risk-prediction/{student_id}")
async def predict_risk(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """Predict failure risk for a student."""
    risk = await ai_insight_service.predict_failure_risk(db, student_id)
    if not risk:
        raise HTTPException(status_code=500, detail="Failed to predict risk")
    return risk.model_dump()


# ---------------------------------------------------------------------------
# AI Coach
# ---------------------------------------------------------------------------
@router.post("/ai-coach/{student_id}/chat")
async def ai_coach_chat(
    student_id: UUID,
    message: str,
    language: str = "English",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Chat with the AI Coach about a student."""
    from app.modules.analytics.models import AIChatSession, AIChatMessage
    # Get or create session
    result = await db.execute(
        select(AIChatSession)
        .where(AIChatSession.student_id == student_id, AIChatSession.is_active == True)
        .order_by(AIChatSession.created_at.desc())
    )
    session = result.scalars().first()
    if not session:
        session = AIChatSession(student_id=student_id, title="AI Coach Session")
        db.add(session)
        await db.flush()

    # Save user message
    user_msg = AIChatMessage(session_id=session.id, role="user", content=message)
    db.add(user_msg)
    await db.flush()

    # Retrieve history
    history_result = await db.execute(
        select(AIChatMessage)
        .where(AIChatMessage.session_id == session.id)
        .order_by(AIChatMessage.created_at.asc())
    )
    messages = history_result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in messages]

    # Generate response
    response = await ai_insight_service.generate_coach_response(db, student_id, history, language)
    if not response:
        raise HTTPException(status_code=500, detail="AI Coach failed to respond")

    # Save assistant response
    assistant_msg = AIChatMessage(session_id=session.id, role="assistant", content=response)
    db.add(assistant_msg)
    await db.commit()

    return {"session_id": str(session.id), "response": response}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@router.get("/reports/preview/html")
async def preview_report_html(
    student_id: UUID,
    term_name: str = "Current Term",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return rendered HTML for in-browser report card preview."""
    from fastapi.responses import HTMLResponse

    await _check_student_access(db, current_user, student_id)
    try:
        html = await report_card_service.get_report_html(db, student_id, term_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return HTMLResponse(content=html)


async def _prepare_reports_for_generation(
    db: AsyncSession,
    student_ids: list[UUID],
    term_name: str,
) -> list[tuple[UUID, UUID]]:
    """Return (student_id, report_id) entries that should be queued for generation."""
    if not student_ids:
        return []

    report_rows = await db.execute(
        select(ReportCard).where(ReportCard.student_id.in_(student_ids), ReportCard.term_name == term_name)
    )
    existing_reports = {report.student_id: report for report in report_rows.scalars().all()}

    reports_to_add: list[ReportCard] = []
    reports_to_queue: list[tuple[UUID, UUID]] = []
    for student_id in student_ids:
        existing = existing_reports.get(student_id)
        if existing:
            if not existing.pdf_url:
                reports_to_queue.append((student_id, existing.id))
            continue
        reports_to_add.append(ReportCard(student_id=student_id, term_name=term_name, pdf_url=None))

    if reports_to_add:
        db.add_all(reports_to_add)
        await db.commit()
        for report in reports_to_add:
            reports_to_queue.append((report.student_id, report.id))

    return reports_to_queue


async def _accessible_student_ids(db: AsyncSession, current_user: User) -> list[UUID]:
    student_stmt = select(Student.id)
    if current_user.role == UserRole.ADMIN:
        if current_user.school_id:
            student_stmt = student_stmt.where(Student.school_id == current_user.school_id)
    else:
        from app.modules.academic.models import Section

        teacher_sections = (
            await db.execute(
                select(Section.id).join(Section.teachers).where(User.id == current_user.id)
            )
        ).scalars().all()
        if teacher_sections:
            student_stmt = student_stmt.where(Student.section_id.in_(teacher_sections))
        else:
            student_stmt = student_stmt.where(Student.section_id == UUID(int=0))

    return (await db.execute(student_stmt)).scalars().all()


@router.post("/reports/generate/batch")
async def batch_generate_reports(
    section_id: UUID,
    term_name: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """Generate report cards for all students in a section."""
    from app.modules.analytics.report_service import background_generate_report

    student_ids = (
        await db.execute(select(Student.id).where(Student.section_id == section_id))
    ).scalars().all()
    if not student_ids:
        raise HTTPException(status_code=404, detail="No students found in this section")

    reports_to_queue = await _prepare_reports_for_generation(db, student_ids, term_name)

    results = []
    for student_id, report_id in reports_to_queue:
        background_tasks.add_task(background_generate_report, report_id)
        results.append({"student_id": str(student_id), "report_id": str(report_id), "status": "pending"})

    return {
        "total": len(student_ids),
        "generated": len(results),
        "failed": 0,
        "results": results,
        "errors": [],
    }



@router.post("/reports/generate")
async def generate_report_card(
    background_tasks: BackgroundTasks,
    student_id: Optional[UUID] = Query(default=None),
    term_name: Optional[str] = Query(default=None),
    payload: Optional[ReportGenerateRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Queue background report card generation for a student."""
    resolved_student_id = student_id or (payload.student_id if payload else None)
    resolved_term_name = term_name or (payload.term_name if payload else None)
    if not resolved_student_id or not resolved_term_name:
        raise HTTPException(status_code=422, detail="student_id and term_name are required")

    await _check_student_access(db, current_user, resolved_student_id)
    
    # Check if a pending report already exists
    stmt = select(ReportCard).where(
        ReportCard.student_id == resolved_student_id,
        ReportCard.term_name == resolved_term_name,
    )
    existing = (await db.execute(stmt)).scalars().first()
    
    if existing and not existing.pdf_url:
        return {
            "id": str(existing.id),
            "student_id": str(existing.student_id),
            "term_name": existing.term_name,
            "pdf_url": existing.pdf_url,
            "generated_at": str(existing.generated_at),
            "status": "pending"
        }
    
    # Check if we should re-generate or if it's new
    if existing:
        report = existing
        report.pdf_url = None # Set to none to indicate pending again
        await db.commit()
    else:
        report = ReportCard(student_id=resolved_student_id, term_name=resolved_term_name, pdf_url=None)
        db.add(report)
        await db.commit()
        await db.refresh(report)
        
    from app.modules.analytics.report_service import background_generate_report
    background_tasks.add_task(background_generate_report, report.id)

    return {
        "id": str(report.id),
        "student_id": str(report.student_id),
        "term_name": report.term_name,
        "pdf_url": report.pdf_url,
        "generated_at": str(report.generated_at),
        "status": "pending"
    }


@router.get("/reports/student/{student_id}")
async def list_student_reports(
    student_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all generated report cards for a student."""
    await _check_student_access(db, current_user, student_id)
    result = await db.execute(
        select(ReportCard).where(ReportCard.student_id == student_id).order_by(ReportCard.generated_at.desc())
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(report.id),
            "student_id": str(report.student_id),
            "term_name": report.term_name,
            "pdf_url": report.pdf_url,
            "generated_at": str(report.generated_at),
        }
        for report in reports
    ]


@router.get("/reports/{report_id}")
async def get_report_metadata(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Fetch report card metadata."""
    report = (await db.execute(select(ReportCard).where(ReportCard.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report card not found")
    await _check_student_access(db, current_user, report.student_id)
    return {
        "id": str(report.id),
        "student_id": str(report.student_id),
        "term_name": report.term_name,
        "pdf_url": report.pdf_url,
        "generated_at": str(report.generated_at),
    }


@router.get("/reports/{report_id}/download")
async def download_report_card(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Download a generated report card PDF."""
    report = (await db.execute(select(ReportCard).where(ReportCard.id == report_id))).scalar_one_or_none()
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

@router.post("/reports/bulk-generate")
async def generate_all_reports(
    background_tasks: BackgroundTasks,
    term_name: Optional[str] = Query(default=None),
    payload: Optional[ReportBulkRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """Generate report cards for all students accessible by the user."""
    from app.modules.analytics.report_service import background_generate_report
    resolved_term_name = term_name or (payload.term_name if payload else None)
    if not resolved_term_name:
        raise HTTPException(status_code=422, detail="term_name is required")

    student_ids = await _accessible_student_ids(db, current_user)
    if not student_ids:
        return {
            "total": 0,
            "generated": 0,
            "failed": 0,
            "results": [],
            "errors": [],
        }

    reports_to_queue = await _prepare_reports_for_generation(db, student_ids, resolved_term_name)

    results = []
    for sid, report_id in reports_to_queue:
        background_tasks.add_task(background_generate_report, report_id)
        results.append({"student_id": str(sid), "report_id": str(report_id), "status": "pending"})

    return {
        "total": len(student_ids),
        "generated": len(results),
        "failed": 0,
        "results": results,
        "errors": [],
    }


@router.post("/reports/stop-generation")
async def stop_report_generation(
    term_name: Optional[str] = Query(default=None),
    payload: Optional[ReportStopRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """
    Best-effort cancellation for pending report generation.
    Pending rows are removed; background tasks that haven't started will no-op.
    """
    resolved_term_name = term_name if term_name is not None else (payload.term_name if payload else None)
    student_ids = await _accessible_student_ids(db, current_user)
    if not student_ids:
        return {"cancelled": 0}

    conditions = [ReportCard.student_id.in_(student_ids), ReportCard.pdf_url.is_(None)]
    if resolved_term_name:
        conditions.append(ReportCard.term_name == resolved_term_name)

    try:
        delete_result = await db.execute(delete(ReportCard).where(*conditions))
        await db.commit()
        return {"cancelled": int(delete_result.rowcount or 0)}
    except Exception as exc:
        logger.exception("Failed stopping report generation")
        raise HTTPException(status_code=500, detail=f"Failed to stop generation: {exc}")


@router.post("/reports/generate-all")
async def generate_all_reports_legacy(
    background_tasks: BackgroundTasks,
    term_name: Optional[str] = Query(default=None),
    payload: Optional[ReportBulkRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER])),
) -> Any:
    """Backward-compatible alias for older frontend clients."""
    return await generate_all_reports(
        background_tasks=background_tasks,
        term_name=term_name,
        payload=payload,
        db=db,
        current_user=current_user,
    )
