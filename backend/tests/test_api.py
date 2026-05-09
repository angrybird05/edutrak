"""
API smoke tests aligned with the current modular router layout.
"""
import uuid

import pytest
from httpx import AsyncClient


def _unique_phone() -> str:
    return f"+91{uuid.uuid4().int % 10_000_000_000:010d}"


def _unique_admission(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


async def _register_admin_and_get_auth(client: AsyncClient) -> tuple[dict, str]:
    response = await client.post(
        "/api/v1/user/auth/register/admin",
        json={
            "full_name": "Teacher Admin",
            "username": f"admin_{uuid.uuid4().hex[:8]}",
            "password": "admin12345",
            "school_name": "Teacher School",
            "school_email": f"school_{uuid.uuid4().hex[:8]}@example.com",
            "village": "Village",
            "mandal": "Mandal",
            "district_city": "City",
            "pincode": "123456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    auth_headers = {"Authorization": f"Bearer {data['access_token']}"}

    profile_response = await client.get("/api/v1/identity/me", headers=auth_headers)
    assert profile_response.status_code == 200
    profile = profile_response.json()
    return profile, data["access_token"]


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Root health endpoint should be reachable."""
    response = await client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_platform_version_endpoint(client: AsyncClient):
    """Platform version endpoint should expose project metadata."""
    response = await client.get("/api/v1/platform/meta/version")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "EduTrack"
    assert data["api_version"] == "v1"


@pytest.mark.asyncio
async def test_login_otp_requires_body(client: AsyncClient):
    """Login OTP endpoint should reject empty requests."""
    response = await client.post("/api/v1/user/auth/login/otp")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_otp_invalid_phone(client: AsyncClient):
    """Login OTP should reject invalid phone format."""
    response = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": "abc", "requested_role": "parent"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_otp_requires_body(client: AsyncClient):
    """Verify OTP endpoint should reject empty requests."""
    response = await client.post("/api/v1/user/auth/verify/otp")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Refresh with invalid token should return 401."""
    response = await client.post("/api/v1/user/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """Responses should include security headers."""
    response = await client.get("/health")
    headers = response.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_protected_identity_endpoint_requires_auth(client: AsyncClient):
    """Protected endpoints should return 401/403 without token."""
    response = await client.get("/api/v1/identity/students")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_registration_succeeds(client: AsyncClient, database_ready: None):
    """Admin registration should create a school and return tokens."""
    response = await client.post(
        "/api/v1/user/auth/register/admin",
        json={
            "full_name": "Test Admin",
            "username": f"admin_{uuid.uuid4().hex[:8]}",
            "password": "admin12345",
            "school_name": "Test School",
            "school_email": "school@example.com",
            "village": "Village",
            "mandal": "Mandal",
            "district_city": "City",
            "pincode": "123456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert data["access_token"]
    assert data["refresh_token"]


@pytest.mark.asyncio
async def test_admin_can_log_in_with_trimmed_username_input(client: AsyncClient, database_ready: None):
    """Whitespace around admin usernames should not make password login fail."""
    raw_username = f"  admin_{uuid.uuid4().hex[:8]}  "
    password = "admin12345"

    response = await client.post(
        "/api/v1/user/auth/register/admin",
        json={
            "full_name": "Whitespace Admin",
            "username": raw_username,
            "password": password,
            "school_name": "Whitespace School",
            "school_email": "whitespace@example.com",
            "village": "Village",
            "mandal": "Mandal",
            "district_city": "City",
            "pincode": "123456",
        },
    )
    assert response.status_code == 200

    login_response = await client.post(
        "/api/v1/user/auth/login/password",
        json={
            "username": raw_username.strip(),
            "password": password,
        },
    )
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["role"] == "admin"
    assert payload["access_token"]
    assert payload["refresh_token"]


@pytest.mark.asyncio
async def test_password_login_accepts_legacy_bcrypt_hashes(client: AsyncClient, database_ready: None):
    """Legacy bcrypt password hashes should remain valid after the pbkdf2 migration."""
    import bcrypt
    from tests.conftest import TestSessionLocal
    from app.modules.auth.models import User, UserRole

    username = f"legacy_{uuid.uuid4().hex[:8]}"
    password = "legacypass123"

    async with TestSessionLocal() as session:
        legacy_user = User(
            username=username,
            password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            full_name="Legacy Admin",
            phone=f"admin_{username}",
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(legacy_user)
        await session.commit()

    login_response = await client.post(
        "/api/v1/user/auth/login/password",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_mock_rate_limit_fallback_does_not_break_registration(client: AsyncClient, database_ready: None):
    """Registration should work even when Redis falls back to MockRedis."""
    response = await client.post(
        "/api/v1/user/auth/register/admin",
        json={
            "full_name": "Fallback Admin",
            "username": f"fallback_{uuid.uuid4().hex[:8]}",
            "password": "admin12345",
            "school_name": "Fallback School",
            "school_email": "fallback@example.com",
            "village": "Village",
            "mandal": "Mandal",
            "district_city": "City",
            "pincode": "123456",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_manage_teacher_assignments_and_credentials(client: AsyncClient, database_ready: None):
    """Admin can create a teacher, update credentials, assign sections/subjects, and schedule a class."""
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    teacher_response = await client.post(
        "/api/v1/identity/teachers",
        headers=auth_headers,
        json={
            "full_name": "Jane Teacher",
            "username": f"teacher_{uuid.uuid4().hex[:8]}",
            "password": "teachpass123",
            "language_pref": "en",
            "is_active": True,
        },
    )
    assert teacher_response.status_code == 201
    teacher = teacher_response.json()

    credentials_response = await client.patch(
        f"/api/v1/identity/teachers/{teacher['id']}/credentials",
        headers=auth_headers,
        json={
            "username": f"teacher_updated_{uuid.uuid4().hex[:8]}",
            "password": "newteachpass123",
        },
    )
    assert credentials_response.status_code == 200
    updated_teacher = credentials_response.json()
    assert updated_teacher["username"].startswith("teacher_updated_")

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 8", "class_number": 8, "school_id": school_id},
    )
    assert class_response.status_code == 200
    class_id = class_response.json()["id"]

    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section A", "class_id": class_id},
    )
    assert section_response.status_code == 200
    section_id = section_response.json()["id"]

    subject_response = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "Mathematics", "code": "MATH", "school_id": school_id},
    )
    assert subject_response.status_code == 200
    subject_id = subject_response.json()["id"]

    assign_sections_response = await client.put(
        f"/api/v1/academic/teachers/{teacher['id']}/sections",
        headers=auth_headers,
        json={"section_ids": [section_id]},
    )
    assert assign_sections_response.status_code == 200

    assign_subjects_response = await client.put(
        f"/api/v1/academic/teachers/{teacher['id']}/subjects",
        headers=auth_headers,
        json={"subject_ids": [subject_id]},
    )
    assert assign_subjects_response.status_code == 200

    assignments_response = await client.get(
        f"/api/v1/academic/teachers/{teacher['id']}/assignments",
        headers=auth_headers,
    )
    assert assignments_response.status_code == 200
    assignments = assignments_response.json()
    assert section_id in assignments["section_ids"]
    assert subject_id in assignments["subject_ids"]

    timetable_response = await client.post(
        "/api/v1/academic/timetable",
        headers=auth_headers,
        json={
            "section_id": section_id,
            "subject_id": subject_id,
            "teacher_id": teacher["id"],
            "day_of_week": 1,
            "start_time": "09:00",
            "end_time": "10:00",
            "room": "Room 201",
        },
    )
    assert timetable_response.status_code == 201
    timetable_entry = timetable_response.json()
    assert timetable_entry["teacher_id"] == teacher["id"]


@pytest.mark.asyncio
async def test_teacher_timetable_conflict_is_rejected(client: AsyncClient, database_ready: None):
    """Teacher cannot be scheduled in overlapping slots across sections."""
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    teacher_response = await client.post(
        "/api/v1/identity/teachers",
        headers=auth_headers,
        json={
            "full_name": "Conflict Teacher",
            "username": f"conflict_{uuid.uuid4().hex[:8]}",
            "password": "teachpass123",
        },
    )
    assert teacher_response.status_code == 201
    teacher_id = teacher_response.json()["id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 9", "class_number": 9, "school_id": school_id},
    )
    class_id = class_response.json()["id"]

    section_a = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section A", "class_id": class_id},
    )
    section_b = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section B", "class_id": class_id},
    )
    section_a_id = section_a.json()["id"]
    section_b_id = section_b.json()["id"]

    subject_response = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "Science", "code": "SCI", "school_id": school_id},
    )
    subject_id = subject_response.json()["id"]

    await client.put(
        f"/api/v1/academic/teachers/{teacher_id}/sections",
        headers=auth_headers,
        json={"section_ids": [section_a_id, section_b_id]},
    )
    await client.put(
        f"/api/v1/academic/teachers/{teacher_id}/subjects",
        headers=auth_headers,
        json={"subject_ids": [subject_id]},
    )

    first_entry = await client.post(
        "/api/v1/academic/timetable",
        headers=auth_headers,
        json={
            "section_id": section_a_id,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "day_of_week": 2,
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    assert first_entry.status_code == 201

    conflict_entry = await client.post(
        "/api/v1/academic/timetable",
        headers=auth_headers,
        json={
            "section_id": section_b_id,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "day_of_week": 2,
            "start_time": "10:30",
            "end_time": "11:30",
        },
    )
    assert conflict_entry.status_code == 400
    assert "Teacher already has another class" in conflict_entry.json()["message"]


@pytest.mark.asyncio
async def test_admin_can_manage_academic_structure(client: AsyncClient, database_ready: None):
    """Admin can create classes, sections, subjects, and assign subjects to a section."""
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 7", "class_number": 7, "school_id": school_id},
    )
    assert class_response.status_code == 200
    class_id = class_response.json()["id"]

    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section Blue", "class_id": class_id},
    )
    assert section_response.status_code == 200
    section_id = section_response.json()["id"]

    english_response = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "English", "code": "ENG", "school_id": school_id},
    )
    science_response = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "Science", "code": "SCI", "school_id": school_id},
    )
    assert english_response.status_code == 200
    assert science_response.status_code == 200

    section_subjects_response = await client.put(
        f"/api/v1/academic/sections/{section_id}/subjects",
        headers=auth_headers,
        json={"subject_ids": [english_response.json()["id"], science_response.json()["id"]]},
    )
    assert section_subjects_response.status_code == 200

    structure_response = await client.get(
        f"/api/v1/academic/structure/{school_id}",
        headers=auth_headers,
    )
    assert structure_response.status_code == 200
    structure = structure_response.json()

    created_class = next(item for item in structure["classes"] if item["id"] == class_id)
    created_section = next(item for item in created_class["sections"] if item["id"] == section_id)
    assert {subject["name"] for subject in created_section["subjects"]} == {"English", "Science"}


@pytest.mark.asyncio
async def test_academic_duplicates_and_updates_are_enforced(client: AsyncClient, database_ready: None):
    """Academic CRUD should prevent duplicates and support updates/deletes."""
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 5", "class_number": 5, "school_id": school_id},
    )
    assert class_response.status_code == 200
    class_id = class_response.json()["id"]

    duplicate_class = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 5", "class_number": 6, "school_id": school_id},
    )
    assert duplicate_class.status_code == 400

    updated_class = await client.patch(
        f"/api/v1/academic/classes/{class_id}",
        headers=auth_headers,
        json={"name": "Class 5 Prime", "class_number": 15},
    )
    assert updated_class.status_code == 200
    assert updated_class.json()["name"] == "Class 5 Prime"

    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section A", "class_id": class_id},
    )
    assert section_response.status_code == 200
    section_id = section_response.json()["id"]

    duplicate_section = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section A", "class_id": class_id},
    )
    assert duplicate_section.status_code == 400

    updated_section = await client.patch(
        f"/api/v1/academic/sections/{section_id}",
        headers=auth_headers,
        json={"name": "Section Alpha"},
    )
    assert updated_section.status_code == 200
    assert updated_section.json()["name"] == "Section Alpha"

    subject_response = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "Math", "code": "MTH", "school_id": school_id},
    )
    assert subject_response.status_code == 200
    subject_id = subject_response.json()["id"]

    duplicate_subject = await client.post(
        "/api/v1/academic/subjects",
        headers=auth_headers,
        json={"name": "Math", "code": "MTH2", "school_id": school_id},
    )
    assert duplicate_subject.status_code == 400

    updated_subject = await client.patch(
        f"/api/v1/academic/subjects/{subject_id}",
        headers=auth_headers,
        json={"name": "Mathematics", "code": "MATH"},
    )
    assert updated_subject.status_code == 200
    assert updated_subject.json()["name"] == "Mathematics"

    delete_subject = await client.delete(f"/api/v1/academic/subjects/{subject_id}", headers=auth_headers)
    assert delete_subject.status_code == 204

    delete_section = await client.delete(f"/api/v1/academic/sections/{section_id}", headers=auth_headers)
    assert delete_section.status_code == 204

    delete_class = await client.delete(f"/api/v1/academic/classes/{class_id}", headers=auth_headers)
    assert delete_class.status_code == 204


@pytest.mark.asyncio
async def test_admin_can_create_students_and_reuse_parent_accounts(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    """Admin student creation should capture guardian data, reuse the parent account, and expose linked children."""
    from app.modules.auth.service import AuthService
    from app.core.sms import sms_client

    monkeypatch.setattr(AuthService, "generate_otp", lambda self, length=6: "123456")
    async def fake_send_otp(phone: str, otp: str) -> bool:
        return True
    monkeypatch.setattr(sms_client, "send_otp", fake_send_otp)
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 6", "class_number": 6, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section Blue", "class_id": class_id},
    )
    section_id = section_response.json()["id"]

    guardian_phone = _unique_phone()
    first_admission = _unique_admission("ADM")
    second_admission = _unique_admission("ADM")
    first_student = await client.post(
        "/api/v1/identity/students",
        headers=auth_headers,
        json={
            "full_name": "Aarav Kumar",
            "admission_number": first_admission,
            "roll_number": "1",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Sanjay Kumar",
            "guardian_relation": "Father",
            "guardian_phone": guardian_phone,
        },
    )
    assert first_student.status_code == 200
    first_payload = first_student.json()
    assert first_payload["guardian_phone"] == guardian_phone
    assert first_payload["parent_account_created"] is True
    assert first_payload["parent_joining_code"]

    second_student = await client.post(
        "/api/v1/identity/students",
        headers=auth_headers,
        json={
            "full_name": "Meera Kumar",
            "admission_number": second_admission,
            "roll_number": "2",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Sanjay Kumar",
            "guardian_relation": "Father",
            "guardian_phone": guardian_phone,
        },
    )
    assert second_student.status_code == 200
    second_payload = second_student.json()
    assert second_payload["parent_account_created"] is False

    otp_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone, "requested_role": "parent"},
    )
    assert otp_request.status_code == 200

    parent_login = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone, "requested_role": "parent", "otp_code": "123456"},
    )
    assert parent_login.status_code == 200
    parent_payload = parent_login.json()
    assert parent_payload["role"] == "parent"

    parent_headers = {"Authorization": f"Bearer {parent_payload['access_token']}"}
    children_response = await client.get("/api/v1/identity/parents/me/children", headers=parent_headers)
    assert children_response.status_code == 200
    children = children_response.json()
    assert len(children) == 2
    assert {child["admission_number"] for child in children} == {first_admission, second_admission}


@pytest.mark.asyncio
async def test_student_otp_selection_flow_and_parent_link_by_code(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    """Shared guardian phone should require student profile selection and allow idempotent parent linking by code."""
    from app.modules.auth.service import AuthService
    from app.core.sms import sms_client

    monkeypatch.setattr(AuthService, "generate_otp", lambda self, length=6: "123456")
    async def fake_send_otp(phone: str, otp: str) -> bool:
        return True
    monkeypatch.setattr(sms_client, "send_otp", fake_send_otp)
    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 4", "class_number": 4, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section Red", "class_id": class_id},
    )
    section_id = section_response.json()["id"]

    guardian_phone = _unique_phone()
    created_students = []
    for index, name in enumerate(["Riya", "Kabir"], start=1):
        response = await client.post(
            "/api/v1/identity/students",
            headers=auth_headers,
            json={
                "full_name": name,
                "admission_number": _unique_admission(f"ADM{index}"),
                "roll_number": str(index),
                "class_id": class_id,
                "section_id": section_id,
                "guardian_name": "Priya Sharma",
                "guardian_relation": "Mother",
                "guardian_phone": guardian_phone,
            },
        )
        assert response.status_code == 200
        created_students.append(response.json())

    otp_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone, "requested_role": "student"},
    )
    assert otp_request.status_code == 200

    select_response = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone, "requested_role": "student", "otp_code": "123456"},
    )
    assert select_response.status_code == 200
    selection_payload = select_response.json()
    assert selection_payload["selection_required"] is True
    assert len(selection_payload["profiles"]) == 2

    profile_login = await client.post(
        "/api/v1/user/auth/select-profile",
        json={
          "selection_token": selection_payload["selection_token"],
          "student_id": created_students[0]["id"],
        },
    )
    assert profile_login.status_code == 200
    assert profile_login.json()["role"] == "student"

    parent_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone, "requested_role": "parent"},
    )
    assert parent_request.status_code == 200
    parent_verify = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone, "requested_role": "parent", "otp_code": "123456"},
    )
    assert parent_verify.status_code == 200
    parent_headers = {"Authorization": f"Bearer {parent_verify.json()['access_token']}"}

    link_response = await client.post(
        "/api/v1/identity/parents/link-by-code",
        headers=parent_headers,
        json={"joining_code": created_students[0]["parent_joining_code"]},
    )
    assert link_response.status_code == 200
    assert link_response.json()["admission_number"] == created_students[0]["admission_number"]

    children_response = await client.get("/api/v1/identity/parents/me/children", headers=parent_headers)
    assert children_response.status_code == 200
    assert len(children_response.json()) == 2


@pytest.mark.asyncio
async def test_legacy_student_phone_owner_is_converted_for_shared_guardian_reuse(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    """Legacy student rows that still own the guardian phone should be auto-repaired and allow more children."""
    from tests.conftest import TestSessionLocal
    from app.core.sms import sms_client
    from app.modules.auth.models import User, UserRole
    from app.modules.auth.service import AuthService
    from app.modules.identity.models import Student

    monkeypatch.setattr(AuthService, "generate_otp", lambda self, length=6: "123456")

    async def fake_send_otp(phone: str, otp: str) -> bool:
        return True

    monkeypatch.setattr(sms_client, "send_otp", fake_send_otp)

    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 3", "class_number": 3, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section Green", "class_id": class_id},
    )
    section_id = section_response.json()["id"]

    guardian_phone = _unique_phone()
    legacy_admission = _unique_admission("LEG")
    new_admission = _unique_admission("ADM")

    async with TestSessionLocal() as session:
        legacy_user = User(
            phone=guardian_phone,
            full_name="Legacy Child",
            role=UserRole.STUDENT,
            school_id=uuid.UUID(school_id),
            is_active=True,
        )
        session.add(legacy_user)
        await session.flush()

        legacy_student = Student(
            user_id=legacy_user.id,
            school_id=uuid.UUID(school_id),
            class_id=uuid.UUID(class_id),
            section_id=uuid.UUID(section_id),
            admission_number=legacy_admission,
            roll_number="1",
        )
        session.add(legacy_student)
        await session.commit()

    create_response = await client.post(
        "/api/v1/identity/students",
        headers=auth_headers,
        json={
            "full_name": "New Child",
            "admission_number": new_admission,
            "roll_number": "2",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Suma Parent",
            "guardian_relation": "Mother",
            "guardian_phone": guardian_phone,
        },
    )
    assert create_response.status_code == 200

    parent_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone, "requested_role": "parent"},
    )
    assert parent_request.status_code == 200

    parent_verify = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone, "requested_role": "parent", "otp_code": "123456"},
    )
    assert parent_verify.status_code == 200
    parent_headers = {"Authorization": f"Bearer {parent_verify.json()['access_token']}"}

    children_response = await client.get("/api/v1/identity/parents/me/children", headers=parent_headers)
    assert children_response.status_code == 200
    assert {child["admission_number"] for child in children_response.json()} == {legacy_admission, new_admission}


@pytest.mark.asyncio
async def test_teacher_phone_can_also_be_used_as_guardian_phone(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    """A teacher phone should still be usable as the guardian/parent phone for student creation and parent OTP login."""
    from app.core.sms import sms_client
    from app.modules.auth.service import AuthService

    monkeypatch.setattr(AuthService, "generate_otp", lambda self, length=6: "123456")

    async def fake_send_otp(phone: str, otp: str) -> bool:
        return True

    monkeypatch.setattr(sms_client, "send_otp", fake_send_otp)

    profile, access_token = await _register_admin_and_get_auth(client)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    school_id = profile["school_id"]

    teacher_phone = _unique_phone()
    teacher_response = await client.post(
        "/api/v1/identity/teachers",
        headers=auth_headers,
        json={
            "full_name": "Shared Phone Teacher",
            "username": f"teacher_{uuid.uuid4().hex[:8]}",
            "password": "teachpass123",
            "phone": teacher_phone,
        },
    )
    assert teacher_response.status_code == 201

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=auth_headers,
        json={"name": "Class 2", "class_number": 2, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=auth_headers,
        json={"name": "Section Silver", "class_id": class_id},
    )
    section_id = section_response.json()["id"]

    student_response = await client.post(
        "/api/v1/identity/students",
        headers=auth_headers,
        json={
            "full_name": "Guardian Linked Child",
            "admission_number": _unique_admission("SHR"),
            "roll_number": "1",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Shared Phone Teacher",
            "guardian_relation": "Mother",
            "guardian_phone": teacher_phone,
        },
    )
    assert student_response.status_code == 200
    assert student_response.json()["guardian_phone"] == teacher_phone

    teacher_otp_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": teacher_phone, "requested_role": "teacher"},
    )
    assert teacher_otp_request.status_code == 200

    parent_otp_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": teacher_phone, "requested_role": "parent"},
    )
    assert parent_otp_request.status_code == 200
