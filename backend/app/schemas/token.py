from typing import Optional
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    token_type: Optional[str] = None
    jti: Optional[str] = None
    exp: Optional[int] = None
