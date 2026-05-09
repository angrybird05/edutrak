# Admin Teacher Management Task File

## Goal

Implement a complete administrator-controlled teacher management workflow in EduTrack so that:

1. Admin can create, list, edit, and manage teachers.
2. Admin can create and change teacher username and password.
3. Admin can assign teachers to classes, sections, and subjects.
4. Admin can create and update teacher timetable/scheduling by class section, subject, day, and hour.
5. Frontend admin experience matches the existing EduTrack visual theme and navigation system.

## Current Codebase Audit

### Existing Foundations Already Present

- `User` already supports role `teacher`.
- `teacher_section` association table already exists in:
  - `backend/app/modules/academic/models.py`
- `Timetable` already exists and already links:
  - `section_id`
  - `subject_id`
  - `teacher_id`
  - `day_of_week`
  - `start_time`
  - `end_time`
  - `room`
- Admin-only dependency helpers already exist:
  - `requires_admin`
  - `requires_roles`
- Frontend already has admin shell/navigation and teacher role routing.

### Missing or Incomplete Pieces

- No dedicated admin teacher CRUD page in frontend.
- No admin teacher CRUD endpoints in current modular backend.
- No admin teacher credential reset/update endpoints.
- No teacher-to-subject assignment model beyond timetable rows.
- No clean admin API to assign teacher -> section(s) and teacher -> subject(s).
- No admin UI for timetable creation/editing.
- No schema to represent teacher subject capability independently from timetable.

## Schema Gap Analysis

### Keep Existing Tables

- `user`
- `class`
- `section`
- `subject`
- `teacher_section`
- `timetable`

### New Schema Required

Add a dedicated teacher-subject assignment table so admin can declare what a teacher is allowed to teach independently of timetable rows.

Recommended table:

- `teacher_subject`
  - `teacher_id` -> `user.id`
  - `subject_id` -> `subject.id`
  - composite primary key or unique constraint

### Why This Is Needed

Without `teacher_subject`, subject eligibility exists only indirectly inside `timetable`.
That makes it hard to:

- list what a teacher is allowed to teach
- validate timetable edits
- show teacher capabilities in admin UI
- support future teacher dashboards and scheduling tools

### Existing Schema That Can Be Reused

- `teacher_section` can store section assignment.
- `timetable` can store actual scheduled class periods.

## Implementation Parts

## Part 1: Backend Data Model and Migration

### Tasks

- Add `teacher_subject` association table to:
  - `backend/app/modules/academic/models.py`
- Export/import it in DB model registries if needed:
  - `backend/app/db/base.py`
  - `backend/app/shared/db/base.py`
- Create Alembic migration for:
  - `teacher_subject`
  - indexes/constraints as needed

### Acceptance Criteria

- Migration applies successfully on PostgreSQL.
- Schema supports:
  - teacher <-> section assignment
  - teacher <-> subject assignment
  - timetable rows referencing teacher, section, and subject

## Part 2: Backend Teacher Admin APIs

### New API Capability Set

Add admin-managed teacher endpoints under modular routers, preferably in `identity` plus `academic`.

### Teacher CRUD

Implement endpoints for:

- `GET /api/v1/identity/teachers`
- `GET /api/v1/identity/teachers/{teacher_id}`
- `POST /api/v1/identity/teachers`
- `PATCH /api/v1/identity/teachers/{teacher_id}`
- `PATCH /api/v1/identity/teachers/{teacher_id}/credentials`

### Assignment APIs

Implement endpoints for:

- `GET /api/v1/academic/teacher-assignments/{teacher_id}`
- `PUT /api/v1/academic/teachers/{teacher_id}/sections`
- `PUT /api/v1/academic/teachers/{teacher_id}/subjects`

### Timetable APIs

Implement admin timetable management endpoints for:

- `GET /api/v1/academic/timetable/{section_id}`
- `POST /api/v1/academic/timetable`
- `PATCH /api/v1/academic/timetable/{entry_id}`
- `DELETE /api/v1/academic/timetable/{entry_id}`

### Validation Rules

- Only admin can create/edit teachers.
- Teacher usernames must be unique.
- Teacher password update must hash password before save.
- Teacher must belong to same school as admin.
- Teacher-section assignment must stay within admin school.
- Teacher-subject assignment must stay within admin school.
- Timetable create/update must validate:
  - teacher is assigned to that section
  - teacher is assigned to that subject
  - subject belongs to the same school
  - no teacher time collision
  - no section time collision

## Part 3: Backend Schemas and Services

### Tasks

