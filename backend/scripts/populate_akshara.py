"""
Populate Akshara School Kakinada with realistic full data.

Akshara School, NFCL Township, Kakinada, East Godavari, AP 533003
CBSE Affiliated | Established 1990
~1850 students | ~74 teachers | Nursery to Class 10
~4 sections per class (A, B, C, D)

This script:
1. Updates the existing school record with real details
2. Creates all classes: Nursery, LKG, UKG, Class 1 through Class 10 (13 classes)
3. Creates 4 sections (A-D) per class = 52 sections
4. Creates 15 CBSE subjects
5. Creates 74 teacher users + assigns them to sections/subjects
6. Creates ~1850 student users + student records with realistic names
7. Links subjects to sections appropriately
"""

import asyncio
import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.security import get_password_hash
from app.shared.db.session import engine
from app.modules.auth.models import User, UserRole
from app.modules.academic.models import (
    School, Chain, Class, Section, Subject, Timetable,
    teacher_section, teacher_subject, section_subject, student_subject,
)
from app.modules.identity.models import Student, parent_student
from app.modules.assessment.models import Attendance, Mark, LearningTask, Exam
from app.modules.analytics.models import AIInsight, ReportCard, AIChatSession, AIChatMessage, InstitutionalInsight
from app.modules.platform.models import AuditLog, UserSettings, APIRequestLog
from app.modules.notification.models import Notification, NotificationEvent, UserNotification, DeviceToken

# ─── Name Data (Indian names common in Andhra Pradesh) ───────────────────────

FIRST_NAMES_MALE = [
    "Aarav", "Aditya", "Ajay", "Akash", "Amith", "Anand", "Anil", "Arjun",
    "Ashwin", "Balaji", "Bhanu", "Chaitanya", "Chiranjeevi", "Dhanush",
    "Dinesh", "Ganesh", "Gopal", "Harish", "Hemanth", "Jagadeesh",
    "Karthik", "Kishore", "Krishna", "Kumar", "Lokesh", "Mahesh",
    "Manoj", "Mohan", "Nagaraj", "Naveen", "Pavan", "Phaneendra",
    "Pradeep", "Prakash", "Prasad", "Praveen", "Rahul", "Rajesh",
    "Rakesh", "Ramesh", "Ravi", "Rohith", "Sai", "Sandeep",
    "Sanjay", "Shankar", "Shiva", "Srikanth", "Sumanth", "Suresh",
    "Teja", "Uday", "Varun", "Venkat", "Vijay", "Vinay", "Vishnu",
    "Yashwanth", "Sathish", "Surya", "Tarun", "Trilok", "Vivek",
    "Abhinav", "Deepak", "Girish", "Hari", "Jagan", "Kalyan",
    "Lakshman", "Murali", "Nagendra", "Omkar", "Prudhvi", "Raghu",
    "Samanth", "Tilak", "Upendra", "Vamsi", "Yaswanth", "Charan",
    "Dheeraj", "Eswar", "Feroz", "Gowtham", "Hitesh", "Indu",
    "Jayaram", "Kiran", "Lohith", "Madhu", "Nikhil", "Prabhas",
    "Ranjith", "Sridhar", "Tharun", "Uttam", "Vikram", "Wasim",
]

FIRST_NAMES_FEMALE = [
    "Aadhya", "Amrutha", "Ananya", "Anusha", "Bhavani", "Chandana",
    "Charita", "Deepthi", "Divya", "Durga", "Gayathri", "Harika",
    "Ishwarya", "Jyothi", "Kavitha", "Keerthi", "Lakshmi", "Lavanya",
    "Madhavi", "Manasa", "Meghana", "Mounika", "Nandini", "Niharika",
    "Padma", "Pavithra", "Pooja", "Priya", "Radhika", "Ramya",
    "Roja", "Sahithi", "Sailaja", "Sameera", "Sandhya", "Sarika",
    "Saritha", "Shravani", "Sindhu", "Sirisha", "Sneha", "Sowmya",
    "Sravanthi", "Sridevi", "Sujatha", "Sunitha", "Swathi", "Tejaswi",
    "Uma", "Vaishnavi", "Vasantha", "Vidhya", "Yamini", "Yashaswini",
    "Aparna", "Bindu", "Charitha", "Deepa", "Eswari", "Fathima",
    "Girija", "Hema", "Indira", "Janaki", "Kamala", "Lalitha",
    "Mallika", "Nagalakshmi", "Omvathi", "Pallavi", "Rajitha",
    "Sarala", "Tulasi", "Usha", "Vanaja", "Wahida", "Aruna",
    "Bhargavi", "Chithra", "Dharani", "Esther", "Firoza",
    "Gowri", "Hymavathi", "Ila", "Jayanthi", "Kiranmai", "Latha",
    "Madhumitha", "Navya", "Praneetha", "Rekha", "Spandana", "Tanvi",
]

