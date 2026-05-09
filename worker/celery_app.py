from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "mlservice",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=("worker.tasks",),
    task_default_queue="celery",
)

celery_app.conf.beat_schedule = {
    "loyalty-recalculate-monthly": {
        "task": "worker.tasks.recalculate_loyalty_monthly",
        "schedule": crontab(day_of_month=1, hour=0, minute=0),
    },
}
