from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..geo import latlng, to_geojson
from ..models import ACTIVE_TRIP, OPEN_REPORT, Cluster, Flag, GpsPoint, Plant, Property, Report, Tank, Trip, User

router = APIRouter(tags=["map"])


def _feat(geom: dict, **props) -> dict:
    return {"type": "Feature", "geometry": geom, "properties": props}


def _fc(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


@router.get("/map/layers")
def layers(ward: str | None = None, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """One call for the ward map: tanks, open reports, clusters, plants, active trips and open flags (GeoJSON)."""
    w = user.ward if user.role == "officer" else ward
    today = date.today()

    tq = select(Tank).join(Property, Tank.property_id == Property.id)
    rq = select(Report).where(Report.status.in_(OPEN_REPORT), Report.duplicate_of_id.is_(None))
    cq = select(Cluster)
    fq = select(Flag).where(Flag.status.in_(("open", "needs_info")))
    if w:
        tq, rq, cq, fq = (tq.where(Property.ward == w), rq.where(Report.ward == w), cq.where(Cluster.ward == w),
                          fq.where(Flag.ward == w))

    tanks = [_feat(to_geojson(t.prop.location), id=t.id, due=str(t.predicted_due) if t.predicted_due else None,
                   overdue=bool(t.predicted_due and t.predicted_due < today)) for t in db.scalars(tq)]
    reports = [_feat(to_geojson(r.location), id=r.id, type=r.type, severity=r.severity, status=r.status)
               for r in db.scalars(rq)]
    clusters = [_feat(to_geojson(c.center), id=c.id, status=c.status, radius_m=c.radius_m, score=c.score,
                      reports=c.report_count, cases=c.case_count) for c in db.scalars(cq)]
    plants = [_feat(to_geojson(p.geofence), id=p.id, name=p.name) for p in db.scalars(select(Plant))]

    trips = []
    for t in db.scalars(select(Trip).where(Trip.status.in_(ACTIVE_TRIP + ("flagged",)))):
        if w and not any(s.job.ward == w for s in t.stops):
            continue
        last = db.scalar(select(GpsPoint).where(GpsPoint.trip_id == t.id).order_by(GpsPoint.recorded_at.desc()).limit(1))
        if last:
            trips.append(_feat(to_geojson(last.location), id=t.id, status=t.status, plate=t.vehicle.plate,
                               at=last.recorded_at.isoformat()))
    flags = []
    for f in db.scalars(fq):
        geom = None
        if f.report_id:
            r = db.get(Report, f.report_id)
            geom = to_geojson(r.location) if r else None
        elif f.trip_id:
            t = db.get(Trip, f.trip_id)
            if t and t.stops:
                geom = to_geojson(t.stops[0].job.location)
        if geom:
            flags.append(_feat(geom, id=f.id, reason=f.reason, status=f.status))
    return {"tanks": _fc(tanks), "reports": _fc(reports), "clusters": _fc(clusters), "plants": _fc(plants),
            "trips": _fc(trips), "flags": _fc(flags)}


@router.get("/public/stats", tags=["public"])
def public_stats(db: Session = Depends(get_db)):
    """No login. Ward-level counts and coarse hotspots only: no names, phones or exact addresses."""
    today = date.today()
    wards = {}
    for ward, total, overdue in db.execute(
        select(Property.ward, func.count(Tank.id), func.count(Tank.id).filter(Tank.predicted_due < today))
        .join(Tank, Tank.property_id == Property.id).group_by(Property.ward)
    ):
        wards[ward or "unassigned"] = {"tanks": total, "overdue": overdue, "open_reports": 0}
    for ward, n in db.execute(select(Report.ward, func.count()).where(Report.status.in_(OPEN_REPORT), Report.duplicate_of_id.is_(None)).group_by(Report.ward)):
        wards.setdefault(ward or "unassigned", {"tanks": 0, "overdue": 0, "open_reports": 0})["open_reports"] = n
    hotspots = []
    for c in db.scalars(select(Cluster)):
        lat, lng = latlng(c.center)
        hotspots.append({"ward": c.ward, "status": c.status, "lat": round(lat, 2), "lng": round(lng, 2)})  # ~1 km grid
    return {"wards": wards, "hotspots": hotspots}