LAST_NAMES = [
    "Reddy", "Naidu", "Rao", "Sharma", "Kumar", "Varma", "Gupta",
    "Patel", "Chowdary", "Prasad", "Murthy", "Raju", "Srinivas",
    "Babu", "Nair", "Iyer", "Das", "Mishra", "Pillai", "Choudhury",
    "Venkatesh", "Subramanian", "Acharya", "Bhat", "Hegde",
    "Joshi", "Kamath", "Menon", "Padmanabhan", "Ramakrishna",
    "Setty", "Tiwari", "Verma", "Yadav", "Devi", "Goud",
    "Khatri", "Mehta", "Pandey", "Saxena", "Trivedi", "Bhatt",
    "Desai", "Gandhi", "Iyengar", "Kulkarni", "Nambiar", "Patnaik",
    "Rajput", "Shukla", "Thakur", "Upadhyay", "Vyas", "Zaveri",
    "Acharyulu", "Bhaskar", "Chakravarthy", "Dandamudi", "Eepuri",
]

GUARDIAN_RELATIONS = ["Father", "Mother", "Father", "Father", "Mother", "Father"]

# ─── Subjects per class level ────────────────────────────────────────────────

# CBSE subjects for Akshara School Kakinada
SUBJECTS_DATA = [
    ("English", "ENG"),
    ("Hindi", "HIN"),
    ("Telugu", "TEL"),
    ("Mathematics", "MAT"),
    ("Science", "SCI"),
    ("Social Science", "SST"),
    ("Computer Science", "CSC"),
    ("Physical Education", "PHE"),
    ("Art & Craft", "ART"),
    ("Music", "MUS"),
    ("Moral Science", "MSC"),
    ("Environmental Studies", "EVS"),
    ("General Knowledge", "GKN"),
    ("Life Skills", "LSK"),
    ("Sanskrit", "SAN"),
]

# Which subjects apply to which class levels
# Nursery/LKG/UKG (class_number 0,-1,-2): English, Hindi, Telugu, Mathematics, EVS, Art, Music, GK
# Classes 1-2: English, Hindi, Telugu, Mathematics, EVS, Computer Science, Art, Music, GK, Moral Science
# Classes 3-5: English, Hindi, Telugu, Mathematics, EVS, Computer Science, Art, Music, GK, Moral Science, Life Skills
# Classes 6-8: English, Hindi, Telugu, Mathematics, Science, Social Science, Computer Science, PE, Art, Sanskrit
# Classes 9-10: English, Hindi, Telugu, Mathematics, Science, Social Science, Computer Science, PE, Sanskrit

def get_subjects_for_class(class_number: int, all_subjects: dict) -> list:
    """Return list of Subject objects appropriate for the class level."""
    if class_number <= 0:  # Nursery, LKG, UKG
        codes = ["ENG", "HIN", "TEL", "MAT", "EVS", "ART", "MUS", "GKN"]
    elif class_number <= 2:  # Class 1-2
        codes = ["ENG", "HIN", "TEL", "MAT", "EVS", "CSC", "ART", "MUS", "GKN", "MSC"]
    elif class_number <= 5:  # Class 3-5
        codes = ["ENG", "HIN", "TEL", "MAT", "EVS", "CSC", "ART", "MUS", "GKN", "MSC", "LSK"]
    elif class_number <= 8:  # Class 6-8
        codes = ["ENG", "HIN", "TEL", "MAT", "SCI", "SST", "CSC", "PHE", "ART", "SAN"]
    else:  # Class 9-10
        codes = ["ENG", "HIN", "TEL", "MAT", "SCI", "SST", "CSC", "PHE", "SAN"]
    return [all_subjects[c] for c in codes if c in all_subjects]


