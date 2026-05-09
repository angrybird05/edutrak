import asyncio
from sqlalchemy import text
from app.db.session import SessionLocal

async def clean_attendance_raw():
    async with SessionLocal() as session:
        # PostgreSQL specific query to delete duplicates keeping the one with minimal ID
        sql = """
        DELETE FROM attendance
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY student_id, date
                           ORDER BY created_at DESC
                       ) as row_num
                FROM attendance
            ) t
            WHERE t.row_num > 1
        );
        """
        await session.execute(text(sql))
        await session.commit()
        print("Raw SQL Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(clean_attendance_raw())
