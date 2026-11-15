from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require_roles, ward_clause
from ..models import Flag, Trip, User, now
from ..schemas import FlagDecision

router = APIRouter(prefix="/flags", tags=["flags"])


def _out(f: Flag) -> dict:
    return {"id": f.id, "trip_id": f.trip_id, "report_id": f.report_id, "reason": f.reason, "status": f.status,
            "detail": f.detail, "ward": f.ward, "decision": f.decision, "review_note": f.review_note,
            "created_at": f.created_at, "reviewed_at": f.reviewed_at}


@router.get("")
def list_flags(status: str | None = None, limit: int = Query(50, le=200), user: User = Depends(require_roles("officer")),
               db: Session = Depends(get_db)):
    q = select(Flag)
    wc = ward_clause(user, Flag.ward)
    if wc is not None:
        q = q.where(wc)
    if status:
        q = q.where(Flag.status == status)
    return [_out(f) for f in db.scalars(q.order_by(Flag.created_at.desc()).limit(limit))]


@router.get("/{flag_id}")
def get_flag(flag_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    f = db.get(Flag, flag_id)
    if not f or (user.role == "officer" and f.ward != user.ward):
        raise HTTPException(404, "flag not found")
    audit.log(db, user, "view", f"flag:{f.id}")
    db.commit()
    return _out(f)


@router.post("/{flag_id}/decision")
def decide(flag_id: int, body: FlagDecision, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """A flag is a lead for a human. The system never penalises an operator on its own."""
    f = db.get(Flag, flag_id)
    if not f or (user.role == "officer" and f.ward != user.ward):
        raise HTTPException(404, "flag not found")
    f.decision, f.review_note, f.reviewed_by = body.decision, body.note, user.id
    f.status = {"confirmed": "confirmed", "dismissed": "dismissed", "needs_more_info": "needs_info"}[body.decision]
    if body.decision != "needs_more_info":
        f.reviewed_at = now()
    if body.decision == "dismissed" and f.trip_id:
        trip = db.get(Trip, f.trip_id)
        if trip and trip.status == "flagged":
            trip.status = "closed_reviewed"
    audit.log(db, user, "flag_decision", f"flag:{f.id}", decision=body.decision)
    db.commit()
    return _out(f)
