from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, require_roles, ward_clause
from ..models import Job, Property, Tank, User, now
from ..schemas import JobCreate
from ..serializers import job_out
from ..services import prediction, scheduling

router = APIRouter(tags=["jobs"])


def _get_job(db: Session, user: User, job_id: int) -> Job:
    job = db.get(Job, job_id)
    ok = job is not None and (
        user.role == "admin"
        or (user.role == "operator" and job.operator_id == user.operator_id)
        or (user.role == "officer" and job.ward == user.ward)
        or (user.role == "household" and job.tank is not None and job.tank.prop.owner_id == user.id)
    )
    if not ok:
        raise HTTPException(404, "job not found")
    return job


@router.post("/jobs", status_code=201)
def request_pumpout(body: JobCreate, user: User = Depends(require_roles("household", "officer")),
                    db: Session = Depends(get_db)):
    tank = db.get(Tank, body.tank_id)
    if not tank or (user.role == "household" and tank.prop.owner_id != user.id) or \
            (user.role == "officer" and tank.prop.ward != user.ward):
        raise HTTPException(404, "tank not found")
    job = Job(tank_id=tank.id, source="household" if user.role == "household" else "officer", status="pending",
              location=tank.prop.location, ward=tank.prop.ward, requested_by=user.id,
              window_start=body.window_start or now().date(), window_end=body.window_end,
              estimated_litres=int(tank.capacity_litres * 0.33))
    job.tank = tank
    prediction.score_job(db, job)
    db.add(job)
    db.flush()
    audit.log(db, user, "create", f"job:{job.id}")
    db.commit()
    return job_out(job, user)


@router.get("/jobs")
def list_jobs(status: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
              user: User = Depends(require_roles("household", "operator", "officer")), db: Session = Depends(get_db)):
    q = select(Job)
    if user.role == "household":
        q = q.join(Tank, Job.tank_id == Tank.id).join(Property, Tank.property_id == Property.id).where(Property.owner_id == user.id)
    elif user.role == "operator":
        q = q.where(Job.operator_id == user.operator_id)
    elif user.role == "officer":
        q = q.where(ward_clause(user, Job.ward))
    if status:
        q = q.where(Job.status == status)
    rows = db.scalars(q.order_by(Job.priority_score.desc(), Job.created_at).limit(limit).offset(offset))
    return [job_out(j, user) for j in rows]


@router.get("/priority/tanks")
def priority_tanks(limit: int = Query(50, le=200), user: User = Depends(require_roles("officer")),
                   db: Session = Depends(get_db)):
    return prediction.rank_tanks(db, ward=user.ward if user.role == "officer" else None, limit=limit)


@router.post("/jobs/refresh")
def refresh(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """Recompute due dates, create jobs for tanks due soon, rescore the queue."""
    prediction.refresh_predictions(db)
    created = prediction.ensure_due_jobs(db)
    db.flush()
    rescored = prediction.rescore_open_jobs(db)
    db.commit()
    return {"jobs_created": len(created), "jobs_rescored": rescored}


@router.post("/jobs/run-scheduler")
def run_scheduler(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    assigned = scheduling.assign_operators(db)
    db.commit()
    return {"offered": [j.id for j in assigned]}


@router.post("/jobs/{job_id}/accept")
def accept(job_id: int, user: User = Depends(require_roles("operator")), db: Session = Depends(get_db)):
    job = _get_job(db, user, job_id)
    if job.status != "offered":
        raise HTTPException(409, f"job is {job.status}")
    scheduling.accept_job(db, job)
    audit.log(db, user, "accept", f"job:{job.id}")
    db.commit()
    return job_out(job, user)


@router.post("/jobs/{job_id}/decline")
def decline(job_id: int, user: User = Depends(require_roles("operator")), db: Session = Depends(get_db)):
    job = _get_job(db, user, job_id)
    if job.status != "offered":
        raise HTTPException(409, f"job is {job.status}")
    scheduling.decline_job(db, job)
    audit.log(db, user, "decline", f"job:{job.id}")
    db.commit()
    return job_out(job, user)


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: int, user: User = Depends(require_roles("household", "officer")), db: Session = Depends(get_db)):
    job = _get_job(db, user, job_id)
    if job.status not in ("pending", "offered", "scheduled"):
        raise HTTPException(409, f"job is {job.status}")
    job.status = "cancelled"
    audit.log(db, user, "cancel", f"job:{job.id}")
    db.commit()
    return job_out(job, user)
