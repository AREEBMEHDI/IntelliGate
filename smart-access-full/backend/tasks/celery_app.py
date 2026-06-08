from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery(
    "intelligate",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Karachi",
    enable_utc=True,
    beat_schedule={
        # Daily entry report at 11pm
        "daily-report": {
            "task": "tasks.tasks.generate_daily_report",
            "schedule": crontab(hour=23, minute=0),
        },
        # Clean captures older than 90 days
        "cleanup-old-captures": {
            "task": "tasks.tasks.cleanup_old_captures",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


# ─── Import tasks so Celery discovers them ────────────────────
from tasks import tasks  # noqa
