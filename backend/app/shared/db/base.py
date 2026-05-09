"""
Model registry — imports all models so Alembic can detect them.

This replaces the old app/db/base.py. Every module's models.py is imported
here so that SQLAlchemy's metadata contains all tables for migration generation.
"""
from app.models.base import Base  # noqa — the declarative base

# Auth module
from app.modules.auth.models import User, OTPSession  # noqa

# Identity module
from app.modules.identity.models import Student, parent_student  # noqa

# Academic module
from app.modules.academic.models import (  # noqa
    Chain, School, Class, Section, Subject, Timetable, teacher_section, teacher_subject, section_subject, student_subject,
)

# Assessment module
from app.modules.assessment.models import (  # noqa
    Exam, Mark, Attendance, Homework, LearningTask,
)

# Analytics module
from app.modules.analytics.models import (  # noqa
    AIInsight, ReportCard, InstitutionalInsight, AIChatSession, AIChatMessage,
)
from app.modules.analytics.insights_v2.models import AIInsightV2  # noqa

# Notification module
from app.modules.notification.models import (  # noqa
    Notification, NotificationEvent, UserNotification, DeviceToken,
)

# Platform module
from app.modules.platform.models import (  # noqa
    AuditLog, APIRequestLog, IdempotencyKey, OutboxJob, UserSettings,
)
