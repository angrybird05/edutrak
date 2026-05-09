"""
Authentication and authorization dependencies for FastAPI endpoints.

Provides:
- get_current_user: JWT validation + user lookup
- requires_role: Single role checker
- requires_roles: Multi-role checker (new)
- requires_admin: Admin-only shorthand
- requires_school_access: School-scoped authorization (new)
"""
from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_token, is_token_revoked
from app.core.config import settings
from app.shared.db.session import get_db
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/user/auth/login/otp"
)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """Validate JWT and return the current authenticated user."""
    try:
        payload = decode_token(token)
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if token_data.token_type and token_data.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid access token type",
        )

    if token_data.jti and await is_token_revoked(token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    query = select(User).where(User.id == token_data.sub)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    request.state.current_user = user
    request.state.current_user_id = user.id
    request.state.current_user_role = user.role.value if user.role else None
    request.state.current_school_id = user.school_id
    return user


def requires_role(role: UserRole):
    """Dependency that ensures the user has a specific role."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The user doesn't have enough privileges (Required: {role.value})",
            )
        return current_user
    return role_checker


def requires_roles(roles: List[UserRole]):
    """
    Dependency that ensures the user has one of the specified roles.

    Usage:
        @router.get("/dashboard")
        async def dashboard(user = Depends(requires_roles([UserRole.ADMIN, UserRole.TEACHER]))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required one of: {allowed}",
            )
        return current_user
    return role_checker


def requires_admin(current_user: User = Depends(get_current_user)):
    """Shorthand for admin-only endpoints."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Admin required)",
        )
    return current_user


def requires_school_access(school_id_param: str = "school_id"):
    """
    Dependency that verifies the current user belongs to the requested school.

    Admins can access any school. Teachers/students can only access their own.

    Usage:
        @router.get("/schools/{school_id}/students")
        async def list_students(
            school_id: UUID,
            user = Depends(requires_school_access("school_id")),
        ):
            ...
    """
    def checker(request: Request, current_user: User = Depends(get_current_user)):
        school_id = request.path_params.get(school_id_param)
        if school_id and current_user.school_id and str(current_user.school_id) != str(school_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this school's data",
            )
        return current_user
    return checker
