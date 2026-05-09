"""
AI Insight Engine — Uses local Ollama instance to generate
Personalized student insights across multiple personas (Coach, Analyst, Liaison, Admin).
"""
import httpx
import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Literal, Tuple
from uuid import UUID
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from dotenv import load_dotenv

from app.models.performance import Mark, Attendance, AIInsight, Exam
from app.models.academic import Subject
from app.models.student import Student
from app.services import ai_prompts

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
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

        # Organize marks by subject, excluding absent/exempt records from score averages
        # Context Truncation: Limit to latest 10 exams per subject to prevent token overflow
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
            
            # Truncation logic: keep only the last 10 records per subject
            if len(subjects[subject_name]) >= 10:
                continue

            subjects[subject_name].append({
                "exam": exam_name,
                "obtained": mark.marks_obtained,
                "max": mark.max_marks,
                "percentage": round((mark.marks_obtained / mark.max_marks) * 100, 1),
                "comments": mark.comments
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

        return {
            "student_id": str(student_id),
            "student_name": f"{student.first_name} {student.last_name}",
            "grade_level": getattr(student, "grade", "Unknown"),
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
        """Formats the raw subjects dict into a readable structured text block for the LLM."""
        out = ""
        for subj, scores in data["subjects"].items():
            avg = data["subject_averages"][subj]
            trend_scores = [s["percentage"] for s in scores]
            trend = "insufficient data"
            if len(trend_scores) >= 2:
                trend = "improving" if trend_scores[-1] > trend_scores[0] else "declining"
            out += f"- {subj}: Avg {avg}%, Trend: {trend}, Latest Scores: {trend_scores}\n"
            comments = [s.get("comments") for s in scores if s.get("comments")]
            if comments:
                out += f"  Teacher's Notes: {'; '.join(comments)}\n"
        return out

    @staticmethod
    async def _call_ollama(messages: List[Dict[str, str]], json_mode: bool = False, temperature: float = 0.2) -> Optional[Any]:
        """Send messages to Ollama."""
        model_candidates = [OLLAMA_MODEL] + OLLAMA_FALLBACK_MODELS
        try:
            timeout = httpx.Timeout(timeout=400.0, connect=60.0, read=400.0, write=60.0, pool=60.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                for model in model_candidates:
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature, "top_p": 0.9}
                    }
                    if json_mode:
                        payload["format"] = "json"
                    
                    try:
                        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
                        resp.raise_for_status()
                        result = resp.json().get("message", {}).get("content", "").strip()
                        
                        if json_mode:
                            start = result.find('{')
                            end = result.rfind('}')
                            if start != -1 and end != -1:
                                return json.loads(result[start:end+1])
                            return None
                        
                        return result
                    except httpx.HTTPError:
                        continue
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return None

    # =====================================================================
    # ADMIN ANALYTICS CALCULATIONS (SQL-BASED, NO LLM HALLUCINATIONS)
    # =====================================================================

    async def _calculate_admin_metrics(self, db: AsyncSession, school_id: Optional[UUID] = None, section_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Calculates accurate school-wide or section-wide metrics via raw SQLAlchemy."""
        from sqlalchemy import case, literal_column
        
        # Base filters
        student_filters = []
        if school_id:
            student_filters.append(Student.school_id == school_id)
        if section_id:
            student_filters.append(Student.section_id == section_id)
            
        # 1. Overall Average
        marks_query = select(func.avg((Mark.marks_obtained / Mark.max_marks) * 100)).join(Student, Mark.student_id == Student.id)
        if student_filters:
            marks_query = marks_query.where(*student_filters)
        avg_score = (await db.execute(marks_query)).scalar() or 0.0

        # 2. Attendance Average
        att_query = select(func.count(Attendance.id), func.count(case((Attendance.status.in_(["Present", "Late"]), 1)))).join(Student, Attendance.student_id == Student.id)
        if student_filters:
            att_query = att_query.where(*student_filters)
        total_att, present_att = (await db.execute(att_query)).one()
        avg_attendance = (present_att / total_att * 100) if total_att > 0 else 0.0

        # 3. Subject-wise performance
        subj_query = select(Subject.name, func.avg((Mark.marks_obtained / Mark.max_marks) * 100)).join(Mark, Mark.subject_id == Subject.id).join(Student, Mark.student_id == Student.id)
        if student_filters:
            subj_query = subj_query.where(*student_filters)
        subj_query = subj_query.group_by(Subject.name).order_by(func.avg((Mark.marks_obtained / Mark.max_marks) * 100).asc())
        subj_performance = (await db.execute(subj_query)).all()
        
        return {
            "avg_score": round(float(avg_score), 1),
            "avg_attendance": round(float(avg_attendance), 1),
            "subject_rankings": {row[0]: round(float(row[1]), 1) for row in subj_performance},
            "total_students_tracked": (await db.execute(select(func.count(Student.id)).where(*student_filters))).scalar()
        }

    async def generate_admin_digest(self, db: AsyncSession, school_id: Optional[UUID] = None, section_id: Optional[UUID] = None) -> Optional[str]:
        """Generate high-level strategic summary for the Principal/Admin."""
        metrics = await self._calculate_admin_metrics(db, school_id, section_id)
        
        sys_msg = ai_prompts.ROLE_ADMIN_ANALYST
        
        subj_text = "\n".join([f"- {s}: {v}%" for s, v in metrics["subject_rankings"].items()])
        user_msg = f"""SCHOOL AGGREGATE DATA:
Total Students: {metrics['total_students_tracked']}
Average Academic Score: {metrics['avg_score']}%
Average Attendance Rate: {metrics['avg_attendance']}%

SUBJECT PERFORMANCE RANKINGS:
{subj_text}
"""
        return await self._call_ollama([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], temperature=0.3)

    # =====================================================================
    # FEATURE ENDPOINTS
    # =====================================================================

    async def generate_study_plan(self, db: AsyncSession, student_id: UUID, language: str = "English") -> Optional[str]:
        data = await self._collect_student_data(db, student_id)
        sys_msg = ai_prompts.ROLE_STUDENT_COACH.format(
            student_name=data["student_name"], grade_level=data["grade_level"], language=language
        )
        if language.lower() != "english":
            sys_msg += ai_prompts.MULTILINGUAL_WRAPPER.format(target_language=language, student_name=data['student_name'])
            
        user_msg = ai_prompts.FEATURE_STUDY_PLAN.format(
            student_name=data["student_name"], 
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data),
            language=language
        )
        return await self._call_ollama([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], json_mode=False, temperature=0.6)

    async def predict_failure_risk(self, db: AsyncSession, student_id: UUID) -> Optional[RiskPredictionSchema]:
        data = await self._collect_student_data(db, student_id)
        if not data["subjects"]:
            return None
            
        sys_msg = ai_prompts.ROLE_FAILURE_PREDICTOR
        user_msg = ai_prompts.FEATURE_RISK_PREDICTION.format(
            student_name=data["student_name"],
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data)
        )
        
        result_json = await self._call_ollama([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], json_mode=True, temperature=0.0)
        if result_json:
            try:
                return RiskPredictionSchema(**result_json)
            except ValidationError as e:
                logger.error(f"Pydantic schema failure on Risk Prediction: {e}")
        return None

    async def generate_parent_report(self, db: AsyncSession, student_id: UUID, language: str = "English") -> Optional[str]:
        data = await self._collect_student_data(db, student_id)
        sys_msg = ai_prompts.ROLE_PARENT_LIAISON.format(student_name=data["student_name"], language=language)
        if language.lower() != "english":
            sys_msg += ai_prompts.MULTILINGUAL_WRAPPER.format(target_language=language, student_name=data['student_name'])
            
        user_msg = ai_prompts.FEATURE_PARENT_REPORT.format(
            student_name=data["student_name"],
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data),
            language=language
        )
        return await self._call_ollama([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], json_mode=False, temperature=0.4)

    # Legacy method updated to use the new architecture to not break frontend compatibility
    async def generate_insight(self, db: AsyncSession, student_id: UUID) -> Optional[AIInsight]:
        data = await self._collect_student_data(db, student_id)
        hash_payload = json.dumps(data, sort_keys=True)
        context_hash = hashlib.md5(hash_payload.encode()).hexdigest()

        existing = await db.execute(select(AIInsight).where(AIInsight.student_id == student_id).order_by(AIInsight.created_at.desc()))
        latest = existing.scalars().first()
        if latest and latest.context_hash == context_hash:
            return latest

        risk = await self.predict_failure_risk(db, student_id)
        
        # New structured report for Parents
        sys_msg = ai_prompts.ROLE_PARENT_LIAISON.format(student_name=data["student_name"], language="English")
        user_msg = ai_prompts.FEATURE_PARENT_REPORT_STRUCTURED.format(
            student_name=data["student_name"],
            attendance=data["attendance_rate"],
            overall_average=data["overall_average"],
            subjects_data=self._format_subject_context(data),
            language="English"
        )
        
        report_json = await self._call_ollama(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], 
            json_mode=True, 
            temperature=0.3
        )
        
        if not report_json or not risk:
            return None

        # Bundle into a rich JSON structure that the frontend can use
        bundled_recommendations = {
            "summary": report_json.get("summary_narrative", ""),
            "strengths": report_json.get("strengths", []),
            "concerns": report_json.get("concerns", []),
            "tips": report_json.get("tips", []),
            "weaknesses": risk.at_risk_subjects,
            "risk_level": risk.risk_category,
            "attendance_flag": data["attendance_rate"] < LOW_ATTENDANCE_THRESHOLD
        }

        insight = AIInsight(
            student_id=student_id,
            insight_text=report_json.get("summary_narrative", "Academic summary generated."),
            recommendations=bundled_recommendations,
            context_hash=context_hash,
            prompt_version="v2.1"
        )
        db.add(insight)
        await db.commit()
        await db.refresh(insight)
        return insight

    async def generate_coach_response(
        self, 
        db: AsyncSession, 
        student_id: UUID, 
        history: List[Dict[str, str]], 
        language: str = "English"
    ) -> Optional[str]:
        """Generate a contextual response for the AI Coach using student metadata and chat history."""
        data = await self._collect_student_data(db, student_id)
        
        sys_msg = ai_prompts.ROLE_STUDENT_COACH.format(
            student_name=data["student_name"], 
            grade_level=data["grade_level"], 
            language=language
        )
        
        context_block = f"""
STUDENT CONTEXT:
Name: {data['student_name']}
Current Average: {data['overall_average']}%
Attendance: {data['attendance_rate']}%
Performance Trend:
{self._format_subject_context(data)}
"""
        
        # Combine system prompt with context and history
        full_messages = [
            {"role": "system", "content": sys_msg + "\n" + context_block}
        ]
        
        # Add limited history (last 5 exchanges to avoid context window issues)
        full_messages.extend(history[-10:])
        
        return await self._call_ollama(full_messages, temperature=0.7)

    @staticmethod
    async def generate_insight_stream(db: AsyncSession, student_id: UUID, language: str = "English"):
        # Legacy stream endpoint rewritten for Study Plan delivery as an example
        try:
            data = await AIInsightService._collect_student_data(db, student_id)
            if not data["subjects"]:
                yield 'data: {"done": true, "error": "No marks data available"}\n\n'
                return

            sys_msg = ai_prompts.ROLE_STUDENT_COACH.format(
                student_name=data["student_name"], grade_level=data["grade_level"], language=language
            )
            user_msg = ai_prompts.FEATURE_STUDY_PLAN.format(
                student_name=data["student_name"], 
                attendance=data["attendance_rate"],
                overall_average=data["overall_average"],
                subjects_data=AIInsightService._format_subject_context(data),
                language=language
            )

            async with httpx.AsyncClient(timeout=400.0) as client:
                async with client.stream(
                    "POST", f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                        "stream": True,
                        "options": {"temperature": 0.6, "top_p": 0.9}
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line: yield f"data: {line}\n\n"
        except Exception as e:
            logger.error(f"Stream failed: {e}")

ai_insight_service = AIInsightService()
