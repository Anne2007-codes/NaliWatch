import hmac
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, events, kv
from ..config import settings
from ..db import get_db
from ..deps import current_user, require_roles
from ..geo import point
from ..models import ACTIVE_TRIP, Driver, GpsPoint, Job, Trip, TripStop, User, now
from ..schemas import GpsBatch, PlanRequest, StartTrip, StopConfirm
from ..security import gen_otp, hash_otp
from ..serializers import trip_out
from ..services import notifications, routing
from ..services.prediction import predict_due_date

router = APIRouter(prefix="/trips", tags=["trips"])


def _my_driver(db: Session, user: User) -> Driver:
    d = db.scalar(select(Driver).where(Driver.user_id == user.id))
    if not d:
        raise HTTPException(403, "no driver profile")
    return d


def _visible(db: Session, user: User, trip: Trip) -> bool:
    if user.role == "admin":
        return True
    if user.role == "operator":
        return trip.operator_id == user.operator_id
    if user.role == "driver":
        return trip.driver.user_id == user.id and (trip.planned_date == date.today() or trip.status in ACTIVE_TRIP)
    if user.role == "officer":
        return any((s.job.ward == user.ward) for s in trip.stops)
    if user.role == "plant":
        return trip.plant_id == user.plant_id
    return False


def _get(db: Session, user: User, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip or not _visible(db, user, trip):
        raise HTTPException(404, "trip not found")
    return trip


def _driver_trip(db: Session, user: User, trip_id: int) -> Trip:
    trip = _get(db, user, trip_id)
    if trip.driver.user_id != user.id:
        raise HTTPException(403, "this trip is assigned to another driver")
    return trip


@router.post("/plan", status_code=201)
def plan(body: PlanRequest, user: User = Depends(require_roles("operator", "officer")), db: Session = Depends(get_db)):
    op_id = user.operator_id if user.role == "operator" else body.operator_id
    if not op_id:
        raise HTTPException(400, "operator_id is required")
    try:
        trips, dropped = routing.plan_routes(db, op_id, body.plan_date)
    except ValueError as e:
        raise HTTPException(422, str(e))
    for t in trips:
        audit.log(db, user, "plan", f"trip:{t.id}")
    db.commit()
    return {"trips": [trip_out(t, user) for t in trips], "unrouted_job_ids": [j.id for j in dropped]}


@router.get("")
def list_trips(status: str | None = None, user: User = Depends(require_roles("operator", "driver", "officer", "plant")),
               db: Session = Depends(get_db)):
    q = select(Trip)
    if user.role == "operator":
        q = q.where(Trip.operator_id == user.operator_id)
    elif user.role == "driver":
        d = _my_driver(db, user)
        q = q.where(Trip.driver_id == d.id, (Trip.planned_date == date.today()) | Trip.status.in_(ACTIVE_TRIP))
    elif user.role == "plant":
        q = q.where(Trip.plant_id == user.plant_id)
    if status:
        q = q.where(Trip.status == status)
    trips = [t for t in db.scalars(q.order_by(Trip.created_at.desc()).limit(100)) if _visible(db, user, t)]
    return [trip_out(t, user) for t in trips]


@router.get("/{trip_id}")
def get_trip(trip_id: int, user: User = Depends(require_roles("operator", "driver", "officer", "plant")),
             db: Session = Depends(get_db)):
    trip = _get(db, user, trip_id)
    audit.log(db, user, "view", f"trip:{trip.id}")
    db.commit()
    return trip_out(trip, user)


@router.post("/{trip_id}/start")
def start(trip_id: int, body: StartTrip, user: User = Depends(require_roles("driver")), db: Session = Depends(get_db)):
    trip = _driver_trip(db, user, trip_id)
    if not body.consent_gps:
        raise HTTPException(400, "GPS consent is required to start a shift")
    if trip.status != "planned":
        raise HTTPException(409, f"trip is {trip.status}")
    if not user.consent_at:
        user.consent_at = now()
    trip.status, trip.started_at = "in_progress", now()
    for s in trip.stops:
        s.job.status = "in_progress"
    audit.log(db, user, "start", f"trip:{trip.id}")
    db.commit()
    events.publish("trip", None, id=trip.id, status=trip.status)
    return {**trip_out(trip, user), "gps_ping_interval_seconds": settings.gps_ping_interval_seconds}


@router.post("/{trip_id}/gps")
def gps(trip_id: int, body: GpsBatch, user: User = Depends(require_roles("driver")), db: Session = Depends(get_db)):
    trip = _driver_trip(db, user, trip_id)
    if trip.status not in ACTIVE_TRIP:
        raise HTTPException(409, f"trip is {trip.status}")
    for p in body.points:
        db.add(GpsPoint(trip_id=trip.id, location=point(p.lat, p.lng), recorded_at=p.recorded_at))
    db.commit()
    if body.points:
        last = max(body.points, key=lambda p: p.recorded_at)
        events.publish("gps", None, trip_id=trip.id, lat=last.lat, lng=last.lng)
    return {"stored": len(body.points)}


@router.post("/{trip_id}/stops/{stop_id}/otp")
def request_stop_otp(trip_id: int, stop_id: int, user: User = Depends(require_roles("driver")),
                     db: Session = Depends(get_db)):
    """Driver at the tank asks for a code. It goes to the household, who read it out to the driver."""
    trip = _driver_trip(db, user, trip_id)
    stop = db.get(TripStop, stop_id)
    if not stop or stop.trip_id != trip.id or trip.status != "in_progress":
        raise HTTPException(404, "stop not found")
    owner = stop.job.tank.prop.owner if stop.job.tank else None
    if not owner:
        return {"otp_required": False}
    if not kv.rate_limit(f"rl:stopotp:{stop.id}", 5, 3600):
        raise HTTPException(429, "too many codes requested for this stop")
    code = gen_otp()
    kv.r.setex(f"stopotp:{stop.id}", 900, hash_otp(f"stop:{stop.id}", code))
    kv.r.delete(f"stopotp_try:{stop.id}")
    # WhatsApp/Telegram first, SMS fallback (printed code on the QR plate is an alternative: decision pending)
    notifications.notify_user(owner, f"NaliWatch: your tanker pump-out code is {code}. Share it only with the driver at your door.")
    return {"otp_required": True, **({"dev_otp": code} if settings.otp_dev_echo else {})}


@router.post("/{trip_id}/stops/{stop_id}/confirm")
def confirm_stop(trip_id: int, stop_id: int, body: StopConfirm, user: User = Depends(require_roles("driver")),
                 db: Session = Depends(get_db)):
    trip = _driver_trip(db, user, trip_id)
    stop = db.get(TripStop, stop_id)
    if not stop or stop.trip_id != trip.id or trip.status != "in_progress":
        raise HTTPException(404, "stop not found")
    if stop.confirmed_at:
        raise HTTPException(409, "stop already confirmed")
    owner = stop.job.tank.prop.owner if stop.job.tank else None
    if owner:
        tries = kv.r.incr(f"stopotp_try:{stop.id}")
        kv.r.expire(f"stopotp_try:{stop.id}", 900)
        stored = kv.r.get(f"stopotp:{stop.id}")
        if tries > 5 or not body.otp or not stored or not hmac.compare_digest(stored, hash_otp(f"stop:{stop.id}", body.otp)):
            raise HTTPException(401, "wrong or expired code")
        kv.r.delete(f"stopotp:{stop.id}")
    t = now()
    stop.arrival_time = stop.arrival_time or t
    stop.volume_pumped_litres, stop.otp_confirmed, stop.confirmed_at = body.volume_pumped_litres, owner is not None, t
    if body.lat is not None and body.lng is not None:
        stop.confirm_location = point(body.lat, body.lng)
    job: Job = stop.job
    job.status, job.completed_at = "completed", t
    if job.tank:
        job.tank.last_emptied = t.date()
        job.tank.predicted_due = predict_due_date(job.tank.last_emptied, job.tank.capacity_litres,
                                                  job.tank.prop.household_size, job.tank.install_year)
    audit.log(db, user, "confirm_stop", f"trip_stop:{stop.id}", litres=body.volume_pumped_litres)
    db.commit()
    return {"confirmed": True, "otp_confirmed": stop.otp_confirmed}


@router.post("/{trip_id}/finish")
def finish(trip_id: int, user: User = Depends(require_roles("driver")), db: Session = Depends(get_db)):
    """Driver says the collection is done and is heading to / at the plant. The trip stays open until the plant confirms."""
    trip = _driver_trip(db, user, trip_id)
    if trip.status != "in_progress":
        raise HTTPException(409, f"trip is {trip.status}")
    trip.status = "awaiting_plant"
    audit.log(db, user, "finish_collection", f"trip:{trip.id}")
    db.commit()
    events.publish("trip", None, id=trip.id, status=trip.status)
    return {"status": trip.status}
