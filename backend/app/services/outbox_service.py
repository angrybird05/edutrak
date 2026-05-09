import asyncio
import datetime
import logging
from datetime import timezone
from typing import Awaitable, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.scale_foundation import OutboxJob

logger = logging.getLogger(__name__)

OutboxHandler = Callable[[dict], Awaitable[None]]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(timezone.utc)


class OutboxService:
    def __init__(self) -> None:
        self._handlers: Dict[str, OutboxHandler] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._stopping = False

    def register_handler(self, job_type: str, handler: OutboxHandler) -> None:
        self._handlers[job_type] = handler

    async def enqueue(
        self,
        db: AsyncSession,
        *,
        job_type: str,
        payload_json: dict,
        max_attempts: int = 5,
    ) -> OutboxJob:
        job = OutboxJob(
            job_type=job_type,
            payload_json=payload_json,
            status="pending",
            attempts=0,
            max_attempts=max_attempts,
            next_run_at=_utcnow(),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    async def process_due_jobs(self, db: AsyncSession, batch_size: int = 50) -> None:
        now = _utcnow()
        result = await db.execute(
            select(OutboxJob)
            .where(
                OutboxJob.status.in_(["pending", "retry"]),
                OutboxJob.next_run_at <= now,
            )
            .order_by(OutboxJob.created_at.asc())
            .limit(batch_size)
        )
        jobs = result.scalars().all()
        for job in jobs:
            job.locked_at = now
            db.add(job)
            await db.flush()
            await self._execute_job(db, job)
        await db.commit()

    async def _execute_job(self, db: AsyncSession, job: OutboxJob) -> None:
        handler = self._handlers.get(job.job_type)
        try:
            if not handler:
                raise ValueError(f"No outbox handler registered for {job.job_type}")
            await handler(job.payload_json)
            job.status = "completed"
            job.last_error = None
            job.locked_at = None
        except Exception as exc:
            job.attempts = int(job.attempts or 0) + 1
            job.last_error = str(exc)
            job.locked_at = None
            if job.attempts >= job.max_attempts:
                job.status = "dead_letter"
            else:
                backoff_seconds = min(300, 2 ** job.attempts)
                job.status = "retry"
                job.next_run_at = _utcnow() + datetime.timedelta(seconds=backoff_seconds)
            logger.warning("Outbox job %s failed: %s", job.id, exc)
        db.add(job)

    async def start_worker(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return
        self._stopping = False
        self._worker_task = asyncio.create_task(self._worker_loop(), name="outbox-worker")

    async def stop_worker(self) -> None:
        self._stopping = True
        if self._worker_task:
            await self._worker_task
            self._worker_task = None

    async def _worker_loop(self) -> None:
        while not self._stopping:
            try:
                async with SessionLocal() as db:
                    await self.process_due_jobs(db)
            except Exception:
                logger.exception("Outbox worker loop error")
            await asyncio.sleep(2)

    async def metrics(self, db: AsyncSession) -> dict:
        result = await db.execute(select(OutboxJob.status))
        counts: dict[str, int] = {"pending": 0, "retry": 0, "completed": 0, "dead_letter": 0}
        for s in result.scalars().all():
            if s in counts:
                counts[s] += 1
        return counts


outbox_service = OutboxService()
