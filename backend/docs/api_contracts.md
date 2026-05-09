# EduTrack Modular Monolith — API Contracts & Endpoints

This document outlines the API topology after the modular restructure.
The API remains fully backwards compatible. The Gateway (Nginx) and GraphQL layers are new additions.

## API Gateway (Nginx)

The frontend should now point to `http://localhost:80` (or the respective production domain).
Do not hit port `8000` directly.

### Rate Limiting Tiers
| Route Prefix | Category | Rate Limit |
|---|---|---|
| `/api/v1/user/auth/` | Authentication | 5 req/sec (burst 3) |
| `/api/v1/insights/` | Heavy AI Processing | 10 req/sec (burst 5) |
| `/api/v1/reports/` | Heavy PDF Generation | 10 req/sec (burst 5) |
| `/api/v1/bulk/` | Heavy Data Uploads | 10 req/sec (burst 3) |
| `/graphql` | Flexible Querying | 20 req/sec (burst 10) |
| All other `/api/v1/` | Standard Data Access | 30 req/sec (burst 20) |

---

## REST API Modules

All endpoints are prefixed with `/api/v1` and wrapped in the Standard Response Envelope unless streaming.

### Standard Response Envelope
```json
{
  "success": true,
  "data": { ... payload ... },
  "error": null
}
```

### Module Route Prefixes

**Auth Module (`/api/v1/user/auth`)**
- `POST /login/otp`
- `POST /verify/otp`
- `POST /login/password`
- `POST /refresh`
- `POST /logout`

**Identity Module (`/api/v1/identity`)**
- `GET /me`
- `PATCH /me`
- `GET /students` (paginated)
- `POST /students`
- `GET /students/{id}`
- `GET /students/{id}/profile-summary`

**Academic Module (`/api/v1/academic`)**
- `GET/POST /chains`
- `GET/POST /schools`
- `GET/POST /classes`
- `GET/POST /sections`
- `GET/POST /subjects`

**Assessment Module (`/api/v1/assessment`)**
- `GET/POST /exams`
- `GET/POST /marks`
- `GET/POST /attendance`
- `POST /bulk/marks`
- `POST /bulk/attendance`

**Analytics Module (`/api/v1/analytics`)**
- `GET /insights/{student_id}`
- `POST /insights/{student_id}/generate`
- `POST /study-plan/{student_id}`
- `POST /risk-prediction/{student_id}`
- `POST /ai-coach/{student_id}/chat`

**Notification Module (`/api/v1/notifications`)**
- `GET /` (paginated list)
- `PATCH /{id}/read`
- `PATCH /read-all`

**Platform Module (`/api/v1/platform`)**
- `GET/PATCH /settings`
- `GET /health` (Gateway maps `/health` directly to this)
- `GET /meta/version`

---

## GraphQL API (New)

**Endpoint**: `POST /graphql`
**Playground**: `GET /graphql` (Development mode only)

GraphQL sits alongside REST. It is initialized, but currently acts as a foundation. Future frontend iterations can migrate complex dashboard queries (like deeply nested student -> class -> marks -> insights) to GraphQL to avoid over-fetching.

### Example Query
```graphql
query GetStudentDashboard($id: UUID!) {
  student(id: $id) {
    id
    admissionNumber
    # Relationships to be expanded in Phase 5...
  }
}
```
