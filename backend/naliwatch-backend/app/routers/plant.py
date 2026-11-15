from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require_roles
from ..models import ACTIVE_TRIP, Plant, Trip, User
from ..schemas import DisposalIn
from ..services import verification

router = APIRouter(prefix="/plant", tags=["plant"])


@router.get("/expected")
def expected(user: User = Depends(require_roles("plant")), db: Session = Depends(get_db)):
    """Tankers heading to this plant. The pumped volume is deliberately NOT shown, so staff measure independently."""
    trips = db.scalars(select(Trip).where(Trip.plant_id == user.plant_id, Trip.status.in_(ACTIVE_TRIP)).order_by(Trip.started_at))
    return [{"trip_id": t.id, "status": t.status, "plate": t.vehicle.plate, "driver": t.driver.name,
             "started_at": t.started_at, "stops": len(t.stops)} for t in trips]


@router.post("/disposals", status_code=201)
def confirm_load(body: DisposalIn, user: User = Depends(require_roles("plant")), db: Session = Depends(get_db)):
    plant = db.get(Plant, user.plant_id) if user.plant_id else None
    trip = db.get(Trip, body.trip_id)
    if not plant or not trip:
        raise HTTPException(404, "trip or plant not found")
    try:
        d = verification.verify_disposal(db, trip, plant, body.volume_received_litres, user.id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    audit.log(db, user, "confirm_load", f"trip:{trip.id}", result=d.result)
    db.commit()
    return {"trip_id": trip.id, "result": d.result, "trip_status": trip.status}
