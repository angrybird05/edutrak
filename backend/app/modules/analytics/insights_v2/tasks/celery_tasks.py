"""
Celery tasks for AI Insights V2.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Optional
from uuid import UUID

from app.core.celery_app import celery_app
from app.modules.analytics.insights_v2.services.data_service import insight_data_service
from app.modules.analytics.insights_v2.services.generation_service import insight_generation_service
from app.shared.db.session import SessionLocal

logger = logging.getLogger(__name__)

AI_INSIGHTS_V2_QUEUE = "ai_insights_v2"
AI_INSIGHTS_V2_DISPATCH_QUEUE = "ai_insights_v2_dispatch"


def _run_async(coro):
    """BUG-003 FIX: safely run an async coroutine from a sync Celery task.

    asyncio.run() creates a brand-new event loop every time which:
    - Fails with "cannot be called when another event loop is running" on
      asyncio-pool Celery workers (Python 3.10+).
    - Destroys and recreates an event loop per task — massive overhead at scale.

    This helper reuses an existing running loop when available, or uses a
    persistent per-thread loop for standard prefork workers.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside a running event loop (asyncio Celery pool).
        # Schedule the coroutine and block until done via a thread-safe future.
        future: concurrent.futures.Future = concurrent.futures.Future()

        async def _wrapper():
            try:
                future.set_result(await coro)
            except Exception as exc:  # noqa: BLE001
                future.set_exception(exc)

        loop.create_task(_wrapper())
        return future.result(timeout=600)
    else:
        # Standard sync Celery prefork worker: reuse or create a thread-local loop.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("loop closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


@celery_app.task(name="ai_insights_v2.generate_student_insight", bind=True, max_retries=3)
def generate_student_insight_task(
    self,
    student_id_str: str,
    exam_id_str: str,
    model_version: str = "v2.0",
    explicit_ai: bool = False,
    force_regenerate: bool = False,
    reprocess_failed: bool = False,
) -> dict[str, Any]:
    student_id = UUID(student_id_str)
    exam_id = UUID(exam_id_str)

    async def _run() -> dict[str, Any]:
        async with SessionLocal() as db:
            row = await insight_generation_service.generate_for_student_exam(
                db,
                student_id=student_id,
                exam_id=exam_id,
                model_version=model_version,
                explicit_ai=explicit_ai,
                force_regenerate=force_regenerate,
                reprocess_failed=reprocess_failed,
            )
            return {
                "student_id": str(row.student_id),
                "exam_id": str(row.exam_id),
                "status": row.status,
            }

    try:
        return _run_async(_run())
    except Exception as exc:
        retry_count = int(self.request.retries or 0)
        countdown = min(30 * (2 ** retry_count), 300)
        logger.exception(
            "Student insight task failed student_id=%s exam_id=%s retry=%s",
            student_id,
            exam_id,
            retry_count,
        )
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="ai_insights_v2.dispatch_exam_generation", bind=True)
def dispatch_exam_generation_task(
    self,
    exam_id_str: str,
    section_id_str: Optional[str] = None,
    student_id_strs: Optional[list[str]] = None,
    model_version: str = "v2.0",
    explicit_ai: bool = False,
    force_regenerate: bool = False,
    reprocess_failed: bool = False,
) -> dict[str, Any]:
    exam_id = UUID(exam_id_str)
    section_id = UUID(section_id_str) if section_id_str else None
    student_ids = [UUID(item) for item in (student_id_strs or [])]

    async def _run() -> dict[str, Any]:
        async with SessionLocal() as db:
            resolved_student_ids = await insight_data_service.resolve_student_ids(
                db,
                exam_id=exam_id,
                section_id=section_id,
                student_ids=student_ids or None,
            )

        task_ids: list[str] = []
        for student_id in resolved_student_ids:
            task = generate_student_insight_task.apply_async(
                args=[
                    str(student_id),
                    str(exam_id),
                    model_version,
                    explicit_ai,
                    force_regenerate,
                    reprocess_failed,
                ],
                queue=AI_INSIGHTS_V2_QUEUE,
            )
            task_ids.append(task.id)

        return {
            "enqueued": len(resolved_student_ids),
            "exam_id": str(exam_id),
            "task_ids": task_ids,
        }

    return _run_async(_run())


class AIInsightsV2TaskQueue:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def enqueue_exam(
        self,
        *,
        exam_id: UUID,
        section_id: Optional[UUID] = None,
        student_ids: Optional[list[UUID]] = None,
        model_version: str = "v2.0",
        explicit_ai: bool = False,
        force_regenerate: bool = False,
        reprocess_failed: bool = False,
    ) -> dict[str, Any]:
        task = dispatch_exam_generation_task.apply_async(
            args=[
                str(exam_id),
                str(section_id) if section_id else None,
                [str(item) for item in (student_ids or [])],
                model_version,
                explicit_ai,
                force_regenerate,
                reprocess_failed,
            ],
            queue=AI_INSIGHTS_V2_DISPATCH_QUEUE,
        )
        return {"status": "queued", "dispatch_task_id": task.id}

    async def enqueue_students_for_exam(
        self,
        *,
        exam_id: UUID,
        student_ids: list[UUID],
        model_version: str = "v2.0",
        explicit_ai: bool = False,
        force_regenerate: bool = False,
        reprocess_failed: bool = False,
    ) -> dict[str, Any]:
        task_ids: list[str] = []
        for student_id in list(dict.fromkeys(student_ids)):
            task = generate_student_insight_task.apply_async(
                args=[
                    str(student_id),
                    str(exam_id),
                    model_version,
                    explicit_ai,
                    force_regenerate,
                    reprocess_failed,
                ],
                queue=AI_INSIGHTS_V2_QUEUE,
            )
            task_ids.append(task.id)
        return {"status": "queued", "enqueued": len(task_ids), "task_ids": task_ids}

    def stats(self) -> dict[str, str]:
        return {
            "dispatch_queue": AI_INSIGHTS_V2_DISPATCH_QUEUE,
            "worker_queue": AI_INSIGHTS_V2_QUEUE,
        }


ai_insights_v2_task_queue = AIInsightsV2TaskQueue()
