from datetime import date, datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

TS = DateTime(timezone=True)


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---- role / status vocab (plain strings in the DB) ----
ROLES = ("household", "reporter", "asha", "operator", "driver", "plant", "officer", "admin")
REPORT_TYPES = ("overflow", "dumping", "manual_cleaning", "other")
OPEN_REPORT = ("triaged", "needs_review", "job_created")
OPEN_JOB = ("offered", "scheduled", "routed", "in_progress")
ACTIVE_TRIP = ("in_progress", "awaiting_plant")


class Ward(Base):
    __tablename__ = "wards"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    boundary = mapped_column(Geometry("GEOMETRY", srid=4326))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="household", index=True)
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))
    plant_id: Mapped[int | None] = mapped_column(ForeignKey("plants.id"))
    consent_at: Mapped[datetime | None] = mapped_column(TS)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    address: Mapped[str] = mapped_column(Text)
    location = mapped_column(Geometry("POINT", srid=4326))
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    household_size: Mapped[int] = mapped_column(Integer, default=4)
    owner: Mapped["User"] = relationship()
    tanks: Mapped[list["Tank"]] = relationship(back_populates="prop")


class Tank(Base):
    __tablename__ = "tanks"
    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    capacity_litres: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(30), default="septic")
    install_year: Mapped[int | None] = mapped_column(Integer)
    last_emptied: Mapped[date | None] = mapped_column(Date)
    predicted_due: Mapped[date | None] = mapped_column(Date, index=True)
    qr_code: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)
    prop: Mapped["Property"] = relationship(back_populates="tanks")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), default="other")
    severity: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ai_reason: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(60))
    summary: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    photo_key: Mapped[str | None] = mapped_column(String(200))
    location = mapped_column(Geometry("POINT", srid=4326))
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(20), default="api")
    status: Mapped[str] = mapped_column(String(20), default="triaged", index=True)
    tank_id: Mapped[int | None] = mapped_column(ForeignKey("tanks.id"))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    officer_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=now, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)


class HealthSignal(Base):
    __tablename__ = "health_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    case_count: Mapped[int] = mapped_column(Integer)
    symptoms: Mapped[list | None] = mapped_column(JSON)
    location = mapped_column(Geometry("POINT", srid=4326))
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    reported_at: Mapped[datetime] = mapped_column(TS, default=now, index=True)


class Cluster(Base):
    __tablename__ = "clusters"
    id: Mapped[int] = mapped_column(primary_key=True)
    center = mapped_column(Geometry("POINT", srid=4326))
    radius_m: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10))  # risk | watch
    score: Mapped[float] = mapped_column(Float)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    ward: Mapped[str | None] = mapped_column(String(100))
    computed_at: Mapped[datetime] = mapped_column(TS, default=now)


class Operator(Base):
    __tablename__ = "operators"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200))
    certification_number: Mapped[str] = mapped_column(String(100))
    valid_until: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    phone: Mapped[str | None] = mapped_column(String(32))
    depot = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="operator")
    drivers: Mapped[list["Driver"]] = relationship(back_populates="operator")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), index=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    capacity_litres: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    operator: Mapped["Operator"] = relationship(back_populates="vehicles")


class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    licence: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="active")
    operator: Mapped["Operator"] = relationship(back_populates="drivers")
    user: Mapped["User"] = relationship()


class Plant(Base):
    __tablename__ = "plants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    authorization_number: Mapped[str] = mapped_column(String(100))
    geofence = mapped_column(Geometry("POLYGON", srid=4326))
    valid_until: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tank_id: Mapped[int | None] = mapped_column(ForeignKey("tanks.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"))
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    source: Mapped[str] = mapped_column(String(20), default="prediction")
    urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_reason: Mapped[list | None] = mapped_column(JSON)
    location = mapped_column(Geometry("POINT", srid=4326))
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    estimated_litres: Mapped[int] = mapped_column(Integer, default=1000)
    declined_operator_ids: Mapped[list] = mapped_column(JSON, default=list)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TS, default=now)
    assigned_at: Mapped[datetime | None] = mapped_column(TS)
    scheduled_at: Mapped[datetime | None] = mapped_column(TS)
    completed_at: Mapped[datetime | None] = mapped_column(TS)
    tank: Mapped["Tank | None"] = relationship()
    report: Mapped["Report | None"] = relationship()


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"))
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    planned_date: Mapped[date] = mapped_column(Date)
    planned_route: Mapped[list | None] = mapped_column(JSON)  # [[lat,lng], ...] depot, stops..., plant
    planned_distance_m: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)
    stops: Mapped[list["TripStop"]] = relationship(
        back_populates="trip", order_by="TripStop.sequence", cascade="all, delete-orphan"
    )
    vehicle: Mapped["Vehicle"] = relationship()
    driver: Mapped["Driver"] = relationship()
    plant: Mapped["Plant"] = relationship()
    operator: Mapped["Operator"] = relationship()


class TripStop(Base):
    __tablename__ = "trip_stops"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    arrival_time: Mapped[datetime | None] = mapped_column(TS)
    volume_pumped_litres: Mapped[int | None] = mapped_column(Integer)
    otp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(TS)
    confirm_location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    trip: Mapped["Trip"] = relationship(back_populates="stops")
    job: Mapped["Job"] = relationship()


class GpsPoint(Base):
    __tablename__ = "gps_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    location = mapped_column(Geometry("POINT", srid=4326))
    recorded_at: Mapped[datetime] = mapped_column(TS)
    __table_args__ = (Index("ix_gps_trip_time", "trip_id", "recorded_at"),)


class Disposal(Base):
    __tablename__ = "disposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), unique=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"))
    arrival_time: Mapped[datetime] = mapped_column(TS)
    volume_received_litres: Mapped[int] = mapped_column(Integer)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    result: Mapped[str] = mapped_column(String(20))  # matched | mismatch
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)


class Flag(Base):
    __tablename__ = "flags"
    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id"), index=True)
    reason: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ward: Mapped[str | None] = mapped_column(String(100), index=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str | None] = mapped_column(String(30))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(TS)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    record: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict | None] = mapped_column(JSON)
    at: Mapped[datetime] = mapped_column(TS, default=now, index=True)
