"""
Worker tuning knobs for AI Insights V2.
"""
from app.core.config import settings

AI_INSIGHTS_V2_WORKER_CONCURRENCY = max(1, int(getattr(settings, "AI_INSIGHT_QUEUE_WORKERS", 1) or 1))

