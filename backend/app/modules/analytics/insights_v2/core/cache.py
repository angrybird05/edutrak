"""
Redis-backed cache and lightweight idempotency locks for insights V2.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

AI_CACHE_TTL_SECONDS = 60 * 60 * 24
LOCK_TTL_SECONDS = 60 * 5


def _ai_cache_key(pattern_hash: str) -> str:
    return f"ai_insights_v2:pattern:{pattern_hash}"


def _lock_key(student_id: UUID, exam_id: UUID) -> str:
    return f"ai_insights_v2:lock:{student_id}:{exam_id}"


async def get_cached_ai(pattern_hash: str) -> Optional[dict[str, Any]]:
    redis_client = await get_redis_client()
    raw = await redis_client.get(_ai_cache_key(pattern_hash))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid cached ai payload for hash=%s", pattern_hash)
        return None


async def set_cached_ai(pattern_hash: str, payload: dict[str, Any]) -> None:
    redis_client = await get_redis_client()
    await redis_client.set(_ai_cache_key(pattern_hash), json.dumps(payload), ex=AI_CACHE_TTL_SECONDS)


async def acquire_lock(student_id: UUID, exam_id: UUID) -> bool:
    """Atomically acquire a distributed lock using SET NX EX.
    
    Returns True if lock was acquired, False if already held.
    Uses a single atomic Redis command to prevent race conditions
    under high-concurrency bulk generation.
    """
    redis_client = await get_redis_client()
    key = _lock_key(student_id, exam_id)
    # SET key value NX EX ttl — atomic: only sets if key does not exist
    # Returns the set value on success, None if key already existed
    result = await redis_client.set(key, "1", ex=LOCK_TTL_SECONDS, nx=True)
    return result is not None


async def release_lock(student_id: UUID, exam_id: UUID) -> None:
    redis_client = await get_redis_client()
    await redis_client.delete(_lock_key(student_id, exam_id))

