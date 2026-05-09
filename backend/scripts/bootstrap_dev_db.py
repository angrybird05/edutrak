import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import get_password_hash
from app.shared.db.session import engine
from app.modules.auth.models import User, UserRole
from app.modules.academic.models import School, Chain, Class, Section


async def bootstrap() -> None:
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        admin_exists = await session.execute(
            select(User).where(User.username == "admin")
        )
        if admin_exists.scalars().first():
            print("Development bootstrap skipped: admin user already exists.")
            return

        chain = Chain(name="EduTrack Academy Chain")
        session.add(chain)
        await session.flush()

        school = School(
            name="EduTrack Primary School",
            chain_id=chain.id,
            email="primary@edutrack.com",
            village="Sample Village",
            mandal="Sample Mandal",
            district_city="Sample City",
            pincode="123456",
        )
        session.add(school)
        await session.flush()

        admin_user = User(
            full_name="System Admin",
            username="admin",
            password_hash=get_password_hash("admin123"),
            phone="+15550000001",
            role=UserRole.ADMIN,
            school_id=school.id,
            is_active=True,
        )
        session.add(admin_user)

        test_class = Class(name="Class 10", class_number=10, school_id=school.id)
        session.add(test_class)
        await session.flush()

        test_section = Section(name="Section A", class_id=test_class.id)
        session.add(test_section)

        await session.commit()
        print("Development bootstrap complete: seeded default school, class, section, and admin/admin123.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
