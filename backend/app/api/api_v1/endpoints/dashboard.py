from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.academic import Class, Section, Subject, teacher_section
from app.models.performance import AIInsight, Attendance, Mark, ReportCard, LearningTask
from app.models.scale_foundation import NotificationEvent, UserNotification
from app.models.student import Student, parent_student
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/admin")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.ADMIN)),
) -> Any:
    school_filter = Student.school_id == current_user.school_id if current_user.school_id else True

    # Initial counts
    students_count = (await db.execute(select(func.count()).select_from(Student).where(school_filter))).scalar_one()
    teachers_count = (await db.execute(select(func.count()).select_from(User).where(User.role == UserRole.TEACHER, User.school_id == current_user.school_id if current_user.school_id else True))).scalar_one()
    parents_count = (await db.execute(select(func.count()).select_from(User).where(User.role == UserRole.PARENT, User.school_id == current_user.school_id if current_user.school_id else True))).scalar_one()
    classes_count = (await db.execute(select(func.count()).select_from(Class).where(Class.school_id == current_user.school_id if current_user.school_id else True))).scalar_one()
    sections_count = (await db.execute(select(func.count()).select_from(Section))).scalar_one()
    subjects_count = (await db.execute(select(func.count()).select_from(Subject).where(Subject.school_id == current_user.school_id if current_user.school_id else True))).scalar_one()

    # Trends: Monthly performance average (last 6 months)
    six_months_ago = func.now() - func.cast("6 months", func.interval)
    trends_stmt = (
        select(
            func.date_trunc("month", Mark.created_at).label("month"),
            func.avg((Mark.marks_obtained / Mark.max_marks) * 100).label("avg_score")
        )
        .join(Student, Mark.student_id == Student.id)
        .where(
            school_filter,
            Mark.mark_status == "present",
            Mark.created_at >= six_months_ago
        )
        .group_by(func.date_trunc("month", Mark.created_at))
        .order_by(func.date_trunc("month", Mark.created_at).asc())
    )
    trends_rows = (await db.execute(trends_stmt)).all()
    monthly_trends = [
        {"month": str(row.month.date()) if row.month else "N/A", "score": round(float(row.avg_score), 1) if row.avg_score else 0.0}
        for row in trends_rows
    ]

    # Subject-wise Averages
    subj_avg_stmt = (
        select(
            Subject.name,
            func.avg((Mark.marks_obtained / Mark.max_marks) * 100).label("avg_score")
        )
        .join(Mark, Mark.subject_id == Subject.id)
        .join(Student, Mark.student_id == Student.id)
        .where(school_filter, Mark.mark_status == "present")
        .group_by(Subject.name)
        .order_by(Subject.name.asc())
    )
    subj_rows = (await db.execute(subj_avg_stmt)).all()
    subject_averages = {row.name: round(float(row.avg_score), 1) for row in subj_rows}

    # At-Risk Stats (Risk Distribution)
    risk_stmt = select(
        case(
            (Mark.marks_obtained / Mark.max_marks < 0.4, "high"),
            (Mark.marks_obtained / Mark.max_marks < 0.6, "medium"),
            else_="low"
        ).label("risk_level"),
        func.count(func.distinct(Mark.student_id))
    ).join(Student, Mark.student_id == Student.id).where(school_filter).group_by(literal_column("risk_level"))
    
    risk_rows = (await db.execute(risk_stmt)).all()
    risk_distribution = {row[0]: row[1] for row in risk_rows}

    # Aggregate stats for top-level cards
    overall_att_stmt = select(
        func.count().label("total"),
        func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present")
    ).join(Student, Attendance.student_id == Student.id).where(school_filter)
    overall_att = (await db.execute(overall_att_stmt)).one()
    att_rate = round((overall_att.present / overall_att.total) * 100, 1) if overall_att.total else 0.0

    return {
        "status": "success",
        "counts": {
            "students": students_count,
            "teachers": teachers_count,
            "parents": parents_count,
            "classes": classes_count,
            "sections": sections_count,
            "subjects": subjects_count,
        },
        "metrics": {
            "average_performance": round(float(sum(subject_averages.values()) / len(subject_averages)), 1) if subject_averages else 0.0,
            "attendance_rate": att_rate,
            "at_risk_count": risk_distribution.get("high", 0),
        },
        "charts": {
            "monthly_performance": monthly_trends,
            "subject_performance": subject_averages,
            "risk_distribution": risk_distribution,
        }
    }


