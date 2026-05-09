"""
Generate AI Insights V2 directly for existing DB records.

This script is intended for bootstrap/backfill when Celery/Redis workers
are not available in the local environment.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy import and_, func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.assessment.models import Exam, Mark
from app.modules.analytics.insights_v2.services.generation_service import insight_generation_service
from app.shared.db.session import SessionLocal

logger = logging.getLogger("generate_ai_insights_v2")


async def _load_student_exam_pairs(latest_exam_per_section: bool) -> list[tuple[UUID, UUID]]:
    async with SessionLocal() as db:
        if latest_exam_per_section:
            latest_exam_subq = (
                select(
                    Exam.section_id.label("section_id"),
                    func.max(Exam.created_at).label("max_created_at"),
                )
                .join(Mark, Mark.exam_id == Exam.id)
                .group_by(Exam.section_id)
                .subquery()
            )
            exams_stmt = (
                select(Exam.id)
                .join(
                    latest_exam_subq,
                    and_(
                        Exam.section_id == latest_exam_subq.c.section_id,
                        Exam.created_at == latest_exam_subq.c.max_created_at,
                    ),
                )
            )
            exam_ids = [row[0] for row in (await db.execute(exams_stmt)).all()]
        else:
            exam_ids = [
                row[0]
                for row in (
                    await db.execute(
                        select(Mark.exam_id).distinct().join(Exam, Exam.id == Mark.exam_id)
                    )
                ).all()
            ]

        if not exam_ids:
            return []

        pairs_stmt = (
            select(Mark.student_id, Mark.exam_id)
            .where(Mark.exam_id.in_(exam_ids), Mark.mark_status == "present")
            .distinct()
        )
        return [(row[0], row[1]) for row in (await db.execute(pairs_stmt)).all()]


async def _generate_one(
    student_id: UUID,
    exam_id: UUID,
    *,
    model_version: str,
    force_regenerate: bool,
    reprocess_failed: bool,
) -> bool:
    async with SessionLocal() as db:
        try:
            await insight_generation_service.generate_for_student_exam(
                db,
                student_id=student_id,
                exam_id=exam_id,
                model_version=model_version,
                explicit_ai=False,
                force_regenerate=force_regenerate,
                reprocess_failed=reprocess_failed,
            )
            return True
        except Exception:
            logger.exception("Generation failed for student=%s exam=%s", student_id, exam_id)
            return False


async def _run_parallel(
    pairs: Iterable[tuple[UUID, UUID]],
    *,
    model_version: str,
    force_regenerate: bool,
    reprocess_failed: bool,
    concurrency: int,
) -> tuple[int, int]:
    sem = asyncio.Semaphore(max(1, concurrency))
    total = 0
    success = 0

    async def _wrapped(student_id: UUID, exam_id: UUID) -> bool:
        async with sem:
            return await _generate_one(
                student_id,
                exam_id,
                model_version=model_version,
                force_regenerate=force_regenerate,
                reprocess_failed=reprocess_failed,
            )

    tasks = []
    for student_id, exam_id in pairs:
        total += 1
        tasks.append(asyncio.create_task(_wrapped(student_id, exam_id)))

    for idx, task in enumerate(asyncio.as_completed(tasks), start=1):
        ok = await task
        if ok:
            success += 1
        if idx % 25 == 0 or idx == total:
            logger.info("Progress: %s/%s processed (success=%s)", idx, total, success)

    return total, success


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill AI Insights V2")
    parser.add_argument("--all-exams", action="store_true", help="Process all exams with marks (default: latest per section)")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of student+exam pairs")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel workers")
    parser.add_argument("--model-version", type=str, default="v2.0")
    parser.add_argument("--force-regenerate", action="store_true")
    parser.add_argument("--reprocess-failed", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    pairs = await _load_student_exam_pairs(latest_exam_per_section=not args.all_exams)
    if not pairs:
        logger.info("No eligible student+exam pairs found.")
        return

    if args.limit and args.limit > 0:
        pairs = pairs[: args.limit]

    logger.info("Starting generation for %s pairs (concurrency=%s)", len(pairs), args.concurrency)
    total, success = await _run_parallel(
        pairs,
        model_version=args.model_version,
        force_regenerate=args.force_regenerate,
        reprocess_failed=args.reprocess_failed,
        concurrency=args.concurrency,
    )
    logger.info("Done. success=%s total=%s failed=%s", success, total, total - success)


if __name__ == "__main__":
    asyncio.run(main())

