import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings


def normalize_phone(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return "+" + digits


def gen_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(scope: str, code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), f"{scope}:{code}".encode(), hashlib.sha256).hexdigest()


def create_token(user) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
