"""Desludging estimator + priority ranker. Plain code on purpose: repeatable and auditable."""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from ..config import settings
from ..geo import latlng, within_m
from ..models import OPEN_JOB, OPEN_REPORT, Cluster, Job, Report, Tank


def predict_due_date(
    last_emptied: date | None,
    capacity_litres: int,
    household_size: int,
    install_year: int | None = None,
    fill_limit: float | None = None,
    sludge_per_person_day: float | None = None,
) -> date:
    """due = last_emptied + capacity * fill_limit / (occupants * sludge per person per day)."""
    fill_limit = fill_limit if fill_limit is not None else settings.fill_limit
    sludge = sludge_per_person_day if sludge_per_person_day is not None else settings.sludge_litres_per_person_day
    base = last_emptied or (date(install_year, 1, 1) if install_year else date.today())
    days = capacity_litres * fill_limit / (max(household_size, 1) * sludge)
    return base + timedelta(days=int(days))


@dataclass
class PriorityInput:
    today: date
    due_date: date | None = None
    overflow_severity: int = 0       # 0 = no open overflow report nearby, else 1..3
    report_days_open: int = 0
    cluster_status: str | None = None  # None | "watch" | "risk"
    manual_cleaning: bool = False


def priority_score(p: PriorityInput) -> tuple[float, list[str]]:
    """Scoring rules. Returns (score, reasons) so every ranking can be explained."""
    if p.manual_cleaning:
        return 1000.0, ["manual cleaning report: emergency"]
    score, why = 0.0, []
    if p.due_date is not None:
        gap = (p.due_date - p.today).days
        if gap <= 0:
            s = 40 + min(-gap, 60) * 0.5
            score += s
            why.append(f"overdue by {-gap} days (+{s:.0f})")
        elif gap <= 30:
            s = 30 - gap
            score += s
            why.append(f"due in {gap} days (+{s:.0f})")
    if p.overflow_severity:
        s = 30 * p.overflow_severity / 3
        score += s
        why.append(f"open overflow report severity {p.overflow_severity} (+{s:.0f})")
        d = min(p.report_days_open, 10)
        if d:
            score += d
            why.append(f"report open {p.report_days_open} days (+{d})")
    if p.cluster_status == "risk":
        score += 15
        why.append("inside risk zone (failures + sickness) (+15)")
    elif p.cluster_status == "watch":
        score += 7
        why.append("inside watch zone (+7)")
    return round(score, 1), why


def _signals(db, lat: float, lng: float, today: date):
    reps = db.scalars(
        select(Report).where(
            Report.status.in_(OPEN_REPORT),
            Report.duplicate_of_id.is_(None),
            Report.type.in_(("overflow", "dumping", "manual_cleaning")),
            within_m(Report.location, lat, lng, 100),
        )
    ).all()
    sev = max([r.severity for r in reps if r.type != "manual_cleaning"] or [0])
    days = max([(today - r.created_at.date()).days for r in reps] or [0])
    manual = any(r.type == "manual_cleaning" for r in reps)
    cl = db.scalars(select(Cluster).where(within_m(Cluster.center, lat, lng, Cluster.radius_m))).all()
    status = "risk" if any(c.status == "risk" for c in cl) else ("watch" if cl else None)
    return sev, days, manual, status


def score_location(db, lat: float, lng: float, due: date | None, today: date | None = None):
    today = today or date.today()
    sev, days, manual, status = _signals(db, lat, lng, today)
    return priority_score(PriorityInput(today, due, sev, days, status, manual))


def score_job(db, job: Job) -> None:
    lat, lng = latlng(job.location)
    due = job.tank.predicted_due if job.tank else None
    job.priority_score, job.priority_reason = score_location(db, lat, lng, due)


def rank_tanks(db, ward: str | None = None, limit: int = 100) -> list[dict]:
    q = select(Tank)
    tanks = db.scalars(q).all()
    out = []
    for t in tanks:
        if ward and t.prop.ward != ward:
            continue
        lat, lng = latlng(t.prop.location)
        score, why = score_location(db, lat, lng, t.predicted_due)
        out.append({"tank_id": t.id, "address": t.prop.address, "ward": t.prop.ward, "predicted_due": t.predicted_due,
                    "score": score, "reasons": why})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def refresh_predictions(db) -> int:
    n = 0
    for t in db.scalars(select(Tank)).all():
        t.predicted_due = predict_due_date(t.last_emptied, t.capacity_litres, t.prop.household_size, t.install_year)
        n += 1
    return n


def ensure_due_jobs(db, horizon_days: int = 14) -> list[Job]:
    """Create a pending job for every tank due within the horizon that has no open job."""
    today = date.today()
    created = []
    tanks = db.scalars(select(Tank).where(Tank.predicted_due <= today + timedelta(days=horizon_days))).all()
    for t in tanks:
        busy = db.scalar(
            select(Job.id).where(Job.tank_id == t.id, Job.status.in_(("pending",) + OPEN_JOB)).limit(1)
        )
        if busy:
            continue
        j = Job(
            tank_id=t.id, source="prediction", status="pending", location=t.prop.location, ward=t.prop.ward,
            window_start=max(today, t.predicted_due - timedelta(days=7)), window_end=t.predicted_due + timedelta(days=7),
            estimated_litres=int(t.capacity_litres * settings.fill_limit),
        )
        j.tank = t
        score_job(db, j)
        db.add(j)
        created.append(j)
    return created


def rescore_open_jobs(db) -> int:
    jobs = db.scalars(select(Job).where(Job.status == "pending")).all()
    for j in jobs:
        score_job(db, j)
    return len(jobs)
