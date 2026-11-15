import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, require_roles, ward_clause
from ..geo import assign_ward, point
from ..models import Job, Property, Tank, User
from ..schemas import TankCreate, TankUpdate
from ..security import normalize_phone
from ..serializers import tank_out
from ..services.prediction import predict_due_date

router = APIRouter(prefix="/tanks", tags=["tanks"])


def _can_view(db: Session, user: User, tank: Tank) -> bool:
    if user.role == "admin":
        return True
    if user.role == "household":
        return tank.prop.owner_id == user.id
    if user.role == "officer":
        return tank.prop.ward == user.ward
    if user.role == "operator":
        return db.scalar(select(Job.id).where(Job.tank_id == tank.id, Job.operator_id == user.operator_id).limit(1)) is not None
    return False


@router.post("", status_code=201)
def register_tank(body: TankCreate, user: User = Depends(require_roles("household", "operator", "officer")),
                  db: Session = Depends(get_db)):
    if not body.consent:
        raise HTTPException(400, "owner consent is required to register a tank")
    owner = user
    if user.role != "household":
        if not body.owner_phone:
            raise HTTPException(400, "owner_phone is required when registering for a household")
        phone = normalize_phone(body.owner_phone)
        owner = db.scalar(select(User).where(User.phone == phone))
        if not owner:
            owner = User(phone=phone, name=body.owner_name, role="household")
            db.add(owner)
            db.flush()
    if not owner.consent_at:
        owner.consent_at = datetime.now(timezone.utc)
    prop = Property(owner_id=owner.id, address=body.address, location=point(body.lat, body.lng),
                    ward=body.ward or assign_ward(db, body.lat, body.lng), household_size=body.household_size)
    tank = Tank(prop=prop, capacity_litres=body.capacity_litres, type=body.type, install_year=body.install_year,
                last_emptied=body.last_emptied, qr_code=secrets.token_urlsafe(6))
    tank.predicted_due = predict_due_date(body.last_emptied, body.capacity_litres, body.household_size, body.install_year)
    db.add_all([prop, tank])
    db.flush()
    audit.log(db, user, "create", f"tank:{tank.id}")
    db.commit()
    return tank_out(tank)


@router.get("")
def list_tanks(limit: int = Query(50, le=200), offset: int = 0, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    q = select(Tank).join(Property, Tank.property_id == Property.id)
    if user.role == "household":
        q = q.where(Property.owner_id == user.id)
    elif user.role == "officer":
        q = q.where(ward_clause(user, Property.ward))
    elif user.role == "operator":
        q = q.where(Tank.id.in_(select(Job.tank_id).where(Job.operator_id == user.operator_id, Job.tank_id.isnot(None))))
    elif user.role != "admin":
        raise HTTPException(403, "forbidden")
    return [tank_out(t) for t in db.scalars(q.order_by(Tank.id).limit(limit).offset(offset))]


@router.get("/by-qr/{code}")
def by_qr(code: str, user: User = Depends(require_roles("operator", "officer")), db: Session = Depends(get_db)):
    tank = db.scalar(select(Tank).where(Tank.qr_code == code))
    if not tank or not _can_view(db, user, tank):
        raise HTTPException(404, "tank not found")
    audit.log(db, user, "view", f"tank:{tank.id}")
    db.commit()
    return tank_out(tank)


@router.get("/{tank_id}")
def get_tank(tank_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tank = db.get(Tank, tank_id)
    if not tank or not _can_view(db, user, tank):
        raise HTTPException(404, "tank not found")
    audit.log(db, user, "view", f"tank:{tank.id}")
    db.commit()
    return tank_out(tank)


@router.patch("/{tank_id}")
def update_tank(tank_id: int, body: TankUpdate, user: User = Depends(require_roles("household", "officer")),
                db: Session = Depends(get_db)):
    tank = db.get(Tank, tank_id)
    if not tank or not _can_view(db, user, tank):
        raise HTTPException(404, "tank not found")
    d = body.model_dump(exclude_unset=True)
    for k in ("capacity_litres", "last_emptied", "install_year"):
        if k in d:
            setattr(tank, k, d[k])
    if "household_size" in d:
        tank.prop.household_size = d["household_size"]
    if "address" in d:
        tank.prop.address = d["address"]
    tank.predicted_due = predict_due_date(tank.last_emptied, tank.capacity_litres, tank.prop.household_size, tank.install_year)
    audit.log(db, user, "update", f"tank:{tank.id}", fields=list(d))
    db.commit()
    return tank_out(tank)
