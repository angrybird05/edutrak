from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase
from app.models.student import Student, parent_student
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentUpdate
from app.services.link_service import link_service


class CRUDStudent(CRUDBase[Student, StudentCreate, StudentUpdate]):
    async def create_with_user(
        self, db: AsyncSession, *, obj_in: StudentCreate
    ) -> Student:
        # 1. Create User
        db_user = User(
            phone=obj_in.phone,
            full_name=obj_in.full_name,
            role=UserRole.STUDENT,
            school_id=obj_in.school_id
        )
        db.add(db_user)
        await db.flush()  # Get user.id
        
        # 3. Create Student
        obj_in_data = jsonable_encoder(obj_in)
        # Remove fields not in Student model
        del obj_in_data["phone"]
        del obj_in_data["full_name"]
        
        # Generate parent joining code
        joining_code = await link_service.get_unique_joining_code(db)
        
        db_student = Student(
            **obj_in_data,
            user_id=db_user.id,
            parent_joining_code=joining_code
        )
        db.add(db_student)
        await db.commit()
        await db.refresh(db_student)
        return db_student

    async def get_by_school(self, db: AsyncSession, *, school_id: UUID) -> List[Student]:
        query = select(Student).where(Student.school_id == school_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_class(self, db: AsyncSession, *, class_id: UUID) -> List[Student]:
        query = select(Student).where(Student.class_id == class_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def link_parent(self, db: AsyncSession, *, student_id: UUID, parent_id: UUID):
        stmt = parent_student.insert().values(student_id=student_id, parent_id=parent_id)
        await db.execute(stmt)
        await db.commit()


student = CRUDStudent(Student)
