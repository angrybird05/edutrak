"""
Assessment Module — Exams, Marks, Attendance, Homework, Bulk operations.
"""
from app.modules.assessment.endpoints import router  # noqa
from app.modules.assessment.models import Exam, Mark, Attendance, Homework, LearningTask  # noqa
