from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.school import School
from app.schemas.school import SchoolCreate, SchoolUpdate


class CRUDSchool(CRUDBase[School, SchoolCreate, SchoolUpdate]):
    async def get_by_chain(self, db: AsyncSession, *, chain_id: UUID) -> List[School]:
        query = select(School).where(School.chain_id == chain_id)
        result = await db.execute(query)
        return result.scalars().all()


school = CRUDSchool(School)
