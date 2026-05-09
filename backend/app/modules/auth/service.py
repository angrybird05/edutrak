"""
Auth module service â€” OTP, password login, and JWT lifecycle.

Migrated from app/services/auth_service.py with event bus integration.
"""
import random
import re
import string
from datetime import UTC, datetime, timedelta
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.rate_limit import request_ip_limiter, verify_ip_limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_selection_token,
    decode_selection_token,
    get_password_hash,
    verify_password,
)
from app.core.sms import sms_client
from app.modules.academic.models import School
from app.modules.auth.models import OTPSession, User, UserRole
from app.modules.auth.schemas import AdminRegister
from app.modules.identity.models import Student, parent_student

PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_school_name(name: str) -> str:
        normalized = " ".join(str(name or "").strip().split())
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="School name is required",
            )
        return normalized

    def generate_otp(self, length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = str(username or "").strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is required",
            )
        return normalized

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        normalized = str(phone or "").strip().replace(" ", "")
        if not PHONE_PATTERN.match(normalized):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone format",
            )
        return normalized

    async def _generate_internal_student_phone(self) -> str:
        while True:
            candidate = f"student_{random.randrange(10**12, 10**13)}_{random.randrange(10**6, 10**7)}"
            result = await self.db.execute(select(User).where(User.phone == candidate))
            if not result.scalars().first():
                return candidate

    async def _migrate_legacy_student_guardian_phone(self, phone: str) -> list[Student]:
        legacy_student_result = await self.db.execute(
            select(Student)
            .join(User, Student.user_id == User.id)
            .where(User.phone == phone, User.role == UserRole.STUDENT)
            .options(selectinload(Student.user))
        )
        legacy_student = legacy_student_result.scalars().first()
        if not legacy_student or not legacy_student.user:
            return []

        legacy_student.guardian_phone = phone
        legacy_student.user.phone = await self._generate_internal_student_phone()
        self.db.add(legacy_student)
        self.db.add(legacy_student.user)
        await self.db.flush()
        return [legacy_student]

    async def _get_students_by_guardian_phone(self, phone: str) -> list[Student]:
        result = await self.db.execute(
            select(Student)
            .where(Student.guardian_phone == phone)
            .options(selectinload(Student.user))
            .order_by(Student.created_at.asc())
        )
        students = result.scalars().all()
        if students:
            return students
        return await self._migrate_legacy_student_guardian_phone(phone)

    async def _get_teacher_by_phone(self, phone: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.phone == phone, User.role == UserRole.TEACHER)
        )
        return result.scalars().first()

    async def _sync_parent_links(self, parent_user: User, students: list[Student]) -> None:
        existing_links_result = await self.db.execute(
            select(parent_student.c.student_id).where(parent_student.c.parent_id == parent_user.id)
        )
        existing_student_ids = set(existing_links_result.scalars().all())

        from sqlalchemy import insert

        linked_student_ids: list[str] = []
        for student in students:
            if student.id in existing_student_ids:
                continue
            await self.db.execute(insert(parent_student).values(parent_id=parent_user.id, student_id=student.id))
            linked_student_ids.append(str(student.id))

        if linked_student_ids:
            await event_bus.emit(
                "identity.parent_linked",
                {"parent_id": str(parent_user.id), "student_ids": linked_student_ids},
            )

    async def _resolve_parent_login(self, phone: str) -> Optional[User]:
        existing_parent_result = await self.db.execute(
            select(User).where(User.phone == phone, User.role == UserRole.PARENT)
        )
        existing_parent = existing_parent_result.scalars().first()
        students = await self._get_students_by_guardian_phone(phone)

        if not existing_parent and not students:
            return None

        if existing_parent:
            if students:
                await self._sync_parent_links(existing_parent, students)
                await self.db.commit()
            return existing_parent

        school_ids = {student.school_id for student in students}
        if len(school_ids) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guardian phone is linked to multiple schools and cannot be auto-created",
            )

        display_name = next((student.guardian_name for student in students if student.guardian_name), "Parent")
        parent_user = User(
            phone=phone,
            full_name=display_name,
            role=UserRole.PARENT,
            school_id=students[0].school_id,
            is_active=True,
        )
        self.db.add(parent_user)
        await self.db.flush()
        await self._sync_parent_links(parent_user, students)
        await self.db.commit()
        await self.db.refresh(parent_user)
        return parent_user

    async def _resolve_role_candidate(self, phone: str, requested_role: str) -> bool:
        if requested_role == UserRole.TEACHER.value:
            return bool(await self._get_teacher_by_phone(phone))
        if requested_role == UserRole.PARENT.value:
            existing_parent_result = await self.db.execute(
                select(User).where(User.phone == phone, User.role == UserRole.PARENT)
            )
            if existing_parent_result.scalars().first():
                return True
            return bool(await self._get_students_by_guardian_phone(phone))
        if requested_role == UserRole.STUDENT.value:
            return bool(await self._get_students_by_guardian_phone(phone))
        return False

    async def request_otp(self, phone: str, requested_role: str, request_ip: Optional[str] = None) -> bool:
        """Generates an OTP, hashes it, saves it to the database, and sends it via SMS."""
        phone = self._normalize_phone(phone)
        if requested_role not in {
            UserRole.TEACHER.value,
            UserRole.STUDENT.value,
            UserRole.PARENT.value,
        }:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OTP login role")

        if not await self._resolve_role_candidate(phone, requested_role):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found for this phone and role")

        if request_ip and not await request_ip_limiter.allow(f"{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP requests from this IP. Please try again later.",
            )

        now = _utcnow()
        cooldown_cutoff = now - timedelta(seconds=settings.OTP_REQUEST_COOLDOWN_SECONDS)
        recent_window_cutoff = now - timedelta(minutes=10)
        role_filter = or_(OTPSession.requested_role == requested_role, OTPSession.requested_role.is_(None))

        latest_result = await self.db.execute(
            select(OTPSession)
            .where(OTPSession.phone == phone, role_filter)
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
                and_(
                    OTPSession.phone == phone,
                    role_filter,
                    OTPSession.created_at >= recent_window_cutoff,
                )
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

        otp_session = OTPSession(
            phone=phone,
            requested_role=requested_role,
            otp_code=hashed_otp,
            expires_at=expires_at,
            attempts_count=0,
            locked_until=None,
            request_ip=request_ip,
        )
        self.db.add(otp_session)
        await self.db.commit()

        return await sms_client.send_otp(phone, otp)

    async def verify_otp(
        self,
        phone: str,
        otp_code: str,
        requested_role: str,
        request_ip: Optional[str] = None,
    ) -> Optional[Tuple[str, str, User] | dict]:
        """Verifies the OTP and returns JWT tokens if valid."""
        phone = self._normalize_phone(phone)
        if request_ip and not await verify_ip_limiter.allow(f"{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many OTP verification attempts from this IP. Try later.",
            )

        now = _utcnow()
        role_filter = or_(OTPSession.requested_role == requested_role, OTPSession.requested_role.is_(None))
        query = (
            select(OTPSession)
            .where(
                and_(
                    OTPSession.phone == phone,
                    role_filter,
                    OTPSession.is_used == False,
                    OTPSession.expires_at > now,
                )
            )
            .order_by(OTPSession.created_at.desc())
        )

        result = await self.db.execute(query)
        otp_session = result.scalars().first()

        if not otp_session:
            await event_bus.emit("auth.login_failed", {"phone": phone, "reason": "no_valid_otp", "ip": request_ip})
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
            await event_bus.emit("auth.login_failed", {"phone": phone, "reason": "wrong_otp", "ip": request_ip})
            return None

        otp_session.is_used = True
        otp_session.attempts_count = 0
        otp_session.locked_until = None
        self.db.add(otp_session)

        user: Optional[User] = None
        if requested_role == UserRole.TEACHER.value:
            user = await self._get_teacher_by_phone(phone)
        elif requested_role == UserRole.PARENT.value:
            user = await self._resolve_parent_login(phone)
        elif requested_role == UserRole.STUDENT.value:
            students = await self._get_students_by_guardian_phone(phone)
            if not students:
                await self.db.commit()
                return None
            if len(students) == 1:
                user = students[0].user
            else:
                await self.db.commit()
                return {
                    "selection_required": True,
                    "selection_token": create_selection_token(
                        phone=phone,
                        requested_role=requested_role,
                        student_ids=[str(student.id) for student in students],
                    ),
                    "role": UserRole.STUDENT.value,
                    "phone": phone,
                    "profiles": [
                        {
                            "student_id": str(student.id),
                            "user_id": str(student.user_id),
                            "full_name": student.user.full_name or student.admission_number,
                            "admission_number": student.admission_number,
                            "roll_number": student.roll_number,
                        }
                        for student in students
                    ],
                }
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported OTP login role")

        if not user:
            await self.db.commit()
            return None
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled.")

        await self.db.commit()

        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value)

        await event_bus.emit(
            "auth.login_success",
            {
                "user_id": str(user.id),
                "phone": phone,
                "method": "otp",
                "requested_role": requested_role,
                "ip": request_ip,
            },
        )

        return access_token, refresh_token, user

    async def select_student_profile(self, selection_token: str, student_id: str) -> Tuple[str, str, User]:
        payload = decode_selection_token(selection_token)
        allowed_student_ids = {str(item) for item in payload.get("student_ids") or []}
        phone = payload.get("phone")

        if str(student_id) not in allowed_student_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Selected profile is not permitted")

        student_result = await self.db.execute(
            select(Student)
            .where(Student.id == student_id, Student.guardian_phone == phone)
            .options(selectinload(Student.user))
        )
        student = student_result.scalars().first()
        if not student or not student.user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
        if not student.user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student account is disabled")

        access_token = create_access_token(subject=student.user.id, role=student.user.role.value)
        refresh_token = create_refresh_token(subject=student.user.id, role=student.user.role.value)
        return access_token, refresh_token, student.user

    async def login_with_password(
        self, username: str, password: str, request_ip: Optional[str] = None
    ) -> Optional[Tuple[str, str, User]]:
        """Verifies username and password and returns JWT tokens."""
        username = self._normalize_username(username)
        if request_ip and not await verify_ip_limiter.allow(f"pwd_{request_ip}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )

        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        user = result.scalars().first()

        if not user or not user.password_hash:
            await event_bus.emit("auth.login_failed", {"username": username, "reason": "user_not_found", "ip": request_ip})
            return None

        if not verify_password(password, user.password_hash):
            await event_bus.emit("auth.login_failed", {"username": username, "reason": "wrong_password", "ip": request_ip})
            return None

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled.",
            )

        access_token = create_access_token(subject=user.id, role=user.role.value)
        refresh_token = create_refresh_token(subject=user.id, role=user.role.value)

        await event_bus.emit(
            "auth.login_success",
            {
                "user_id": str(user.id),
                "username": username,
                "method": "password",
                "ip": request_ip,
            },
        )

        return access_token, refresh_token, user

    async def register_admin(self, data: AdminRegister) -> User:
        """Creates a new School and a primary Admin user."""
        username = self._normalize_username(data.username)
        full_name = str(data.full_name or "").strip()
        school_name = self._normalize_school_name(data.school_name)
        district_city = str(data.district_city or "").strip()
        pincode = str(data.pincode or "").strip()

        existing_user_query = await self.db.execute(select(User).where(User.username == username))
        if existing_user_query.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

        existing_school_query = await self.db.execute(
            select(School).where(func.lower(School.name) == school_name.lower())
        )
        if existing_school_query.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A school with this name already exists. Please sign in with the existing admin account or use a distinct school name.",
            )

        school = School(
            name=school_name,
            email=data.school_email.strip() if data.school_email else None,
            village=data.village.strip() if data.village else None,
            mandal=data.mandal.strip() if data.mandal else None,
            district_city=district_city,
            pincode=pincode,
        )
        self.db.add(school)
        await self.db.flush()

        user = User(
            username=username,
            password_hash=get_password_hash(data.password),
            full_name=full_name,
            role=UserRole.ADMIN,
            school_id=school.id,
            phone=f"admin_{username}",
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        await event_bus.emit(
            "auth.admin_registered",
            {
                "user_id": str(user.id),
                "username": user.username,
                "school_id": str(school.id),
            },
        )

        return user


def get_auth_service(db: AsyncSession) -> AuthService:
    return AuthService(db)
