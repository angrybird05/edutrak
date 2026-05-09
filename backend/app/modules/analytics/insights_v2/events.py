"""
Event subscribers for AI Insights V2 orchestration.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.redis import get_redis_client
from app.core.event_bus import event_bus
from app.modules.analytics.insights_v2.tasks.celery_tasks import ai_insights_v2_task_queue

logger = logging.getLogger(__name__)
EXAM_COMPLETE_DEDUP_TTL_SECONDS = 60 * 10


@event_bus.on("assessment.marks_recorded")
async def on_marks_recorded_v2(payload: dict) -> None:
    # Policy: run full-batch generation only on exam completion.
    logger.debug("Ignoring marks event for v2 insight generation policy: exam-completion only")


@event_bus.on("assessment.exam_completed")
async def on_exam_completed_v2(payload: dict) -> None:
    exam_id_raw = payload.get("exam_id")
    section_id_raw = payload.get("section_id")
    if not exam_id_raw:
        return

    try:
        exam_id = UUID(exam_id_raw)
        section_id = UUID(section_id_raw) if section_id_raw else None
    except Exception:
        logger.warning("Skipping v2 exam_completed event due to invalid ids: %s", payload)
        return

    # Guardrail: dedupe duplicate exam completion events to avoid queue storms.
    redis_client = await get_redis_client()
    dedupe_key = f"ai_insights_v2:exam_completed:{exam_id}"
    lock_set = await redis_client.set(
        dedupe_key,
        "1",
        ex=EXAM_COMPLETE_DEDUP_TTL_SECONDS,
        nx=True,
    )
    if lock_set is None:
        logger.info("Skipped duplicate AI Insights V2 exam completion enqueue for exam=%s", exam_id)
        return

    await ai_insights_v2_task_queue.enqueue_exam(
        exam_id=exam_id,
        section_id=section_id,
        model_version="v2.0",
    )
    logger.info("Queued AI Insights V2 exam completion generation for exam=%s", exam_id)


@event_bus.on("assessment.attendance_recorded")
async def on_attendance_recorded_v2(payload: dict) -> None:
    # Policy: run full-batch generation only on exam completion.
    logger.debug("Ignoring attendance event for v2 insight generation policy: exam-completion only")
