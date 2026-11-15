from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=True)


def current_user(creds=Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(creds.credentials)
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(401, "invalid or expired token")
    if not user or not user.active:
        raise HTTPException(401, "inactive user")
    # Session variables for the optional Postgres RLS policies in sql/rls_example.sql
    db.execute(
        text("SELECT set_config('app.user_id', :u, true), set_config('app.role', :r, true), set_config('app.ward', :w, true)"),
        {"u": str(user.id), "r": user.role, "w": user.ward or ""},
    )
    return user


def require_roles(*roles: str):
    allowed = set(roles) | {"admin"}

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "your role cannot do this")
        return user

    return dep


def ward_clause(user: User, column):
    """Officers only see their own ward. Admin (and everyone else handled by the caller) gets no filter."""
    if user.role == "officer":
        return column == user.ward
    return None
