from typing import Any, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    trace_id: Optional[str] = None
