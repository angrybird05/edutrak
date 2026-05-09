import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.core.event_bus import event_bus
from app.modules.analytics.insights_v2.ai.service import AIService
from app.modules.analytics.insights_v2.models import AIInsightV2
from app.modules.analytics.insights_v2.schemas import StructuredPerformanceData, SubjectSnapshot
from app.modules.analytics.insights_v2.services.eligibility import AIEligibilityPolicy
from app.modules.analytics.insights_v2.services.rule_engine import RuleEngine
from tests.conftest import TestSessionLocal, test_engine


def _unique_phone() -> str:
    return f"+91{uuid.uuid4().int % 10_000_000_000:010d}"


def _unique_admission(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


async def _register_admin_and_get_auth(client: AsyncClient) -> tuple[dict, str]:
    response = await client.post(
        "/api/v1/user/auth/register/admin",
        json={
            "full_name": "Insights Admin",
            "username": f"insights_admin_{uuid.uuid4().hex[:8]}",
            "password": "admin12345",
            "school_name": f"Insights School {uuid.uuid4().hex[:6]}",
            "school_email": f"insights_{uuid.uuid4().hex[:8]}@example.com",
            "village": "Village",
            "mandal": "Mandal",
            "district_city": "City",
            "pincode": "123456",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    auth_headers = {"Authorization": f"Bearer {payload['access_token']}"}

    profile_response = await client.get("/api/v1/identity/me", headers=auth_headers)
    assert profile_response.status_code == 200
    return profile_response.json(), payload["access_token"]


def _enable_mock_otp(monkeypatch) -> None:
    from app.core.sms import sms_client
    from app.modules.auth.service import AuthService

    monkeypatch.setattr(AuthService, "generate_otp", lambda self, length=6: "123456")

    async def _fake_send_otp(phone: str, otp: str) -> bool:
        return True

    monkeypatch.setattr(sms_client, "send_otp", _fake_send_otp)


@pytest.mark.asyncio
async def test_insight_endpoints_require_auth(client: AsyncClient):
    student_id = uuid.uuid4()
    exam_id = uuid.uuid4()

    insight_response = await client.get(f"/api/v1/insights/{student_id}/{exam_id}")
    status_response = await client.get(f"/api/v1/insights/status/{student_id}/{exam_id}")
    generate_response = await client.post("/api/v1/insights/generate", json={"exam_id": str(exam_id)})

    assert insight_response.status_code in (401, 403)
    assert status_response.status_code in (401, 403)
    assert generate_response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_parent_can_only_access_linked_child_insights(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    _enable_mock_otp(monkeypatch)
    async with test_engine.begin() as conn:
        await conn.run_sync(AIInsightV2.__table__.create, checkfirst=True)

    profile, token = await _register_admin_and_get_auth(client)
    admin_headers = {"Authorization": f"Bearer {token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=admin_headers,
        json={"name": "Class 7", "class_number": 7, "school_id": school_id},
    )
    assert class_response.status_code == 200
    class_id = class_response.json()["id"]

    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=admin_headers,
        json={"name": "Section Insight", "class_id": class_id},
    )
    assert section_response.status_code == 200
    section_id = section_response.json()["id"]

    exam_response = await client.post(
        "/api/v1/assessment/exams",
        headers=admin_headers,
        params={"section_id": section_id, "name": "Term Insight 1"},
    )
    assert exam_response.status_code == 200
    exam_id = uuid.UUID(exam_response.json()["id"])

    guardian_phone_1 = _unique_phone()
    guardian_phone_2 = _unique_phone()

    student_1_response = await client.post(
        "/api/v1/identity/students",
        headers=admin_headers,
        json={
            "full_name": "Student One",
            "admission_number": _unique_admission("ADM"),
            "roll_number": "1",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Guardian One",
            "guardian_relation": "Parent",
            "guardian_phone": guardian_phone_1,
        },
    )
    assert student_1_response.status_code == 200
    student_1_id = uuid.UUID(student_1_response.json()["id"])

    student_2_response = await client.post(
        "/api/v1/identity/students",
        headers=admin_headers,
        json={
            "full_name": "Student Two",
            "admission_number": _unique_admission("ADM"),
            "roll_number": "2",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Guardian Two",
            "guardian_relation": "Parent",
            "guardian_phone": guardian_phone_2,
        },
    )
    assert student_2_response.status_code == 200
    student_2_id = uuid.UUID(student_2_response.json()["id"])

    async with TestSessionLocal() as db:
        db.add(
            AIInsightV2(
                student_id=student_1_id,
                exam_id=exam_id,
                insight_text="Insight one",
                recommendations_json={"strengths": ["Math"]},
                performance_summary_json={"trend": "improving"},
                model_version="v2.0",
                status="completed",
                generated_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            AIInsightV2(
                student_id=student_2_id,
                exam_id=exam_id,
                insight_text="Insight two",
                recommendations_json={"strengths": ["Science"]},
                performance_summary_json={"trend": "stable"},
                model_version="v2.0",
                status="completed",
                generated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    otp_request = await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone_1, "requested_role": "parent"},
    )
    assert otp_request.status_code == 200
    otp_verify = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone_1, "requested_role": "parent", "otp_code": "123456"},
    )
    assert otp_verify.status_code == 200
    parent_headers = {"Authorization": f"Bearer {otp_verify.json()['access_token']}"}

    own_response = await client.get(f"/api/v1/insights/{student_1_id}/{exam_id}", headers=parent_headers)
    assert own_response.status_code == 200
    assert own_response.json()["status"] == "completed"

    other_response = await client.get(f"/api/v1/insights/{student_2_id}/{exam_id}", headers=parent_headers)
    assert other_response.status_code == 403


@pytest.mark.asyncio
async def test_generate_requires_admin_role(client: AsyncClient, database_ready: None, monkeypatch):
    _enable_mock_otp(monkeypatch)
    profile, token = await _register_admin_and_get_auth(client)
    admin_headers = {"Authorization": f"Bearer {token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=admin_headers,
        json={"name": "Class 8", "class_number": 8, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=admin_headers,
        json={"name": "Section Role", "class_id": class_id},
    )
    section_id = section_response.json()["id"]
    exam_response = await client.post(
        "/api/v1/assessment/exams",
        headers=admin_headers,
        params={"section_id": section_id, "name": "Role Exam"},
    )
    exam_id = exam_response.json()["id"]

    guardian_phone = _unique_phone()
    student_response = await client.post(
        "/api/v1/identity/students",
        headers=admin_headers,
        json={
            "full_name": "Role Student",
            "admission_number": _unique_admission("ADM"),
            "roll_number": "1",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Role Guardian",
            "guardian_relation": "Parent",
            "guardian_phone": guardian_phone,
        },
    )
    assert student_response.status_code == 200

    await client.post(
        "/api/v1/user/auth/login/otp",
        json={"phone": guardian_phone, "requested_role": "parent"},
    )
    verify_response = await client.post(
        "/api/v1/user/auth/verify/otp",
        json={"phone": guardian_phone, "requested_role": "parent", "otp_code": "123456"},
    )
    parent_headers = {"Authorization": f"Bearer {verify_response.json()['access_token']}"}

    parent_call = await client.post(
        "/api/v1/insights/generate",
        headers=parent_headers,
        json={"exam_id": exam_id},
    )
    assert parent_call.status_code == 403


@pytest.mark.asyncio
async def test_marks_event_does_not_enqueue_insights_policy(monkeypatch):
    calls: list[tuple] = []

    async def _fake_enqueue_exam(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "queued"}

    monkeypatch.setattr(
        "app.modules.analytics.insights_v2.tasks.celery_tasks.AIInsightsV2TaskQueue.enqueue_exam",
        _fake_enqueue_exam,
    )

    await event_bus.emit(
        "assessment.marks_recorded",
        {
            "exam_id": str(uuid.uuid4()),
            "student_ids": [str(uuid.uuid4())],
        },
    )
    assert calls == []


@pytest.mark.asyncio
async def test_exam_completed_event_dedupes_enqueues(monkeypatch):
    calls: list[tuple] = []

    async def _fake_enqueue_exam(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "queued"}

    monkeypatch.setattr(
        "app.modules.analytics.insights_v2.tasks.celery_tasks.AIInsightsV2TaskQueue.enqueue_exam",
        _fake_enqueue_exam,
    )

    exam_id = uuid.uuid4()
    payload = {
        "exam_id": str(exam_id),
        "section_id": str(uuid.uuid4()),
    }
    await event_bus.emit("assessment.exam_completed", payload)
    await event_bus.emit("assessment.exam_completed", payload)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_batch_status_tracks_unstarted_students(
    client: AsyncClient,
    database_ready: None,
    monkeypatch,
):
    _enable_mock_otp(monkeypatch)
    profile, token = await _register_admin_and_get_auth(client)
    admin_headers = {"Authorization": f"Bearer {token}"}
    school_id = profile["school_id"]

    class_response = await client.post(
        "/api/v1/academic/classes",
        headers=admin_headers,
        json={"name": "Class 9", "class_number": 9, "school_id": school_id},
    )
    class_id = class_response.json()["id"]
    section_response = await client.post(
        "/api/v1/academic/sections",
        headers=admin_headers,
        json={"name": "Section Auto", "class_id": class_id},
    )
    section_id = section_response.json()["id"]
    exam_response = await client.post(
        "/api/v1/assessment/exams",
        headers=admin_headers,
        params={"section_id": section_id, "name": "Auto Exam"},
    )
    exam_id = uuid.UUID(exam_response.json()["id"])

    student_one_response = await client.post(
        "/api/v1/identity/students",
        headers=admin_headers,
        json={
            "full_name": "Auto Student One",
            "admission_number": _unique_admission("ADM"),
            "roll_number": "1",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Guardian One",
            "guardian_relation": "Parent",
            "guardian_phone": _unique_phone(),
        },
    )
    student_two_response = await client.post(
        "/api/v1/identity/students",
        headers=admin_headers,
        json={
            "full_name": "Auto Student Two",
            "admission_number": _unique_admission("ADM"),
            "roll_number": "2",
            "class_id": class_id,
            "section_id": section_id,
            "guardian_name": "Guardian Two",
            "guardian_relation": "Parent",
            "guardian_phone": _unique_phone(),
        },
    )
    student_one_id = uuid.UUID(student_one_response.json()["id"])
    assert student_one_response.status_code == 200
    assert student_two_response.status_code == 200

    async with TestSessionLocal() as db:
        db.add(
            AIInsightV2(
                student_id=student_one_id,
                exam_id=exam_id,
                insight_text="Generated insight",
                recommendations_json={},
                performance_summary_json={},
                model_version="v2.0",
                status="completed",
                generated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    batch_response = await client.get(
        "/api/v1/insights/batch-status",
        headers=admin_headers,
        params={"exam_id": str(exam_id)},
    )
    assert batch_response.status_code == 200
    payload = batch_response.json()
    assert payload["total"] == 2
    assert payload["generated"] == 1
    assert payload["completed"] == 1
    assert payload["pending"] == 1
    assert payload["in_progress"] == 1
    assert payload["remaining"] == 1
    assert payload["auto_mode"] is True

    list_response = await client.get(
        "/api/v1/insights/list",
        headers=admin_headers,
        params={"exam_id": str(exam_id)},
    )
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 2
    assert sum(1 for row in rows if row["status"] == "pending") == 1
    assert sum(1 for row in rows if row["status"] == "completed") == 1
    assert all("admission_number" in row for row in rows)
    assert all(row["admission_number"] for row in rows)

    overview_response = await client.get(
        "/api/v1/insights/overview",
        headers=admin_headers,
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert {"total", "generated", "in_progress", "failed", "completion_pct", "task_processing_time_ms_avg", "task_processing_time_ms_last", "top_exams"} <= set(overview.keys())


def test_rule_engine_thresholds_and_trend():
    data = StructuredPerformanceData(
        student_id=uuid.uuid4(),
        exam_id=uuid.uuid4(),
        overall_percentage=67.2,
        attendance_percentage=90.0,
        overall_trend="improving",
        subject_snapshots=[
            SubjectSnapshot(
                subject_id=uuid.uuid4(),
                subject_name="Math",
                current_percentage=82.0,
                history_percentages=[64.0, 71.0, 82.0],
            ),
            SubjectSnapshot(
                subject_id=uuid.uuid4(),
                subject_name="Science",
                current_percentage=44.0,
                history_percentages=[58.0, 51.0, 44.0],
            ),
        ],
        meta={},
    )

    summary = RuleEngine().analyze(data)
    assert "Math (82.0%)" in summary["strengths"]
    assert "Science (44.0%)" in summary["weaknesses"]
    assert summary["trend"] == "improving"


def test_ai_insight_v2_model_contract():
    table = AIInsightV2.__table__
    assert table.name == "ai_insights"
    assert {"student_id", "exam_id", "insight_text", "recommendations_json", "performance_summary_json", "model_version", "status", "generated_at"} <= set(table.c.keys())
    unique_constraints = [c for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"]
    assert any(
        set(col.name for col in constraint.columns) == {"student_id", "exam_id"}
        for constraint in unique_constraints
    )


def test_ai_eligibility_policy_and_prompt_contract():
    data = StructuredPerformanceData(
        student_id=uuid.uuid4(),
        exam_id=uuid.uuid4(),
        overall_percentage=61.0,
        attendance_percentage=72.0,
        overall_trend="stable",
        subject_snapshots=[
            SubjectSnapshot(
                subject_id=uuid.uuid4(),
                subject_name="English",
                current_percentage=78.0,
                history_percentages=[70.0, 74.0, 78.0],
            ),
            SubjectSnapshot(
                subject_id=uuid.uuid4(),
                subject_name="Math",
                current_percentage=45.0,
                history_percentages=[49.0, 47.0, 45.0],
            ),
        ],
        meta={},
    )
    summary = {"strengths": ["English"], "weaknesses": ["Math"], "trend": "stable"}
    policy = AIEligibilityPolicy()

    assert policy.should_use_ai(
        structured_data=data,
        summary=summary,
        high_value_user=False,
        explicit_request=False,
    )
    assert policy.should_use_ai(
        structured_data=data,
        summary={"strengths": [], "weaknesses": [], "trend": "stable"},
        high_value_user=True,
        explicit_request=False,
    )

    prompt = AIService._build_prompt(data.model_dump(mode="json"))
    assert "Given the following student performance data:" in prompt
    assert "Keep output concise and structured." in prompt
