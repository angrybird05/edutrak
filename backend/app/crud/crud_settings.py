from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.settings import UserSettings
from app.schemas.settings import UserSettingsBase, UserSettingsUpdate
from uuid import UUID

class CRUDSettings(CRUDBase[UserSettings, UserSettingsBase, UserSettingsUpdate]):
    async def get_by_user(self, db: AsyncSession, *, user_id: UUID) -> Optional[UserSettings]:
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        return result.scalars().first()

    async def create_for_user(self, db: AsyncSession, *, user_id: UUID) -> UserSettings:
        db_obj = UserSettings(user_id=user_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

user_settings = CRUDSettings(UserSettings)
