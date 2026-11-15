from datetime import date
from statistics import median

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import Flag, Job, Report, Trip, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


@router.get("/kpis")
def kpis(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """The five pilot targets from the plan, computed from live data."""
    w = user.ward if user.role == "officer" else None
    today = date.today()

    jq = select(Job).where(Job.window_end.isnot(None))
    if w:
        jq = jq.where(Job.ward == w)
    jobs = [j for j in db.scalars(jq) if j.completed_at or j.window_end <= today]
    on_time = sum(1 for j in jobs if j.completed_at and j.completed_at.date() <= j.window_end)

    trips = [t for t in db.scalars(select(Trip).where(Trip.status.in_(("verified", "flagged", "closed_reviewed"))))
             if not w or any(s.job.ward == w for s in t.stops)]
    verified = sum(1 for t in trips if t.status == "verified")

    fq = select(Flag).where(Flag.reviewed_at.isnot(None))
    if w:
        fq = fq.where(Flag.ward == w)
    hrs = [(f.reviewed_at - f.created_at).total_seconds() / 3600 for f in db.scalars(fq)]

    mq = select(Report).where(Report.type == "manual_cleaning", Report.duplicate_of_id.is_(None))
    rq = select(Report).where(Report.resolved_at.isnot(None))
    if w:
        mq, rq = mq.where(Report.ward == w), rq.where(Report.ward == w)
    dispatch_min = []
    for r in db.scalars(mq):
        j = db.scalar(select(Job).where(Job.report_id == r.id, Job.assigned_at.isnot(None)))
        if j:
            dispatch_min.append((j.assigned_at - r.created_at).total_seconds() / 60)
    res_days = [(r.resolved_at - r.created_at).total_seconds() / 86400 for r in db.scalars(rq)]

    return {
        "tanks_emptied_on_schedule": {"pct": _pct(on_time, len(jobs)), "target": 80, "n": len(jobs)},
        "trips_with_verified_drop": {"pct": _pct(verified, len(trips)), "target": 95, "n": len(trips)},
        "flags_reviewed_within_24h": {"pct": _pct(sum(1 for h in hrs if h <= 24), len(hrs)), "target": 100,
                                      "median_hours": round(median(hrs), 1) if hrs else None, "n": len(hrs)},
        "manual_cleaning_dispatch_under_2h": {"pct": _pct(sum(1 for m in dispatch_min if m <= 120), len(dispatch_min)),
                                              "median_minutes": round(median(dispatch_min), 1) if dispatch_min else None,
                                              "n": len(dispatch_min)},
        "report_to_resolution": {"median_days": round(median(res_days), 1) if res_days else None, "target_days": 3,
                                 "n": len(res_days)},
    }
