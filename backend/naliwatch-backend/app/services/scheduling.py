"""Match pending jobs to certified operators (constraint matching, least-loaded first)."""
from datetime import date

from sqlalchemy import func, select

from ..models import OPEN_JOB, Driver, Job, Operator, User, Vehicle, now
from . import notifications


def eligible_operators(db, on_date: date, exclude: list[int] | None = None) -> list[Operator]:
    ops = db.scalars(select(Operator).where(Operator.status == "active", Operator.valid_until >= on_date)).all()
    out = []
    for o in ops:
        if exclude and o.id in exclude:
            continue
        has_vehicle = db.scalar(select(Vehicle.id).where(Vehicle.operator_id == o.id, Vehicle.status == "active").limit(1))
        has_driver = db.scalar(select(Driver.id).where(Driver.operator_id == o.id, Driver.status == "active").limit(1))
        if has_vehicle and has_driver:
            out.append(o)
    return out


def assign_operators(db, job_ids: list[int] | None = None, limit: int = 200) -> list[Job]:
    q = select(Job).where(Job.status == "pending")
    if job_ids is not None:
        q = q.where(Job.id.in_(job_ids))
    jobs = db.scalars(q.order_by(Job.priority_score.desc(), Job.created_at).limit(limit)).all()
    load = dict(db.execute(
        select(Job.operator_id, func.count()).where(Job.status.in_(OPEN_JOB), Job.operator_id.isnot(None)).group_by(Job.operator_id)
    ).all())
    assigned = []
    for job in jobs:
        on = job.window_end or date.today()
        ops = eligible_operators(db, on, job.declined_operator_ids or [])
        if not ops:
            continue
        op = min(ops, key=lambda o: (load.get(o.id, 0), o.id))
        job.operator_id, job.status, job.assigned_at = op.id, "offered", now()
        load[op.id] = load.get(op.id, 0) + 1
        assigned.append(job)
        for u in db.scalars(select(User).where(User.operator_id == op.id, User.role == "operator")):
            tag = "URGENT " if job.urgent else ""
            notifications.notify_user(u, f"{tag}New NaliWatch job #{job.id} offered. Open your dashboard to accept.")
    return assigned


def accept_job(db, job: Job) -> None:
    job.status, job.scheduled_at = "scheduled", now()
    if job.tank:
        notifications.notify_user(job.tank.prop.owner, f"Your septic tank pump-out is scheduled (job #{job.id}). "
                                                       "Keep the access cover clear. You will get a code when the tanker arrives.")


def decline_job(db, job: Job) -> None:
    job.declined_operator_ids = list(job.declined_operator_ids or []) + [job.operator_id]
    job.operator_id, job.status, job.assigned_at = None, "pending", None
