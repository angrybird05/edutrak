"""
Auth module schemas â€” Request/response models for authentication.
"""
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

OTPRequestedRole = Literal["teacher", "student", "parent"]


class OTPRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format")
    requested_role: OTPRequestedRole


class OTPVerify(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format")
    requested_role: OTPRequestedRole
    otp_code: str = Field(..., min_length=6, max_length=6)


class PasswordLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[UUID] = None
    role: Optional[str] = None
    token_type: Optional[str] = None
    jti: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class StudentLoginChoice(BaseModel):
    student_id: str
    user_id: str
    full_name: str
    admission_number: str
    roll_number: Optional[str] = None


class OTPSelectionResponse(BaseModel):
    selection_required: bool = True
    selection_token: str
    role: str = "student"
    phone: str
    profiles: list[StudentLoginChoice]


class StudentProfileSelectRequest(BaseModel):
    selection_token: str
    student_id: str


class AdminRegister(BaseModel):
    full_name: str
    username: str
    password: str
    school_name: str
    school_email: Optional[str] = None
    village: Optional[str] = None
    mandal: Optional[str] = None
    district_city: str
    pincode: str
