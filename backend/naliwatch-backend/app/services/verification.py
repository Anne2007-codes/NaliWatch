"""Disposal verification. A trip is verified only if it entered an authorized plant geofence inside its
time window and the received volume is within tolerance of the pumped volume. Anything else becomes a flag."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from geoalchemy2.shape import to_shape
from shapely.geometry import Point
from sqlalchemy import select

from .. import events
from ..config import settings
from ..geo import latlng
from ..models import Disposal, Flag, GpsPoint, Job, Plant, Report, Trip, now


@dataclass
class Fix:
    t: datetime
    lat: float
    lng: float


def volume_ok(pumped: int, received: int, pct: float, min_litres: int) -> tuple[bool, int, float]:
    tol = max(pumped * pct / 100.0, float(min_litres))
    diff = received - pumped
    return abs(diff) <= tol, diff, tol


def entered_geofence(fixes: list[Fix], polygon, start: datetime, end: datetime) -> bool:
    return any(start <= f.t <= end and polygon.contains(Point(f.lng, f.lat)) for f in fixes)


def find_gaps(fixes: list[Fix], max_minutes: int) -> list[tuple[datetime, datetime]]:
    fs = sorted(fixes, key=lambda f: f.t)
    return [(a.t, b.t) for a, b in zip(fs, fs[1:]) if (b.t - a.t) > timedelta(minutes=max_minutes)]


def evaluate(*, pumped: int, received: int, fixes: list[Fix], polygon, start: datetime, end: datetime,
             arrival: datetime, plant_valid: bool, confirmed_stops: int) -> tuple[list[str], dict]:
    """Pure decision function. Returns (reasons, detail). Empty reasons == verified."""
    reasons: list[str] = []
    detail: dict = {}
    if not plant_valid:
        reasons.append("plant_not_authorized")
    if confirmed_stops == 0:
        reasons.append("no_confirmed_stops")
    if not (start <= arrival <= end):
        reasons.append("outside_time_window")
    ok, diff, tol = volume_ok(pumped, received, settings.volume_tolerance_pct, settings.volume_tolerance_min_litres)
    detail.update(pumped=pumped, received=received, diff=diff, tolerance=round(tol, 1))
    if not ok:
        reasons.append("volume_mismatch")
    if not entered_geofence(fixes, polygon, start, end):
        gaps = find_gaps(fixes, settings.gps_gap_minutes)
        if not fixes:
            reasons.append("no_gps_trail")
        elif gaps:
            reasons.append("gps_gap_unverified")  # check gaps before suspecting dumping
            detail["gaps"] = [[a.isoformat(), b.isoformat()] for a, b in gaps]
        else:
            reasons.append("no_geofence_entry")
    return reasons, detail


def verify_disposal(db, trip: Trip, plant: Plant, volume_received: int, confirmed_by: int,
                    arrival: datetime | None = None) -> Disposal:
    if trip.status not in ("in_progress", "awaiting_plant"):
        raise ValueError(f"trip is {trip.status}, not waiting for a plant")
    arrival = arrival or now()
    start = trip.started_at or arrival
    end = start + timedelta(hours=settings.trip_window_hours)
    stops = [s for s in trip.stops if s.confirmed_at is not None]
    pumped = sum(s.volume_pumped_litres or 0 for s in stops)
    fixes = []
    for g in db.scalars(select(GpsPoint).where(GpsPoint.trip_id == trip.id).order_by(GpsPoint.recorded_at)):
        lat, lng = latlng(g.location)
        fixes.append(Fix(g.recorded_at, lat, lng))

    reasons, detail = evaluate(
        pumped=pumped, received=volume_received, fixes=fixes, polygon=to_shape(plant.geofence), start=start, end=end,
        arrival=arrival, plant_valid=plant.status == "active" and plant.valid_until >= arrival.date(),
        confirmed_stops=len(stops),
    )
    disposal = Disposal(trip_id=trip.id, plant_id=plant.id, arrival_time=arrival, volume_received_litres=volume_received,
                        confirmed_by=confirmed_by, result="mismatch" if reasons else "matched",
                        detail={**detail, "reasons": reasons})
    db.add(disposal)
    trip.finished_at = trip.finished_at or arrival
    ward = _trip_ward(db, trip)
    if reasons:
        trip.status = "flagged"
        db.add(Flag(trip_id=trip.id, reason=reasons[0], ward=ward, detail={**detail, "reasons": reasons}))
    else:
        trip.status = "verified"
        _resolve_reports(db, trip)
    db.flush()
    events.publish("trip", ward, id=trip.id, status=trip.status)
    return disposal


def flag_skipped_plants(db, force: bool = False) -> int:
    """Trips whose time window ended with no plant confirmation become flags (for a human to review)."""
    t, n = now(), 0
    trips = db.scalars(select(Trip).where(Trip.status.in_(("in_progress", "awaiting_plant")))).all()
    for trip in trips:
        if trip.started_at and (force or trip.started_at + timedelta(hours=settings.trip_window_hours) < t):
            trip.status = "flagged"
            ward = _trip_ward(db, trip)
            db.add(Flag(trip_id=trip.id, reason="plant_skipped", ward=ward, detail={"reasons": ["plant_skipped"]}))
            events.publish("trip", ward, id=trip.id, status="flagged")
            n += 1
    return n


def _trip_ward(db, trip: Trip) -> str | None:
    for s in trip.stops:
        job = s.job or db.get(Job, s.job_id)
        if job and job.ward:
            return job.ward
    return None


def _resolve_reports(db, trip: Trip) -> None:
    for s in trip.stops:
        job = s.job or db.get(Job, s.job_id)
        if job and job.report_id:
            r = db.get(Report, job.report_id)
            if r and r.status != "resolved":
                r.status, r.resolved_at = "resolved", now()
