import asyncio
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.shared.db.session import engine
from app.modules.academic.models import School, Section, Subject, student_subject, Class
from app.modules.identity.models import Student
from app.modules.assessment.models import Exam, Mark, Attendance

async def populate_grades():
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with session_factory() as session:
        result = await session.execute(select(School).where(School.name == "Akshara School Kakinada"))
        school = result.scalars().first()
        if not school:
            print("School not found.")
            return

        print("Cleaning up old grades and attendance if any...")
        students_result = await session.execute(select(Student).where(Student.school_id == school.id))
        all_students = students_result.scalars().all()
        student_ids = [s.id for s in all_students]
        
        if student_ids:
            await session.execute(delete(Attendance).where(Attendance.student_id.in_(student_ids)))
            await session.execute(delete(Mark).where(Mark.student_id.in_(student_ids)))
            
        classes_result = await session.execute(select(Class.id).where(Class.school_id == school.id))
        class_ids = [c[0] for c in classes_result.all()]
        
        if class_ids:
            sections_result = await session.execute(select(Section.id).where(Section.class_id.in_(class_ids)))
            section_ids = [r[0] for r in sections_result.all()]
            if section_ids:
                await session.execute(delete(Exam).where(Exam.section_id.in_(section_ids)))
        
        await session.flush()
        print("Cleaned up old records.")
        
        print(f"Found {len(all_students)} students in {len(section_ids)} sections.")

        # Create an exam for each section
        print("Creating exams (Term 1 & Term 2)...")
        exam_date_t1 = date(2025, 12, 15)
        exam_date_t2 = date(2026, 3, 10)
        
        exams_by_section = {}
        for sec_id in section_ids:
            e1 = Exam(section_id=sec_id, name="Term 1 Final", exam_date=exam_date_t1)
            e2 = Exam(section_id=sec_id, name="Term 2 Mid", exam_date=exam_date_t2)
            session.add_all([e1, e2])
            exams_by_section[sec_id] = [e1, e2]
            
        await session.flush()
        print("Exams created.")
        
        print("Populating marks for all students...")
        ss_result = await session.execute(
            select(student_subject.c.student_id, student_subject.c.subject_id)
            .where(student_subject.c.student_id.in_(student_ids))
        )
        student_subjects_map = {}
        for row in ss_result.all():
            stu_id = row[0]
            sub_id = row[1]
            if stu_id not in student_subjects_map:
                student_subjects_map[stu_id] = []
            student_subjects_map[stu_id].append(sub_id)
            
        mark_count = 0
        for student in all_students:
            sec_id = student.section_id
            exams = exams_by_section.get(sec_id, [])
            sub_ids = student_subjects_map.get(student.id, [])
            
            for exam in exams:
                for sub_id in sub_ids:
                    # Randomize marks, higher probability of 60-100
                    base_mark = random.normalvariate(75, 15)
                    marks_obtained = max(0.0, min(100.0, round(base_mark, 1)))
                    # 2% chance of being absent for exam
                    mark_status = "present" if random.random() > 0.02 else "absent"
                    if mark_status == "absent":
                        marks_obtained = 0.0
                        
                    mark = Mark(
                        exam_id=exam.id,
                        student_id=student.id,
                        subject_id=sub_id,
                        marks_obtained=marks_obtained,
                        max_marks=100.0,
                        mark_status=mark_status
                    )
                    session.add(mark)
                    mark_count += 1
                    
            if mark_count % 10000 == 0:
                await session.flush()
                
        await session.flush()
        print(f"Populated {mark_count} mark records.")
        
        print("Populating attendance for last 30 days...")
        today = date.today()
        dates = [today - timedelta(days=x) for x in range(30)]
        # Exclude Sundays (weekday 6)
        dates = [d for d in dates if d.weekday() != 6]
        
        att_count = 0
        for student in all_students:
            profile_rnd = random.random()
            if profile_rnd < 0.8:
                present_prob = 0.95
            elif profile_rnd < 0.95:
                present_prob = 0.80
            else:
                present_prob = 0.60
                
            for d in dates:
                status = "Present" if random.random() < present_prob else "Absent"
                att = Attendance(
                    student_id=student.id,
                    date=d,
                    status=status
                )
                session.add(att)
                att_count += 1
                
            if att_count % 10000 == 0:
                await session.flush()
                
        await session.flush()
        print(f"Populated {att_count} attendance records.")
        
        await session.commit()
        print("Successfully committed grades and attendance to database.")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(populate_grades())
