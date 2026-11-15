from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import current_user, require_roles
from ..geo import from_geojson, latlng, point, to_geojson
from ..models import AuditLog, Driver, Operator, Plant, User, Vehicle, Ward
from ..schemas import (DriverCreate, OperatorCreate, OperatorPatch, PlantCreate, UserCreate, VehicleCreate, WardCreate)
from ..security import normalize_phone

router = APIRouter(tags=["admin"])


def _op_out(o: Operator) -> dict:
    return {"id": o.id, "company": o.company, "certification_number": o.certification_number,
            "valid_until": o.valid_until, "status": o.status, "phone": o.phone,
            "depot": dict(zip(("lat", "lng"), latlng(o.depot))) if o.depot is not None else None}


def _own_operator(db: Session, user: User, operator_id: int) -> Operator:
    op = db.get(Operator, operator_id)
    if not op or (user.role == "operator" and user.operator_id != operator_id):
        raise HTTPException(404, "operator not found")
    return op


# ---- users ----
@router.post("/admin/users", status_code=201)
def create_user(body: UserCreate, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    u = db.scalar(select(User).where(User.phone == phone)) or User(phone=phone)
    u.name, u.role, u.ward, u.operator_id, u.plant_id = body.name, body.role, body.ward, body.operator_id, body.plant_id
    db.add(u)
    db.flush()
    audit.log(db, admin, "set_role", f"user:{u.id}", role=u.role)
    db.commit()
    return {"id": u.id, "phone": u.phone, "role": u.role, "ward": u.ward}


# ---- wards and plants ----
@router.post("/admin/wards", status_code=201)
def create_ward(body: WardCreate, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    w = Ward(name=body.name, boundary=from_geojson(body.boundary))
    db.add(w)
    db.commit()
    return {"id": w.id, "name": w.name}


@router.post("/admin/plants", status_code=201)
def create_plant(body: PlantCreate, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    p = Plant(name=body.name, authorization_number=body.authorization_number, geofence=from_geojson(body.geofence),
              valid_until=body.valid_until)
    db.add(p)
    db.flush()
    audit.log(db, admin, "create", f"plant:{p.id}")
    db.commit()
    return {"id": p.id, "name": p.name}


@router.get("/plants")
def list_plants(user: User = Depends(require_roles("officer", "operator")), db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "authorization_number": p.authorization_number, "valid_until": p.valid_until,
             "status": p.status, "geofence": to_geojson(p.geofence)} for p in db.scalars(select(Plant))]


# ---- operators, vehicles, drivers ----
@router.post("/operators", status_code=201)
def create_operator(body: OperatorCreate, admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    depot = point(body.depot_lat, body.depot_lng) if body.depot_lat is not None and body.depot_lng is not None else None
    o = Operator(company=body.company, certification_number=body.certification_number, valid_until=body.valid_until,
                 phone=body.phone, depot=depot)
    db.add(o)
    db.flush()
    audit.log(db, admin, "create", f"operator:{o.id}")
    db.commit()
    return _op_out(o)


@router.get("/operators")
def list_operators(user: User = Depends(require_roles("officer", "operator")), db: Session = Depends(get_db)):
    q = select(Operator)
    if user.role == "operator":
        q = q.where(Operator.id == user.operator_id)
    return [_op_out(o) for o in db.scalars(q)]


@router.patch("/operators/{operator_id}")
def patch_operator(operator_id: int, body: OperatorPatch, admin: User = Depends(require_roles()),
                   db: Session = Depends(get_db)):
    o = db.get(Operator, operator_id)
    if not o:
        raise HTTPException(404, "operator not found")
    d = body.model_dump(exclude_unset=True)
    for k, v in d.items():
        setattr(o, k, v)
    audit.log(db, admin, "update", f"operator:{o.id}", fields=d)
    db.commit()
    return _op_out(o)


@router.post("/operators/{operator_id}/vehicles", status_code=201)
def add_vehicle(operator_id: int, body: VehicleCreate, user: User = Depends(require_roles("operator")),
                db: Session = Depends(get_db)):
    op = _own_operator(db, user, operator_id)
    v = Vehicle(operator_id=op.id, plate=body.plate.upper(), capacity_litres=body.capacity_litres)
    db.add(v)
    db.commit()
    return {"id": v.id, "plate": v.plate, "capacity_litres": v.capacity_litres}


@router.post("/operators/{operator_id}/drivers", status_code=201)
def add_driver(operator_id: int, body: DriverCreate, user: User = Depends(require_roles("operator")),
               db: Session = Depends(get_db)):
    op = _own_operator(db, user, operator_id)
    phone = normalize_phone(body.phone)
    u = db.scalar(select(User).where(User.phone == phone)) or User(phone=phone)
    if u.role in ("admin", "officer", "plant", "operator"):
        raise HTTPException(409, "that phone belongs to another staff role")
    u.name, u.role, u.operator_id = body.name, "driver", op.id
    db.add(u)
    db.flush()
    d = Driver(user_id=u.id, operator_id=op.id, name=body.name, licence=body.licence)
    db.add(d)
    db.commit()
    return {"id": d.id, "user_id": u.id, "name": d.name}


# ---- audit ----
@router.get("/admin/audit-log")
def audit_log(record: str | None = None, limit: int = Query(100, le=500), admin: User = Depends(require_roles()),
              db: Session = Depends(get_db)):
    q = select(AuditLog)
    if record:
        q = q.where(AuditLog.record == record)
    return [{"id": a.id, "actor_id": a.actor_id, "action": a.action, "record": a.record, "detail": a.detail, "at": a.at}
            for a in db.scalars(q.order_by(AuditLog.at.desc()).limit(limit))]
