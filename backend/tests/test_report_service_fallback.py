from app.modules.analytics.report_service import ReportCardService


def test_fallback_ai_content_populates_all_sections():
    marks_rows = [
        {"subject": "Math", "percentage_val": 86.0},
        {"subject": "Science", "percentage_val": 42.0},
        {"subject": "English", "percentage_val": 78.0},
        {"subject": "Social", "percentage_val": None},
    ]

    ai = ReportCardService._build_fallback_ai_content(
        marks_rows=marks_rows,
        attendance_percentage=68.0,
        absent_exam_count=1,
        overall_percentage=64.5,
        term_name="Term 1",
    )

    assert isinstance(ai.get("summary"), str) and ai["summary"].strip()
    assert isinstance(ai.get("strengths"), list) and ai["strengths"]
    assert isinstance(ai.get("weaknesses"), list) and ai["weaknesses"]
    assert isinstance(ai.get("recommendations"), list) and ai["recommendations"]
    assert any("Math" in item for item in ai["strengths"])
    assert any("Science" in item for item in ai["weaknesses"])


def test_normalize_list_filters_empty_values():
    values = ["  Focus  ", "", " ", None, "Revise"]
    normalized = ReportCardService._normalize_list(values)
    assert normalized == ["Focus", "Revise"]
