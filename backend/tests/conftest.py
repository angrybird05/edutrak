import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.base import Base
from app.core.redis import get_redis_client, redis_manager
from app.shared.db.session import get_db


# Use a separate test database
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", settings.SQLALCHEMY_DATABASE_URI)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)
TestSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session")
async def database_ready() -> None:
    try:
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Database is not available for DB-dependent tests: {exc}")

@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client wired to the test DB session."""
    from main import app

    await redis_manager.close()
    redis_client = await get_redis_client()
    if hasattr(redis_client, "flushdb"):
        await redis_client.flushdb()

    async def _override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.rollback()

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await redis_manager.close()
