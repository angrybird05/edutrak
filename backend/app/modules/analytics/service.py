"""
Analytics module service — AI Insight Engine.

Migrated from app/services/ai_service.py. Contains the core AI insight
generation logic using Ollama.
"""
import httpx
import json
import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from dotenv import load_dotenv

from app.modules.assessment.models import Mark, Attendance, Exam
from app.modules.academic.models import Subject
from app.modules.identity.models import Student
from app.modules.analytics.models import AIInsight
from app.services.ai_prompts import (
    ROLE_STUDENT_COACH, ROLE_FAILURE_PREDICTOR, ROLE_PARENT_LIAISON,
    ROLE_ADMIN_ANALYST, FEATURE_STUDY_PLAN, FEATURE_RISK_PREDICTION,
    FEATURE_PARENT_REPORT, FEATURE_PARENT_REPORT_STRUCTURED,
    MULTILINGUAL_WRAPPER,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(BACKEND_ROOT / ".env")


def _parse_model_list(raw: str) -> List[str]:
    return [model.strip() for model in raw.split(",") if model.strip()]


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_FALLBACK_MODELS = _parse_model_list(
    os.getenv("OLLAMA_FALLBACK_MODELS", "llama3.2:3b,phi3:mini")
)
LOW_ATTENDANCE_THRESHOLD = 75.0


class RiskPredictionSchema(BaseModel):
    overall_risk_score: int
    risk_category: Literal["low", "medium", "high"]
    at_risk_subjects: List[Dict[str, str]]
    primary_driver: str
    predicted_failure_subjects: List[str]
    confidence_level: str


class AIInsightService:
    @staticmethod
    async def _collect_student_data(db: AsyncSession, student_id: UUID) -> Dict[str, Any]:
        """Gather all performance data for a student."""
        student = await db.get(Student, student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found")

        marks_query = (
            select(Mark, Subject.name.label("subject_name"), Exam.name.label("exam_name"))
            .join(Subject, Mark.subject_id == Subject.id)
            .join(Exam, Mark.exam_id == Exam.id)
            .where(Mark.student_id == student_id)
            .order_by(Exam.exam_date.desc())
        )
        marks_rows = (await db.execute(marks_query)).all()

        subjects: Dict[str, List[Dict]] = {}
        absent_exam_count = 0
        absent_subjects = set()
        for mark, subject_name, exam_name in marks_rows:
            mark_status = str(getattr(mark, "mark_status", "present") or "present").lower()
            if mark_status in {"absent", "exempt"}:
                absent_exam_count += 1
                absent_subjects.add(subject_name)
                continue
            if subject_name not in subjects:
                subjects[subject_name] = []
            if len(subjects[subject_name]) >= 10:
                continue
            subjects[subject_name].append({
                "exam": exam_name,
                "obtained": mark.marks_obtained,
                "max": mark.max_marks,
                "percentage": round((mark.marks_obtained / mark.max_marks) * 100, 1),
                "comments": mark.comments,
            })

        subject_averages = {}
        for subj, scores in subjects.items():
            avg = sum(s["percentage"] for s in scores) / len(scores)
            subject_averages[subj] = round(avg, 1)

        total_query = select(func.count()).where(Attendance.student_id == student_id)
        present_query = select(func.count()).where(
            and_(Attendance.student_id == student_id, Attendance.status.in_(["Present", "Late"]))
        )
        total_days = (await db.execute(total_query)).scalar() or 0
        present_days = (await db.execute(present_query)).scalar() or 0
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 0

        student_name = getattr(student, "full_name", None) or getattr(student, "name", None) or "Student"
        return {
            "student_id": str(student_id),
            "student_name": student_name,
            "subjects": subjects,
            "subject_averages": subject_averages,
            "overall_average": round(sum(subject_averages.values()) / len(subject_averages), 1) if subject_averages else 0,
            "attendance_rate": attendance_rate,
            "total_days": total_days,
            "present_days": present_days,
            "absent_exam_count": absent_exam_count,
            "absent_subjects": sorted(list(absent_subjects)),
        }

    @staticmethod
    def _format_subject_context(data: Dict[str, Any]) -> str:
        out = ""
        for subj, scores in data["subjects"].items():
            avg = data["subject_averages"][subj]
            trend_scores = [s["percentage"] for s in scores]
            trend = "insufficient data"
            if len(trend_scores) >= 2:
                # Scores are ordered exam_date DESC (newest first):
                # index 0 = latest score, index -1 = oldest score
                # Improving means latest > oldest
                trend = "improving" if trend_scores[0] > trend_scores[-1] else "declining"
            out += f"- {subj}: Avg {avg}%, Trend: {trend}, Latest Scores: {trend_scores}\n"
        return out

    @staticmethod
    async def _call_ollama(messages: List[Dict[str, str]], json_mode: bool = False, temperature: float = 0.2) -> Optional[Any]:
        model_candidates = [OLLAMA_MODEL] + OLLAMA_FALLBACK_MODELS
        try:
            timeout = httpx.Timeout(timeout=400.0, connect=60.0, read=400.0, write=60.0, pool=60.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                for model in model_candidates:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature, "top_p": 0.9},
                    }
                    if json_mode:
                        payload["format"] = "json"
                    try:
                        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
                        resp.raise_for_status()
                        result = resp.json().get("message", {}).get("content", "").strip()
                        if json_mode:
                            start = result.find("{")
                            end = result.rfind("}")
                            if start != -1 and end != -1:
                                return json.loads(result[start : end + 1])
                            return None
                        return result
                    except httpx.HTTPError:
                        continue
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None

    async def generate_insight(self, db: AsyncSession, student_id: UUID) -> Optional[AIInsight]:
        # BUG-002 FIX: collect data once and pass it into predict_failure_risk
        # to avoid two full DB scans per student.
        data = await self._collect_student_data(db, student_id)
        hash_payload = json.dumps(data, sort_keys=True, default=str)
        context_hash = hashlib.blake2b(hash_payload.encode(), digest_size=16).hexdigest()

        existing = await db.execute(
            select(AIInsight).where(AIInsight.student_id == student_id).order_by(AIInsight.created_at.desc())
        )
        latest = existing.scalars().first()
        if latest and latest.context_hash == context_hash:
            return latest

        # BUG-002 FIX: pass pre-collected data so predict_failure_risk does NOT
        # call _collect_student_data a second time.
        risk = await self.predict_failure_risk(db, student_id, prefetched_data=data)

        # BUG-004 FIX: use real student name from collected data.
        student_name = data.get("student_name", "Student")
        sys_msg = ROLE_PARENT_LIAISON.format(student_name=student_name, language="English")
        user_msg = FEATURE_PARENT_REPORT_STRUCTURED.format(
            student_name=student_name,
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data),
            language="English",
        )

        report_json = await self._call_ollama(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            json_mode=True, temperature=0.3,
        )

        if not report_json or not risk:
            return None

        bundled_recommendations = {
            "summary": report_json.get("summary_narrative", ""),
            "strengths": report_json.get("strengths", []),
            "concerns": report_json.get("concerns", []),
            "tips": report_json.get("tips", []),
            "weaknesses": risk.at_risk_subjects,
            "risk_level": risk.risk_category,
            "attendance_flag": data["attendance_rate"] < LOW_ATTENDANCE_THRESHOLD,
        }

        insight = AIInsight(
            student_id=student_id,
            insight_text=report_json.get("summary_narrative", "Academic summary generated."),
            recommendations=bundled_recommendations,
            context_hash=context_hash,
            prompt_version="v2.1",
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)
        return insight

    async def predict_failure_risk(
        self,
        db: AsyncSession,
        student_id: UUID,
        prefetched_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[RiskPredictionSchema]:
        # BUG-002 FIX: accept pre-collected data to avoid double DB scan when
        # called from generate_insight (which already fetched data).
        data = prefetched_data if prefetched_data is not None else await self._collect_student_data(db, student_id)
        if not data["subjects"]:
            return None

        student_name = data.get("student_name", "Student")
        sys_msg = ROLE_FAILURE_PREDICTOR
        user_msg = FEATURE_RISK_PREDICTION.format(
            student_name=student_name,
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data),
        )

        result_json = await self._call_ollama(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            json_mode=True, temperature=0.0,
        )
        if result_json:
            try:
                return RiskPredictionSchema(**result_json)
            except ValidationError as e:
                logger.error(f"Pydantic schema failure on Risk Prediction: {e}")
        return None

    async def generate_study_plan(self, db: AsyncSession, student_id: UUID, language: str = "English") -> Optional[str]:
        data = await self._collect_student_data(db, student_id)
        sys_msg = ROLE_STUDENT_COACH.format(student_name="Student", grade_level="Unknown", language=language)
        user_msg = FEATURE_STUDY_PLAN.format(
            student_name="Student", attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data), language=language,
        )
        return await self._call_ollama(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            json_mode=False, temperature=0.6,
        )

    async def generate_coach_response(
        self, db: AsyncSession, student_id: UUID,
        history: List[Dict[str, str]], language: str = "English",
    ) -> Optional[str]:
        data = await self._collect_student_data(db, student_id)
        sys_msg = ROLE_STUDENT_COACH.format(student_name="Student", grade_level="Unknown", language=language)
        context_block = f"\nSTUDENT CONTEXT:\nAverage: {data['overall_average']}%\nAttendance: {data['attendance_rate']}%\n{self._format_subject_context(data)}"
        full_messages = [{"role": "system", "content": sys_msg + context_block}]
        full_messages.extend(history[-10:])
        return await self._call_ollama(full_messages, temperature=0.7)


    async def generate_global_insight(self, db: AsyncSession, school_id: Optional[UUID] = None) -> Optional[Dict[str, Any]]:
        """Generate AI insight for the entire institution/school."""
        from sqlalchemy import func
        from app.modules.identity.models import Student
        from app.modules.assessment.models import Mark, Attendance

        # 1. Collect Aggregate Data
        student_count_stmt = select(func.count(Student.id))
        if school_id:
            student_count_stmt = student_count_stmt.where(Student.school_id == school_id)
        total_students = (await db.execute(student_count_stmt)).scalar() or 0

        perf_stmt = select(func.avg(Mark.marks_obtained))
        if school_id:
            perf_stmt = perf_stmt.join(Student, Student.id == Mark.student_id).where(Student.school_id == school_id)
        avg_perf = (await db.execute(perf_stmt)).scalar() or 0.0

        att_stmt = select(func.count(Attendance.id)).where(Attendance.status == "Present")
        total_att_stmt = select(func.count(Attendance.id))
        if school_id:
            att_stmt = att_stmt.join(Student, Student.id == Attendance.student_id).where(Student.school_id == school_id)
            total_att_stmt = total_att_stmt.join(Student, Student.id == Attendance.student_id).where(Student.school_id == school_id)
        
        present_count = (await db.execute(att_stmt)).scalar() or 0
        total_count = (await db.execute(total_att_stmt)).scalar() or 1
        attendance_rate = (present_count / total_count) * 100

        # 2. Call AI
        sys_msg = ROLE_ADMIN_ANALYST.format(institution_name="EduTrack", language="English")
        user_msg = f"""
        Institution Statistics:
        - Total Students: {total_students}
        - Average Performance: {avg_perf:.2f}%
        - Attendance Rate: {attendance_rate:.2f}%
        
        Please provide a comprehensive institutional analysis including findings, risks, and recommendations.
        """

        insight_text = await self._call_ollama(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            json_mode=False, temperature=0.5,
        )

        if not insight_text:
            return None

        return {
            "insight_text": insight_text,
            "metadata": {
                "total_students": total_students,
                "avg_performance": round(float(avg_perf), 2),
                "attendance_rate": round(attendance_rate, 2),
            },
            "created_at": str(_utcnow())
        }


ai_insight_service = AIInsightService()
