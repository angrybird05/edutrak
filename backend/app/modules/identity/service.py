"""
Identity module service â€” Student management, teacher management, and parent linking.
"""
import random
import re
import string
import uuid
from typing import Optional, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.event_bus import event_bus
from app.core.security import get_password_hash
from app.modules.academic.models import Class, Section
from app.modules.auth.models import User, UserRole
from app.modules.identity.models import Student, parent_student
from app.modules.identity.schemas import (
    ParentChildSummary,
    StudentCreate,
    TeacherCreate,
    TeacherCredentialsUpdate,
    TeacherUpdate,
)

PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{7,14}$")


class IdentityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_teacher_for_school(self, teacher_id: UUID, school_id: UUID) -> User:
        result = await self.db.execute(
            select(User).where(
                User.id == teacher_id,
                User.role == UserRole.TEACHER,
                User.school_id == school_id,
            )
        )
        teacher = result.scalars().first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return teacher

    async def _ensure_unique_username(self, username: str, exclude_user_id: Optional[UUID] = None) -> None:
        query = select(User).where(User.username == username)
        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    async def _ensure_unique_phone(
        self,
        phone: str,
        *,
        role: Optional[UserRole] = None,
        exclude_user_id: Optional[UUID] = None,
    ) -> None:
        query = select(User).where(User.phone == phone)
        if role is not None:
            query = query.where(User.role == role)
        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already in use",
            )

    async def _generate_placeholder_phone(self) -> str:
        while True:
            candidate = f"teacher_{uuid.uuid4().hex[:20]}"
            result = await self.db.execute(select(User).where(User.phone == candidate))
            if not result.scalars().first():
                return candidate

    async def _generate_internal_student_phone(self) -> str:
        while True:
            candidate = f"student_{uuid.uuid4().hex}"
            result = await self.db.execute(select(User).where(User.phone == candidate))
            if not result.scalars().first():
                return candidate

    async def _validate_student_placement(self, school_id: UUID, class_id: UUID, section_id: UUID) -> tuple[Class, Section]:
        class_result = await self.db.execute(
            select(Class).where(Class.id == class_id, Class.school_id == school_id)
        )
        class_obj = class_result.scalars().first()
        if not class_obj:
            raise HTTPException(status_code=400, detail="Class does not belong to the admin school")

        section_result = await self.db.execute(
            select(Section).where(Section.id == section_id, Section.class_id == class_id)
        )
        section_obj = section_result.scalars().first()
        if not section_obj:
            raise HTTPException(status_code=400, detail="Section does not belong to the selected class")
        return class_obj, section_obj

    async def _get_student_by_admission_number(self, school_id: UUID, admission_number: str) -> Optional[Student]:
        result = await self.db.execute(
            select(Student).where(
                Student.school_id == school_id,
                Student.admission_number == admission_number,
            )
        )
        return result.scalars().first()

    async def _repair_legacy_student_phone_owner(
        self,
        *,
        existing_user: User,
        school_id: UUID,
        guardian_name: str,
        guardian_phone: str,
    ) -> Optional[tuple[User, bool]]:
        if existing_user.role != UserRole.STUDENT:
            return None

        student_result = await self.db.execute(
            select(Student)
            .where(Student.user_id == existing_user.id)
            .options(selectinload(Student.user))
        )
        legacy_student = student_result.scalars().first()
        if not legacy_student:
            return None

        if legacy_student.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guardian phone is already linked to another school",
            )

        if legacy_student.guardian_phone and legacy_student.guardian_phone != guardian_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guardian phone is already used by a non-parent account",
            )

        # Older student rows could store the guardian number directly on the student user.
        # Move that student to an internal placeholder phone, then mint the parent user.
        existing_user.phone = await self._generate_internal_student_phone()
        legacy_student.guardian_phone = guardian_phone
        if not legacy_student.guardian_name:
            legacy_student.guardian_name = guardian_name

        self.db.add(existing_user)
        self.db.add(legacy_student)
        await self.db.flush()

        parent_user = User(
            phone=guardian_phone,
            full_name=guardian_name,
            role=UserRole.PARENT,
            school_id=school_id,
            is_active=True,
        )
        self.db.add(parent_user)
        await self.db.flush()
        await self._link_parent_user_to_students(parent_user, [legacy_student])
        return parent_user, True

    async def _resolve_parent_account(
        self,
        *,
        school_id: UUID,
        guardian_name: str,
        guardian_phone: str,
    ) -> tuple[User, bool]:
        existing_parent_result = await self.db.execute(
            select(User).where(User.phone == guardian_phone, User.role == UserRole.PARENT)
        )
        existing_parent = existing_parent_result.scalars().first()
        if existing_parent:
            if existing_parent.school_id != school_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Guardian phone is already linked to another school",
                )
            if not existing_parent.full_name:
                existing_parent.full_name = guardian_name
                self.db.add(existing_parent)
            return existing_parent, False

        conflicting_user_result = await self.db.execute(
            select(User).where(
                User.phone == guardian_phone,
                User.role.in_([UserRole.ADMIN, UserRole.STUDENT]),
            )
        )
        conflicting_user = conflicting_user_result.scalars().first()
        if conflicting_user:
            repaired_parent = await self._repair_legacy_student_phone_owner(
                existing_user=conflicting_user,
                school_id=school_id,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
            )
            if repaired_parent:
                return repaired_parent

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Guardian phone is already used by a non-parent account",
            )

        parent_user = User(
            phone=guardian_phone,
            full_name=guardian_name,
            role=UserRole.PARENT,
            school_id=school_id,
            is_active=True,
        )
        self.db.add(parent_user)
        await self.db.flush()
        return parent_user, True

    async def _link_parent_user_to_students(self, parent_user: User, students: Sequence[Student]) -> None:
        if not students:
            return

        existing_links_result = await self.db.execute(
            select(parent_student.c.student_id).where(parent_student.c.parent_id == parent_user.id)
        )
        existing_student_ids = set(existing_links_result.scalars().all())

        from sqlalchemy import insert

        linked_student_ids: list[str] = []
        for student in students:
            if student.id in existing_student_ids:
                continue
            await self.db.execute(
                insert(parent_student).values(parent_id=parent_user.id, student_id=student.id)
            )
            linked_student_ids.append(str(student.id))

        if linked_student_ids:
            await event_bus.emit(
                "identity.parent_linked",
                {"parent_id": str(parent_user.id), "student_ids": linked_student_ids},
            )

    async def create_teacher(self, admin_user: User, obj_in: TeacherCreate) -> User:
        if not admin_user.school_id:
            raise HTTPException(status_code=400, detail="Admin is not linked to a school")

        username = obj_in.username.strip()
        full_name = obj_in.full_name.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        if not full_name:
            raise HTTPException(status_code=400, detail="Teacher full name is required")

        await self._ensure_unique_username(username)
        phone = obj_in.phone.strip() if obj_in.phone and obj_in.phone.strip() else await self._generate_placeholder_phone()
        await self._ensure_unique_phone(phone, role=UserRole.TEACHER)

        teacher = User(
            phone=phone,
            username=username,
            password_hash=get_password_hash(obj_in.password),
            full_name=full_name,
            role=UserRole.TEACHER,
            language_pref=obj_in.language_pref,
            is_active=obj_in.is_active,
            school_id=admin_user.school_id,
        )
        self.db.add(teacher)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def update_teacher(self, admin_user: User, teacher_id: UUID, obj_in: TeacherUpdate) -> User:
        if not admin_user.school_id:
            raise HTTPException(status_code=400, detail="Admin is not linked to a school")

        teacher = await self._get_teacher_for_school(teacher_id, admin_user.school_id)

        if obj_in.full_name is not None:
            teacher.full_name = obj_in.full_name.strip()
        if obj_in.phone is not None:
            phone = obj_in.phone.strip()
            await self._ensure_unique_phone(phone, role=UserRole.TEACHER, exclude_user_id=teacher.id)
            teacher.phone = phone
        if obj_in.language_pref is not None:
            teacher.language_pref = obj_in.language_pref
        if obj_in.is_active is not None:
            teacher.is_active = obj_in.is_active

        self.db.add(teacher)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def update_teacher_credentials(
        self, admin_user: User, teacher_id: UUID, obj_in: TeacherCredentialsUpdate
    ) -> User:
        if not admin_user.school_id:
            raise HTTPException(status_code=400, detail="Admin is not linked to a school")

        teacher = await self._get_teacher_for_school(teacher_id, admin_user.school_id)

        if obj_in.username is not None:
            username = obj_in.username.strip()
            await self._ensure_unique_username(username, exclude_user_id=teacher.id)
            teacher.username = username
        if obj_in.password is not None:
            teacher.password_hash = get_password_hash(obj_in.password)

        self.db.add(teacher)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def create_student(self, admin_user: User, obj_in: StudentCreate) -> tuple[Student, bool]:
        """Create a student with their associated user account."""
        if not admin_user.school_id:
            raise HTTPException(status_code=400, detail="Admin is not linked to a school")

        full_name = obj_in.full_name.strip()
        guardian_name = obj_in.guardian_name.strip()
        guardian_relation = obj_in.guardian_relation.strip()
        guardian_phone = obj_in.guardian_phone.strip()
        admission_number = obj_in.admission_number.strip()

        if not full_name:
            raise HTTPException(status_code=400, detail="Student full name is required")
        if not guardian_name:
            raise HTTPException(status_code=400, detail="Guardian name is required")
        if not guardian_relation:
            raise HTTPException(status_code=400, detail="Guardian relation is required")
        if not guardian_phone:
            raise HTTPException(status_code=400, detail="Guardian phone is required")
        if not PHONE_PATTERN.match(guardian_phone):
            raise HTTPException(status_code=400, detail="Guardian phone must be in a valid international format")

        duplicate_student = await self._get_student_by_admission_number(admin_user.school_id, admission_number)
        if duplicate_student:
            raise HTTPException(status_code=400, detail="Admission number already exists")

        await self._validate_student_placement(admin_user.school_id, obj_in.class_id, obj_in.section_id)
        parent_user, parent_account_created = await self._resolve_parent_account(
            school_id=admin_user.school_id,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
        )

        internal_phone = await self._generate_internal_student_phone()
        user = User(
            phone=internal_phone,
            full_name=full_name,
            role=UserRole.STUDENT,
            school_id=admin_user.school_id,
        )
        self.db.add(user)
        await self.db.flush()

        joining_code = await self._get_unique_joining_code()

        student = Student(
            user_id=user.id,
            school_id=admin_user.school_id,
            class_id=obj_in.class_id,
            section_id=obj_in.section_id,
            admission_number=admission_number,
            roll_number=obj_in.roll_number,
            dob=obj_in.dob,
            guardian_name=guardian_name,
            guardian_relation=guardian_relation,
            guardian_phone=guardian_phone,
            parent_joining_code=joining_code,
        )
        self.db.add(student)
        await self.db.flush()
        await self._link_parent_user_to_students(parent_user, [student])
        await self.db.commit()
        student_result = await self.db.execute(
            select(Student)
            .where(Student.id == student.id)
            .options(selectinload(Student.user))
        )
        loaded_student = student_result.scalar_one()

        await event_bus.emit(
            "identity.student_created",
            {
                "student_id": str(student.id),
                "user_id": str(user.id),
                "school_id": str(admin_user.school_id),
                "admission_number": admission_number,
            },
        )

        return loaded_student, parent_account_created

    async def link_parent(self, student_id: UUID, parent_id: UUID) -> None:
        """Link a parent user to a student."""
        student = await self.db.get(Student, student_id)
        parent = await self.db.get(User, parent_id)
        if not student or not parent:
            raise HTTPException(status_code=404, detail="Student or parent not found")
        if parent.role != UserRole.PARENT:
            raise HTTPException(status_code=400, detail="Target user is not a parent account")
        if parent.school_id and parent.school_id != student.school_id:
            raise HTTPException(status_code=400, detail="Parent and student belong to different schools")
        await self._link_parent_user_to_students(parent, [student])
        await self.db.commit()

    async def link_parent_by_code(self, parent_id: UUID, joining_code: str) -> Optional[Student]:
        """Link a parent to a student using the joining code."""
        result = await self.db.execute(
            select(Student).where(Student.parent_joining_code == joining_code)
        )
        student = result.scalars().first()
        if not student:
            return None

        await self.link_parent(student.id, parent_id)
        return student

    async def get_parent_children(self, parent_user: User) -> list[ParentChildSummary]:
        result = await self.db.execute(
            select(Student)
            .join(parent_student, parent_student.c.student_id == Student.id)
            .where(parent_student.c.parent_id == parent_user.id)
            .options(selectinload(Student.user))
            .order_by(Student.created_at.desc())
        )
        children = result.scalars().all()
        return [
            ParentChildSummary(
                id=child.id,
                user_id=child.user_id,
                full_name=child.user.full_name if child.user else None,
                admission_number=child.admission_number,
                roll_number=child.roll_number,
                class_id=child.class_id,
                section_id=child.section_id,
                guardian_name=child.guardian_name,
                guardian_relation=child.guardian_relation,
                guardian_phone=child.guardian_phone,
                parent_joining_code=child.parent_joining_code,
            )
            for child in children
        ]

    async def _get_unique_joining_code(self, length: int = 6) -> str:
        """Generate a unique parent joining code."""
        chars = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0OI1L")
        while True:
            code = "".join(random.choices(chars, k=length))
            result = await self.db.execute(
                select(Student).where(Student.parent_joining_code == code)
            )
            if not result.scalars().first():
                return code


def get_identity_service(db: AsyncSession) -> IdentityService:
    return IdentityService(db)
