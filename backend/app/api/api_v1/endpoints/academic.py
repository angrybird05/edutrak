from typing import Any, List, Optional
from pydantic import BaseModel
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app import crud, models, schemas
from app.api import deps
from app.models.performance import Exam, Mark
from app.models.academic import Section, Timetable
from app.models.student import Student
from app.models.user import UserRole

router = APIRouter()


# --- Class Endpoints ---

@router.get("/classes", response_model=List[schemas.academic.Class])
async def read_classes(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve classes (scoped to user's school).
    """
    if current_user.school_id:
        return await crud.academic_class.get_by_school(db, school_id=current_user.school_id)
    classes = await crud.academic_class.get_multi(db, skip=skip, limit=limit)
    return classes


@router.post("/classes", response_model=schemas.academic.Class)
async def create_class(
    *,
    db: AsyncSession = Depends(deps.get_db),
    class_in: schemas.academic.ClassCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new class.
    """
    new_class = await crud.academic_class.create(db, obj_in=class_in)
    return new_class


@router.get("/classes/school/{school_id}", response_model=List[schemas.academic.Class])
async def read_classes_by_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    school_id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all classes for a specific school.
    """
    classes = await crud.academic_class.get_by_school(db, school_id=school_id)
    return classes


@router.put("/classes/{class_id}", response_model=schemas.academic.Class)
async def update_class(
    *,
    db: AsyncSession = Depends(deps.get_db),
    class_id: UUID,
    class_in: schemas.academic.ClassUpdate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    db_obj = await crud.academic_class.get(db, id=class_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    return await crud.academic_class.update(db, db_obj=db_obj, obj_in=class_in)


@router.delete("/classes/{class_id}", response_model=dict)
async def delete_class(
    *,
    db: AsyncSession = Depends(deps.get_db),
    class_id: UUID,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    section_count = (
        await db.execute(select(func.count()).select_from(Section).where(Section.class_id == class_id))
    ).scalar_one()
    student_count = (
        await db.execute(select(func.count()).select_from(Student).where(Student.class_id == class_id))
    ).scalar_one()
    if section_count or student_count:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete class with dependent sections/students",
        )
    await crud.academic_class.remove(db, id=class_id)
    return {"message": "Class deleted"}


# --- Section Endpoints ---

@router.get("/sections", response_model=List[schemas.academic.Section])
async def read_sections(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve sections.
    """
    sections = await crud.section.get_multi(db, skip=skip, limit=limit)
    return sections


@router.post("/sections", response_model=schemas.academic.Section)
async def create_section(
    *,
    db: AsyncSession = Depends(deps.get_db),
    section_in: schemas.academic.SectionCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new section.
    """
    new_section = await crud.section.create(db, obj_in=section_in)
    return new_section


@router.get("/sections/class/{class_id}", response_model=List[schemas.academic.Section])
async def read_sections_by_class(
    *,
    db: AsyncSession = Depends(deps.get_db),
    class_id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all sections for a specific class.
    """
    sections = await crud.section.get_by_class(db, class_id=class_id)
    return sections


@router.put("/sections/{section_id}", response_model=schemas.academic.Section)
async def update_section(
    *,
    db: AsyncSession = Depends(deps.get_db),
    section_id: UUID,
    section_in: schemas.academic.SectionUpdate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    db_obj = await crud.section.get(db, id=section_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Section not found")
    return await crud.section.update(db, db_obj=db_obj, obj_in=section_in)


@router.delete("/sections/{section_id}", response_model=dict)
async def delete_section(
    *,
    db: AsyncSession = Depends(deps.get_db),
    section_id: UUID,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    student_count = (
        await db.execute(select(func.count()).select_from(Student).where(Student.section_id == section_id))
    ).scalar_one()
    exam_count = (
        await db.execute(select(func.count()).select_from(Exam).where(Exam.section_id == section_id))
    ).scalar_one()
    if student_count or exam_count:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete section with dependent students/exams",
        )
    await crud.section.remove(db, id=section_id)
    return {"message": "Section deleted"}


# --- Subject Endpoints ---

@router.get("/subjects", response_model=List[schemas.academic.Subject])
async def read_subjects(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve subjects (scoped to user's school).
    """
    if current_user.school_id:
        return await crud.subject.get_by_school(db, school_id=current_user.school_id)
    subjects = await crud.subject.get_multi(db, skip=skip, limit=limit)
    return subjects


@router.post("/subjects", response_model=schemas.academic.Subject)
async def create_subject(
    *,
    db: AsyncSession = Depends(deps.get_db),
    subject_in: schemas.academic.SubjectCreate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    """
    Create new subject.
    """
    new_subject = await crud.subject.create(db, obj_in=subject_in)
    return new_subject


@router.get("/subjects/school/{school_id}", response_model=List[schemas.academic.Subject])
async def read_subjects_by_school(
    *,
    db: AsyncSession = Depends(deps.get_db),
    school_id: UUID,
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all subjects for a specific school.
    """
    subjects = await crud.subject.get_by_school(db, school_id=school_id)
    return subjects


@router.put("/subjects/{subject_id}", response_model=schemas.academic.Subject)
async def update_subject(
    *,
    db: AsyncSession = Depends(deps.get_db),
    subject_id: UUID,
    subject_in: schemas.academic.SubjectUpdate,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    db_obj = await crud.subject.get(db, id=subject_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Subject not found")
    return await crud.subject.update(db, db_obj=db_obj, obj_in=subject_in)


@router.delete("/subjects/{subject_id}", response_model=dict)
async def delete_subject(
    *,
    db: AsyncSession = Depends(deps.get_db),
    subject_id: UUID,
    current_user: models.user.User = Depends(deps.requires_admin),
) -> Any:
    mark_count = (
        await db.execute(select(func.count()).select_from(Mark).where(Mark.subject_id == subject_id))
    ).scalar_one()
    if mark_count:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete subject with dependent marks",
        )
    await crud.subject.remove(db, id=subject_id)
    return {"message": "Subject deleted"}

# --- Timetable Endpoints ---

class TimetableCreate(BaseModel):
    section_id: UUID
    subject_id: UUID
    teacher_id: UUID
    day_of_week: int
    start_time: str
    end_time: str
    room: Optional[str] = None

@router.post("/timetables", response_model=dict)
async def create_timetable_entry(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: models.user.User = Depends(deps.requires_admin),
    entry_in: TimetableCreate,
) -> Any:
    """Create a new timetable entry (Admin only)."""
    db_obj = Timetable(**entry_in.model_dump())
    db.add(db_obj)
    await db.commit()
    return {"message": "Timetable entry created"}

@router.get("/timetables/section/{section_id}", response_model=List[dict])
async def read_section_timetable(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """Get the full weekly timetable for a section."""
    query = select(Timetable).where(Timetable.section_id == section_id).order_by(Timetable.day_of_week, Timetable.start_time)
    result = await db.execute(query)
    return [
        {
            "id": t.id,
            "day_of_week": t.day_of_week,
            "start_time": t.start_time,
            "end_time": t.end_time,
            "subject_name": (await db.get(models.academic.Subject, t.subject_id)).name,
            "teacher_name": (await db.get(models.user.User, t.teacher_id)).full_name,
            "room": t.room
        }
        for t in result.scalars().all()
    ]

@router.get("/schedule/today", response_model=List[dict])
async def read_today_schedule(
    db: AsyncSession = Depends(get_db),
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """Get today's classes for the current user."""
    from datetime import datetime
    today_weekday = datetime.now().weekday() # 0=Mon, 6=Sun
    
    if current_user.role == UserRole.STUDENT:
        student_res = await db.execute(select(Student).where(Student.user_id == current_user.id))
        student = student_res.scalar_one_or_none()
        if not student:
            return []
        query = select(Timetable).where(Timetable.section_id == student.section_id, Timetable.day_of_week == today_weekday)
    elif current_user.role == UserRole.TEACHER:
        query = select(Timetable).where(Timetable.teacher_id == current_user.id, Timetable.day_of_week == today_weekday)
    else:
        return []
        
    result = await db.execute(query.order_by(Timetable.start_time))
    rows = result.scalars().all()
    
    output = []
    for t in rows:
        subj = await db.get(models.academic.Subject, t.subject_id)
        output.append({
            "start_time": t.start_time,
            "end_time": t.end_time,
            "subject": subj.name if subj else "Unknown",
            "room": t.room
        })
    return output


@router.get("/schedule/weekly", response_model=dict)
async def read_weekly_schedule(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """Get weekly classes for the current user, grouped by day."""
    if current_user.role == UserRole.STUDENT:
        student_res = await db.execute(select(Student).where(Student.user_id == current_user.id))
        student = student_res.scalar_one_or_none()
        if not student:
            return {}
        query = select(Timetable).where(Timetable.section_id == student.section_id)
    elif current_user.role == UserRole.TEACHER:
        query = select(Timetable).where(Timetable.teacher_id == current_user.id)
    else:
        return {}
        
    result = await db.execute(query.order_by(Timetable.day_of_week, Timetable.start_time))
    rows = result.scalars().all()
    
    # 0=Monday, 1=Tuesday, ..., 6=Sunday
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_data = {day: [] for day in days}
    
    for t in rows:
        if 0 <= t.day_of_week <= 6:
            day_name = days[t.day_of_week]
            subj = await db.get(models.academic.Subject, t.subject_id)
            weekly_data[day_name].append({
                "start_time": t.start_time,
                "end_time": t.end_time,
                "subject": subj.name if subj else "Unknown",
                "room": t.room
            })
            
    return weekly_data

@router.get("/tree")
async def get_academic_tree(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.user.User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the full academic hierarchy: Class -> Section -> Subject.
    This is used by the frontend to render the school structure.
    """
    school_id = current_user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="User not associated with a school")

    # Fetch all classes for the school
    classes_result = await db.execute(
        select(models.academic.Class).where(models.academic.Class.school_id == school_id).order_by(models.academic.Class.class_number.asc())
    )
    classes = classes_result.scalars().all()

    tree = []
    for cls in classes:
        # Fetch sections for this class
        sections_result = await db.execute(
            select(models.academic.Section).where(models.academic.Section.class_id == cls.id).order_by(models.academic.Section.name.asc())
        )
        sections = sections_result.scalars().all()
        
        section_list = []
        for sec in sections:
            # Fetch subjects for this section (via Timetable or student_subject)
            # For the tree, we'll fetch all school subjects and filter by those that have a weekly timetable entry for this section
            subjects_query = (
                select(models.academic.Subject)
                .distinct()
                .join(models.academic.Timetable, models.academic.Timetable.subject_id == models.academic.Subject.id)
                .where(models.academic.Timetable.section_id == sec.id)
            )
            subj_result = await db.execute(subjects_query)
            subjects = subj_result.scalars().all()
            
            section_list.append({
                "id": str(sec.id),
                "name": f"Section {sec.name}",
                "subjects": [
                    {"id": str(s.id), "name": s.name, "code": s.code}
                    for s in subjects
                ]
            })
            
        tree.append({
            "id": str(cls.id),
            "name": cls.name,
            "class_number": cls.class_number,
            "sections": section_list
        })

    return tree
