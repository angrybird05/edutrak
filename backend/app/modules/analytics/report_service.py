import logging
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Class, School, Section, Subject
from app.modules.analytics.insights_v2.models import AIInsightV2
from app.modules.analytics.insights_v2.tasks import ai_insights_v2_task_queue
from app.modules.analytics.models import ReportCard
from app.modules.assessment.models import Attendance, Exam, Mark
from app.modules.identity.models import Student
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = BACKEND_ROOT / "generated_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
GTK_RUNTIME_BIN = Path(os.getenv("GTK_RUNTIME_BIN", str(BACKEND_ROOT / "_deps" / "gtk3-runtime" / "bin")))
LOW_ATTENDANCE_THRESHOLD = 75.0


class ReportCardService:
    @staticmethod
    def _normalize_list(values: Any) -> List[str]:
        if isinstance(values, list):
            cleaned = [str(item).strip() for item in values if item is not None and str(item).strip()]
            return cleaned
        return []

    @staticmethod
    def _build_fallback_ai_content(
        marks_rows: List[Dict[str, Any]],
        attendance_percentage: float,
        absent_exam_count: int,
        overall_percentage: float | None,
        term_name: str,
    ) -> Dict[str, Any]:
        present_rows = [row for row in marks_rows if row.get("percentage_val") is not None]
        sorted_rows = sorted(
            present_rows,
            key=lambda row: float(row.get("percentage_val") or 0.0),
            reverse=True,
        )
        top_rows = sorted_rows[:2]
        low_rows = [row for row in sorted_rows if float(row.get("percentage_val") or 0.0) < 50][:2]

        strengths: List[str] = []
        weaknesses: List[str] = []
        recommendations: List[str] = []

        for row in top_rows:
            pct = float(row.get("percentage_val") or 0.0)
            strengths.append(f"Strong performance in {row['subject']} ({pct:.1f}%).")

        if overall_percentage is not None and overall_percentage >= 70:
            strengths.append(f"Overall academic consistency is good in {term_name}.")

        if attendance_percentage >= 90:
            strengths.append(f"Excellent attendance at {attendance_percentage:.1f}% supports strong learning continuity.")
        elif attendance_percentage >= LOW_ATTENDANCE_THRESHOLD:
            strengths.append(f"Attendance is stable at {attendance_percentage:.1f}%.")

        for row in low_rows:
            pct = float(row.get("percentage_val") or 0.0)
            weaknesses.append(f"{row['subject']} needs improvement ({pct:.1f}%).")

        if overall_percentage is not None and overall_percentage < 50:
            weaknesses.append("Overall performance is below expected benchmark.")

        if attendance_percentage < LOW_ATTENDANCE_THRESHOLD:
            weaknesses.append(
                f"Attendance is low at {attendance_percentage:.1f}% and may impact performance."
            )

        if absent_exam_count > 0:
            weaknesses.append(f"Student was absent in {absent_exam_count} exam(s).")

        for row in low_rows:
            recommendations.append(
                f"Create a focused weekly revision plan for {row['subject']} and practice previous question patterns."
            )

        if attendance_percentage < LOW_ATTENDANCE_THRESHOLD:
            recommendations.append(
                "Improve attendance consistency with a daily schedule and guardian follow-up."
            )

        recommendations.append(
            "Set measurable targets for next assessment and review progress with class teacher weekly."
        )

        summary_parts: List[str] = []
        if overall_percentage is not None:
            summary_parts.append(
                f"In {term_name}, the student scored an overall {overall_percentage:.1f}%."
            )
        else:
            summary_parts.append(
                f"In {term_name}, marks are partially available; performance is evaluated from recorded subjects."
            )
        summary_parts.append(f"Attendance is {attendance_percentage:.1f}%.")
        if top_rows:
            summary_parts.append(
                "Best performance areas: "
                + ", ".join(f"{row['subject']} ({float(row.get('percentage_val') or 0.0):.1f}%)" for row in top_rows)
                + "."
            )
        if low_rows:
            summary_parts.append(
                "Immediate improvement needed in: "
                + ", ".join(row["subject"] for row in low_rows)
                + "."
            )
        if absent_exam_count > 0:
            summary_parts.append(f"Absence recorded in {absent_exam_count} exam(s).")

        if not strengths:
            strengths = ["Steady engagement observed in available assessments."]
        if not weaknesses:
            weaknesses = ["No critical weaknesses identified from current records."]
        if not recommendations:
            recommendations = ["Continue regular revision and periodic performance review."]

        return {
            "summary": " ".join(summary_parts),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
        }

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
    def _grade_color(grade: str) -> str:
        colors = {
            "A+": "#059669", "A": "#10b981", "B": "#3b82f6",
            "C": "#f59e0b", "D": "#ef4444", "F": "#dc2626", "N/A": "#6b7280",
        }
        return colors.get(grade, "#6b7280")

    @staticmethod
    def _attendance_color(pct: float) -> str:
        if pct >= 90:
            return "#059669"
        if pct >= 75:
            return "#f59e0b"
        return "#ef4444"

    @staticmethod
    def _build_html(data: Dict[str, Any]) -> str:
        def e(value: Any) -> str:
            return escape(str(value if value is not None else ""))

        # Build subject rows
        rows_html = ""
        for i, row in enumerate(data["marks_rows"]):
            bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
            pct_val = row.get("percentage_val")
            bar_color = "#3b82f6"
            if pct_val is not None:
                if pct_val >= 80:
                    bar_color = "#059669"
                elif pct_val >= 60:
                    bar_color = "#3b82f6"
                elif pct_val >= 40:
                    bar_color = "#f59e0b"
                else:
                    bar_color = "#ef4444"
            bar_width = pct_val if pct_val is not None else 0
            rows_html += f"""
            <tr style="background:{bg};">
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;font-weight:500;color:#1e293b;">{e(row['subject'])}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#475569;text-align:center;">{e(row['obtained_display'])}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#475569;text-align:center;">{e(row['max_display'])}</td>
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:center;">
                <span style="font-weight:700;color:{bar_color};">{e(row['percentage_display'])}</span>
              </td>
              <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;color:#64748b;font-style:italic;font-size:11px;">{e(row['comment'])}</td>
            </tr>
            """

        # Build AI sections
        strengths_html = "".join(
            f'<li style="margin-bottom:6px;color:#166534;"><span style="display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:8px;"></span>{e(s)}</li>'
            for s in data["ai"]["strengths"]
        )
        weaknesses_html = "".join(
            f'<li style="margin-bottom:6px;color:#9a3412;"><span style="display:inline-block;width:8px;height:8px;background:#f97316;border-radius:50%;margin-right:8px;"></span>{e(w)}</li>'
            for w in data["ai"]["weaknesses"]
        )
        recs_html = "".join(
            f'<li style="margin-bottom:6px;color:#1e40af;"><span style="display:inline-block;width:8px;height:8px;background:#3b82f6;border-radius:50%;margin-right:8px;"></span>{e(r)}</li>'
            for r in data["ai"]["recommendations"]
        )

        grade_color = ReportCardService._grade_color(data["overall_grade"])
        att_color = ReportCardService._attendance_color(data["attendance_percentage"])

        school_address = data.get("school_address", "")
        school_email = data.get("school_email", "")
        school_district = data.get("school_district", "")
        school_pincode = data.get("school_pincode", "")

        address_parts = [p for p in [school_address, school_district, school_pincode] if p]
        address_line = ", ".join(address_parts) if address_parts else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @page {{ size: A4; margin: 0; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      color: #1e293b;
      font-size: 12px;
      line-height: 1.5;
      background: #ffffff;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
    }}
    .page-container {{
      padding: 0;
      position: relative;
      min-height: 297mm;
    }}

    /* ── Decorative top bar ── */
    .top-bar {{
      height: 8px;
      background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f97316, #3b82f6);
      background-size: 200% 100%;
    }}

    /* ── Header / School Info ── */
    .school-header {{
      background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #7c3aed 100%);
      color: white;
      padding: 20px 30px 18px;
      display: flex;
      align-items: center;
      gap: 18px;
    }}
    .school-logo {{
      width: 70px;
      height: 70px;
      background: rgba(255,255,255,0.2);
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      font-weight: 800;
      color: #fff;
      flex-shrink: 0;
      border: 2px solid rgba(255,255,255,0.3);
    }}
    .school-info {{
      flex: 1;
    }}
    .school-name {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 0.5px;
      text-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }}
    .school-tagline {{
      font-size: 11px;
      opacity: 0.85;
      margin-top: 2px;
    }}
    .school-contact {{
      font-size: 10px;
      opacity: 0.75;
      margin-top: 4px;
    }}
    .report-badge {{
      background: rgba(255,255,255,0.2);
      border: 1px solid rgba(255,255,255,0.3);
      border-radius: 12px;
      padding: 10px 16px;
      text-align: center;
      flex-shrink: 0;
    }}
    .report-badge-title {{
      font-size: 14px;
      font-weight: 700;
      letter-spacing: 1px;
    }}
    .report-badge-term {{
      font-size: 10px;
      opacity: 0.85;
      margin-top: 2px;
    }}

    /* ── Student Info Strip ── */
    .student-strip {{
      background: #f1f5f9;
      border-bottom: 2px solid #e2e8f0;
      padding: 14px 30px;
      display: grid;
      grid-template-columns: 1fr 1fr 1fr 1fr;
      gap: 8px;
    }}
    .student-field {{
      display: flex;
      flex-direction: column;
    }}
    .student-label {{
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #94a3b8;
      font-weight: 600;
    }}
    .student-value {{
      font-size: 13px;
      font-weight: 600;
      color: #1e293b;
      margin-top: 2px;
    }}

    /* ── Metrics Cards ── */
    .metrics-row {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr 1fr;
      gap: 12px;
      padding: 16px 30px;
    }}
    .metric-card {{
      border-radius: 12px;
      padding: 14px 16px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}
    .metric-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
    }}
    .metric-label {{
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 1px;
      font-weight: 600;
      margin-bottom: 4px;
    }}
    .metric-value {{
      font-size: 24px;
      font-weight: 800;
    }}
    .metric-sub {{
      font-size: 10px;
      margin-top: 2px;
    }}

    /* ── Subject Table ── */
    .section-title {{
      padding: 12px 30px 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .section-icon {{
      width: 28px;
      height: 28px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }}
    .section-text {{
      font-size: 14px;
      font-weight: 700;
      color: #1e293b;
    }}

    .marks-table {{
      width: calc(100% - 60px);
      margin: 0 30px;
      border-collapse: collapse;
      border-radius: 10px;
      overflow: hidden;
      border: 1px solid #e2e8f0;
    }}
    .marks-table th {{
      background: linear-gradient(135deg, #1e3a5f, #2563eb);
      color: white;
      text-align: left;
      padding: 10px 14px;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      font-weight: 700;
    }}

    /* ── AI Comment Section ── */
    .ai-section {{
      margin: 14px 30px;
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid #e0e7ff;
    }}
    .ai-header {{
      background: linear-gradient(135deg, #4f46e5, #7c3aed);
      color: white;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .ai-header-icon {{
      width: 30px;
      height: 30px;
      background: rgba(255,255,255,0.2);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
    }}
    .ai-header-text {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .ai-body {{
      background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%);
      padding: 16px 18px;
    }}
    .ai-summary {{
      font-size: 12px;
      color: #3730a3;
      background: rgba(99,102,241,0.08);
      border-left: 3px solid #6366f1;
      padding: 10px 14px;
      border-radius: 0 8px 8px 0;
      margin-bottom: 14px;
      line-height: 1.6;
    }}
    .ai-columns {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 12px;
    }}
    .ai-column {{
      border-radius: 10px;
      padding: 12px;
    }}
    .ai-column-title {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      font-weight: 700;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .ai-column ul {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    .ai-column li {{
      font-size: 11px;
      line-height: 1.5;
      display: flex;
      align-items: flex-start;
    }}

    /* ── Footer ── */
    .footer {{
      margin-top: 12px;
      padding: 14px 30px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      border-top: 2px solid #e2e8f0;
    }}
    .footer-left {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .signature-box {{
      text-align: center;
    }}
    .signature-line {{
      width: 120px;
      border-bottom: 1px solid #94a3b8;
      margin-bottom: 4px;
      height: 30px;
    }}
    .signature-label {{
      font-size: 9px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .footer-generated {{
      font-size: 9px;
      color: #94a3b8;
      text-align: right;
    }}

    /* ── Decorative bottom bar ── */
    .bottom-bar {{
      height: 6px;
      background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #f97316, #3b82f6);
      background-size: 200% 100%;
    }}

    /* ── Decorative children icons ── */
    .child-icons {{
      display: flex;
      gap: 6px;
      align-items: center;
    }}
    .child-icon {{
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
    }}
  </style>
</head>
<body>
  <div class="page-container">
    <!-- Top decorative bar -->
    <div class="top-bar"></div>

    <!-- ── School Header ── -->
    <div class="school-header">
      <div class="school-logo">
        {e(data['school_name'][:2].upper())}
      </div>
      <div class="school-info">
        <div class="school-name">{e(data['school_name'])}</div>
        <div class="school-tagline">Nurturing Minds, Shaping Futures ✨</div>
        <div class="school-contact">
          {f'📍 {e(address_line)}' if address_line else ''}
          {f' &nbsp;|&nbsp; 📧 {e(school_email)}' if school_email else ''}
        </div>
      </div>
      <div class="report-badge">
        <div class="report-badge-title">📋 REPORT CARD</div>
        <div class="report-badge-term">{e(data['term_name'])}</div>
      </div>
    </div>

    <!-- ── Student Info ── -->
    <div class="student-strip">
      <div class="student-field">
        <span class="student-label">👤 Student Name</span>
        <span class="student-value">{e(data['student_name'])}</span>
      </div>
      <div class="student-field">
        <span class="student-label">🏫 Class / Section</span>
        <span class="student-value">{e(data['class_name'])} - {e(data['section_name'])}</span>
      </div>
      <div class="student-field">
        <span class="student-label">🔢 Admission No</span>
        <span class="student-value">{e(data['admission_number'])}</span>
      </div>
      <div class="student-field">
        <span class="student-label">📝 Roll No</span>
        <span class="student-value">{e(data['roll_number'] or '-')}</span>
      </div>
    </div>

    <!-- ── Metrics Cards ── -->
    <div class="metrics-row">
      <div class="metric-card" style="background:linear-gradient(135deg,#ecfdf5,#d1fae5);border:1px solid #a7f3d0;">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;background:#059669;border-radius:12px 12px 0 0;"></div>
        <div class="metric-label" style="color:#065f46;">Overall Score</div>
        <div class="metric-value" style="color:#059669;">{e(data['overall_percentage_display'])}</div>
        <div class="metric-sub" style="color:#047857;">🎯 Cumulative Average</div>
      </div>
      <div class="metric-card" style="background:linear-gradient(135deg,#f0f9ff,#dbeafe);border:1px solid #93c5fd;">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{grade_color};border-radius:12px 12px 0 0;"></div>
        <div class="metric-label" style="color:#1e40af;">Grade</div>
        <div class="metric-value" style="color:{grade_color};">{e(data['overall_grade'])}</div>
        <div class="metric-sub" style="color:#2563eb;">📚 Performance Grade</div>
      </div>
      <div class="metric-card" style="background:linear-gradient(135deg,#fefce8,#fef9c3);border:1px solid #fde68a;">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{att_color};border-radius:12px 12px 0 0;"></div>
        <div class="metric-label" style="color:#92400e;">Attendance</div>
        <div class="metric-value" style="color:{att_color};">{data['attendance_percentage']:.1f}%</div>
        <div class="metric-sub" style="color:#a16207;">📅 {data.get('present_days', 0)}/{data.get('total_days', 0)} Days</div>
      </div>
      <div class="metric-card" style="background:linear-gradient(135deg,#fdf2f8,#fce7f3);border:1px solid #fbcfe8;">
        <div style="position:absolute;top:0;left:0;right:0;height:3px;background:#ec4899;border-radius:12px 12px 0 0;"></div>
        <div class="metric-label" style="color:#9d174d;">Exams Missed</div>
        <div class="metric-value" style="color:#ec4899;">{data['absent_exam_count']}</div>
        <div class="metric-sub" style="color:#be185d;">⚠️ Absent Count</div>
      </div>
    </div>

    <!-- ── Subject Performance Table ── -->
    <div class="section-title">
      <div class="section-icon" style="background:#dbeafe;color:#2563eb;">📊</div>
      <span class="section-text">Subject-Wise Performance</span>
      <span style="margin-left:auto;font-size:10px;color:#94a3b8;">{len(data['marks_rows'])} records</span>
    </div>
    <table class="marks-table">
      <thead>
        <tr>
          <th style="width:25%;">Subject</th>
          <th style="width:15%;text-align:center;">Obtained</th>
          <th style="width:15%;text-align:center;">Maximum</th>
          <th style="width:15%;text-align:center;">Percentage</th>
          <th style="width:30%;">Teacher Remark</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>

    <!-- ── AI Insights Section ── -->
    <div class="ai-section">
      <div class="ai-header">
        <div class="ai-header-icon">🤖</div>
        <div>
          <div class="ai-header-text">AI-Powered Student Analysis</div>
          <div style="font-size:10px;opacity:0.8;">Personalized insights generated by EduTrack AI</div>
        </div>
        <div class="child-icons" style="margin-left:auto;">
          <span class="child-icon" style="background:rgba(255,255,255,0.2);">👦</span>
          <span class="child-icon" style="background:rgba(255,255,255,0.2);">👧</span>
          <span class="child-icon" style="background:rgba(255,255,255,0.2);">📖</span>
          <span class="child-icon" style="background:rgba(255,255,255,0.2);">🎓</span>
        </div>
      </div>
      <div class="ai-body">
        <div class="ai-summary">{e(data['ai']['summary'])}</div>
        <div class="ai-columns">
          <div class="ai-column" style="background:#ecfdf5;border:1px solid #bbf7d0;">
            <div class="ai-column-title" style="color:#166534;">✅ Strengths</div>
            <ul>{strengths_html}</ul>
          </div>
          <div class="ai-column" style="background:#fff7ed;border:1px solid #fed7aa;">
            <div class="ai-column-title" style="color:#9a3412;">⚡ Areas to Improve</div>
            <ul>{weaknesses_html}</ul>
          </div>
          <div class="ai-column" style="background:#eff6ff;border:1px solid #bfdbfe;">
            <div class="ai-column-title" style="color:#1e40af;">🚀 Action Plan</div>
            <ul>{recs_html}</ul>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Footer with Signatures ── -->
    <div class="footer">
      <div class="footer-left">
        <div class="signature-box">
          <div class="signature-line"></div>
          <div class="signature-label">Class Teacher</div>
        </div>
        <div class="signature-box">
          <div class="signature-line"></div>
          <div class="signature-label">Principal</div>
        </div>
        <div class="signature-box">
          <div class="signature-line"></div>
          <div class="signature-label">Parent / Guardian</div>
        </div>
      </div>
      <div class="footer-generated">
        <div style="color:#64748b;font-size:10px;font-weight:600;">EduTrack</div>
        <div>Generated: {e(data['generated_at'])}</div>
        <div style="margin-top:2px;">This is a computer-generated report</div>
      </div>
    </div>

    <!-- Bottom decorative bar -->
    <div class="bottom-bar"></div>
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
        mark_items = (await db.execute(marks_query)).all()
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
            else:
                total_obtained += mark.marks_obtained
                total_max += mark.max_marks

            marks_rows.append(
                {
                    "subject": subject_name,
                    "exam": exam_name,
                    "obtained_display": "AB" if is_absent else f"{mark.marks_obtained:.1f}",
                    "max_display": "-" if is_absent else f"{mark.max_marks:.1f}",
                    "percentage_display": "-" if is_absent or pct is None else f"{pct:.1f}%",
                    "percentage_val": round(pct, 1) if pct is not None else None,
                    "comment": mark.comments or ("Absent in exam" if is_absent else "-"),
                }
            )

        overall_percentage = (total_obtained / total_max * 100) if total_max else None
        overall_percentage_display = f"{overall_percentage:.1f}%" if overall_percentage is not None else "N/A"
        overall_grade = self._grade_from_percentage(overall_percentage) if overall_percentage is not None else "N/A"

        total_days = (await db.execute(select(func.count()).where(Attendance.student_id == student_id))).scalar() or 0
        present_days = (
            await db.execute(
                select(func.count()).where(
                    and_(Attendance.student_id == student_id, Attendance.status.in_(["Present", "Late"]))
                )
            )
        ).scalar() or 0
        attendance_percentage = (present_days / total_days * 100) if total_days else 0.0

        exam_for_term = (
            await db.execute(
                select(Exam.id)
                .where(
                    Exam.section_id == student.section_id,
                    Exam.name == term_name,
                )
                .order_by(Exam.exam_date.desc().nulls_last(), Exam.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        insight_v2 = None
        if exam_for_term:
            insight_v2 = (
                await db.execute(
                    select(AIInsightV2).where(
                        AIInsightV2.student_id == student_id,
                        AIInsightV2.exam_id == exam_for_term,
                        AIInsightV2.status == "completed",
                    )
                )
            ).scalar_one_or_none()
            if not insight_v2:
                await ai_insights_v2_task_queue.enqueue_students_for_exam(
                    exam_id=exam_for_term,
                    student_ids=[student_id],
                    model_version="v2.0",
                )

        ai_data = insight_v2.recommendations_json if insight_v2 and insight_v2.recommendations_json else {}
        fallback_ai = self._build_fallback_ai_content(
            marks_rows=marks_rows,
            attendance_percentage=attendance_percentage,
            absent_exam_count=absent_exam_count,
            overall_percentage=overall_percentage,
            term_name=term_name,
        )

        ai_strengths = self._normalize_list(ai_data.get("strengths"))
        ai_weaknesses = self._normalize_list(ai_data.get("weaknesses"))
        ai_recommendations = (
            self._normalize_list(ai_data.get("recommendations"))
            or self._normalize_list(ai_data.get("improvement_suggestions"))
            or self._normalize_list(ai_data.get("study_plan"))
        )
        ai_summary = str(ai_data.get("summary") or "").strip() or (str(insight_v2.insight_text).strip() if insight_v2 and insight_v2.insight_text else "")

        return {
            "term_name": term_name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "student_name": user.full_name if user else "Unknown",
            "admission_number": student.admission_number,
            "roll_number": student.roll_number,
            "class_name": class_obj.name if class_obj else "-",
            "section_name": section.name if section else "-",
            "school_name": school.name if school else "School",
            "school_address": school.address if school else "",
            "school_email": school.email if school else "",
            "school_district": school.district_city if school else "",
            "school_pincode": school.pincode if school else "",
            "marks_rows": marks_rows,
            "overall_percentage_display": overall_percentage_display,
            "overall_grade": overall_grade,
            "attendance_percentage": attendance_percentage,
            "present_days": present_days,
            "total_days": total_days,
            "absent_exam_count": absent_exam_count,
            "ai": {
                "summary": ai_summary or fallback_ai["summary"],
                "strengths": ai_strengths or fallback_ai["strengths"],
                "weaknesses": ai_weaknesses or fallback_ai["weaknesses"],
                "recommendations": ai_recommendations or fallback_ai["recommendations"],
            },
        }

    async def get_report_html(self, db: AsyncSession, student_id: UUID, term_name: str) -> str:
        """Return the rendered HTML for a report card (for in-browser preview)."""
        data = await self._collect_report_data(db, student_id, term_name)
        return self._build_html(data)

    async def process_report_card(self, db: AsyncSession, report: ReportCard) -> ReportCard:
        import asyncio

        self._prepare_weasyprint_runtime()
        try:
            from weasyprint import HTML
        except Exception as exc:
            raise RuntimeError(f"WeasyPrint is not available on this system: {exc}")

        data = await self._collect_report_data(db, report.student_id, report.term_name)
        html_content = self._build_html(data)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pdf_path = REPORTS_DIR / f"report_{report.student_id}_{timestamp}.pdf"
        
        def _write_pdf():
            HTML(string=html_content).write_pdf(target=str(pdf_path))

        await asyncio.to_thread(_write_pdf)

        report.pdf_url = str(pdf_path)
        report.generated_at = datetime.now(timezone.utc)
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

async def background_generate_report(report_id: UUID) -> None:
    """Background task to generate PDF for a pending report card."""
    from app.shared.db.session import SessionLocal
    async with SessionLocal() as db:
        report = await db.get(ReportCard, report_id)
        if not report:
            return
        try:
            await report_card_service.process_report_card(db, report)
        except Exception as e:
            logger.error(f"Failed to generate report {report_id} in background: {e}")

report_card_service = ReportCardService()
