"""
Auth module endpoints — OTP login, password login, token refresh, logout.

Migrated from app/api/api_v1/endpoints/auth.py with event bus integration.
Audit logging is now handled by event subscribers instead of direct service calls.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, decode_token, revoke_token, _utcnow
from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    OTPRequest, OTPVerify, PasswordLogin, Token, RefreshRequest, AuthResponse, AdminRegister,
    OTPSelectionResponse, StudentProfileSelectRequest,
)
from app.modules.auth.service import get_auth_service

router = APIRouter()


@router.post("/login/otp", response_model=dict)
async def login_otp(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: OTPRequest,
) -> Any:
    """Step 1: Request OTP for a phone number."""
    auth_service = get_auth_service(db)
    request_ip = request.client.host if request.client else None
    success = await auth_service.request_otp(body.phone, body.requested_role, request_ip=request_ip)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )
    return {"message": "OTP sent successfully", "phone": body.phone, "requested_role": body.requested_role}


@router.post("/register/admin", response_model=AuthResponse)
async def register_admin(
    *,
    db: AsyncSession = Depends(get_db),
    body: AdminRegister,
) -> Any:
    """Register a new School and Administrator."""
    auth_service = get_auth_service(db)
    user = await auth_service.register_admin(body)
    
    # Auto-login after registration
    access_token = create_access_token(subject=user.id, role=user.role.value)
    refresh_token = create_refresh_token(subject=user.id, role=user.role.value)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role.value,
        "full_name": user.full_name,
    }


@router.post("/login/password", response_model=AuthResponse)
async def login_password(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: PasswordLogin,
) -> Any:
    """Standard username/password login for Staff."""
    auth_service = get_auth_service(db)
    request_ip = request.client.host if request.client else None
    result = await auth_service.login_with_password(body.username, body.password, request_ip=request_ip)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    access_token, refresh_token, user = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role.value,
        "full_name": user.full_name,
    }


@router.post("/verify/otp", response_model=AuthResponse | OTPSelectionResponse)
async def verify_otp(
    *,
    db: AsyncSession = Depends(get_db),
    request: Request,
    body: OTPVerify,
) -> Any:
    """Step 2: Verify OTP and return JWT token."""
    auth_service = get_auth_service(db)
    request_ip = request.client.host if request.client else None
    result = await auth_service.verify_otp(
        body.phone,
        body.otp_code,
        body.requested_role,
        request_ip=request_ip,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )

    if isinstance(result, dict) and result.get("selection_required"):
        return result

    access_token, refresh_token, user = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role.value,
        "full_name": user.full_name,
    }


@router.post("/select-profile", response_model=AuthResponse)
async def select_student_profile(
    *,
    db: AsyncSession = Depends(get_db),
    body: StudentProfileSelectRequest,
) -> Any:
    """Complete student login after selecting one child from a shared guardian phone."""
    auth_service = get_auth_service(db)
    access_token, refresh_token, user = await auth_service.select_student_profile(
        body.selection_token,
        body.student_id,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role.value,
        "full_name": user.full_name,
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    *,
    db: AsyncSession = Depends(get_db),
    body: RefreshRequest,
) -> Any:
    """Refresh access token using a refresh token."""
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
    current_user: User = Depends(get_current_user),
) -> Any:
    """Logout by revoking the JWT token via Redis blocklist."""
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
        pass

    return {"message": "Logged out successfully"}
