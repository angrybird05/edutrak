from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.academic import Class, Section, Subject
from app.schemas.academic import (
    ClassCreate, ClassUpdate,
    SectionCreate, SectionUpdate,
    SubjectCreate, SubjectUpdate
)


class CRUDClass(CRUDBase[Class, ClassCreate, ClassUpdate]):
    async def get_by_school(self, db: AsyncSession, *, school_id: UUID) -> List[Class]:
        query = select(Class).where(Class.school_id == school_id)
        result = await db.execute(query)
        return result.scalars().all()


class CRUDSection(CRUDBase[Section, SectionCreate, SectionUpdate]):
    async def get_by_class(self, db: AsyncSession, *, class_id: UUID) -> List[Section]:
        query = select(Section).where(Section.class_id == class_id)
        result = await db.execute(query)
        return result.scalars().all()


class CRUDSubject(CRUDBase[Subject, SubjectCreate, SubjectUpdate]):
    async def get_by_school(self, db: AsyncSession, *, school_id: UUID) -> List[Subject]:
        query = select(Subject).where(Subject.school_id == school_id)
        result = await db.execute(query)
        return result.scalars().all()


academic_class = CRUDClass(Class)
section = CRUDSection(Section)
subject = CRUDSubject(Subject)
