import asyncio
from sqlalchemy import select, func, delete
from app.db.session import SessionLocal
from app.models.performance import Attendance

async def clean_attendance():
    async with SessionLocal() as session:
        # Find duplicates
        subq = (
            select(Attendance.student_id, Attendance.date, func.min(Attendance.id).label("min_id"))
            .group_by(Attendance.student_id, Attendance.date)
            .having(func.count() > 1)
            .subquery()
        )
        
        # This is a bit complex in one go with SQLAlchemy async, 
        # let's just fetch the ones to KEEP or DELETE.
        
        # Get all duplicates pairs
        duplicates_query = select(Attendance.student_id, Attendance.date).group_by(Attendance.student_id, Attendance.date).having(func.count() > 1)
        result = await session.execute(duplicates_query)
        duplicate_pairs = result.all()
        
        print(f"Found {len(duplicate_pairs)} duplicate (student_id, date) pairs.")
        
        for student_id, date in duplicate_pairs:
            # Find all IDs for this pair
            ids_query = select(Attendance.id).where(Attendance.student_id == student_id, Attendance.date == date).order_by(Attendance.created_at.desc())
            ids_result = await session.execute(ids_query)
            ids = ids_result.scalars().all()
            
            # Keep the first one (most recent), delete the rest
            ids_to_delete = ids[1:]
            if ids_to_delete:
                print(f"Deleting {len(ids_to_delete)} duplicates for student {student_id} on {date}")
                await session.execute(delete(Attendance).where(Attendance.id.in_(ids_to_delete)))
        
        await session.commit()
        print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(clean_attendance())
