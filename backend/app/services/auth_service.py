import random
import string
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, OTPSession
from app.core.sms import sms_client
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password

PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


from app.core.rate_limit import request_ip_limiter, verify_ip_limiter

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def generate_otp(self, length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        normalized = str(phone or "").strip().replace(" ", "")
        if not PHONE_PATTERN.match(normalized):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone format",
            )
        return normalized

    async def request_otp(self, phone: str, request_ip: Optional[str] = None) -> bool:
        """
        Generates an OTP, hashes it, saves it to the database, and sends it via SMS.
        """
        phone = self._normalize_phone(phone)
        if request_ip and not await request_ip_limiter.allow(f"{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests from this IP. Please try again later.",
            )

        now = _utcnow()
        cooldown_cutoff = now - timedelta(seconds=settings.OTP_REQUEST_COOLDOWN_SECONDS)
        recent_window_cutoff = now - timedelta(minutes=10)

        latest_result = await self.db.execute(
            select(OTPSession)
            .where(OTPSession.phone == phone)
            .order_by(OTPSession.created_at.desc())
            .limit(1)
        )
        latest_session = latest_result.scalars().first()
        if latest_session and latest_session.created_at >= cooldown_cutoff:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="OTP requested too recently. Please wait before requesting again.",
            )

        recent_count_result = await self.db.execute(
            select(func.count()).where(
                and_(OTPSession.phone == phone, OTPSession.created_at >= recent_window_cutoff)
            )
        )
        recent_count = int(recent_count_result.scalar() or 0)
        if recent_count >= settings.OTP_MAX_REQUESTS_PER_10_MIN:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests. Please try again after some time.",
            )

        otp = self.generate_otp()
        hashed_otp = get_password_hash(otp)
        expires_at = _utcnow() + timedelta(minutes=10)
        
        # Create OTP session
        otp_session = OTPSession(
            phone=phone,
            otp_code=hashed_otp,
            expires_at=expires_at,
            attempts_count=0,
            locked_until=None,
            request_ip=request_ip,
        )
        self.db.add(otp_session)
        await self.db.commit()
        
        # Send SMS (using plain OTP)
        return await sms_client.send_otp(phone, otp)

    async def verify_otp(
        self, phone: str, otp_code: str, request_ip: Optional[str] = None
    ) -> Optional[Tuple[str, str, User]]:
        """
        Verifies the OTP and returns a JWT token if valid.
        """
        phone = self._normalize_phone(phone)
        if request_ip and not await verify_ip_limiter.allow(f"{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP verification attempts from this IP. Try later.",
            )

        now = _utcnow()
        # Find the latest valid OTP session for this phone
        query = select(OTPSession).where(
            and_(
                OTPSession.phone == phone,
                OTPSession.is_used == False,
                OTPSession.expires_at > now
            )
        ).order_by(OTPSession.created_at.desc())
        
        result = await self.db.execute(query)
        otp_session = result.scalars().first()
        
        if not otp_session:
            return None

        if otp_session.locked_until and otp_session.locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="OTP verification is temporarily locked due to repeated failures.",
            )

        if not verify_password(otp_code, otp_session.otp_code):
            otp_session.attempts_count = int(otp_session.attempts_count or 0) + 1
            if otp_session.attempts_count >= settings.OTP_MAX_VERIFY_ATTEMPTS:
                otp_session.locked_until = now + timedelta(minutes=settings.OTP_LOCK_MINUTES)
            self.db.add(otp_session)
            await self.db.commit()
            return None
        
        # Mark OTP as used
        otp_session.is_used = True
        otp_session.attempts_count = 0
        otp_session.locked_until = None
        self.db.add(otp_session)
        
        # Find or create user
        query_user = select(User).where(User.phone == phone)
        result_user = await self.db.execute(query_user)
        user = result_user.scalars().first()
        
        if not user:
            return None
        
        await self.db.commit()
        
        # Issue JWT
        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value)
        return access_token, refresh_token, user

    async def login_with_password(
        self, username: str, password: str, request_ip: Optional[str] = None
    ) -> Optional[Tuple[str, str, User]]:
        """
        Verifies username and password and returns JWT tokens.
        """
        # Rate limiting (reusing verify_ip_limiter or separate one)
        if request_ip and not await verify_ip_limiter.allow(f"pwd_{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )

        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        user = result.scalars().first()

        if not user or not user.password_hash:
            return None

        if not verify_password(password, user.password_hash):
            return None

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled.",
            )

        # Issue JWT
        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value)
        return access_token, refresh_token, user

def get_auth_service(db: AsyncSession) -> AuthService:
    return AuthService(db)
