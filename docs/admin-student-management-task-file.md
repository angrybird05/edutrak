# Admin Student Management Task File

## Goal

Implement the complete administrator-controlled student onboarding and parent-student OTP flow in EduTrack so that:

1. Only admins can create students.
2. Admin captures guardian login phone and guardian details at student creation time.
3. Parent accounts are auto-created or reused from the guardian phone.
4. A joining code is generated for each student as a backup linking path.
5. Parents and students can both log in with the guardian phone using OTP verification.
6. When one guardian phone is linked to multiple students, the student login flow supports profile selection.
7. Admin gets a real Students management page matching the existing admin design language.
8. Parent and student dashboards use modular backend data instead of mocks.

## Implementation Summary

- Add `guardian_name`, `guardian_relation`, and `guardian_phone` to the student schema.
- Backfill legacy student phone data into `guardian_phone`, then rewrite legacy student `user.phone` values to internal placeholders.
- Keep `User.phone` globally unique and use `Student.guardian_phone` for shared student/parent login discovery.
- Extend auth OTP flow with requested role support and student profile selection.
- Add parent self-service link-by-code and linked-children endpoints under the modular identity router.
- Replace the placeholder admin Students page and wire parent/student portals to live modular APIs.

## Acceptance Criteria

- Admin can create a student with guardian details and receive join code data immediately.
- Creating multiple students with the same guardian phone reuses one parent account and links all matching children.
- Parent OTP login returns the parent account for the guardian phone.
- Student OTP login returns the student account for a single matching child or a profile selection payload for multiple matching children.
- Parent can manually link a child by join code without duplicate associations.
- Student and parent dashboards render live data from modular endpoints.
- Backend tests pass and frontend production build passes.
