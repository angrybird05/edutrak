"""
EduTrack Domain Modules Package.

Each module encapsulates a bounded context:
- auth: Authentication, OTP, JWT lifecycle
- identity: User profiles, students, parent-student linking
- academic: Schools, classes, sections, subjects, timetables
- assessment: Exams, marks, attendance, homework, bulk ops
- analytics: AI insights, reports, dashboards, AI coach
- notification: Events, user notifications, device tokens, SMS
- platform: Audit logs, API logging, idempotency, settings

Module Communication Rules:
1. Modules communicate via the event bus (app.core.event_bus), not direct imports
2. Modules MAY import each other's schemas for type safety
3. Modules MAY import each other's models for SQLAlchemy joins (shared DB)
4. Modules MUST NOT import each other's service or CRUD layers directly
"""
