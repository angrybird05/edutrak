import asyncio
import sys
import os
sys.path.insert(0, ".")

async def main():
    from app.shared.db.session import SessionLocal
    from sqlalchemy import text
    from app.modules.analytics.report_service import report_card_service
    
    async with SessionLocal() as db:
        # Get a student ID who HAS marks
        result = await db.execute(text("SELECT DISTINCT student_id FROM mark LIMIT 1"))
        student_id = result.scalar()
        if not student_id:
            print("No students with marks found.")
            return

        print(f"Generating report for student {student_id}...")
        try:
            report = await report_card_service.generate_report_card(db, student_id, "Term 1 Final")
            print(f"Success! Report generated at: {report.pdf_url}")
        except Exception as e:
            print(f"Failed to generate report: {e}")

asyncio.run(main())
