from datetime import timedelta

from sqlalchemy import delete, select

from ..config import settings
from ..db import session_scope
from ..models import GpsPoint, Job, Report, now
from ..services import clustering, notifications, prediction, scheduling, storage, verification
from .celery_app import celery


@celery.task
def recompute_clusters() -> int:
    with session_scope() as db:
        return clustering.recompute_clusters(db)


@celery.task
def refresh_predictions_and_jobs() -> dict:
    with session_scope() as db:
        prediction.refresh_predictions(db)
        created = prediction.ensure_due_jobs(db)
        db.flush()
        return {"created": len(created), "rescored": prediction.rescore_open_jobs(db)}


@celery.task
def run_scheduler() -> int:
    with session_scope() as db:
        return len(scheduling.assign_operators(db))


@celery.task
def check_overdue_trips() -> int:
    with session_scope() as db:
        return verification.flag_skipped_plants(db)


@celery.task
def send_reminders() -> int:
    """Tell households their pump-out is tomorrow. (Outside the 24-hour WhatsApp window this needs an approved template.)"""
    tomorrow = (now() + timedelta(days=1)).date()
    n = 0
    with session_scope() as db:
        from ..models import Trip
        for trip in db.scalars(select(Trip).where(Trip.planned_date == tomorrow, Trip.status == "planned")):
            for s in trip.stops:
                if s.job.tank:
                    notifications.notify_user(s.job.tank.prop.owner, "Reminder: your septic tank pump-out is planned for tomorrow.")
                    n += 1
    return n


@celery.task
def purge_retention() -> dict:
    """Retention: photos and GPS trails. Raw voice notes are never stored."""
    t = now()
    with session_scope() as db:
        res = db.execute(delete(GpsPoint).where(GpsPoint.recorded_at < t - timedelta(days=settings.retention_gps_days)))
        photos = 0
        old = db.scalars(select(Report).where(Report.photo_key.isnot(None),
                                              Report.created_at < t - timedelta(days=settings.retention_photo_days)))
        for r in old:
            storage.delete(r.photo_key)
            r.photo_key = None
            photos += 1
        return {"gps_deleted": res.rowcount, "photos_deleted": photos}
