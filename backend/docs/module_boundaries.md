# EduTrack Modular Monolith Boundaries

This document defines the architectural boundaries, ownership, and communication rules
for the EduTrack Modular Monolith, introduced in Phase 2 of the restructuring.

## Core Principles

1. **High Cohesion**: Code that changes together stays together inside a module.
2. **Low Coupling**: Modules do not depend on the internal implementation details of other modules.
3. **Event-Driven Integration**: Cross-module business logic is triggered asynchronously via the `event_bus`.
4. **Shared Database, Isolated Namespaces**: While sharing a single PostgreSQL instance, models are namespaced to their owning module.

---

## The 7 Domain Modules

### 1. Auth (`app.modules.auth`)
- **Responsibility**: Authentication, OTP lifecycle, JWT minting and revocation.
- **Models Owned**: `User` (identity core), `OTPSession`.
- **Publishes**: `auth.login_success`, `auth.login_failed`.
- **Subscribes to**: None.

### 2. Identity (`app.modules.identity`)
- **Responsibility**: User profiles, student records, parent-student linking, and join codes.
- **Models Owned**: `Student`, `parent_student` (association table).
- **Publishes**: `identity.student_created`, `identity.parent_linked`.
- **Subscribes to**: None.

### 3. Academic (`app.modules.academic`)
- **Responsibility**: School hierarchy, classes, sections, subjects, timetables.
- **Models Owned**: `Chain`, `School`, `Class`, `Section`, `Subject`, `Timetable`.
- **Publishes**: `academic.school_created`.
- **Subscribes to**: None.

### 4. Assessment (`app.modules.assessment`)
- **Responsibility**: Exams, marks recording, daily attendance, homework distribution, bulk CSV uploads.
- **Models Owned**: `Exam`, `Mark`, `Attendance`, `Homework`, `LearningTask`.
- **Publishes**: `assessment.marks_recorded`, `assessment.attendance_recorded`.
- **Subscribes to**: None.

### 5. Analytics (`app.modules.analytics`)
- **Responsibility**: AI coach, automated insights, study plans, terminal report cards, dashboards.
- **Models Owned**: `AIInsight`, `ReportCard`, `AIChatSession`, `AIChatMessage`.
- **Publishes**: `analytics.insight_generated`.
- **Subscribes to**: 
  - `assessment.marks_recorded` → Triggers AI insight regeneration.
  - `assessment.attendance_recorded` → Triggers AI insight regeneration.

### 6. Notification (`app.modules.notification`)
- **Responsibility**: In-app notifications, SMS delivery, push notification tokens.
- **Models Owned**: `Notification`, `NotificationEvent`, `UserNotification`, `DeviceToken`.
- **Publishes**: None.
- **Subscribes to**: (Future) All core domain events to route to users.

### 7. Platform (`app.modules.platform`)
- **Responsibility**: Infrastructure features: audit logging, API request tracing, idempotency, user settings.
- **Models Owned**: `AuditLog`, `APIRequestLog`, `IdempotencyKey`, `OutboxJob`, `UserSettings`.
- **Publishes**: None.
- **Subscribes to**: 
  - `auth.*` and `identity.*` → Creates `AuditLog` entries.

---

## Inter-Module Communication Rules

**Rule 1: Direct Service Calls are FORBIDDEN between modules.**
- Example: `assessment_service.py` CANNOT import `ai_insight_service.py`.
- *Why?* Prevents tight coupling. If Analytics goes down, Assessment should still record marks.

**Rule 2: Use the Event Bus for cross-domain side effects.**
- Example: When `Assessment` records marks, it calls `await event_bus.emit("assessment.marks_recorded", payload)`.
- `Analytics` registers `@event_bus.on("assessment.marks_recorded")` and reacts asynchronously.

**Rule 3: Schema sharing is ALLOWED.**
- Modules may import Pydantic models from `app.modules.X.schemas` to type-hint shared payloads.

**Rule 4: Model sharing is ALLOWED (for now).**
- Modules may import SQLAlchemy models from other modules to build `relationship()` links.
- Example: `Mark` (`assessment`) has a Foreign Key to `Student` (`identity`).
- *Note*: If we ever split into true microservices, these foreign keys will become loose string IDs (`student_id: str`).
