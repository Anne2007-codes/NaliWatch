from .geo import latlng, to_geojson
from .models import Job, Report, Tank, Trip, User
from .services import storage


def tank_out(t: Tank) -> dict:
    lat, lng = latlng(t.prop.location)
    return {"id": t.id, "property_id": t.property_id, "address": t.prop.address, "lat": lat, "lng": lng,
            "ward": t.prop.ward, "household_size": t.prop.household_size, "capacity_litres": t.capacity_litres,
            "type": t.type, "install_year": t.install_year, "last_emptied": t.last_emptied,
            "predicted_due": t.predicted_due, "qr_code": t.qr_code}


def report_out(r: Report, viewer: User) -> dict:
    lat, lng = latlng(r.location)
    out = {"id": r.id, "type": r.type, "severity": r.severity, "confidence": r.confidence, "summary": r.summary,
           "text": r.text, "status": r.status, "ward": r.ward, "lat": lat, "lng": lng, "source": r.source,
           "tank_id": r.tank_id, "duplicate_of_id": r.duplicate_of_id, "created_at": r.created_at,
           "resolved_at": r.resolved_at, "officer_note": r.officer_note}
    if viewer.role in ("officer", "admin"):  # reporter identity and AI reasoning stay with municipal staff
        out["ai_reason"] = r.ai_reason
        out["transcript"] = r.transcript
        out["photo_url"] = storage.signed_url(r.photo_key) if r.photo_key else None
    return out


def job_out(j: Job, viewer: User) -> dict:
    lat, lng = latlng(j.location)
    out = {"id": j.id, "tank_id": j.tank_id, "status": j.status, "source": j.source, "urgent": j.urgent,
           "priority_score": j.priority_score, "priority_reason": j.priority_reason, "ward": j.ward, "lat": lat,
           "lng": lng, "window_start": j.window_start, "window_end": j.window_end,
           "estimated_litres": j.estimated_litres, "operator_id": j.operator_id, "created_at": j.created_at,
           "assigned_at": j.assigned_at, "completed_at": j.completed_at}
    if j.tank:
        out["address"] = j.tank.prop.address
        out["capacity_litres"] = j.tank.capacity_litres
    if j.report and viewer.role != "household":  # no reporter identity here, ever
        out["report"] = {"id": j.report.id, "type": j.report.type, "severity": j.report.severity,
                         "summary": j.report.summary}
    return out


def trip_out(t: Trip, viewer: User) -> dict:
    stops = []
    for s in t.stops:
        lat, lng = latlng(s.job.location)
        stops.append({"id": s.id, "sequence": s.sequence, "job_id": s.job_id, "lat": lat, "lng": lng,
                      "address": s.job.tank.prop.address if s.job.tank else None,
                      "estimated_litres": s.job.estimated_litres, "arrival_time": s.arrival_time,
                      "volume_pumped_litres": s.volume_pumped_litres, "otp_confirmed": s.otp_confirmed,
                      "confirmed": s.confirmed_at is not None})
    return {"id": t.id, "status": t.status, "planned_date": t.planned_date, "operator_id": t.operator_id,
            "vehicle": {"id": t.vehicle.id, "plate": t.vehicle.plate, "capacity_litres": t.vehicle.capacity_litres},
            "driver": {"id": t.driver.id, "name": t.driver.name}, "plant": {"id": t.plant.id, "name": t.plant.name},
            "planned_route": t.planned_route, "planned_distance_m": t.planned_distance_m,
            "started_at": t.started_at, "finished_at": t.finished_at, "stops": stops}
