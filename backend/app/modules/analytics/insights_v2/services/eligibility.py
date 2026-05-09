"""
Policy layer for deciding when AI enhancement is allowed.
"""
from __future__ import annotations

from app.modules.analytics.insights_v2.schemas import StructuredPerformanceData


class AIEligibilityPolicy:
    @staticmethod
    def is_complex_performance(structured_data: StructuredPerformanceData, summary: dict) -> bool:
        strengths = len(summary.get("strengths", []))
        weaknesses = len(summary.get("weaknesses", []))
        trend = summary.get("trend")

        # Complex if mixed profile or inconsistent performance history.
        if strengths > 0 and weaknesses > 0:
            return True
        if weaknesses >= 2:
            return True
        if trend == "stable" and 45 <= structured_data.overall_percentage <= 65:
            return True
        return False

    def should_use_ai(
        self,
        *,
        structured_data: StructuredPerformanceData,
        summary: dict,
        high_value_user: bool,
        explicit_request: bool,
    ) -> bool:
        if explicit_request:
            return True
        if high_value_user:
            return True
        return self.is_complex_performance(structured_data, summary)


ai_eligibility_policy = AIEligibilityPolicy()

