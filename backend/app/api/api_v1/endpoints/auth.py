from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, decode_token, revoke_token, _utcnow
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService, get_auth_service
from app.services.audit_service import AuditService, get_audit_service
from app.schemas.token import Token
from app.api import deps

router = APIRouter()


# --- Request Bodies (not query params, to avoid logging sensitive data) ---

class OTPRequestBody(BaseModel):
    phone: str

class OTPVerifyBody(BaseModel):
    phone: str
    otp_code: str

class RefreshTokenBody(BaseModel):
    refresh_token: str

class PasswordLoginBody(BaseModel):
    username: str
    password: str


@router.post("/login/otp", response_model=dict)
async def login_otp(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: OTPRequestBody,
) -> Any:
    """
    Step 1: Request OTP for a phone number.
    """
    auth_service = get_auth_service(db)
    request_ip = request.client.host if request.client else None
    success = await auth_service.request_otp(body.phone, request_ip=request_ip)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )
    return {"message": "OTP sent successfully", "phone": body.phone}

@router.post("/login/password", response_model=Token)
async def login_password(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: PasswordLoginBody,
) -> Any:
    """
    Standard username/password login for Staff.
    """
    auth_service = get_auth_service(db)
    audit_service = get_audit_service(db)
    
    request_ip = request.client.host if request.client else None
    result = await auth_service.login_with_password(body.username, body.password, request_ip=request_ip)
    
    if not result:
        await audit_service.log(
            action="LOGIN_FAILED_PWD",
            resource_type="user",
            details={"username": body.username},
            ip_address=request.client.host if request.client else None,
            trace_id=getattr(request.state, "trace_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    access_token, refresh_token, user = result
    
    await audit_service.log(
        user_id=user.id,
        action="LOGIN_SUCCESS_PWD",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        school_id=user.school_id,
        trace_id=getattr(request.state, "trace_id", None),
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/verify/otp", response_model=Token)
async def verify_otp(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: OTPVerifyBody,
) -> Any:
    """
    Step 2: Verify OTP and return JWT token.
    """
    auth_service = get_auth_service(db)
    audit_service = get_audit_service(db)
    
    request_ip = request.client.host if request.client else None
    result = await auth_service.verify_otp(body.phone, body.otp_code, request_ip=request_ip)
    
    if not result:
        # Optional: log failed login attempt
        await audit_service.log(
            action="LOGIN_FAILED",
            resource_type="user",
            details={"phone": body.phone},
            ip_address=request.client.host if request.client else None,
            trace_id=getattr(request.state, "trace_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )
    
    access_token, refresh_token, user = result
    
    # Log successful login
    await audit_service.log(
        user_id=user.id,
        action="LOGIN_SUCCESS",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        school_id=user.school_id,
        trace_id=getattr(request.state, "trace_id", None),
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    *,
    db: AsyncSession = Depends(get_db),
    body: RefreshTokenBody,
) -> Any:
    """
    Refresh access token using a refresh token.
    """
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not active")

    return {
        "access_token": create_access_token(subject=user_id, role=role),
        "refresh_token": create_refresh_token(subject=user_id, role=role),
        "token_type": "bearer",
    }


@router.post("/logout", response_model=dict)
async def logout(
    *,
    request: Request,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Logout by extracting the JWT token, asserting its TTL, and adding it to the Redis blocklist.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"message": "Logged out successfully"}

    token = auth_header.split(" ")[1]
    
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if jti and exp:
            now_ts = int(_utcnow().timestamp())
            expires_in = exp - now_ts
            if expires_in > 0:
                await revoke_token(jti, expires_in)
    except Exception:
        # Avoid crashing logout if token is invalid or expired
        pass

    return {"message": "Logged out successfully"}
