import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
import redis.asyncio as redis
from redis.asyncio.client import Pipeline

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class RedisWindowRateLimiter:
    """
    Distributed token bucket / window rate limiter using Redis.
    Uses an atomic MULTI/EXEC pipeline to increment and set expiry.
    """
    def __init__(self, prefix: str, window_seconds: int, max_events: int):
        self.prefix = prefix
        self.window_seconds = window_seconds
        self.max_events = max_events

    async def allow(self, key: str) -> bool:
        redis_client = await get_redis_client()
        redis_key = f"rate_limit:{self.prefix}:{key}"
        
        try:
            # Atomic increment and expire
            async with redis_client.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, self.window_seconds, nx=True)
                results = await pipe.execute()
            
            # results[0] is the result of INCR
            current_count = results[0]
            if current_count > self.max_events:
                return False
            return True
        except redis.RedisError as e:
            # Fallback to allow if Redis is unavailable, avoiding complete service outage
            logger.error(f"Redis rate limiting failed: {e}")
            return True

heavy_endpoint_limiter = RedisWindowRateLimiter("heavy", window_seconds=60, max_events=100)
request_ip_limiter = RedisWindowRateLimiter("global_fallback", window_seconds=60, max_events=200)
verify_ip_limiter = RedisWindowRateLimiter("otp_verify", window_seconds=600, max_events=20) # max 20 per 10 min

async def enforce_heavy_rate_limit(request: Request) -> None:
    host = request.client.host if request.client else "unknown"
    path = request.url.path
    key = f"{host}:{path}"
    
    if not await heavy_endpoint_limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this endpoint. Please retry shortly.",
        )