# ─── Class structure (real Akshara School Kakinada layout) ────────────────────

# class_number: (class_name, sections, students_per_section_range)
# Total ~1850 students across all classes
# Nursery/LKG/UKG have fewer students; Classes 1-10 have ~35-45 per section
CLASS_STRUCTURE = {
    -2: ("Nursery",    ["A", "B", "C"],           (25, 30)),
    -1: ("LKG",        ["A", "B", "C", "D"],      (28, 32)),
     0: ("UKG",        ["A", "B", "C", "D"],      (28, 32)),
     1: ("Class 1",    ["A", "B", "C", "D"],      (35, 40)),
     2: ("Class 2",    ["A", "B", "C", "D"],      (35, 40)),
     3: ("Class 3",    ["A", "B", "C", "D"],      (35, 40)),
     4: ("Class 4",    ["A", "B", "C", "D"],      (35, 40)),
     5: ("Class 5",    ["A", "B", "C", "D"],      (35, 40)),
     6: ("Class 6",    ["A", "B", "C", "D"],      (38, 42)),
     7: ("Class 7",    ["A", "B", "C", "D"],      (38, 42)),
     8: ("Class 8",    ["A", "B", "C", "D"],      (38, 42)),
     9: ("Class 9",    ["A", "B", "C", "D"],      (38, 42)),
    10: ("Class 10",   ["A", "B", "C", "D"],      (38, 42)),
}

# ─── Teacher designations ────────────────────────────────────────────────────

TEACHER_SPECIALIZATIONS = [
    # (subject_code, count)  — how many teachers per subject
    ("ENG", 8),
    ("HIN", 5),
    ("TEL", 6),
    ("MAT", 9),
    ("SCI", 7),
    ("SST", 6),
    ("CSC", 4),
    ("PHE", 4),
    ("ART", 3),
    ("MUS", 2),
    ("MSC", 2),
    ("EVS", 5),
    ("GKN", 2),
    ("LSK", 2),
    ("SAN", 3),
]
# Total: 68 subject teachers + some class teachers who double up
# We'll have a total pool of 74 teachers


def generate_phone(index: int) -> str:
    """Generate a unique Indian phone number."""
    return f"+919{random.randint(100000000, 999999999)}"


def random_dob_for_class(class_number: int) -> date:
    """Generate a plausible DOB for a student in the given class.
    Based on the 2025-26 academic year, a Class 10 student is ~15-16 years old.
    """
    # Approximate age: Nursery=3, LKG=4, UKG=5, Class1=6, ..., Class10=15
    age_map = {
        -2: 3, -1: 4, 0: 5,
        1: 6, 2: 7, 3: 8, 4: 9, 5: 10,
        6: 11, 7: 12, 8: 13, 9: 14, 10: 15,
    }
    base_age = age_map.get(class_number, 10)
    # Reference date: April 1, 2026 (start of Indian academic year)
    ref_date = date(2026, 4, 1)
    birth_year = ref_date.year - base_age
    # Random month/day
    birth_month = random.randint(1, 12)
    max_day = 28  # safe for all months
    birth_day = random.randint(1, max_day)
    return date(birth_year, birth_month, birth_day)


