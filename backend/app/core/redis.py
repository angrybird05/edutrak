import logging
import asyncio
from typing import Optional, Any

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class MockPipeline:
    def __init__(self, redis_instance):
        self.redis = redis_instance
        self.commands = []

    def incr(self, key, amount=1):
        self.commands.append(("incr", key, amount))
        return self

    def expire(self, key, seconds, nx=False, xx=False):
        self.commands.append(("expire", key, seconds, nx, xx))
        return self

    async def execute(self):
        results = []
        for cmd, *args in self.commands:
            if cmd == "incr":
                key, amount = args
                val = self.redis.data.get(key, 0)
                new_val = int(val) + amount
                self.redis.data[key] = new_val
                results.append(new_val)
            elif cmd == "expire":
                key, seconds, nx, xx = args
                already_has_expiry = key in self.redis.expiry

                if nx and already_has_expiry:
                    results.append(False)
                    continue
                if xx and not already_has_expiry:
                    results.append(False)
                    continue

                self.redis.expiry[key] = seconds
                results.append(True)
        self.commands = []
        return results

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

class MockRedis:
    """A minimal mock redis for local development when no redis server is found."""
    def __init__(self):
        self.data = {}
        self.expiry = {}
        logger.info("Initialized MockRedis (In-Memory)")

    def pipeline(self, transaction=True):
        return MockPipeline(self)

    async def ping(self):
        return True

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: Any, ex: int = None, nx: bool = False, xx: bool = False):
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        exists = key in self.data
        if nx and exists:
            return None
        if xx and not exists:
            return None
        self.data[key] = value
        if ex is not None:
            self.expiry[key] = ex
        return True

    async def delete(self, key: str):
        if key in self.data:
            del self.data[key]
        self.expiry.pop(key, None)
        return 1

    async def exists(self, key: str):
        return 1 if key in self.data else 0

    async def aclose(self):
        pass

class RedisClient:
    def __init__(self):
        self._redis: Optional[Any] = None
        self._loop_id: Optional[int] = None

    async def get_client(self) -> Any:
        current_loop_id = id(asyncio.get_running_loop())
        if self._redis is not None and self._loop_id != current_loop_id:
            logger.info("Redis client loop changed; recreating client for the active event loop.")
            await self.close()

        if self._redis is None:
            await self._connect(current_loop_id)
        return self._redis

    async def _connect(self, loop_id: int) -> None:
        redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
        try:
            self._redis = redis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            self._loop_id = loop_id
            logger.info("Connected to Redis at %s", redis_url)
        except Exception as e:
            logger.warning("Failed to connect to Redis: %s. Falling back to MockRedis.", e)
            self._redis = MockRedis()
            self._loop_id = loop_id

    async def close(self):
        if self._redis is not None:
            if hasattr(self._redis, "aclose"):
                try:
                    await self._redis.aclose()
                except RuntimeError:
                    logger.warning("Ignoring Redis close failure caused by a closed event loop.")
            self._redis = None
            self._loop_id = None

redis_manager = RedisClient()

async def get_redis_client() -> Any:
    return await redis_manager.get_client()
