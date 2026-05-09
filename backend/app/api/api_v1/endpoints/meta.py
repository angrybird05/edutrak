from typing import Any
from fastapi import APIRouter, Depends, Response

from app.models.user import UserRole
from app.schemas.performance import AttendanceStatus, MarkStatus

router = APIRouter()


@router.get("/enums")
async def get_enums(response: Response) -> Any:
    """
    Return all enum values. Cacheable for 5 minutes.
    """
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "user_roles": [role.value for role in UserRole],
        "attendance_statuses": [status.value for status in AttendanceStatus],
        "mark_statuses": [status.value for status in MarkStatus],
    }
