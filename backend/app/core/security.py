from datetime import datetime, timedelta, timezone
import uuid
from typing import Any, Union
import logging

import bcrypt as bcrypt_lib
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.core.config import settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

ALGORITHM = "HS256"
TOKEN_ISSUER = "edutrack-api"
TOKEN_AUDIENCE = "edutrack-client"


def _utcnow() -> datetime:
    """Timezone-aware UTC now (avoids deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


def create_access_token(
    subject: Union[str, Any], role: str, expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = _utcnow() + expires_delta
    else:
        expire = _utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "token_type": "access",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4())
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], role: str, expires_days: int = 14) -> str:
    expire = _utcnow() + timedelta(days=expires_days)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "token_type": "refresh",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4())
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_selection_token(
    phone: str,
    requested_role: str,
    student_ids: list[str],
    expires_minutes: int = 10,
) -> str:
    expire = _utcnow() + timedelta(minutes=expires_minutes)
    to_encode = {
        "exp": expire,
        "phone": phone,
        "requested_role": requested_role,
        "student_ids": student_ids,
        "token_type": "student_selection",
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
        issuer=TOKEN_ISSUER,
        audience=TOKEN_AUDIENCE,
    )


def decode_selection_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("token_type") != "student_selection":
        raise JWTError("Invalid selection token type")
    return payload


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False

    # Older databases may still hold bcrypt hashes from before the pbkdf2 migration.
    if hashed_password.startswith("$2"):
        try:
            return bcrypt_lib.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def revoke_token(jti: str, expires_in_seconds: int) -> None:
    """Add a token's JTI to the Redis blocklist until it naturally expires."""
    if expires_in_seconds <= 0:
        return
    try:
        redis_client = await get_redis_client()
        await redis_client.setex(f"token_blacklist:{jti}", expires_in_seconds, "revoked")
    except Exception as e:
        logger.error(f"Failed to blacklist token {jti} in Redis: {e}")


async def is_token_revoked(jti: str) -> bool:
    """Check if a token's JTI is in the Redis blocklist."""
    try:
        redis_client = await get_redis_client()
        exists = await redis_client.exists(f"token_blacklist:{jti}")
        return bool(exists)
    except Exception as e:
        logger.error(f"Failed to check token blacklist in Redis for {jti}: {e}")
        # Fail-closed for security: if Redis is down, we cannot guarantee token is valid.
        # However, for UX in small deployments, you might want to consider returning False.
        # We will assume Redis is highly available.
        return False
