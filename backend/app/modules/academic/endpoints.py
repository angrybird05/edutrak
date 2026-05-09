"""
Academic module endpoints — Schools, chains, classes, sections, subjects, timetables.

Migrated from app/api/api_v1/endpoints/schools.py, chains.py, academic.py.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.db.session import get_db
from app.shared.api.deps import get_current_user, requires_admin, requires_roles
from app.modules.auth.models import User, UserRole
from app.modules.academic.models import Chain, School, Class, Section, Subject, Timetable
from app.modules.academic import schemas
from app.modules.academic.service import get_academic_service

router = APIRouter()


def _ensure_school_scope(current_user: User, school_id: UUID) -> None:
    if current_user.school_id and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")


async def _get_authorized_class(
    db: AsyncSession,
    *,
    class_id: UUID,
    current_user: User,
) -> Class:
    result = await db.execute(select(Class).where(Class.id == class_id))
    found_class = result.scalars().first()
    if not found_class:
        raise HTTPException(status_code=404, detail="Class not found")
    _ensure_school_scope(current_user, found_class.school_id)
    return found_class


async def _get_authorized_section(
    db: AsyncSession,
    *,
    section_id: UUID,
    current_user: User,
) -> Section:
    result = await db.execute(
        select(Section)
        .join(Class, Class.id == Section.class_id)
        .where(Section.id == section_id)
    )
    section = result.scalars().first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    found_class = await db.get(Class, section.class_id)
    if not found_class:
        raise HTTPException(status_code=404, detail="Class not found")
    _ensure_school_scope(current_user, found_class.school_id)
    return section


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------
@router.get("/chains", response_model=List[schemas.Chain])
async def list_chains(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(select(Chain))
    return result.scalars().all()


@router.post("/chains", response_model=schemas.Chain)
async def create_chain(
    *,
    db: AsyncSession = Depends(get_db),
    chain_in: schemas.ChainCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    chain = Chain(name=chain_in.name)
    db.add(chain)
    await db.commit()
    await db.refresh(chain)
    return chain


# ---------------------------------------------------------------------------
# Schools
# ---------------------------------------------------------------------------
@router.get("/schools", response_model=List[schemas.School])
async def list_schools(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    stmt = select(School)
    if current_user.school_id:
        stmt = stmt.where(School.id == current_user.school_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/schools", response_model=schemas.School)
async def create_school(
    *,
    db: AsyncSession = Depends(get_db),
    school_in: schemas.SchoolCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    normalized_name = " ".join(school_in.name.strip().split())
    if not normalized_name:
        raise HTTPException(status_code=400, detail="School name is required")

    existing_result = await db.execute(
        select(School).where(School.name.ilike(normalized_name))
    )
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="A school with this name already exists",
        )

    payload = school_in.model_dump()
    payload["name"] = normalized_name
    school = School(**payload)
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@router.get("/schools/{school_id}", response_model=schemas.School)
async def get_school(
    school_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _ensure_school_scope(current_user, school_id)
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
@router.get("/classes/{school_id}", response_model=List[schemas.Class])
async def list_classes(
    school_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _ensure_school_scope(current_user, school_id)
    result = await db.execute(
        select(Class).where(Class.school_id == school_id).options(selectinload(Class.sections))
    )
    return result.scalars().all()


@router.get("/structure/{school_id}", response_model=schemas.AcademicStructureResponse)
async def get_academic_structure(
    school_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return the full academic tree for a school."""
    if current_user.school_id and current_user.school_id != school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")

    service = get_academic_service(db)
    return await service.get_academic_structure(school_id)


