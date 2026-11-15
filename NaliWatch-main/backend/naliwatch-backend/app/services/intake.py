"""Report intake: rate limit, transcribe, classify, protect privacy, dedupe, store, then dispatch."""
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select

from .. import events, kv
from ..config import settings
from ..errors import RateLimited, Rejected
from ..geo import assign_ward, latlng, point, within_m
from ..models import Flag, Job, Property, Report, Tank, User, now
from . import classifier, notifications, prediction, privacy, scheduling, storage, stt

log = logging.getLogger(__name__)


@dataclass
class IntakeResult:
    report: Report
    duplicate: bool = False


def create_report(db, user: User, *, lat: float, lng: float, text: str | None = None, photo: bytes | None = None,
                  audio: bytes | None = None, audio_name: str = "voice.ogg", source: str = "api",
                  claimed_type: str | None = None) -> IntakeResult:
    if not kv.rate_limit(f"rl:report:{user.id}", settings.report_rate_limit_per_hour, 3600):
        raise RateLimited("too many reports, try again later")

    transcript = None
    if audio:
        try:
            transcript = stt.transcribe(audio, audio_name)  # raw audio is never stored
        except Exception:
            log.warning("transcription unavailable", exc_info=True)
    full_text = " ".join(x for x in (text, transcript) if x) or None

    if photo:
        try:
            photo = privacy.normalize_photo(photo)
        except Exception:
            raise Rejected("could not read that photo")
    cls = classifier.classify(photo, full_text)
    if cls.shows_interior:
        raise Rejected("Please do not send photos of the inside of a home. Send a photo of the tank area or the problem outside.")
    if cls.fallback and claimed_type in ("overflow", "dumping", "manual_cleaning"):
        cls.type = claimed_type  # reporter's own label, still goes to review below unless manual cleaning

    photo_key = None
    if photo:
        blurred, n = privacy.blur_faces(photo)
        if cls.contains_face and n == 0:
            photo = None  # a face the detector cannot find: do not keep the photo at all
        else:
            photo = blurred
        if photo:
            photo_key = storage.put(f"reports/{uuid.uuid4().hex}.jpg", photo)

    ward = assign_ward(db, lat, lng)
    t = now()
    dup = db.scalar(
        select(Report).where(
            Report.type == cls.type, Report.duplicate_of_id.is_(None),
            Report.created_at >= t - timedelta(hours=settings.dedupe_hours),
            within_m(Report.location, lat, lng, settings.dedupe_radius_m),
        ).order_by(Report.created_at).limit(1)
    )
    tank = db.scalar(
        select(Tank).join(Property, Tank.property_id == Property.id)
        .where(within_m(Property.location, lat, lng, 50)).limit(1)
    )
    review = cls.confidence < settings.ai_confidence_threshold
    report = Report(
        reporter_id=user.id, type=cls.type, severity=cls.severity, confidence=cls.confidence, ai_reason=cls.reason,
        ai_model=None if cls.fallback else classifier.active_model(), summary=cls.summary, text=text, transcript=transcript,
        photo_key=photo_key, location=point(lat, lng), ward=ward, source=source,
        status="duplicate" if dup else ("needs_review" if review else "triaged"),
        tank_id=tank.id if tank else None, duplicate_of_id=dup.id if dup else None,
    )
    db.add(report)
    db.flush()
    if not dup:
        dispatch_report(db, report)
    events.publish("report", ward, id=report.id, type=report.type, severity=report.severity, status=report.status)
    return IntakeResult(report, duplicate=bool(dup))


def dispatch_report(db, report: Report) -> Job | None:
    """Turn a triaged report into a flag and/or a job. Manual cleaning is an emergency regardless of AI confidence."""
    if report.type == "manual_cleaning":
        pass
    elif report.status == "needs_review" or report.type == "other":
        return None
    if db.scalar(select(Job.id).where(Job.report_id == report.id).limit(1)):
        return None

    lat, lng = latlng(report.location)
    tank = db.get(Tank, report.tank_id) if report.tank_id else None
    job = Job(
        tank_id=tank.id if tank else None, report_id=report.id, source="report", status="pending",
        urgent=report.type == "manual_cleaning", location=report.location, ward=report.ward,
        window_start=now().date(), window_end=now().date() + timedelta(days=1 if report.type == "manual_cleaning" else 3),
        estimated_litres=int(tank.capacity_litres * settings.fill_limit) if tank else settings.default_job_litres,
    )
    job.tank = tank
    prediction.score_job(db, job)
    if report.type == "manual_cleaning":
        job.priority_score = 1000.0
    db.add(job)
    report.status = "job_created"

    if report.type in ("manual_cleaning", "dumping"):
        db.add(Flag(report_id=report.id, reason=f"{report.type}_report", ward=report.ward,
                    detail={"severity": report.severity, "confidence": report.confidence, "reason": report.ai_reason}))
    db.flush()
    scheduling.assign_operators(db, job_ids=[job.id])

    if report.type == "manual_cleaning" and settings.manual_cleaning_responder_phone:
        notifications.send_text(
            settings.manual_cleaning_responder_phone,
            f"URGENT manual cleaning report #{report.id}. Location: https://maps.google.com/?q={lat},{lng}. Please respond now.",
        )
    return job
