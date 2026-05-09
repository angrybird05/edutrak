"""
Deterministic rule engine for AI Insights V2.
"""
from __future__ import annotations

from typing import Any

from app.modules.analytics.insights_v2.schemas import StructuredPerformanceData


class RuleEngine:
    def analyze(self, structured_data: StructuredPerformanceData) -> dict[str, Any]:
        strengths: list[str] = []
        weaknesses: list[str] = []

        for subject in structured_data.subject_snapshots:
            if subject.current_percentage > 75:
                strengths.append(f"{subject.subject_name} ({subject.current_percentage:.1f}%)")
            if subject.current_percentage < 50:
                weaknesses.append(f"{subject.subject_name} ({subject.current_percentage:.1f}%)")

        if structured_data.overall_percentage >= 80:
            overall_performance = "excellent"
        elif structured_data.overall_percentage >= 65:
            overall_performance = "good"
        elif structured_data.overall_percentage >= 50:
            overall_performance = "average"
        else:
            overall_performance = "needs_attention"

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "overall_performance": overall_performance,
            "trend": structured_data.overall_trend,
        }


rule_engine = RuleEngine()

