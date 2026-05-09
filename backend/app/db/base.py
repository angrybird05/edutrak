# Import all models here for Alembic and Metadata discovery
# We use the new refactored modules as the source of truth

from app.models.base import Base # noqa

# Auth Module
from app.modules.auth.models import User, UserRole, OTPSession # noqa

# Academic Module
from app.modules.academic.models import ( # noqa
    Chain, School, Class, Section, Subject, student_subject, Timetable, teacher_section, teacher_subject, section_subject
)

# Identity Module
from app.modules.identity.models import Student, parent_student # noqa

# Assessment Module
from app.modules.assessment.models import Exam, Mark, Attendance, Homework, LearningTask # noqa

# Analytics Module
from app.modules.analytics.models import AIInsight, ReportCard, InstitutionalInsight, AIChatSession, AIChatMessage # noqa
from app.modules.analytics.insights_v2.models import AIInsightV2  # noqa

# Notification Module
from app.modules.notification.models import ( # noqa
    Notification, NotificationEvent, UserNotification, DeviceToken
)

# Platform Module
from app.modules.platform.models import ( # noqa
    AuditLog, APIRequestLog, IdempotencyKey, OutboxJob, UserSettings
)
