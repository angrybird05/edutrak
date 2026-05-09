"""
Data access and preprocessing for AI Insights V2.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.academic.models import Subject
from app.modules.assessment.models import Attendance, Exam, Mark
from app.modules.analytics.insights_v2.schemas import StructuredPerformanceData, SubjectSnapshot
from app.modules.identity.models import Student
from app.modules.platform.models import UserSettings


class InsightDataService:
    async def get_exam(self, db: AsyncSession, exam_id: UUID) -> Exam:
        exam = await db.get(Exam, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        return exam

    async def resolve_student_ids(
        self,
        db: AsyncSession,
        *,
        exam_id: UUID,
        section_id: Optional[UUID] = None,
        student_ids: Optional[list[UUID]] = None,
    ) -> list[UUID]:
        exam = await self.get_exam(db, exam_id)
        target_section_id = section_id or exam.section_id

        if target_section_id != exam.section_id:
            raise HTTPException(status_code=400, detail="Provided section_id does not match exam section")

        stmt = select(Student.id).where(Student.section_id == target_section_id)
        if student_ids:
            stmt = stmt.where(Student.id.in_(student_ids))
        result = await db.execute(stmt)
        resolved = list(dict.fromkeys(result.scalars().all()))
        return resolved

    async def is_high_value_student(self, db: AsyncSession, user_id: UUID) -> bool:
        settings = (
            await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        ).scalar_one_or_none()
        prefs = settings.custom_prefs if settings and settings.custom_prefs else {}
        return bool(prefs.get("ai_high_value", False))

    async def build_structured_data(
        self,
        db: AsyncSession,
        *,
        student_id: UUID,
        exam_id: UUID,
    ) -> StructuredPerformanceData:
        exam = await self.get_exam(db, exam_id)

        student = await db.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        if student.section_id != exam.section_id:
            raise HTTPException(status_code=400, detail="Student does not belong to the exam section")

        marks_stmt = (
            select(
                Mark.exam_id,
                Mark.subject_id,
                Mark.marks_obtained,
                Mark.max_marks,
                Mark.mark_status,
                Exam.exam_date,
                Subject.name.label("subject_name"),
            )
            .join(Exam, Exam.id == Mark.exam_id)
            .join(Subject, Subject.id == Mark.subject_id)
            .where(
                Mark.student_id == student_id,
                Exam.section_id == exam.section_id,
                Mark.mark_status == "present",
            )
            .order_by(Exam.exam_date.asc().nulls_last(), Exam.created_at.asc())
        )
        marks_rows = (await db.execute(marks_stmt)).all()

        history_by_subject: dict[UUID, list[tuple[UUID, float, str]]] = defaultdict(list)
        current_by_subject: dict[UUID, tuple[float, str]] = {}

        for row in marks_rows:
            if not row.max_marks:
                continue
            percentage = round((float(row.marks_obtained) / float(row.max_marks)) * 100, 2)
            history_by_subject[row.subject_id].append((row.exam_id, percentage, row.subject_name))
            if row.exam_id == exam_id:
                current_by_subject[row.subject_id] = (percentage, row.subject_name)

        subject_snapshots: list[SubjectSnapshot] = []
        current_percentages: list[float] = []
        for subject_id, (current_pct, subject_name) in current_by_subject.items():
            history_scores = [item[1] for item in history_by_subject[subject_id]]
            subject_snapshots.append(
                SubjectSnapshot(
                    subject_id=subject_id,
                    subject_name=subject_name,
                    current_percentage=current_pct,
                    history_percentages=history_scores,
                )
            )
            current_percentages.append(current_pct)

        overall_percentage = round(mean(current_percentages), 2) if current_percentages else 0.0

        previous_exam_stmt = select(Exam.id).where(
            Exam.section_id == exam.section_id,
            Exam.id != exam_id,
        )
        if exam.exam_date is not None:
            previous_exam_stmt = previous_exam_stmt.where(
                Exam.exam_date.is_not(None),
                Exam.exam_date < exam.exam_date,
            )
        previous_exam_stmt = previous_exam_stmt.order_by(Exam.exam_date.desc().nulls_last()).limit(1)
        previous_exam_id = (await db.execute(previous_exam_stmt)).scalar_one_or_none()

        previous_overall = 0.0
        if previous_exam_id:
            previous_marks_stmt = select(Mark.marks_obtained, Mark.max_marks).where(
                Mark.student_id == student_id,
                Mark.exam_id == previous_exam_id,
                Mark.mark_status == "present",
            )
            previous_rows = (await db.execute(previous_marks_stmt)).all()
            previous_percentages = [
                round((float(r.marks_obtained) / float(r.max_marks)) * 100, 2)
                for r in previous_rows
                if r.max_marks
            ]
            previous_overall = round(mean(previous_percentages), 2) if previous_percentages else 0.0

        if previous_exam_id is None:
            overall_trend = "stable"
        elif overall_percentage > previous_overall:
            overall_trend = "improving"
        elif overall_percentage < previous_overall:
            overall_trend = "declining"
        else:
            overall_trend = "stable"

        # BUG-006 FIX: use SQL COUNT instead of loading all IDs into memory.
        total_days = (
            await db.execute(
                select(func.count(Attendance.id)).where(Attendance.student_id == student_id)
            )
        ).scalar() or 0
        present_days = (
            await db.execute(
                select(func.count(Attendance.id)).where(
                    Attendance.student_id == student_id,
                    Attendance.status.in_(["Present", "Late"]),
                )
            )
        ).scalar() or 0
        attendance_percentage = round((present_days / total_days) * 100, 2) if total_days else 0.0

        return StructuredPerformanceData(
            student_id=student_id,
            exam_id=exam_id,
            overall_percentage=overall_percentage,
            attendance_percentage=attendance_percentage,
            subject_snapshots=sorted(subject_snapshots, key=lambda item: item.subject_name.lower()),
            overall_trend=overall_trend,
            meta={
                "previous_overall_percentage": previous_overall,
                "total_attendance_days": total_days,
                "present_attendance_days": present_days,
            },
        )

    async def latest_input_update_at(
        self,
        db: AsyncSession,
        *,
        student_id: UUID,
        exam_id: UUID,
    ) -> Optional[datetime]:
        exam = await self.get_exam(db, exam_id)

        latest_mark_update = (
            await db.execute(
                select(func.max(Mark.updated_at))
                .join(Exam, Exam.id == Mark.exam_id)
                .where(
                    Mark.student_id == student_id,
                    Exam.section_id == exam.section_id,
                )
            )
        ).scalar_one_or_none()

        latest_attendance_update = (
            await db.execute(
                select(func.max(Attendance.updated_at)).where(
                    Attendance.student_id == student_id,
                )
            )
        ).scalar_one_or_none()

        candidates = [ts for ts in (latest_mark_update, latest_attendance_update) if ts is not None]
        if not candidates:
            return None
        return max(candidates)


insight_data_service = InsightDataService()
