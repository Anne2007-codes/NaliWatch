import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..config import settings
from ..db import SessionLocal
from ..models import User
from ..security import decode_token

router = APIRouter(tags=["live"])


@router.websocket("/ws/live")
async def live(ws: WebSocket, token: str):
    """Live map/trip updates for ward officers and admins. Connect with ?token=<JWT>."""
    try:
        uid = int(decode_token(token)["sub"])
        with SessionLocal() as db:
            user = db.get(User, uid)
            role, ward = (user.role, user.ward) if user and user.active else (None, None)
    except Exception:
        role = ward = None
    if role not in ("officer", "admin"):
        await ws.close(code=4401)
        return
    await ws.accept()
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe("naliwatch:live")
    try:
        async for m in pubsub.listen():
            if m["type"] != "message":
                continue
            ev = json.loads(m["data"])
            if role == "officer" and ev.get("ward") not in (None, ward):
                continue
            await ws.send_json(ev)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.close()
        await client.aclose()
