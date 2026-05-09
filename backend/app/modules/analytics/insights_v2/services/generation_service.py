"""
End-to-end orchestration for generating and persisting AI insights V2.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.insights_v2.ai.service import ai_service
from app.modules.analytics.insights_v2.core.cache import (
    acquire_lock,
    get_cached_ai,
    release_lock,
    set_cached_ai,
)
from app.modules.analytics.insights_v2.core import metrics
from app.modules.analytics.insights_v2.models.insight import AIInsightV2
from app.modules.analytics.insights_v2.services.data_service import insight_data_service
from app.modules.analytics.insights_v2.services.eligibility import ai_eligibility_policy
from app.modules.analytics.insights_v2.services.rule_engine import rule_engine
from app.modules.analytics.insights_v2.utils.fingerprint import build_pattern_fingerprint
from app.modules.identity.models import Student
from app.modules.platform.models import AuditLog

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InsightGenerationService:
    async def get_insight(self, db: AsyncSession, student_id: UUID, exam_id: UUID) -> Optional[AIInsightV2]:
        return (
            await db.execute(
                select(AIInsightV2).where(
                    AIInsightV2.student_id == student_id,
                    AIInsightV2.exam_id == exam_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    def _build_rule_recommendations(summary: dict[str, Any]) -> dict[str, Any]:
        weaknesses = summary.get("weaknesses", [])
        strengths = summary.get("strengths", [])
        study_plan: list[str] = []
        for item in weaknesses[:3]:
            subject_name = str(item).split("(")[0].strip()
            study_plan.append(f"Spend 30 minutes daily revising {subject_name} fundamentals.")

        if not study_plan:
            study_plan.append("Maintain current performance with one revision slot per day.")

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "improvement_suggestions": [
                "Review mistakes from the latest exam and rewrite corrected solutions.",
                "Use a weekly revision timetable with fixed subject slots.",
            ],
            "study_plan": study_plan,
        }

    @staticmethod
    def _build_rule_text(summary: dict[str, Any], recommendations: dict[str, Any]) -> str:
        return (
            f"Overall performance: {summary.get('overall_performance', 'unknown')}. "
            f"Trend: {summary.get('trend', 'stable')}. "
            f"Strengths: {', '.join(recommendations.get('strengths', [])) or 'None identified yet'}. "
            f"Weaknesses: {', '.join(recommendations.get('weaknesses', [])) or 'None identified yet'}."
        )

    @staticmethod
    def _merge_recommendations(
        rule_recommendations: dict[str, Any],
        ai_recommendations: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(rule_recommendations)
        for key in ("strengths", "weaknesses", "improvement_suggestions", "study_plan"):
            ai_value = ai_recommendations.get(key)
            if ai_value:
                merged[key] = ai_value
        if ai_recommendations.get("raw"):
            merged["raw"] = ai_recommendations["raw"]
        return merged

    async def _audit_failure(
        self,
        db: AsyncSession,
        *,
        student_id: UUID,
        exam_id: UUID,
        model_version: str,
        error: str,
    ) -> None:
        db.add(
            AuditLog(
                action="AI_INSIGHT_V2_FAILED",
                resource_type="ai_insights",
                resource_id=f"{student_id}:{exam_id}",
                student_id=student_id,
                details={
                    "exam_id": str(exam_id),
                    "model_version": model_version,
                    "error": error[:500],
                },
                created_at=_utcnow().replace(tzinfo=None),
            )
        )

    async def generate_for_student_exam(
        self,
        db: AsyncSession,
        *,
        student_id: UUID,
        exam_id: UUID,
        model_version: str = "v2.0",
        explicit_ai: bool = False,
        force_regenerate: bool = False,
        reprocess_failed: bool = False,
    ) -> AIInsightV2:
        started_at = perf_counter()

        # BUG-008 FIX: check the lock BEFORE incrementing tasks_started.
        # Previously, tasks_started was counted even for tasks that skipped
        # due to a held lock (and returned without recording tasks_completed),
        # which inflated the apparent failure_rate metric.
        lock_acquired = await acquire_lock(student_id, exam_id)
        if not lock_acquired:
            existing = await self.get_insight(db, student_id, exam_id)
            if existing:
                return existing

        await metrics.record_task_started()

        insight_row: Optional[AIInsightV2] = None
        try:
            insight_row = await self.get_insight(db, student_id, exam_id)
            if insight_row:
                if (
                    not force_regenerate
                    and insight_row.status == "completed"
                    and insight_row.model_version == model_version
                ):
                    latest_input_update = await insight_data_service.latest_input_update_at(
                        db,
                        student_id=student_id,
                        exam_id=exam_id,
                    )
                    if (
                        insight_row.generated_at is not None
                        and (latest_input_update is None or latest_input_update <= insight_row.generated_at)
                    ):
                        await metrics.record_task_completed()
                        return insight_row
                if not force_regenerate and insight_row.status == "processing":
                    return insight_row
                if not force_regenerate and not reprocess_failed and insight_row.status == "failed":
                    return insight_row
            else:
                insight_row = AIInsightV2(
                    student_id=student_id,
                    exam_id=exam_id,
                    status="pending",
                    model_version=model_version,
                )
                db.add(insight_row)
                await db.commit()
                await db.refresh(insight_row)

            insight_row.status = "processing"
            insight_row.model_version = model_version
            db.add(insight_row)
            await db.commit()

            structured_data = await insight_data_service.build_structured_data(
                db,
                student_id=student_id,
                exam_id=exam_id,
            )
            performance_summary = rule_engine.analyze(structured_data)
            rule_recommendations = self._build_rule_recommendations(performance_summary)
            final_recommendations = rule_recommendations
            final_text = self._build_rule_text(performance_summary, rule_recommendations)

            student = await db.get(Student, student_id)
            high_value_user = False
            if student:
                high_value_user = await insight_data_service.is_high_value_student(db, student.user_id)

            use_ai = ai_eligibility_policy.should_use_ai(
                structured_data=structured_data,
                summary=performance_summary,
                high_value_user=high_value_user,
                explicit_request=explicit_ai,
            )
            if use_ai:
                fingerprint = build_pattern_fingerprint(
                    {
                        "summary": performance_summary,
                        "structured_data": structured_data.model_dump(
                            exclude={"student_id", "exam_id"},
                            mode="json",
                        ),
                    }
                )
                cached = await get_cached_ai(fingerprint)
                if cached:
                    await metrics.record_cache_hit()
                    final_text = cached.get("insight_text", final_text)
                    final_recommendations = self._merge_recommendations(
                        rule_recommendations,
                        cached.get("recommendations", {}),
                    )
                else:
                    ai_result = await ai_service.generate_insight(
                        structured_data.model_dump(mode="json")
                    )
                    if ai_result:
                        await set_cached_ai(fingerprint, ai_result)
                        await metrics.record_ai_usage()
                        final_text = ai_result.get("insight_text", final_text)
                        final_recommendations = self._merge_recommendations(
                            rule_recommendations,
                            ai_result.get("recommendations", {}),
                        )

            insight_row.status = "completed"
            insight_row.insight_text = final_text
            insight_row.recommendations_json = final_recommendations
            insight_row.performance_summary_json = performance_summary
            insight_row.generated_at = _utcnow()
            db.add(insight_row)
            await db.commit()
            await db.refresh(insight_row)

            await metrics.record_task_completed()
            await metrics.record_task_duration((perf_counter() - started_at) * 1000)
            return insight_row
        except Exception as exc:
            logger.exception(
                "Failed generating insight V2 for student_id=%s exam_id=%s",
                student_id,
                exam_id,
            )
            if insight_row:
                insight_row.status = "failed"
                db.add(insight_row)
            await self._audit_failure(
                db,
                student_id=student_id,
                exam_id=exam_id,
                model_version=model_version,
                error=str(exc),
            )
            await db.commit()
            await metrics.record_task_failed()
            await metrics.record_task_duration((perf_counter() - started_at) * 1000)
            raise
        finally:
            await release_lock(student_id, exam_id)


insight_generation_service = InsightGenerationService()
