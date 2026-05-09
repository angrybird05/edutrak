import asyncio
from uuid import UUID
from app.db.session import SessionLocal
from app.models.student import Student
from sqlalchemy import select
from app.services.ai_service import ai_insight_service
from app.models.performance import Mark
import json

async def main():
    async with SessionLocal() as db:
        # Find a student with some marks
        result = await db.execute(select(Mark.student_id).limit(1))
        student_id = result.scalar_one_or_none()
        
        if not student_id:
            print("No students with marks found in the DB.")
            return

        print(f"Collecting data for student {student_id}...")
        
        # Manually collect data first to show what we send to the AI
        data = await ai_insight_service._collect_student_data(db, student_id)
        print("\n--- RAW STUDENT DATA WE SEND TO AI ---")
        print(json.dumps(data, indent=2, default=str))

        print(f"\n--- GENERATING AI INSIGHT (Connecting to local Llama 3.1) ---")
        insight = await ai_insight_service.generate_insight(db, student_id)
        if insight:
            print("\n--- FINAL AI OUTPUT ---")
            print(json.dumps({
                "summary": insight.insight_text,
                "recommendations": insight.recommendations,
                "context_hash": insight.context_hash
            }, indent=2))
        else:
            print("\nFailed to generate insight (Ollama might not be running).")

if __name__ == "__main__":
    asyncio.run(main())
