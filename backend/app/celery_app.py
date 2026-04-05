"""
BOS Pipeline v9.0 �� Celery Application Configuration

Configures Celery for async task execution:
  - Redis as broker and result backend
  - Task routing (default, compute, export queues)
  - Rate limiting
  - Retry policies
  - Periodic beat schedule
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "bos_pipeline",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_track_started=True,

    # Results
    result_expires=86400,  # 24h
    result_backend_transport_options={"visibility_timeout": 3600},

    # Concurrency
    worker_concurrency=4,
    worker_max_tasks_per_child=200,

    # Rate limits
    task_default_rate_limit="100/m",

    # Retry
    task_default_retry_delay=60,
    task_max_retries=3,

    # Routing
    task_routes={
        "app.tasks.compute.*": {"queue": "compute"},
        "app.tasks.export.*": {"queue": "export"},
        "app.tasks.webhook.*": {"queue": "webhook"},
        "app.tasks.maintenance.*": {"queue": "maintenance"},
    },

    # Default queue
    task_default_queue="default",

    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-expired-calculations": {
            "task": "app.tasks.maintenance.cleanup_expired_calculations",
            "schedule": crontab(hour=3, minute=0),  # Daily at 03:00 UTC
        },
        "refresh-materialized-views": {
            "task": "app.tasks.maintenance.refresh_materialized_views",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
        },
        "check-twin-health": {
            "task": "app.tasks.compute.check_twin_health",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
        },
        "deliver-pending-webhooks": {
            "task": "app.tasks.webhook.deliver_pending",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "generate-daily-digest": {
            "task": "app.tasks.maintenance.generate_daily_digest",
            "schedule": crontab(hour=6, minute=0),  # Daily at 06:00 UTC
        },
    },
)

# Auto-discover tasks in the tasks package
celery_app.autodiscover_tasks(["app.tasks"])
