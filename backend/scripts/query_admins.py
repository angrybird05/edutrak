import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from app.shared.db.session import SessionLocal
    from sqlalchemy import text
    async with SessionLocal() as db:
        result = await db.execute(text(
            "SELECT id, username, phone, role, full_name, school_id FROM \"user\" WHERE role='ADMIN' LIMIT 10"
        ))
        rows = result.fetchall()
        print("=== Admin Users ===")
        for r in rows:
            print(f"  id={r[0]}, username={r[1]}, phone={r[2]}, role={r[3]}, name={r[4]}, school_id={r[5]}")

        # Also check students
        result2 = await db.execute(text(
            "SELECT s.id, u.full_name, s.admission_number, s.roll_number, c.name as class_name, sec.name as section_name "
            "FROM student s "
            "JOIN \"user\" u ON u.id = s.user_id "
            "JOIN class c ON c.id = s.class_id "
            "JOIN section sec ON sec.id = s.section_id "
            "LIMIT 10"
        ))
        rows2 = result2.fetchall()
        print(f"\n=== Students ({len(rows2)}) ===")
        for r in rows2:
            print(f"  id={r[0]}, name={r[1]}, adm={r[2]}, roll={r[3]}, class={r[4]}, section={r[5]}")

        # Check marks
        result3 = await db.execute(text("SELECT COUNT(*) FROM mark"))
        print(f"\n=== Marks count: {result3.scalar()} ===")

        # Check exams
        result4 = await db.execute(text("SELECT id, name, exam_date FROM exam LIMIT 5"))
        rows4 = result4.fetchall()
        print(f"\n=== Exams ({len(rows4)}) ===")
        for r in rows4:
            print(f"  id={r[0]}, name={r[1]}, date={r[2]}")

asyncio.run(main())
