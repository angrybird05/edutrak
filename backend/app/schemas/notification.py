from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: UUID
    event_id: UUID
    event_type: str
    channel: str
    status: str
    payload_json: dict[str, Any]
    event_created_at: datetime
    created_at: datetime
    read_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    total: int
    page: int
    page_size: int


class NotificationMarkReadResponse(BaseModel):
    id: UUID
    status: str
    read_at: datetime


class NotificationReadAllResponse(BaseModel):
    updated_count: int
