from celery import Celery
from celery.schedules import crontab

from ..config import settings

celery = Celery("naliwatch", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery.conf.timezone = "Asia/Kolkata"
celery.conf.beat_schedule = {
    "recompute-clusters": {"task": "app.workers.tasks.recompute_clusters", "schedule": crontab(minute="*/15")},
    "refresh-predictions-and-jobs": {"task": "app.workers.tasks.refresh_predictions_and_jobs", "schedule": crontab(hour=2, minute=0)},
    "run-scheduler": {"task": "app.workers.tasks.run_scheduler", "schedule": crontab(minute="*/30")},
    "check-overdue-trips": {"task": "app.workers.tasks.check_overdue_trips", "schedule": crontab(minute="*/15")},
    "send-reminders": {"task": "app.workers.tasks.send_reminders", "schedule": crontab(hour=17, minute=0)},
    "purge-retention": {"task": "app.workers.tasks.purge_retention", "schedule": crontab(hour=3, minute=30)},
}