@router.get("/student/me")
async def student_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.STUDENT)),
) -> Any:
    student_result = await db.execute(select(Student).where(Student.user_id == current_user.id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    avg_marks = (
        await db.execute(
            select(func.avg(Mark.marks_obtained)).where(
                Mark.student_id == student.id, Mark.mark_status == "present"
            )
        )
    ).scalar()
    total_days = (
        await db.execute(select(func.count()).select_from(Attendance).where(Attendance.student_id == student.id))
    ).scalar_one()
    present_days = (
        await db.execute(
            select(func.count()).select_from(Attendance).where(
                Attendance.student_id == student.id, Attendance.status == "Present"
            )
        )
    ).scalar_one()
    insight_result = await db.execute(select(AIInsight).where(AIInsight.student_id == student.id))
    insight = insight_result.scalar_one_or_none()
    latest_report = (
        await db.execute(
            select(ReportCard)
            .where(ReportCard.student_id == student.id)
            .order_by(ReportCard.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    attendance_pct = round((present_days / total_days) * 100, 2) if total_days else 0.0
    
    # Calculate status orb
    status_orb = "green"
    if (avg_marks is not None and avg_marks < 40) or (attendance_pct < 75):
        status_orb = "red"
    elif (avg_marks is not None and avg_marks < 60) or (attendance_pct < 85):
        status_orb = "yellow"

    # Best/Weakest subject
    subject_marks = await db.execute(
        select(Subject.name, func.avg(Mark.marks_obtained))
        .join(Mark, Mark.subject_id == Subject.id)
        .where(Mark.student_id == student.id)
        .group_by(Subject.name)
        .order_by(func.avg(Mark.marks_obtained).desc())
    )
    subject_stats = subject_marks.all()
    best_subject = subject_stats[0][0] if subject_stats else None
    weakest_subject = subject_stats[-1][0] if subject_stats else None

    return {
        "student_id": student.id,
        "full_name": current_user.full_name,
        "status_orb": status_orb,
        "average_marks": round(float(avg_marks), 2) if avg_marks is not None else None,
        "attendance_percentage": attendance_pct,
        "best_subject": best_subject,
        "weakest_subject": weakest_subject,
        "latest_ai_summary": insight.insight_text if insight else None,
        "latest_report": {
            "id": latest_report.id,
            "term_name": latest_report.term_name,
            "generated_at": latest_report.generated_at,
            "pdf_url": latest_report.pdf_url,
        }
        if latest_report
        else None,
    }

@router.get("/teacher/me")
async def teacher_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.TEACHER)),
) -> Any:
    """
    Aggregate dashboard for teachers showing their assigned sections and at-risk students.
    """
    # 1. Get assigned sections
    sections_query = select(Section).join(teacher_section, teacher_section.c.section_id == Section.id).where(
        teacher_section.c.teacher_id == current_user.id
    )
    sections_result = await db.execute(sections_query)
    sections = sections_result.scalars().all()
    
    section_ids = [s.id for s in sections]
    
    # 2. Section Stats (Student count, Avg marks)
    section_stats = []
    total_students = 0
    at_risk_count = 0
    
    for section in sections:
        # Student count in this section
        s_count = (await db.execute(
            select(func.count()).select_from(Student).where(Student.section_id == section.id)
        )).scalar_one()
        total_students += s_count
        
        # Section average marks
        s_avg = (await db.execute(
            select(func.avg(Mark.marks_obtained))
            .join(Student, Student.id == Mark.student_id)
            .where(Student.section_id == section.id, Mark.mark_status == "present")
        )).scalar()
        
        # At-risk students in this section (Marks < 40 or Attendance < 75)
        # Using a subquery for efficiency
        at_risk_query = select(Student.id).where(Student.section_id == section.id)
        # Simplified for now: just count students with any mark < 40 in this section
        at_risk_marks = (await db.execute(
            select(func.count(func.distinct(Student.id)))
            .join(Mark, Mark.student_id == Student.id)
            .where(Student.section_id == section.id, Mark.marks_obtained < 40)
        )).scalar_one()
        
        at_risk_count += at_risk_marks # Rough estimate
        
        section_stats.append({
            "section_id": section.id,
            "section_name": section.name,
            "student_count": s_count,
            "average_marks": round(float(s_avg), 2) if s_avg else None,
            "at_risk_count": at_risk_marks
        })

    # 3. Today's schedule (placeholder logic until Timetable logic is deeper)
    # Get attendance rate for their classes
    total_attendance = (await db.execute(
        select(
            func.count().label("total"),
            func.sum(case((Attendance.status == "Present", 1), else_=0)).label("present")
        )
        .join(Student, Student.id == Attendance.student_id)
        .where(Student.section_id.in_(section_ids))
    )).first()
    
    att_pct = 0.0
    if total_attendance and total_attendance.total:
        att_pct = round((total_attendance.present / total_attendance.total) * 100, 2)

    return {
        "teacher_name": current_user.full_name,
        "total_students": total_students,
        "at_risk_students": at_risk_count,
        "overall_attendance_rate": att_pct,
        "sections": section_stats
    }


@router.get("/parent/me")
async def parent_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.PARENT)),
) -> Any:
    # Get linked children IDs
    children_result = await db.execute(
        select(Student).join(parent_student, parent_student.c.student_id == Student.id).where(
            parent_student.c.parent_id == current_user.id
        )
    )
    children = children_result.scalars().all()
    if not children:
        return {"children_count": 0, "children": [], "kpis": {}, "recent_alerts": []}

    child_ids = [child.id for child in children]

    # --- FIX N+1: Single aggregated query for marks ---
    marks_stats = await db.execute(
        select(
            Mark.student_id,
            func.avg(Mark.marks_obtained).label("avg_marks"),
        )
        .where(Mark.student_id.in_(child_ids), Mark.mark_status == "present")
        .group_by(Mark.student_id)
    )
    marks_map = {row.student_id: float(row.avg_marks) if row.avg_marks is not None else None for row in marks_stats}

    # --- FIX N+1: Single aggregated query for attendance ---
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
        row.student_id: {
            "total": int(row.total_days or 0),
            "present": int(row.present_days or 0),
        }
        for row in attendance_stats
    }

    # --- FIX N+1: Single query for latest reports (using window function) ---
    latest_reports_result = await db.execute(
        select(ReportCard)
        .where(ReportCard.student_id.in_(child_ids))
        .order_by(ReportCard.student_id, ReportCard.generated_at.desc())
        .distinct(ReportCard.student_id)
    )
    report_map = {r.student_id: r for r in latest_reports_result.scalars().all()}

    # Build summaries from the pre-fetched maps
    summaries = []
    low_grade_children = 0
    low_attendance_children = 0
    for child in children:
        avg_marks = marks_map.get(child.id)
        att = attendance_map.get(child.id, {"total": 0, "present": 0})
        attendance_pct = round((att["present"] / att["total"]) * 100, 2) if att["total"] else 0.0

        if avg_marks is not None and avg_marks < 40:
            low_grade_children += 1
        if att["total"] and attendance_pct < 75:
            low_attendance_children += 1

        latest_report = report_map.get(child.id)
        summaries.append(
            {
                "student_id": child.id,
                "average_marks": round(avg_marks, 2) if avg_marks is not None else None,
                "attendance_percentage": attendance_pct,
                "latest_report_id": latest_report.id if latest_report else None,
            }
        )

    # Recent alerts (single query, already efficient)
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
            "read_at": row.read_at,
            "created_at": row.created_at,
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
