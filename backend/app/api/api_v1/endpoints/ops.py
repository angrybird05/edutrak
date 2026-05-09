from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.ai_task_queue import ai_insight_task_queue
from app.services.outbox_service import outbox_service

router = APIRouter()


@router.get("/queue-metrics")
async def queue_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.ADMIN)),
) -> Any:
    return {
        "ai_insight_queue": ai_insight_task_queue.stats(),
        "outbox_jobs": await outbox_service.metrics(db),
    }
