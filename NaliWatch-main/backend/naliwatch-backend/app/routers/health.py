from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, session_scope
from ..deps import current_user, require_roles, ward_clause
from ..geo import assign_ward, latlng, point
from ..models import HealthSignal, User
from ..schemas import HealthCreate
from ..services import clustering

router = APIRouter(prefix="/health-signals", tags=["health"])


def _recluster():
    with session_scope() as db:
        clustering.recompute_clusters(db)


@router.post("", status_code=201)
def add_signal(body: HealthCreate, bg: BackgroundTasks, user: User = Depends(require_roles("asha", "officer")),
               db: Session = Depends(get_db)):
    """Counts for an area only. Never names or patient details."""
    h = HealthSignal(reporter_id=user.id, case_count=body.case_count, symptoms=body.symptoms,
                     location=point(body.lat, body.lng), ward=assign_ward(db, body.lat, body.lng))
    db.add(h)
    db.commit()
    bg.add_task(_recluster)
    return {"id": h.id, "ward": h.ward, "case_count": h.case_count}


@router.get("")
def list_signals(limit: int = Query(100, le=500), user: User = Depends(require_roles("officer")),
                 db: Session = Depends(get_db)):
    q = select(HealthSignal)
    wc = ward_clause(user, HealthSignal.ward)
    if wc is not None:
        q = q.where(wc)
    out = []
    for h in db.scalars(q.order_by(HealthSignal.reported_at.desc()).limit(limit)):
        lat, lng = latlng(h.location)
        out.append({"id": h.id, "case_count": h.case_count, "symptoms": h.symptoms, "ward": h.ward, "lat": lat,
                    "lng": lng, "reported_at": h.reported_at})
    return out
