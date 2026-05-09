from celery import Celery
from kombu import Queue
from app.core.config import settings

# Initialize Celery explicitly pointing to Redis
celery_app = Celery(
    "edutrack_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND_URL,
    include=[
        "app.modules.analytics.task_queue",
        "app.modules.analytics.insights_v2.tasks.celery_tasks",
    ],
)

celery_app.conf.update(
    task_default_queue="ai_insights",
    broker_connection_retry_on_startup=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_queues=(
        Queue("celery"),
        Queue("ai_insights"),
        Queue("ai_insights_v2_dispatch"),
        Queue("ai_insights_v2"),
    ),
    task_routes={
        "ai_insights_v2.dispatch_exam_generation": {"queue": "ai_insights_v2_dispatch"},
        "ai_insights_v2.generate_student_insight": {"queue": "ai_insights_v2"},
        "generate_insight_task": {"queue": "ai_insights"},
    },
)
