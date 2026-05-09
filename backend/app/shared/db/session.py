"""
Shared database session management.

Provides the async SQLAlchemy engine, session factory, and FastAPI dependency
for injecting database sessions into endpoints. Tuned for multi-worker
horizontal scaling with connection pooling.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DB_ECHO,
    future=True,
    # Connection pool tuned for multi-worker deployment.
    # With 2 Uvicorn workers, each gets its own pool of 20+10 connections.
    # Total max connections = workers × (pool_size + max_overflow) = 2 × 30 = 60.
    # Ensure PostgreSQL max_connections >= total + admin headroom.
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,      # Recycle connections every 30 min (prevent stale connections)
    pool_pre_ping=True,     # Verify connection is alive before using it
)

SessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency that yields a scoped async session."""
    async with SessionLocal() as session:
        yield session
