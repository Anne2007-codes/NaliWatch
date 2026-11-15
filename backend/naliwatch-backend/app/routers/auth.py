import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import kv
from ..config import settings
from ..db import get_db
from ..deps import current_user
from ..models import User
from ..schemas import OtpRequest, OtpVerify
from ..security import create_token, gen_otp, hash_otp, normalize_phone
from ..services import notifications

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "phone": u.phone, "name": u.name, "role": u.role, "ward": u.ward, "language": u.language,
            "operator_id": u.operator_id, "plant_id": u.plant_id}


@router.post("/otp/request")
def request_otp(body: OtpRequest):
    phone = normalize_phone(body.phone)
    if not kv.rate_limit(f"rl:otp:{phone}", 5, 3600):
        raise HTTPException(429, "too many code requests, try later")
    code = gen_otp()
    kv.r.setex(f"otp:{phone}", settings.otp_ttl_seconds, hash_otp(phone, code))
    kv.r.delete(f"otp_try:{phone}")
    notifications.send_login_otp(phone, code)
    return {"sent": True, **({"dev_otp": code} if settings.otp_dev_echo else {})}


@router.post("/otp/verify")
def verify_otp(body: OtpVerify, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    tries = kv.r.incr(f"otp_try:{phone}")
    kv.r.expire(f"otp_try:{phone}", settings.otp_ttl_seconds)
    if tries > 5:
        raise HTTPException(429, "too many attempts")
    stored = kv.r.get(f"otp:{phone}")
    if not stored or not hmac.compare_digest(stored, hash_otp(phone, body.otp)):
        raise HTTPException(401, "wrong or expired code")
    kv.r.delete(f"otp:{phone}", f"otp_try:{phone}")
    user = db.scalar(select(User).where(User.phone == phone))
    if not user:
        user = User(phone=phone, role="household")
        db.add(user)
    if body.name and not user.name:
        user.name = body.name
    if body.language:
        user.language = body.language
    if body.consent and not user.consent_at:
        user.consent_at = datetime.now(timezone.utc)
    db.commit()
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
