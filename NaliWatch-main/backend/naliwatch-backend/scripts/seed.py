"""Seed one demo ward with tanks, operator, plant, reports and sickness counts.
Run from the backend root:  python -m scripts.seed [--reset]
Demo coordinates are around Pune; change them to your pilot ward."""
import random
import sys
from datetime import date, timedelta

from sqlalchemy import select

from app.db import Base, SessionLocal, engine, init_db
from app.geo import assign_ward, from_geojson, point
from app.models import (Driver, HealthSignal, Operator, Plant, Property, Report, Tank, User, Vehicle, Ward, now)
from app.services import clustering, prediction, scheduling

random.seed(7)
LAT0, LAT1, LNG0, LNG1 = 18.500, 18.530, 73.840, 73.880


def box(lat, lng, d):
    return {"type": "Polygon", "coordinates": [[[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]]}


def jitter(lat, lng, metres):
    return lat + random.uniform(-metres, metres) / 111000, lng + random.uniform(-metres, metres) / 105000


def user(db, phone, role, name, **kw):
    u = db.scalar(select(User).where(User.phone == phone)) or User(phone=phone)
    u.role, u.name, u.consent_at = role, name, now()
    for k, v in kw.items():
        setattr(u, k, v)
    db.add(u)
    db.flush()
    return u


def main():
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as db:
        ward = "Ward 12 (demo)"
        db.add(Ward(name=ward, boundary=from_geojson({"type": "Polygon", "coordinates": [[[LNG0, LAT0], [LNG1, LAT0], [LNG1, LAT1], [LNG0, LAT1], [LNG0, LAT0]]]})))
        plant = Plant(name="Demo STP", authorization_number="STP-001", geofence=from_geojson(box(18.490, 73.900, 0.003)),
                      valid_until=date.today() + timedelta(days=365))
        op = Operator(company="CleanFlow Desludging", certification_number="CERT-1001", valid_until=date.today() + timedelta(days=365),
                      phone="+919000000003", depot=point(18.505, 73.845))
        db.add_all([plant, op])
        db.flush()
        for plate, cap in (("MH12AB1001", 6000), ("MH12AB1002", 4000)):
            db.add(Vehicle(operator_id=op.id, plate=plate, capacity_litres=cap))
        user(db, "+919000000001", "admin", "Admin")
        user(db, "+919000000002", "officer", "Ward Officer", ward=ward)
        user(db, "+919000000003", "operator", "Operator Manager", operator_id=op.id)
        for i, ph in enumerate(("+919000000004", "+919000000005"), start=1):
            u = user(db, ph, "driver", f"Driver {i}", operator_id=op.id)
            db.add(Driver(user_id=u.id, operator_id=op.id, name=u.name, licence=f"DL-{i}"))
        user(db, "+919000000006", "plant", "Plant Staff", plant_id=plant.id)
        asha = user(db, "+919000000007", "asha", "ASHA Worker", ward=ward)
        reporter = user(db, "+919000000008", "reporter", "Volunteer")

        for i in range(40):
            owner = user(db, f"+9191000000{i:02d}", "household", f"Household {i}")
            lat, lng = random.uniform(LAT0, LAT1), random.uniform(LNG0, LNG1)
            last = date.today() - timedelta(days=random.randint(300, 2200))
            size, cap = random.randint(3, 8), random.choice((2000, 3000, 5000))
            prop = Property(owner_id=owner.id, address=f"House {i + 1}, Lane {i % 7 + 1}, {ward}", location=point(lat, lng), ward=ward, household_size=size)
            tank = Tank(prop=prop, capacity_litres=cap, last_emptied=last, qr_code=f"DEMO{i:03d}")
            tank.predicted_due = prediction.predict_due_date(last, cap, size)
            db.add_all([prop, tank])

        clat, clng = 18.515, 73.860  # a hotspot: failures and sickness overlap here
        for _ in range(5):
            lat, lng = jitter(clat, clng, 40)
            db.add(Report(reporter_id=reporter.id, type="overflow", severity=random.randint(2, 3), confidence=0.9,
                          ai_reason="seeded", summary="Tank overflowing onto the lane", location=point(lat, lng),
                          ward=assign_ward(db, lat, lng), source="seed", status="triaged"))
        for n in (4, 3):
            lat, lng = jitter(clat, clng, 60)
            db.add(HealthSignal(reporter_id=asha.id, case_count=n, symptoms=["diarrhoea", "fever"], location=point(lat, lng), ward=ward))
        db.flush()
        clustering.recompute_clusters(db)
        prediction.refresh_predictions(db)
        created = prediction.ensure_due_jobs(db, horizon_days=30)
        db.flush()
        offered = scheduling.assign_operators(db)
        db.commit()
        print(f"seeded: {len(created)} jobs created, {len(offered)} offered to the operator")
        print("logins (OTP login, set OTP_DEV_ECHO=true): admin +919000000001, officer +919000000002, operator +919000000003,")
        print("  drivers +919000000004 / +919000000005, plant staff +919000000006, ASHA +919000000007")


if __name__ == "__main__":
    main()
