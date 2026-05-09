import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from app.shared.db.session import engine

async def main():
    sf = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sf() as session:
        result = await session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = result.fetchall()
        print("All tables in database:")
        for t in tables:
            print(f"  {t[0]}")
    await engine.dispose()

asyncio.run(main())
