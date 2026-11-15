from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OtpRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=16)


class OtpVerify(OtpRequest):
    otp: str = Field(min_length=6, max_length=6)
    name: str | None = None
    language: str | None = None
    consent: bool = False


class UserCreate(BaseModel):
    phone: str = Field(min_length=10, max_length=16)
    name: str | None = None
    role: Literal["household", "reporter", "asha", "operator", "driver", "plant", "officer", "admin"]
    ward: str | None = None
    operator_id: int | None = None
    plant_id: int | None = None


class TankCreate(BaseModel):
    address: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    capacity_litres: int = Field(gt=0, le=100000)
    type: str = "septic"
    install_year: int | None = Field(None, ge=1950, le=2100)
    last_emptied: date | None = None
    household_size: int = Field(4, ge=1, le=100)
    ward: str | None = None
    consent: bool = False
    owner_phone: str | None = None   # when an operator or ward officer registers on the owner's behalf
    owner_name: str | None = None


class TankUpdate(BaseModel):
    capacity_litres: int | None = Field(None, gt=0, le=100000)
    last_emptied: date | None = None
    household_size: int | None = Field(None, ge=1, le=100)
    install_year: int | None = None
    address: str | None = None


class JobCreate(BaseModel):
    tank_id: int
    window_start: date | None = None
    window_end: date | None = None


class HealthCreate(BaseModel):
    case_count: int = Field(ge=1, le=1000)
    symptoms: list[str] = []
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ReportPatch(BaseModel):
    type: Literal["overflow", "dumping", "manual_cleaning", "other"] | None = None
    severity: int | None = Field(None, ge=1, le=3)
    status: Literal["triaged", "needs_review", "resolved", "rejected"] | None = None
    note: str | None = None


class FlagDecision(BaseModel):
    decision: Literal["confirmed", "dismissed", "needs_more_info"]
    note: str | None = None


class OperatorCreate(BaseModel):
    company: str
    certification_number: str
    valid_until: date
    phone: str | None = None
    depot_lat: float | None = None
    depot_lng: float | None = None


class OperatorPatch(BaseModel):
    status: Literal["active", "suspended"] | None = None
    valid_until: date | None = None
    certification_number: str | None = None


class VehicleCreate(BaseModel):
    plate: str
    capacity_litres: int = Field(gt=0)


class DriverCreate(BaseModel):
    phone: str = Field(min_length=10, max_length=16)
    name: str
    licence: str | None = None


class PlantCreate(BaseModel):
    name: str
    authorization_number: str
    geofence: dict  # GeoJSON Polygon geometry
    valid_until: date


class WardCreate(BaseModel):
    name: str
    boundary: dict  # GeoJSON Polygon or MultiPolygon geometry


class PlanRequest(BaseModel):
    operator_id: int | None = None
    plan_date: date | None = None


class StartTrip(BaseModel):
    consent_gps: bool


class GpsIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    recorded_at: datetime


class GpsBatch(BaseModel):
    points: list[GpsIn] = Field(max_length=500)


class StopConfirm(BaseModel):
    otp: str | None = None
    volume_pumped_litres: int = Field(gt=0, le=100000)
    lat: float | None = None
    lng: float | None = None


class DisposalIn(BaseModel):
    trip_id: int
    volume_received_litres: int = Field(gt=0, le=1000000)
