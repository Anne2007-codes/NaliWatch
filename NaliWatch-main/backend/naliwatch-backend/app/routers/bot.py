import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response

from ..config import settings
from ..db import session_scope
from ..services import bot_core, channels
from ..services.bot_core import Incoming

router = APIRouter(prefix="/bot", tags=["bot"])
log = logging.getLogger(__name__)


def _process(msg: Incoming, send) -> None:
    try:
        with session_scope() as db:
            reply = bot_core.handle(db, msg)
        send(reply)
    except Exception:
        log.exception("bot handling failed")


# ---------------- Telegram (hackathon demo) ----------------
@router.post("/telegram")
async def telegram_webhook(request: Request, bg: BackgroundTasks,
                           x_telegram_bot_api_secret_token: str | None = Header(None)):
    if not settings.telegram_webhook_secret or not hmac.compare_digest(
            x_telegram_bot_api_secret_token or "", settings.telegram_webhook_secret):
        raise HTTPException(403, "bad secret")
    update = await request.json()
    m = update.get("message") or {}
    if not m:
        return {"ok": True}
    chat = str(m["chat"]["id"])
    msg = Incoming(sender=f"tg:{chat}", text=m.get("text") or m.get("caption"),
                   display_name=(m.get("from") or {}).get("first_name"))
    if "location" in m:
        msg.lat, msg.lng = m["location"]["latitude"], m["location"]["longitude"]
    if m.get("photo"):
        fid = m["photo"][-1]["file_id"]
        msg.get_photo = lambda: channels.tg_download(fid)
    if m.get("voice"):
        fid = m["voice"]["file_id"]
        msg.get_audio = lambda: (channels.tg_download(fid), "voice.ogg")
    bg.add_task(_process, msg, lambda text: channels.tg_send(chat, text))
    return {"ok": True}


# ---------------- WhatsApp Cloud API (pilot) ----------------
@router.get("/whatsapp")
def whatsapp_verify(hub_mode: str = Query(None, alias="hub.mode"), hub_token: str = Query(None, alias="hub.verify_token"),
                    hub_challenge: str = Query(None, alias="hub.challenge")):
    if hub_mode == "subscribe" and settings.whatsapp_verify_token and hmac.compare_digest(
            hub_token or "", settings.whatsapp_verify_token):
        return Response(hub_challenge, media_type="text/plain")
    raise HTTPException(403, "verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request, bg: BackgroundTasks, x_hub_signature_256: str | None = Header(None)):
    raw = await request.body()
    if settings.whatsapp_app_secret:
        want = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(want, x_hub_signature_256 or ""):
            raise HTTPException(403, "bad signature")
    body = await request.json()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            val = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in val.get("contacts", [])}
            for m in val.get("messages", []):
                sender = "+" + m["from"]
                msg = Incoming(sender=sender, display_name=names.get(m["from"]))
                t = m.get("type")
                if t == "text":
                    msg.text = m["text"]["body"]
                elif t == "image":
                    mid = m["image"]["id"]
                    msg.text = m["image"].get("caption")
                    msg.get_photo = lambda mid=mid: channels.wa_download(mid)
                elif t == "audio":
                    mid = m["audio"]["id"]
                    msg.get_audio = lambda mid=mid: (channels.wa_download(mid), "voice.ogg")
                elif t == "location":
                    msg.lat, msg.lng = m["location"]["latitude"], m["location"]["longitude"]
                else:
                    continue
                bg.add_task(_process, msg, lambda text, s=sender: channels.wa_send_text(s, text))
    return {"ok": True}
