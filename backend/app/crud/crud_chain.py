from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.school import Chain
from app.schemas.chain import ChainCreate, ChainUpdate


class CRUDChain(CRUDBase[Chain, ChainCreate, ChainUpdate]):
    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[Chain]:
        query = select(Chain).where(Chain.name == name)
        result = await db.execute(query)
        return result.scalars().first()


chain = CRUDChain(Chain)
