from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.academic import Section, teacher_section
from app.core.security import get_password_hash
from pydantic import BaseModel, ConfigDict

router = APIRouter()

class TeacherCreate(BaseModel):
    full_name: str
    phone: str
    username: str
    password: str
    school_id: UUID

class TeacherResponse(BaseModel):
    id: UUID
    full_name: str
    phone: str
    username: str
    role: str
    
    model_config = ConfigDict(from_attributes=True)

class TeacherAssign(BaseModel):
    section_ids: List[UUID]

@router.post("/teachers", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.ADMIN)),
    teacher_in: TeacherCreate,
) -> Any:
    """
    Allow Administrators to create new Teacher accounts with standard credentials.
    """
    # Check if username or phone exists
    result = await db.execute(
        select(User).where((User.username == teacher_in.username) | (User.phone == teacher_in.phone))
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username or Phone already registered")
    
    db_obj = User(
        full_name=teacher_in.full_name,
        phone=teacher_in.phone,
        username=teacher_in.username,
        password_hash=get_password_hash(teacher_in.password),
        role=UserRole.TEACHER,
        school_id=teacher_in.school_id
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

@router.get("/teachers", response_model=List[TeacherResponse])
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.ADMIN)),
) -> Any:
    """
    List all teachers in the administrator's school.
    """
    query = select(User).where(
        User.role == UserRole.TEACHER,
        User.school_id == current_user.school_id if current_user.school_id else True
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/teachers/{teacher_id}/assign")
async def assign_teacher_to_sections(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.requires_role(UserRole.ADMIN)),
    teacher_id: UUID,
    assignment: TeacherAssign,
) -> Any:
    """
    Assign a teacher to multiple sections.
    """
    # Verify teacher exists
    teacher_res = await db.execute(select(User).where(User.id == teacher_id, User.role == UserRole.TEACHER))
    teacher = teacher_res.scalars().first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Clear existing assignments or append? Let's implement 'set' behavior
    # (Delete old, add new)
    from sqlalchemy import delete
    await db.execute(delete(teacher_section).where(teacher_section.c.teacher_id == teacher_id))
    
    for sid in assignment.section_ids:
        # Verify section exists
        sec_res = await db.execute(select(Section).where(Section.id == sid))
        if not sec_res.scalars().first():
            raise HTTPException(status_code=400, detail=f"Section {sid} does not exist")
        
        await db.execute(teacher_section.insert().values(teacher_id=teacher_id, section_id=sid))
    
    await db.commit()
    return {"message": f"Teacher assigned to {len(assignment.section_ids)} sections"}
