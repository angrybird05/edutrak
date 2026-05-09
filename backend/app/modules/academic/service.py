"""
Academic module service — teacher assignments and timetable management.
"""
from datetime import datetime
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.academic.models import Class, Section, Subject, Timetable
from app.modules.auth.models import User, UserRole


class AcademicService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_class_for_school(self, school_id: UUID, class_id: UUID) -> Class:
        result = await self.db.execute(
            select(Class)
            .where(Class.id == class_id, Class.school_id == school_id)
            .options(selectinload(Class.sections))
        )
        found_class = result.scalars().first()
        if not found_class:
            raise HTTPException(status_code=404, detail="Class not found")
        return found_class

    @staticmethod
    def _parse_time(value: str) -> datetime.time:
        try:
            return datetime.strptime(value, "%H:%M").time()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time values must use HH:MM 24-hour format",
            ) from exc

    @classmethod
    def _validate_time_range(cls, start_time: str, end_time: str) -> None:
        if cls._parse_time(start_time) >= cls._parse_time(end_time):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be earlier than end_time",
            )

    async def _get_teacher(self, teacher_id: UUID, school_id: UUID) -> User:
        result = await self.db.execute(
            select(User)
            .where(
                User.id == teacher_id,
                User.role == UserRole.TEACHER,
                User.school_id == school_id,
            )
            .options(
                selectinload(User.assigned_sections).selectinload(Section.parent_class),
                selectinload(User.assigned_subjects),
            )
        )
        teacher = result.scalars().first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return teacher

    async def _get_sections(self, school_id: UUID, section_ids: Iterable[UUID]) -> list[Section]:
        section_ids = list(section_ids)
        if not section_ids:
            return []
        result = await self.db.execute(
            select(Section)
            .join(Class, Class.id == Section.class_id)
            .where(Section.id.in_(section_ids), Class.school_id == school_id)
            .options(selectinload(Section.parent_class))
        )
        sections = result.scalars().all()
        if len(sections) != len(set(section_ids)):
            raise HTTPException(status_code=400, detail="One or more sections are invalid for this school")
        return sections

    async def _get_subjects(self, school_id: UUID, subject_ids: Iterable[UUID]) -> list[Subject]:
        subject_ids = list(subject_ids)
        if not subject_ids:
            return []
        result = await self.db.execute(
            select(Subject).where(Subject.id.in_(subject_ids), Subject.school_id == school_id)
        )
        subjects = result.scalars().all()
        if len(subjects) != len(set(subject_ids)):
            raise HTTPException(status_code=400, detail="One or more subjects are invalid for this school")
        return subjects

    async def _get_section_for_school(self, school_id: UUID, section_id: UUID) -> Section:
        result = await self.db.execute(
            select(Section)
            .join(Class, Class.id == Section.class_id)
            .where(Section.id == section_id, Class.school_id == school_id)
            .options(
                selectinload(Section.parent_class),
                selectinload(Section.subjects),
                selectinload(Section.teachers),
            )
        )
        section = result.scalars().first()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        return section

    async def _get_subject_for_school(self, school_id: UUID, subject_id: UUID) -> Subject:
        result = await self.db.execute(
            select(Subject)
            .where(Subject.id == subject_id, Subject.school_id == school_id)
            .options(selectinload(Subject.sections), selectinload(Subject.teachers))
        )
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        return subject

    async def _ensure_unique_class_name(self, school_id: UUID, name: str, exclude_class_id: UUID | None = None) -> None:
        query = select(Class).where(func.lower(Class.name) == name.lower(), Class.school_id == school_id)
        if exclude_class_id:
            query = query.where(Class.id != exclude_class_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="A class with this name already exists")

    async def _ensure_unique_class_number(
        self, school_id: UUID, class_number: int, exclude_class_id: UUID | None = None
    ) -> None:
        query = select(Class).where(Class.class_number == class_number, Class.school_id == school_id)
        if exclude_class_id:
            query = query.where(Class.id != exclude_class_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="A class with this number already exists")

    async def _ensure_unique_section_name(
        self, class_id: UUID, name: str, exclude_section_id: UUID | None = None
    ) -> None:
        query = select(Section).where(func.lower(Section.name) == name.lower(), Section.class_id == class_id)
        if exclude_section_id:
            query = query.where(Section.id != exclude_section_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="A section with this name already exists in the class")

    async def _ensure_unique_subject_name(
        self, school_id: UUID, name: str, exclude_subject_id: UUID | None = None
    ) -> None:
        query = select(Subject).where(func.lower(Subject.name) == name.lower(), Subject.school_id == school_id)
        if exclude_subject_id:
            query = query.where(Subject.id != exclude_subject_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="A subject with this name already exists")

    async def _ensure_unique_subject_code(
        self, school_id: UUID, code: str | None, exclude_subject_id: UUID | None = None
    ) -> None:
        if not code:
            return
        query = select(Subject).where(func.lower(Subject.code) == code.lower(), Subject.school_id == school_id)
        if exclude_subject_id:
            query = query.where(Subject.id != exclude_subject_id)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="A subject with this code already exists")

    async def get_academic_structure(self, school_id: UUID) -> dict:
        class_result = await self.db.execute(
            select(Class)
            .where(Class.school_id == school_id)
            .options(
                selectinload(Class.sections).selectinload(Section.subjects)
            )
            .order_by(Class.class_number, Class.name)
        )
        classes = class_result.scalars().all()

        subject_result = await self.db.execute(
            select(Subject).where(Subject.school_id == school_id).order_by(Subject.name)
        )
        subjects = subject_result.scalars().all()

        return {
            "classes": [
                {
                    "id": cls.id,
                    "name": cls.name,
                    "class_number": cls.class_number,
                    "school_id": cls.school_id,
                    "sections": [
                        {
                            "id": section.id,
                            "name": section.name,
                            "class_id": section.class_id,
                            "subjects": [
                                {"id": subject.id, "name": subject.name, "code": subject.code}
                                for subject in sorted(section.subjects, key=lambda item: (item.name or "").lower())
                            ],
                        }
                        for section in sorted(cls.sections, key=lambda item: (item.name or "").lower())
                    ],
                }
                for cls in classes
            ],
            "subjects": [
                {"id": subject.id, "name": subject.name, "code": subject.code}
                for subject in subjects
            ],
        }

    async def create_class(self, school_id: UUID, name: str, class_number: int) -> Class:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Class name is required")
        await self._ensure_unique_class_name(school_id, name)
        await self._ensure_unique_class_number(school_id, class_number)
        new_class = Class(name=name, class_number=class_number, school_id=school_id)
        self.db.add(new_class)
        await self.db.commit()
        await self.db.refresh(new_class)
        return new_class

    async def update_class(self, school_id: UUID, class_id: UUID, payload: dict) -> Class:
        found_class = await self._get_class_for_school(school_id, class_id)
        if payload.get("name") is not None:
            name = payload["name"].strip()
            if not name:
                raise HTTPException(status_code=400, detail="Class name is required")
            await self._ensure_unique_class_name(school_id, name, exclude_class_id=class_id)
            found_class.name = name
        if payload.get("class_number") is not None:
            await self._ensure_unique_class_number(
                school_id,
                payload["class_number"],
                exclude_class_id=class_id,
            )
            found_class.class_number = payload["class_number"]
        self.db.add(found_class)
        await self.db.commit()
        await self.db.refresh(found_class)
        return found_class

    async def delete_class(self, school_id: UUID, class_id: UUID) -> None:
        found_class = await self._get_class_for_school(school_id, class_id)
        if found_class.sections:
            raise HTTPException(status_code=400, detail="Remove sections before deleting this class")
        await self.db.execute(delete(Class).where(Class.id == class_id, Class.school_id == school_id))
        await self.db.commit()

    async def create_section(self, school_id: UUID, class_id: UUID, name: str) -> Section:
        found_class = await self._get_class_for_school(school_id, class_id)
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Section name is required")
        await self._ensure_unique_section_name(found_class.id, name)
        section = Section(class_id=found_class.id, name=name)
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def update_section(self, school_id: UUID, section_id: UUID, payload: dict) -> Section:
        section = await self._get_section_for_school(school_id, section_id)
        if payload.get("name") is not None:
            name = payload["name"].strip()
            if not name:
                raise HTTPException(status_code=400, detail="Section name is required")
            await self._ensure_unique_section_name(section.class_id, name, exclude_section_id=section_id)
            section.name = name
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def delete_section(self, school_id: UUID, section_id: UUID) -> None:
        section = await self._get_section_for_school(school_id, section_id)
        timetable_rows = await self.db.execute(select(Timetable.id).where(Timetable.section_id == section_id))
        if timetable_rows.scalars().first():
            raise HTTPException(status_code=400, detail="Remove timetable entries before deleting this section")
        section.subjects = []
        section.teachers = []
        self.db.add(section)
        await self.db.flush()
        await self.db.execute(delete(Section).where(Section.id == section_id))
        await self.db.commit()

    async def create_subject(self, school_id: UUID, name: str, code: str | None = None) -> Subject:
        name = name.strip()
        code = code.strip() if code else None
        if not name:
            raise HTTPException(status_code=400, detail="Subject name is required")
        await self._ensure_unique_subject_name(school_id, name)
        await self._ensure_unique_subject_code(school_id, code)
        subject = Subject(name=name, code=code, school_id=school_id)
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def update_subject(self, school_id: UUID, subject_id: UUID, payload: dict) -> Subject:
        subject = await self._get_subject_for_school(school_id, subject_id)
        if payload.get("name") is not None:
            name = payload["name"].strip()
            if not name:
                raise HTTPException(status_code=400, detail="Subject name is required")
            await self._ensure_unique_subject_name(school_id, name, exclude_subject_id=subject_id)
            subject.name = name
        if "code" in payload:
            code = payload["code"].strip() if payload["code"] else None
            await self._ensure_unique_subject_code(school_id, code, exclude_subject_id=subject_id)
            subject.code = code
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def delete_subject(self, school_id: UUID, subject_id: UUID) -> None:
        subject = await self._get_subject_for_school(school_id, subject_id)
        timetable_rows = await self.db.execute(select(Timetable.id).where(Timetable.subject_id == subject_id))
        if timetable_rows.scalars().first():
            raise HTTPException(status_code=400, detail="Remove timetable entries before deleting this subject")
        subject.sections = []
        subject.teachers = []
        self.db.add(subject)
        await self.db.flush()
        await self.db.execute(delete(Subject).where(Subject.id == subject_id, Subject.school_id == school_id))
        await self.db.commit()

    async def update_section_subjects(self, school_id: UUID, section_id: UUID, subject_ids: list[UUID]) -> dict:
        section = await self._get_section_for_school(school_id, section_id)
        subjects = await self._get_subjects(school_id, subject_ids)
        section.subjects = subjects
        self.db.add(section)
        await self.db.commit()
        return await self.get_academic_structure(school_id)

    async def get_teacher_assignments(self, school_id: UUID, teacher_id: UUID) -> dict:
        teacher = await self._get_teacher(teacher_id, school_id)
        timetable_rows = await self.db.execute(
            select(Timetable, Section, Class, Subject)
            .join(Section, Section.id == Timetable.section_id)
            .join(Class, Class.id == Section.class_id)
            .join(Subject, Subject.id == Timetable.subject_id)
            .where(Timetable.teacher_id == teacher_id, Class.school_id == school_id)
            .order_by(Timetable.day_of_week, Timetable.start_time)
        )

        timetable = [
            {
                "id": row[0].id,
                "section_id": row[1].id,
                "section_name": row[1].name,
                "class_id": row[2].id,
                "class_name": row[2].name,
                "subject_id": row[3].id,
                "subject_name": row[3].name,
                "teacher_id": row[0].teacher_id,
                "day_of_week": row[0].day_of_week,
                "start_time": row[0].start_time,
                "end_time": row[0].end_time,
                "room": row[0].room,
            }
            for row in timetable_rows.all()
        ]

        return {
            "teacher_id": teacher.id,
            "section_ids": [section.id for section in teacher.assigned_sections],
            "subject_ids": [subject.id for subject in teacher.assigned_subjects],
            "sections": [
                {
                    "id": section.id,
                    "name": section.name,
                    "class_id": section.parent_class.id,
                    "class_name": section.parent_class.name,
                }
                for section in teacher.assigned_sections
            ],
            "subjects": [
                {"id": subject.id, "name": subject.name, "code": subject.code}
                for subject in teacher.assigned_subjects
            ],
            "timetable": timetable,
        }

    async def update_teacher_sections(self, school_id: UUID, teacher_id: UUID, section_ids: list[UUID]) -> dict:
        teacher = await self._get_teacher(teacher_id, school_id)
        sections = await self._get_sections(school_id, section_ids)

        existing_rows = await self.db.execute(
            select(Timetable.section_id).where(Timetable.teacher_id == teacher_id)
        )
        scheduled_section_ids = {row[0] for row in existing_rows.all()}
        if not scheduled_section_ids.issubset(set(section_ids)):
            raise HTTPException(
                status_code=400,
                detail="Remove or update timetable entries before removing assigned sections",
            )

        teacher.assigned_sections = sections
        self.db.add(teacher)
        await self.db.commit()
        return await self.get_teacher_assignments(school_id, teacher_id)

    async def update_teacher_subjects(self, school_id: UUID, teacher_id: UUID, subject_ids: list[UUID]) -> dict:
        teacher = await self._get_teacher(teacher_id, school_id)
        subjects = await self._get_subjects(school_id, subject_ids)

        existing_rows = await self.db.execute(
            select(Timetable.subject_id).where(Timetable.teacher_id == teacher_id)
        )
        scheduled_subject_ids = {row[0] for row in existing_rows.all()}
        if not scheduled_subject_ids.issubset(set(subject_ids)):
            raise HTTPException(
                status_code=400,
                detail="Remove or update timetable entries before removing assigned subjects",
            )

        teacher.assigned_subjects = subjects
        self.db.add(teacher)
        await self.db.commit()
        return await self.get_teacher_assignments(school_id, teacher_id)

    async def _validate_timetable_payload(
        self,
        school_id: UUID,
        *,
        section_id: UUID,
        subject_id: UUID,
        teacher_id: UUID,
        day_of_week: int,
        start_time: str,
        end_time: str,
        exclude_entry_id: UUID | None = None,
    ) -> None:
        self._validate_time_range(start_time, end_time)
        teacher = await self._get_teacher(teacher_id, school_id)

        section_rows = {section.id for section in teacher.assigned_sections}
        subject_rows = {subject.id for subject in teacher.assigned_subjects}

        if section_id not in section_rows:
            raise HTTPException(status_code=400, detail="Teacher is not assigned to this section")
        if subject_id not in subject_rows:
            raise HTTPException(status_code=400, detail="Teacher is not assigned to this subject")

        await self._get_sections(school_id, [section_id])
        await self._get_subjects(school_id, [subject_id])

        teacher_collision_query = select(Timetable).where(
            Timetable.teacher_id == teacher_id,
            Timetable.day_of_week == day_of_week,
            Timetable.start_time < end_time,
            Timetable.end_time > start_time,
        )
        section_collision_query = select(Timetable).where(
            Timetable.section_id == section_id,
            Timetable.day_of_week == day_of_week,
            Timetable.start_time < end_time,
            Timetable.end_time > start_time,
        )
        if exclude_entry_id:
            teacher_collision_query = teacher_collision_query.where(Timetable.id != exclude_entry_id)
            section_collision_query = section_collision_query.where(Timetable.id != exclude_entry_id)

        teacher_collision = (await self.db.execute(teacher_collision_query)).scalars().first()
        if teacher_collision:
            raise HTTPException(status_code=400, detail="Teacher already has another class during this time")

        section_collision = (await self.db.execute(section_collision_query)).scalars().first()
        if section_collision:
            raise HTTPException(status_code=400, detail="Section already has another subject scheduled during this time")

    async def create_timetable_entry(self, school_id: UUID, payload: dict) -> Timetable:
        await self._validate_timetable_payload(
            school_id,
            section_id=payload["section_id"],
            subject_id=payload["subject_id"],
            teacher_id=payload["teacher_id"],
            day_of_week=payload["day_of_week"],
            start_time=payload["start_time"],
            end_time=payload["end_time"],
        )
        entry = Timetable(**payload)
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def update_timetable_entry(self, school_id: UUID, entry_id: UUID, payload: dict) -> Timetable:
        result = await self.db.execute(
            select(Timetable)
            .join(Section, Section.id == Timetable.section_id)
            .join(Class, Class.id == Section.class_id)
            .where(Timetable.id == entry_id, Class.school_id == school_id)
        )
        entry = result.scalars().first()
        if not entry:
            raise HTTPException(status_code=404, detail="Timetable entry not found")

        data = {
            "section_id": payload.get("section_id", entry.section_id),
            "subject_id": payload.get("subject_id", entry.subject_id),
            "teacher_id": payload.get("teacher_id", entry.teacher_id),
            "day_of_week": payload.get("day_of_week", entry.day_of_week),
            "start_time": payload.get("start_time", entry.start_time),
            "end_time": payload.get("end_time", entry.end_time),
        }
        await self._validate_timetable_payload(school_id, exclude_entry_id=entry.id, **data)

        for field, value in payload.items():
            setattr(entry, field, value)
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def delete_timetable_entry(self, school_id: UUID, entry_id: UUID) -> None:
        result = await self.db.execute(
            select(Timetable.id)
            .join(Section, Section.id == Timetable.section_id)
            .join(Class, Class.id == Section.class_id)
            .where(Timetable.id == entry_id, Class.school_id == school_id)
        )
        found = result.scalar_one_or_none()
        if not found:
            raise HTTPException(status_code=404, detail="Timetable entry not found")
        await self.db.execute(delete(Timetable).where(Timetable.id == entry_id))
        await self.db.commit()


def get_academic_service(db: AsyncSession) -> AcademicService:
    return AcademicService(db)