async def populate():
    """Main population function."""
    session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        # ── 1. Find the existing Akshara school ──────────────────────────
        # The school is stored as "Ajay" with username "akshara_school"
        result = await session.execute(
            select(School).where(School.name == "Ajay")
        )
        schools = result.scalars().all()

        if not schools:
            print("ERROR: School 'Ajay' not found. Please create it first.")
            return

        # Use the first one (with chain)
        school = schools[0]
        print(f"Found school: {school.name} (ID: {school.id})")

        # ── 2. Clean up existing data for this school ────────────────────
        print("Cleaning existing data for this school...")

        # Get existing class IDs for this school
        existing_classes = await session.execute(
            select(Class).where(Class.school_id == school.id)
        )
        existing_class_ids = [c.id for c in existing_classes.scalars().all()]

        # Get existing section IDs
        existing_sections = []
        for cid in existing_class_ids:
            secs = await session.execute(select(Section).where(Section.class_id == cid))
            existing_sections.extend([s.id for s in secs.scalars().all()])

        # Get existing student IDs for this school
        existing_students = await session.execute(
            select(Student).where(Student.school_id == school.id)
        )
        existing_student_ids = [s.id for s in existing_students.scalars().all()]
        existing_student_user_ids = []
        if existing_student_ids:
            stu_data = await session.execute(
                select(Student.user_id).where(Student.school_id == school.id)
            )
            existing_student_user_ids = [r[0] for r in stu_data.all()]

        # Get existing subject IDs
        existing_subjects = await session.execute(
            select(Subject).where(Subject.school_id == school.id)
        )
        existing_subject_ids = [s.id for s in existing_subjects.scalars().all()]

        # ── Delete ALL dependent data in correct FK order ──────────────

        # Gather all user IDs that belong to this school (students + teachers + others except admin)
        all_school_users = await session.execute(
            select(User.id).where(User.school_id == school.id)
        )
        all_school_user_ids = [r[0] for r in all_school_users.all()]

        # Step 1: UserNotification → depends on user_id and notification_event.id
        if all_school_user_ids:
            await session.execute(
                delete(UserNotification).where(UserNotification.user_id.in_(all_school_user_ids))
            )

        # Step 2: NotificationEvent → depends on student_id, actor_id (user), school_id
        if existing_student_ids:
            await session.execute(
                delete(NotificationEvent).where(NotificationEvent.student_id.in_(existing_student_ids))
            )
        # Also delete by actor_id (teacher/admin users) and school_id
        if all_school_user_ids:
            await session.execute(
                delete(NotificationEvent).where(NotificationEvent.actor_id.in_(all_school_user_ids))
            )
        await session.execute(
            delete(NotificationEvent).where(NotificationEvent.school_id == school.id)
        )

        # Step 3: Notification → depends on user_id
        if all_school_user_ids:
            await session.execute(
                delete(Notification).where(Notification.user_id.in_(all_school_user_ids))
            )

        # Step 4: DeviceToken → depends on user_id
        if all_school_user_ids:
            await session.execute(
                delete(DeviceToken).where(DeviceToken.user_id.in_(all_school_user_ids))
            )

        # Step 5: UserSettings → depends on user_id
        if all_school_user_ids:
            await session.execute(
                delete(UserSettings).where(UserSettings.user_id.in_(all_school_user_ids))
            )

        # Step 6: AI Chat Messages → via sessions → depends on student_id
        if existing_student_ids:
            chat_sessions = await session.execute(
                select(AIChatSession.id).where(AIChatSession.student_id.in_(existing_student_ids))
            )
            chat_session_ids = [r[0] for r in chat_sessions.all()]
            if chat_session_ids:
                await session.execute(
                    delete(AIChatMessage).where(AIChatMessage.session_id.in_(chat_session_ids))
                )
                await session.execute(
                    delete(AIChatSession).where(AIChatSession.id.in_(chat_session_ids))
                )

        # Step 7: AIInsight → depends on student_id
        if existing_student_ids:
            await session.execute(
                delete(AIInsight).where(AIInsight.student_id.in_(existing_student_ids))
            )

        # Step 8: ReportCard → depends on student_id
        if existing_student_ids:
            await session.execute(
                delete(ReportCard).where(ReportCard.student_id.in_(existing_student_ids))
            )

        # Step 9: Attendance → depends on student_id
        if existing_student_ids:
            await session.execute(
                delete(Attendance).where(Attendance.student_id.in_(existing_student_ids))
            )

        # Step 10: Mark → depends on student_id, exam_id, subject_id
        if existing_student_ids:
            await session.execute(
                delete(Mark).where(Mark.student_id.in_(existing_student_ids))
            )

        # Step 11: LearningTask → depends on student_id
        if existing_student_ids:
            await session.execute(
                delete(LearningTask).where(LearningTask.student_id.in_(existing_student_ids))
            )

        # Step 12: Exam → depends on section_id
        if existing_sections:
            await session.execute(
                delete(Exam).where(Exam.section_id.in_(existing_sections))
            )

        # Step 13: Timetable → depends on section_id, subject_id, teacher_id(user)
        if existing_sections:
            await session.execute(
                delete(Timetable).where(Timetable.section_id.in_(existing_sections))
            )

        # Step 13.5: APIRequestLog → depends on user_id
        if all_school_user_ids:
            await session.execute(
                delete(APIRequestLog).where(APIRequestLog.user_id.in_(all_school_user_ids))
            )

        # Step 14: AuditLog → depends on user_id, student_id, school_id
        if existing_student_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.student_id.in_(existing_student_ids))
            )
        if all_school_user_ids:
            await session.execute(
                delete(AuditLog).where(AuditLog.user_id.in_(all_school_user_ids))
            )
        await session.execute(
            delete(AuditLog).where(AuditLog.school_id == school.id)
        )

        # Step 15: InstitutionalInsight → depends on school_id
        await session.execute(
            delete(InstitutionalInsight).where(InstitutionalInsight.school_id == school.id)
        )

        await session.flush()
        print("  Cleaned dependent records (analytics, assessment, notifications, audit).")

        # ── Delete association table entries ──
        if existing_sections:
            await session.execute(
                teacher_section.delete().where(teacher_section.c.section_id.in_(existing_sections))
            )
            await session.execute(
                section_subject.delete().where(section_subject.c.section_id.in_(existing_sections))
            )
        if existing_subject_ids:
            await session.execute(
                teacher_subject.delete().where(teacher_subject.c.subject_id.in_(existing_subject_ids))
            )
            await session.execute(
                student_subject.delete().where(student_subject.c.subject_id.in_(existing_subject_ids))
            )

        if existing_student_ids:
            await session.execute(
                student_subject.delete().where(student_subject.c.student_id.in_(existing_student_ids))
            )
            await session.execute(
                parent_student.delete().where(parent_student.c.student_id.in_(existing_student_ids))
            )

        # ── Delete students ──
        if existing_student_ids:
            await session.execute(
                delete(Student).where(Student.school_id == school.id)
            )

        # ── Delete student user records ──
        if existing_student_user_ids:
            await session.execute(
                delete(User).where(User.id.in_(existing_student_user_ids))
            )

        # ── Delete teacher users (keep admin) ──
        existing_teachers = await session.execute(
            select(User).where(
                User.school_id == school.id,
                User.role == UserRole.TEACHER
            )
        )
        teacher_ids_to_delete = [t.id for t in existing_teachers.scalars().all()]
        if teacher_ids_to_delete:
            await session.execute(
                delete(User).where(User.id.in_(teacher_ids_to_delete))
            )

        # ── Delete subjects ──
        if existing_subject_ids:
            await session.execute(
                delete(Subject).where(Subject.school_id == school.id)
            )

        # ── Delete sections ──
        if existing_sections:
            await session.execute(
                delete(Section).where(Section.id.in_(existing_sections))
            )

        # ── Delete classes ──
        if existing_class_ids:
            await session.execute(
                delete(Class).where(Class.school_id == school.id)
            )

        await session.flush()
        print("  Cleaned up all existing data.")

        # ── 3. Update school details ─────────────────────────────────────
        school.name = "Akshara School Kakinada"
        school.email = "info@aksharaschoolkakinada.org"
        school.address = "NFCL Township, Kakinada"
        school.village = "NFCL Township"
        school.mandal = "Kakinada Urban"
        school.district_city = "Kakinada"
        school.pincode = "533003"
        school.is_active = True
        await session.flush()
        print(f"  Updated school: {school.name}")

        # Also update chain name if it exists
        if school.chain_id:
            chain_result = await session.execute(
                select(Chain).where(Chain.id == school.chain_id)
            )
            chain = chain_result.scalars().first()
            if chain:
                chain.name = "Akshara Educational Society"
                await session.flush()

        # ── 4. Create Subjects ───────────────────────────────────────────
        print("Creating subjects...")
        subjects_by_code = {}
        for subj_name, subj_code in SUBJECTS_DATA:
            subj = Subject(
                school_id=school.id,
                name=subj_name,
                code=subj_code,
            )
            session.add(subj)
            await session.flush()
            subjects_by_code[subj_code] = subj
            print(f"    {subj_name} ({subj_code})")
        print(f"  Created {len(subjects_by_code)} subjects.")

        # ── 5. Create Classes & Sections ─────────────────────────────────
        print("Creating classes and sections...")
        classes_by_num = {}
        sections_list = []  # (section, class_number)
        all_sections_by_class = {}  # class_number -> [Section]

        for class_num, (class_name, section_names, _) in CLASS_STRUCTURE.items():
            cls = Class(
                school_id=school.id,
                name=class_name,
                class_number=class_num,
            )
            session.add(cls)
            await session.flush()
            classes_by_num[class_num] = cls

            all_sections_by_class[class_num] = []
            for sec_name in section_names:
                sec = Section(
                    class_id=cls.id,
                    name=f"Section {sec_name}",
                )
                session.add(sec)
                await session.flush()
                sections_list.append((sec, class_num))
                all_sections_by_class[class_num].append(sec)

            print(f"    {class_name}: {len(section_names)} sections ({', '.join(section_names)})")

        print(f"  Created {len(classes_by_num)} classes, {len(sections_list)} sections total.")

        # ── 6. Link Subjects to Sections ─────────────────────────────────
        print("Linking subjects to sections...")
        link_count = 0
        for sec, class_num in sections_list:
            applicable_subjects = get_subjects_for_class(class_num, subjects_by_code)
            for subj in applicable_subjects:
                await session.execute(
                    section_subject.insert().values(
                        section_id=sec.id,
                        subject_id=subj.id,
                    )
                )
                link_count += 1
        await session.flush()
        print(f"  Created {link_count} section-subject links.")

        # ── 7. Create Teachers ───────────────────────────────────────────
        print("Creating teachers...")
        used_phones = set()
        all_teachers = []
        teacher_by_subject = {}  # subject_code -> [User]
        teacher_index = 0

        for subj_code, count in TEACHER_SPECIALIZATIONS:
            teacher_by_subject[subj_code] = []
            for i in range(count):
                teacher_index += 1
                is_female = random.random() < 0.55  # ~55% female teachers
                if is_female:
                    first = random.choice(FIRST_NAMES_FEMALE)
                else:
                    first = random.choice(FIRST_NAMES_MALE)
                last = random.choice(LAST_NAMES)
                full_name = f"{first} {last}"

                while True:
                    phone = generate_phone(teacher_index)
                    if phone not in used_phones:
                        used_phones.add(phone)
                        break

                username = f"teacher_{subj_code.lower()}_{teacher_index}"

                teacher_user = User(
                    full_name=full_name,
                    username=username,
                    password_hash=get_password_hash("teacher123"),
                    phone=phone,
                    role=UserRole.TEACHER,
                    school_id=school.id,
                    is_active=True,
                )
                session.add(teacher_user)
                await session.flush()
                all_teachers.append(teacher_user)
                teacher_by_subject[subj_code].append(teacher_user)

        # Fill remaining to reach 74 teachers (general/class teachers)
        while len(all_teachers) < 74:
            teacher_index += 1
            is_female = random.random() < 0.55
            first = random.choice(FIRST_NAMES_FEMALE if is_female else FIRST_NAMES_MALE)
            last = random.choice(LAST_NAMES)
            while True:
                phone = generate_phone(teacher_index)
                if phone not in used_phones:
                    used_phones.add(phone)
                    break
            teacher_user = User(
                full_name=f"{first} {last}",
                username=f"teacher_gen_{teacher_index}",
                password_hash=get_password_hash("teacher123"),
                phone=phone,
                role=UserRole.TEACHER,
                school_id=school.id,
                is_active=True,
            )
            session.add(teacher_user)
            await session.flush()
            all_teachers.append(teacher_user)
            # Assign them to a random subject
            random_subj = random.choice(list(teacher_by_subject.keys()))
            teacher_by_subject[random_subj].append(teacher_user)

        print(f"  Created {len(all_teachers)} teachers.")

        # ── 8. Assign Teachers to Subjects (teacher_subject table) ───────
        print("Assigning teachers to subjects...")
        ts_count = 0
        for subj_code, teachers in teacher_by_subject.items():
            if subj_code in subjects_by_code:
                subj = subjects_by_code[subj_code]
                for t in teachers:
                    await session.execute(
                        teacher_subject.insert().values(
                            teacher_id=t.id,
                            subject_id=subj.id,
                        )
                    )
                    ts_count += 1
        await session.flush()
        print(f"  Created {ts_count} teacher-subject assignments.")

        # ── 9. Assign Teachers to Sections (teacher_section table) ───────
        print("Assigning teachers to sections...")
        tsec_count = 0
        for sec, class_num in sections_list:
            applicable_subj_codes = [
                subj.code for subj in get_subjects_for_class(class_num, subjects_by_code)
            ]
            # Assign at least one teacher per subject for this section
            assigned_teacher_ids = set()
            for code in applicable_subj_codes:
                if code in teacher_by_subject and teacher_by_subject[code]:
                    teacher = random.choice(teacher_by_subject[code])
                    if teacher.id not in assigned_teacher_ids:
                        await session.execute(
                            teacher_section.insert().values(
                                teacher_id=teacher.id,
                                section_id=sec.id,
                            )
                        )
                        assigned_teacher_ids.add(teacher.id)
                        tsec_count += 1
        await session.flush()
        print(f"  Created {tsec_count} teacher-section assignments.")

        # ── 10. Create Students ──────────────────────────────────────────
        print("Creating students...")
        total_students = 0
        admission_counter = 20260001  # Admission number series for 2026

        for class_num, (class_name, section_names, (min_stu, max_stu)) in CLASS_STRUCTURE.items():
            sections = all_sections_by_class[class_num]
            cls = classes_by_num[class_num]

            for sec in sections:
                num_students = random.randint(min_stu, max_stu)
                for roll in range(1, num_students + 1):
                    is_female = random.random() < 0.48  # ~48% female students
                    if is_female:
                        first = random.choice(FIRST_NAMES_FEMALE)
                    else:
                        first = random.choice(FIRST_NAMES_MALE)
                    last = random.choice(LAST_NAMES)
                    full_name = f"{first} {last}"

                    while True:
                        phone = generate_phone(admission_counter)
                        if phone not in used_phones:
                            used_phones.add(phone)
                            break

                    # Guardian info
                    guardian_first = random.choice(FIRST_NAMES_MALE)
                    guardian_last = last  # same family name
                    guardian_relation = random.choice(GUARDIAN_RELATIONS)
                    guardian_phone_num = generate_phone(admission_counter + 100000)

                    dob = random_dob_for_class(class_num)

                    # Create User for student
                    student_user = User(
                        full_name=full_name,
                        phone=phone,
                        role=UserRole.STUDENT,
                        school_id=school.id,
                        is_active=True,
                    )
                    session.add(student_user)
                    await session.flush()

                    # Create Student record
                    student = Student(
                        user_id=student_user.id,
                        school_id=school.id,
                        class_id=cls.id,
                        section_id=sec.id,
                        admission_number=str(admission_counter),
                        roll_number=str(roll),
                        dob=dob,
                        guardian_name=f"{guardian_first} {guardian_last}",
                        guardian_relation=guardian_relation,
                        guardian_phone=guardian_phone_num,
                    )
                    session.add(student)
                    await session.flush()

                    # Link student to their class subjects
                    applicable_subjects = get_subjects_for_class(class_num, subjects_by_code)
                    for subj in applicable_subjects:
                        await session.execute(
                            student_subject.insert().values(
                                student_id=student.id,
                                subject_id=subj.id,
                            )
                        )

                    admission_counter += 1
                    total_students += 1

                # Flush every section to avoid memory issues
                await session.flush()

                sec_letter = sec.name.replace("Section ", "")
                print(f"    {class_name} {sec_letter}: {num_students} students")

        print(f"  Created {total_students} students total.")

        # ── 11. Update the admin user for this school ────────────────────
        admin_result = await session.execute(
            select(User).where(
                User.school_id == school.id,
                User.username == "akshara_school"
            )
        )
        admin_user = admin_result.scalars().first()
        if admin_user:
            admin_user.full_name = "Akshara Admin"
            admin_user.role = UserRole.ADMIN
            admin_user.is_active = True
            print(f"  Updated admin user: {admin_user.username}")

        # ── 12. Commit everything ────────────────────────────────────────
        print("\nCommitting all changes to database...")
        await session.commit()
        print("✅ Akshara School Kakinada fully populated!")
        print(f"\n📊 Summary:")
        print(f"   School: Akshara School Kakinada")
        print(f"   Classes: {len(classes_by_num)} (Nursery to Class 10)")
        print(f"   Sections: {len(sections_list)}")
        print(f"   Subjects: {len(subjects_by_code)}")
        print(f"   Teachers: {len(all_teachers)}")
        print(f"   Students: {total_students}")
        print(f"   Admin login: akshara_school / (existing password)")
        print(f"   Teacher login: teacher_eng_1 / teacher123 (example)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(populate())