- Add teacher admin request/response schemas to:
  - `backend/app/modules/identity/schemas.py`
  - `backend/app/modules/academic/schemas.py`
- Add service logic for:
  - create teacher
  - update teacher profile
  - update teacher credentials
  - sync teacher section assignments
  - sync teacher subject assignments
  - create/update/delete timetable rows safely

### Suggested Service Split

- identity service:
  - teacher account CRUD
  - credential management
- academic service:
  - section assignment
  - subject assignment
  - timetable management

## Part 4: Frontend Admin Teachers Page

### New Admin Page

Create a new admin page:

- `web_frontend/src/pages/Teachers.tsx`

### UI Scope

The page should match the existing glassmorphism EduTrack admin style and include:

- teacher list/table/cards
- create teacher form/modal/drawer
- edit teacher profile form
- change username/password form
- assign sections UI
- assign subjects UI
- timetable scheduler UI

### Minimum Page Sections

- Teacher overview header
- Search/filter teacher list
- Add teacher action
- Teacher details panel
- Credentials panel
- Section assignment panel
- Subject assignment panel
- Weekly timetable panel

## Part 5: Frontend Navigation and API Integration

### Tasks

- Add admin route to:
  - `web_frontend/src/App.tsx`
- Add sidebar nav item to:
  - `web_frontend/src/components/sidebars/AdminSidebar.tsx`
- Add frontend API calls for:
  - teacher list/create/update
  - teacher credential updates
  - teacher section assignment
  - teacher subject assignment
  - timetable CRUD

### Recommended New Client Layer

Add a dedicated client helper file:

- `web_frontend/src/lib/teachers.ts`

or extend current API usage patterns carefully.

## Part 6: Admin Workflow Rules to Implement

### Teacher Creation

Admin must be able to create:

- full name
- username
- password

Optional extra fields if present in model:

- phone
- language preference
- active status

### Credential Management

Admin must be able to:

- change teacher username
- reset teacher password
- disable/enable teacher if needed

### Assignment Management

Admin must be able to:

- assign teacher to one or more sections
- assign teacher to one or more subjects
- create timetable entries for the teacher in section-specific hours
- edit timetable later at any time

## Part 7: Verification and Testing

### Backend Tests

Add tests for:

- teacher creation success
- duplicate username rejection
- teacher credential update success
- teacher section assignment success
- teacher subject assignment success
- timetable create success
- teacher timetable conflict rejection
- section timetable conflict rejection
- school boundary authorization rejection

### Frontend Verification

Verify manually or with tests:

- admin can open teachers page
- admin can create teacher
- admin can edit teacher username/password
- admin can assign teacher sections
- admin can assign teacher subjects
- admin can create timetable entries
- updated timetable reflects immediately

## Part 8: Recommended Execution Order

1. Add schema and migration for `teacher_subject`
2. Add backend schemas and service helpers
3. Add backend teacher CRUD endpoints
4. Add backend assignment and timetable endpoints
5. Add backend tests
6. Add frontend teachers page
7. Add sidebar and route wiring
8. Connect frontend to live APIs
9. Run end-to-end admin verification

## File Targets

### Backend

- `backend/app/modules/academic/models.py`
- `backend/app/modules/academic/schemas.py`
- `backend/app/modules/academic/endpoints.py`
- `backend/app/modules/identity/schemas.py`
- `backend/app/modules/identity/endpoints.py`
- `backend/app/modules/identity/service.py`
- `backend/app/db/base.py`
- `backend/app/shared/db/base.py`
- `backend/migrations/versions/<new_migration>.py`
- `backend/tests/test_api.py`
- `backend/tests/conftest.py`

### Frontend

- `web_frontend/src/App.tsx`
- `web_frontend/src/components/sidebars/AdminSidebar.tsx`
- `web_frontend/src/pages/Teachers.tsx`
- `web_frontend/src/lib/api.ts`
- optionally `web_frontend/src/lib/teachers.ts`

## Non-Negotiable Constraints

- Keep admin-only control over teacher creation and scheduling.
- Do not bypass school scoping.
- Do not rely on timetable alone for subject eligibility.
- Do not ship timetable APIs without collision validation.
- Preserve current design language in the new page.

## Definition of Done

- Admin can create teacher accounts from UI.
- Admin can update teacher username and password.
- Admin can assign sections and subjects to teachers.
- Admin can create and edit teacher timetable rows by section/hour.
- Required DB schema exists and migration is applied.
- Backend tests pass.
- Frontend build passes.
- Manual admin registration/login/teacher management flow is verified.
