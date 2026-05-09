"""
Redis-backed counters and lightweight metric accessors.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.modules.analytics.insights_v2.models.insight import AIInsightV2

METRICS_PREFIX = "ai_insights_v2:metrics"


async def _incr(name: str, value: int = 1) -> None:
    redis_client = await get_redis_client()
    key = f"{METRICS_PREFIX}:{name}"
    if hasattr(redis_client, "incr"):
        await redis_client.incr(key, value)
        return
    current = await redis_client.get(key)
    next_value = int(current or 0) + value
    await redis_client.set(key, str(next_value))


async def _set(name: str, value: float) -> None:
    redis_client = await get_redis_client()
    await redis_client.set(f"{METRICS_PREFIX}:{name}", str(value))


async def _get_int(name: str) -> int:
    redis_client = await get_redis_client()
    val = await redis_client.get(f"{METRICS_PREFIX}:{name}")
    return int(float(val or 0))


async def _get_float(name: str) -> float:
    redis_client = await get_redis_client()
    val = await redis_client.get(f"{METRICS_PREFIX}:{name}")
    return float(val or 0.0)


async def record_task_started() -> None:
    await _incr("tasks_started", 1)


async def record_task_completed() -> None:
    await _incr("tasks_completed", 1)


async def record_task_failed() -> None:
    await _incr("tasks_failed", 1)


async def record_ai_usage() -> None:
    await _incr("ai_usage_count", 1)


async def record_cache_hit() -> None:
    await _incr("cache_hits", 1)


async def record_task_duration(duration_ms: float) -> None:
    await _incr("task_duration_ms_total", int(max(duration_ms, 0)))
    await _incr("task_duration_samples", 1)
    await _set("last_task_duration_ms", duration_ms)


async def average_task_duration_ms() -> float:
    samples = await _get_int("task_duration_samples")
    if samples <= 0:
        return 0.0
    total_ms = await _get_int("task_duration_ms_total")
    return round(total_ms / samples, 2)


async def snapshot(db: AsyncSession) -> dict[str, Any]:
    queue_size_stmt = select(func.count(AIInsightV2.id)).where(
        AIInsightV2.status.in_(["pending", "processing"])
    )
    queue_size = int((await db.execute(queue_size_stmt)).scalar() or 0)
    started = await _get_int("tasks_started")
    completed = await _get_int("tasks_completed")
    failed = await _get_int("tasks_failed")
    failure_rate = (failed / started) if started else 0.0
    avg_duration = await average_task_duration_ms()

    return {
        "task_processing_time_ms_last": await _get_float("last_task_duration_ms"),
        "task_processing_time_ms_avg": avg_duration,
        "ai_usage_count": await _get_int("ai_usage_count"),
        "failure_rate": round(failure_rate, 4),
        "queue_size": queue_size,
        "tasks_started": started,
        "tasks_completed": completed,
        "tasks_failed": failed,
        "cache_hits": await _get_int("cache_hits"),
    }
