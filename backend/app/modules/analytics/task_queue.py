"""
Analytics module — Celery task queue for background AI insight generation.

Migrated from app/services/ai_task_queue.py.
"""
import asyncio
import logging
from typing import Dict, List, Any
from uuid import UUID

from app.core.celery_app import celery_app
from app.shared.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_insight_task", bind=True, max_retries=3)
def generate_insight_task(self, student_id_str: str):
    """Celery background task to generate insights for a student."""
    student_id = UUID(student_id_str)

    async def _run():
        from app.modules.analytics.service import ai_insight_service
        async with SessionLocal() as db:
            logger.info("Celery task starting AI insight generation for %s", student_id)
            await ai_insight_service.generate_insight(db, student_id)

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.exception("AI insight background task failed for %s", student_id)
        raise self.retry(exc=exc, countdown=60)


class AIInsightTaskQueue:
    """Wrapper to route enqueue requests to Celery asynchronously."""

    async def enqueue_students(self, student_ids: List[UUID]) -> Dict[str, Any]:
        enqueued = 0
        task_ids = []
        unique_ids = list(dict.fromkeys(student_ids))

        for student_id in unique_ids:
            task = generate_insight_task.apply_async(args=[str(student_id)])
            task_ids.append(task.id)
            enqueued += 1

        return {"enqueued": enqueued, "task_ids": task_ids}

    async def start(self):
        """No-op for compatibility with lifespan manager."""
        pass

    async def stop(self):
        """No-op for compatibility with lifespan manager."""
        pass


ai_insight_task_queue = AIInsightTaskQueue()
