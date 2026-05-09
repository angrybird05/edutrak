from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> Optional[User]:
        query = select(User).where(User.phone == phone)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_by_role(
        self, db: AsyncSession, *, role: UserRole, skip: int = 0, limit: int = 100
    ) -> List[User]:
        query = select(User).where(User.role == role).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()


user = CRUDUser(User)