@router.post("/classes", response_model=schemas.Class)
async def create_class(
    *,
    db: AsyncSession = Depends(get_db),
    class_in: schemas.ClassCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    if current_user.school_id and class_in.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    service = get_academic_service(db)
    return await service.create_class(current_user.school_id, class_in.name, class_in.class_number)


@router.patch("/classes/{class_id}", response_model=schemas.Class)
async def update_class(
    *,
    class_id: UUID,
    class_in: schemas.ClassUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    return await service.update_class(current_user.school_id, class_id, class_in.model_dump(exclude_unset=True))


@router.delete("/classes/{class_id}", status_code=204, response_class=Response, response_model=None)
async def delete_class(
    *,
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Response:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    await service.delete_class(current_user.school_id, class_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
@router.get("/sections/{class_id}", response_model=List[schemas.Section])
async def list_sections(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _get_authorized_class(db, class_id=class_id, current_user=current_user)
    result = await db.execute(select(Section).where(Section.class_id == class_id))
    return result.scalars().all()


@router.post("/sections", response_model=schemas.Section)
async def create_section(
    *,
    db: AsyncSession = Depends(get_db),
    section_in: schemas.SectionCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    return await service.create_section(current_user.school_id, section_in.class_id, section_in.name)


@router.patch("/sections/{section_id}", response_model=schemas.Section)
async def update_section(
    *,
    section_id: UUID,
    section_in: schemas.SectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    return await service.update_section(current_user.school_id, section_id, section_in.model_dump(exclude_unset=True))


@router.delete("/sections/{section_id}", status_code=204, response_class=Response, response_model=None)
async def delete_section(
    *,
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Response:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    await service.delete_section(current_user.school_id, section_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------
@router.get("/subjects/{school_id}", response_model=List[schemas.Subject])
async def list_subjects(
    school_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    _ensure_school_scope(current_user, school_id)
    result = await db.execute(select(Subject).where(Subject.school_id == school_id))
    return result.scalars().all()


@router.post("/subjects", response_model=schemas.Subject)
async def create_subject(
    *,
    db: AsyncSession = Depends(get_db),
    subject_in: schemas.SubjectCreate,
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    if current_user.school_id and subject_in.school_id != current_user.school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school's data")
    service = get_academic_service(db)
    return await service.create_subject(current_user.school_id, subject_in.name, subject_in.code)


@router.patch("/subjects/{subject_id}", response_model=schemas.Subject)
async def update_subject(
    *,
    subject_id: UUID,
    subject_in: schemas.SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    return await service.update_subject(current_user.school_id, subject_id, subject_in.model_dump(exclude_unset=True))


@router.delete("/subjects/{subject_id}", status_code=204, response_class=Response, response_model=None)
async def delete_subject(
    *,
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Response:
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")
    service = get_academic_service(db)
    await service.delete_subject(current_user.school_id, subject_id)
    return Response(status_code=204)


@router.put("/sections/{section_id}/subjects", response_model=schemas.AcademicStructureResponse)
async def update_section_subjects(
    *,
    section_id: UUID,
    body: schemas.SectionSubjectAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Replace the subjects mapped to a section."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    return await service.update_section_subjects(current_user.school_id, section_id, body.subject_ids)


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------
@router.get("/timetable/{section_id}", response_model=List[schemas.TimetableEntry])
async def get_timetable(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _get_authorized_section(db, section_id=section_id, current_user=current_user)
    result = await db.execute(
        select(Timetable).where(Timetable.section_id == section_id).order_by(Timetable.day_of_week, Timetable.start_time)
    )
    return result.scalars().all()


@router.get("/teachers/{teacher_id}/assignments", response_model=schemas.TeacherAssignmentsResponse)
async def get_teacher_assignments(
    *,
    teacher_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Get teacher sections, subjects, and timetable."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    return await service.get_teacher_assignments(current_user.school_id, teacher_id)


@router.get("/teachers/me/assignments", response_model=schemas.TeacherAssignmentsResponse)
async def get_my_teacher_assignments(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_roles([UserRole.TEACHER])),
) -> Any:
    """Get the current teacher's sections, subjects, and timetable."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Teacher is not linked to a school")

    service = get_academic_service(db)
    return await service.get_teacher_assignments(current_user.school_id, current_user.id)


@router.put("/teachers/{teacher_id}/sections", response_model=schemas.TeacherAssignmentsResponse)
async def update_teacher_sections(
    *,
    teacher_id: UUID,
    body: schemas.TeacherSectionAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Replace the sections assigned to a teacher."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    return await service.update_teacher_sections(current_user.school_id, teacher_id, body.section_ids)


@router.put("/teachers/{teacher_id}/subjects", response_model=schemas.TeacherAssignmentsResponse)
async def update_teacher_subjects(
    *,
    teacher_id: UUID,
    body: schemas.TeacherSubjectAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Replace the subjects assigned to a teacher."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    return await service.update_teacher_subjects(current_user.school_id, teacher_id, body.subject_ids)


@router.post("/timetable", response_model=schemas.TimetableEntry, status_code=201)
async def create_timetable_entry(
    *,
    body: schemas.TimetableEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Create a timetable row with teacher/section/subject validation."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    return await service.create_timetable_entry(current_user.school_id, body.model_dump())


@router.patch("/timetable/{entry_id}", response_model=schemas.TimetableEntry)
async def update_timetable_entry(
    *,
    entry_id: UUID,
    body: schemas.TimetableEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Any:
    """Update a timetable row with collision validation."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    payload = body.model_dump(exclude_unset=True)
    return await service.update_timetable_entry(current_user.school_id, entry_id, payload)


@router.delete("/timetable/{entry_id}", status_code=204, response_class=Response, response_model=None)
async def delete_timetable_entry(
    *,
    entry_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(requires_admin),
) -> Response:
    """Delete a timetable row."""
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Admin is not linked to a school")

    service = get_academic_service(db)
    await service.delete_timetable_entry(current_user.school_id, entry_id)
    return Response(status_code=204)
