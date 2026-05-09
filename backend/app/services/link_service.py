import random
import string
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.student import Student

class LinkService:
    @staticmethod
    def generate_joining_code(length: int = 6) -> str:
        """Generates a unique 6-digit alphanumeric code."""
        # Use uppercase letters and digits, excluding confusing characters (0, O, 1, I, L)
        chars = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0OI1L")
        return "".join(random.choices(chars, k=length))

    async def get_unique_joining_code(self, db: AsyncSession) -> str:
        """Ensures the generated code is unique in the database."""
        while True:
            code = self.generate_joining_code()
            result = await db.execute(select(Student).where(Student.parent_joining_code == code))
            if not result.scalars().first():
                return code

link_service = LinkService()
