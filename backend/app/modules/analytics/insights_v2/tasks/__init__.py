
from app.modules.analytics.insights_v2.tasks.celery_tasks import (
    AI_INSIGHTS_V2_DISPATCH_QUEUE,
    AI_INSIGHTS_V2_QUEUE,
    ai_insights_v2_task_queue,
    dispatch_exam_generation_task,
    generate_student_insight_task,
)

__all__ = [
    "AI_INSIGHTS_V2_DISPATCH_QUEUE",
    "AI_INSIGHTS_V2_QUEUE",
    "ai_insights_v2_task_queue",
    "dispatch_exam_generation_task",
    "generate_student_insight_task",
]
