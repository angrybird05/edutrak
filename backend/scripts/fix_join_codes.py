import asyncio
import random
import string
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.shared.db.session import engine
from app.modules.identity.models import Student

async def fix_join_codes():
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with session_factory() as session:
        print("Finding students with pending join codes...")
        result = await session.execute(
            select(Student).where(Student.parent_joining_code.is_(None))
        )
        students = result.scalars().all()
        
        if not students:
            print("No students found with pending join codes.")
            return
            
        print(f"Found {len(students)} students. Generating codes...")
        
        chars = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0OI1L")
        
        # Load existing codes to avoid collision
        existing_result = await session.execute(
            select(Student.parent_joining_code).where(Student.parent_joining_code.isnot(None))
        )
        existing_codes = {r[0] for r in existing_result.all()}
        
        for student in students:
            while True:
                code = "".join(random.choices(chars, k=6))
                if code not in existing_codes:
                    existing_codes.add(code)
                    student.parent_joining_code = code
                    break
        
        await session.commit()
        print(f"Successfully generated and saved join codes for {len(students)} students.")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_join_codes())
