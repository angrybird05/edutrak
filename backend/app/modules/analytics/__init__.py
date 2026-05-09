"""
Analytics Module — AI Insights, Report Cards, Dashboards, AI Coach.
"""
from app.modules.analytics.endpoints import router  # noqa
from app.modules.analytics.models import AIInsight, ReportCard, AIChatSession, AIChatMessage  # noqa
from app.modules.analytics.insights_v2.models import AIInsightV2  # noqa
