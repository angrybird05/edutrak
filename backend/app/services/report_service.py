import logging
import os
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Class, Section, Subject
from app.models.performance import AIInsight, Attendance, Exam, Mark, ReportCard
from app.models.school import School
from app.models.student import Student
from app.models.user import User
from app.services.ai_service import LOW_ATTENDANCE_THRESHOLD
from app.services.ai_task_queue import ai_insight_task_queue

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = BACKEND_ROOT / "generated_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GTK_RUNTIME_BIN = Path(os.getenv("GTK_RUNTIME_BIN", str(BACKEND_ROOT / "_deps" / "gtk3-runtime" / "bin")))


class ReportCardService:
    @staticmethod
    def _prepare_weasyprint_runtime() -> None:
        if GTK_RUNTIME_BIN.exists():
            current_path = os.environ.get("PATH", "")
            if str(GTK_RUNTIME_BIN) not in current_path:
                os.environ["PATH"] = f"{GTK_RUNTIME_BIN};{current_path}"
            try:
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(str(GTK_RUNTIME_BIN))
            except Exception:
                logger.warning("Failed to add GTK runtime directory to DLL lookup path")

    @staticmethod
    def _grade_from_percentage(percentage: float) -> str:
        if percentage >= 90:
            return "A+"
        if percentage >= 80:
            return "A"
        if percentage >= 70:
            return "B"
        if percentage >= 60:
            return "C"
        if percentage >= 50:
            return "D"
        return "F"

    @staticmethod
    def _build_html(data: Dict[str, Any]) -> str:
        def e(value: Any) -> str:
            return escape(str(value if value is not None else ""))

        rows_html = "\n".join(
            f"""
            <tr>
              <td>{e(row['subject'])}</td>
              <td>{e(row['exam'])}</td>
              <td>{e(row['obtained_display'])}</td>
              <td>{e(row['max_display'])}</td>
              <td>{e(row['percentage_display'])}</td>
              <td>{e(row['comment'])}</td>
            </tr>
            """
            for row in data["marks_rows"]
        )

        strengths_html = "".join(f"<li>{e(s)}</li>" for s in data["ai"]["strengths"])
        weaknesses_html = "".join(f"<li>{e(w)}</li>" for w in data["ai"]["weaknesses"])
        recs_html = "".join(f"<li>{e(r)}</li>" for r in data["ai"]["recommendations"])

        risk_class = {
            "low": "risk-low",
            "medium": "risk-medium",
            "high": "risk-high",
        }.get(data["ai"]["risk_level"], "risk-medium")

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @page {{ size: A4; margin: 18mm; }}
    body {{ font-family: "DejaVu Sans", Arial, sans-serif; color: #1f2a37; font-size: 12px; }}
    .header {{ border-bottom: 2px solid #174b7a; padding-bottom: 8px; margin-bottom: 14px; }}
    .school {{ font-size: 20px; font-weight: 700; color: #174b7a; }}
    .meta {{ font-size: 11px; color: #445; margin-top: 4px; }}
    .student {{ margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }}
    .summary {{ margin: 14px 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
    .card {{ border: 1px solid #d5deea; border-radius: 6px; padding: 8px; background: #f8fbff; }}
    .label {{ font-size: 10px; color: #5a6b7f; text-transform: uppercase; }}
    .value {{ margin-top: 4px; font-size: 15px; font-weight: 700; color: #0f2942; }}
    .risk-low {{ color: #1e7a34; }}
    .risk-medium {{ color: #946200; }}
    .risk-high {{ color: #a80f22; }}
    h3 {{ margin: 12px 0 6px; font-size: 13px; color: #10395e; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    th, td {{ border: 1px solid #dce4ef; padding: 6px; vertical-align: top; }}
    th {{ background: #edf3fb; text-align: left; }}
    .ai {{ margin-top: 12px; border: 1px solid #cfdced; border-radius: 6px; padding: 10px; background: #f6faff; }}
    ul {{ margin: 6px 0 0 18px; padding: 0; }}
    .footer {{ margin-top: 18px; display: grid; grid-template-columns: 1fr 1fr; gap: 30px; font-size: 11px; }}
    .sign {{ border-top: 1px solid #8ca0b3; margin-top: 28px; padding-top: 4px; color: #47596b; }}
  </style>
</head>
<body>
  <div class="header">
    <div class="school">{e(data['school_name'])}</div>
    <div class="meta">Report Card | {e(data['term_name'])} | Generated: {e(data['generated_at'])}</div>
    <div class="student">
      <div><b>Student:</b> {e(data['student_name'])}</div>
      <div><b>Admission No:</b> {e(data['admission_number'])}</div>
      <div><b>Class/Section:</b> {e(data['class_name'])} - {e(data['section_name'])}</div>
      <div><b>Roll No:</b> {e(data['roll_number'] or '-')}</div>
    </div>
  </div>

  <div class="summary">
    <div class="card"><div class="label">Overall %</div><div class="value">{e(data['overall_percentage_display'])}</div></div>
    <div class="card"><div class="label">Grade</div><div class="value">{e(data['overall_grade'])}</div></div>
    <div class="card"><div class="label">Attendance</div><div class="value">{data['attendance_percentage']:.1f}%</div></div>
    <div class="card"><div class="label">Risk Level</div><div class="value {risk_class}">{e(data['ai']['risk_level'].upper())}</div></div>
  </div>
  <div><b>Missed Exams:</b> {data['absent_exam_count']}</div>

  <h3>Subject-Wise Performance</h3>
  <table>
    <thead>
      <tr>
        <th>Subject</th>
        <th>Exam</th>
        <th>Obtained</th>
        <th>Max</th>
        <th>%</th>
        <th>Teacher Remark</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <h3>Attendance</h3>
  <div>{data['present_days']}/{data['total_days']} days attended ({data['attendance_percentage']:.1f}%)</div>
  <div>{e(data['attendance_alert'])}</div>

  <div class="ai">
    <h3>AI Insight Summary</h3>
    <div>{e(data['ai']['summary'])}</div>
    <h3>Strengths</h3>
    <ul>{strengths_html}</ul>
    <h3>Areas to Improve</h3>
    <ul>{weaknesses_html}</ul>
    <h3>Action Plan</h3>
    <ul>{recs_html}</ul>
    <h3>Attendance Note</h3>
    <div>{e(data['ai']['attendance_note'])}</div>
  </div>

  <div class="footer">
    <div class="sign">Class Teacher Signature</div>
    <div class="sign">Principal Signature</div>
  </div>
</body>
</html>"""

    async def _collect_report_data(self, db: AsyncSession, student_id: UUID, term_name: str) -> Dict[str, Any]:
        student = await db.get(Student, student_id)
        if not student:
            raise ValueError("Student not found")

        user = await db.get(User, student.user_id)
        school = await db.get(School, student.school_id)
        class_obj = await db.get(Class, student.class_id)
        section = await db.get(Section, student.section_id)

        marks_query = (
            select(Mark, Subject.name.label("subject_name"), Exam.name.label("exam_name"))
            .join(Subject, Mark.subject_id == Subject.id)
            .join(Exam, Mark.exam_id == Exam.id)
            .where(Mark.student_id == student_id)
            .order_by(Exam.exam_date)
        )
        marks_rows_result = await db.execute(marks_query)
        mark_items = marks_rows_result.all()
        if not mark_items:
            raise ValueError("No marks available for this student")

        marks_rows: List[Dict[str, Any]] = []
        total_obtained = 0.0
        total_max = 0.0
        absent_exam_count = 0
        for mark, subject_name, exam_name in mark_items:
            mark_status = str(getattr(mark, "mark_status", "present") or "present").lower()
            is_absent = mark_status in {"absent", "exempt"}
            pct = (mark.marks_obtained / mark.max_marks * 100) if mark.max_marks and not is_absent else None
            if is_absent:
                absent_exam_count += 1

            marks_rows.append(
                {
                    "subject": subject_name,
                    "exam": exam_name,
                    "obtained": mark.marks_obtained,
                    "max": mark.max_marks,
                    "percentage": pct,
                    "obtained_display": "AB" if is_absent else f"{mark.marks_obtained:.1f}",
                    "max_display": "-" if is_absent else f"{mark.max_marks:.1f}",
                    "percentage_display": "-" if is_absent else f"{pct:.1f}%",
                    "comment": (mark.comments or ("Absent in exam" if is_absent else "-")),
                }
            )
            if not is_absent:
                total_obtained += mark.marks_obtained
                total_max += mark.max_marks
        overall_percentage = (total_obtained / total_max * 100) if total_max else None
        overall_percentage_display = f"{overall_percentage:.1f}%" if overall_percentage is not None else "N/A"
        overall_grade = self._grade_from_percentage(overall_percentage) if overall_percentage is not None else "N/A"

        total_days_query = select(func.count()).where(Attendance.student_id == student_id)
        present_days_query = select(func.count()).where(
            and_(Attendance.student_id == student_id, Attendance.status.in_(["Present", "Late"]))
        )
        total_days = (await db.execute(total_days_query)).scalar() or 0
        present_days = (await db.execute(present_days_query)).scalar() or 0
        attendance_percentage = (present_days / total_days * 100) if total_days else 0.0

        insight_result = await db.execute(select(AIInsight).where(AIInsight.student_id == student_id))
        insight = insight_result.scalar_one_or_none()
        if not insight:
            # Do not block report generation on slow model inference.
            await ai_insight_task_queue.enqueue_students([student_id])

        ai_data = insight.recommendations if insight and insight.recommendations else {}
        ai_payload = {
            "summary": ai_data.get("summary") or (insight.insight_text if insight else "No insight available."),
            "strengths": ai_data.get("strengths") or ["No strengths generated yet."],
            "weaknesses": ai_data.get("weaknesses") or ["No weaknesses generated yet."],
            "recommendations": ai_data.get("recommendations") or ["No recommendations generated yet."],
            "attendance_note": ai_data.get("attendance_note") or "No attendance note available.",
            "risk_level": str(ai_data.get("risk_level") or "medium").lower(),
        }

        attendance_alert = (
            f"Alert: Attendance is below threshold ({LOW_ATTENDANCE_THRESHOLD:.0f}%)."
            if attendance_percentage < LOW_ATTENDANCE_THRESHOLD
            else "Attendance is within healthy range."
        )

        return {
            "term_name": term_name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "student_name": user.full_name if user else "Unknown",
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "class_name": class_obj.name if class_obj else "-",
            "section_name": section.name if section else "-",
            "school_name": school.name if school else "School",
            "marks_rows": marks_rows,
            "overall_percentage": overall_percentage if overall_percentage is not None else 0.0,
            "overall_percentage_display": overall_percentage_display,
            "overall_grade": overall_grade,
            "total_days": total_days,
            "present_days": present_days,
            "attendance_percentage": attendance_percentage,
            "attendance_alert": attendance_alert,
            "absent_exam_count": absent_exam_count,
            "ai": ai_payload,
        }

    async def generate_report_card(self, db: AsyncSession, student_id: UUID, term_name: str) -> ReportCard:
        self._prepare_weasyprint_runtime()
        try:
            from weasyprint import HTML
        except Exception as e:
            raise RuntimeError(f"WeasyPrint is not available on this system: {e}")

        data = await self._collect_report_data(db, student_id, term_name)
        html_content = self._build_html(data)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"report_{student_id}_{timestamp}.pdf"
        pdf_path = REPORTS_DIR / filename
        HTML(string=html_content).write_pdf(target=str(pdf_path))

        report = ReportCard(
            student_id=student_id,
            term_name=term_name,
            pdf_url=str(pdf_path),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report


report_card_service = ReportCardService()
