from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.api import deps
from app.db.session import get_db
from app.models.user import User

router = APIRouter()

@router.get("/settings", response_model=schemas.settings.UserSettings)
async def get_user_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user's settings.
    """
    settings = await crud.user_settings.get_by_user(db, user_id=current_user.id)
    if not settings:
        # Create default settings if they don't exist
        settings = await crud.user_settings.create_for_user(db, user_id=current_user.id)
    return settings

@router.patch("/settings", response_model=schemas.settings.UserSettings)
async def update_user_settings(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    settings_in: schemas.settings.UserSettingsUpdate,
) -> Any:
    """
    Update current user's settings.
    """
    settings = await crud.user_settings.get_by_user(db, user_id=current_user.id)
    if not settings:
        settings = await crud.user_settings.create_for_user(db, user_id=current_user.id)
    
    updated_settings = await crud.user_settings.update(db, db_obj=settings, obj_in=settings_in)
    return updated_settings
