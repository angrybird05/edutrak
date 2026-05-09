import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.shared.db.session import engine

async def main():
    sf = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sf() as session:
        # Check for tables referencing student
        result = await session.execute(text(
            "SELECT tc.table_name, tc.constraint_name, ccu.table_name AS foreign_table_name "
            "FROM information_schema.table_constraints AS tc "
            "JOIN information_schema.constraint_column_usage AS ccu "
            "ON ccu.constraint_name = tc.constraint_name "
            "AND ccu.table_schema = tc.table_schema "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "AND ccu.table_name = 'student'"
        ))
        fks = result.fetchall()
        print("FK references to student:")
        for fk in fks:
            print(f"  {fk}")

        # Check for aiinsight data referencing our students
        result2 = await session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE '%insight%'"
        ))
        for t in result2.fetchall():
            tname = t[0]
            print(f"\nTable: {tname}")
            cols = await session.execute(text(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tname}'"
            ))
            print(f"  Columns: {[c[0] for c in cols.fetchall()]}")
            cnt = await session.execute(text(f"SELECT COUNT(*) FROM {tname}"))
            print(f"  Row count: {cnt.scalar()}")

        # Check attendance, mark, homework, learningtask referencing students
        for tname in ["attendance", "mark", "aiinsight", "auditlog", "learningtask"]:
            try:
                cnt = await session.execute(text(f"SELECT COUNT(*) FROM {tname}"))
                print(f"\n{tname}: {cnt.scalar()} rows")
            except Exception as e:
                print(f"\n{tname}: table not found or error: {e}")

    await engine.dispose()

asyncio.run(main())
