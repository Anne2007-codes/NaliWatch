"""Channel-neutral chat flow for WhatsApp and Telegram.
A person sends a location plus a photo, voice note or text; the report is created once both are present.
ASHA workers send `sick <count> <symptoms>` after sharing a location."""
import json
import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select

from .. import kv
from ..errors import RateLimited, Rejected
from ..geo import assign_ward, point
from ..models import HealthSignal, User, now
from ..security import normalize_phone
from . import intake

TTL = 1800

WELCOME = (
    "NaliWatch\n"
    "Send the place (📎 > Location) and a photo, voice note or message about the septic tank problem. "
    "Do not send photos of faces or the inside of homes. By sending a report you agree that NaliWatch stores it to "
    "fix the problem.\n\n"
    "NaliWatch: problem ki jagah (📎 > Location) bhejiye aur photo, voice note ya message bhejiye. "
    "Chehre ya ghar ke andar ki photo na bhejein."
)


@dataclass
class Incoming:
    sender: str                      # "tg:<chat id>" or "+<phone>"
    text: str | None = None
    lat: float | None = None
    lng: float | None = None
    get_photo: Callable[[], bytes] | None = None
    get_audio: Callable[[], tuple[bytes, str]] | None = None
    display_name: str | None = None


def get_or_create_user(db, sender: str, name: str | None) -> User:
    phone = sender if sender.startswith("tg:") else normalize_phone(sender)
    u = db.scalar(select(User).where(User.phone == phone))
    if not u:
        u = User(phone=phone, name=name, role="reporter")
        db.add(u)
        db.flush()
    return u


def _clear(sender: str) -> None:
    kv.r.delete(f"bot:{sender}")
    kv.rb.delete(f"botphoto:{sender}", f"botaudio:{sender}")


def handle(db, msg: Incoming) -> str:
    user = get_or_create_user(db, msg.sender, msg.display_name)
    text = (msg.text or "").strip()
    low = text.lower()
    if low in ("/start", "start", "hi", "hello", "help", "/help", "namaste", "नमस्ते"):
        return WELCOME
    if low in ("/cancel", "cancel"):
        _clear(msg.sender)
        return "Cancelled. / Radd kiya."

    key = f"bot:{msg.sender}"
    state = json.loads(kv.r.get(key) or "{}")
    if msg.lat is not None and msg.lng is not None:
        state["lat"], state["lng"] = msg.lat, msg.lng

    m = re.match(r"^/?sick\s+(\d+)\s*(.*)$", low)
    if m:
        if user.role != "asha":
            return "Only registered ASHA workers can send sickness counts."
        if "lat" not in state:
            return "Please share the location of the lane or area first (📎 > Location), then send the message again."
        h = HealthSignal(reporter_id=user.id, case_count=int(m.group(1)), location=point(state["lat"], state["lng"]),
                         symptoms=[s.strip() for s in re.split(r"[,\s]+", m.group(2)) if s.strip()],
                         ward=assign_ward(db, state["lat"], state["lng"]), reported_at=now())
        db.add(h)
        kv.r.setex(key, TTL, json.dumps(state))
        return f"Recorded {h.case_count} cases for this area. Thank you."

    if text:
        state["text"] = f"{state.get('text', '')} {text}".strip()
    if msg.get_photo:
        kv.rb.setex(f"botphoto:{msg.sender}", TTL, msg.get_photo())
        state["has_photo"] = True
    if msg.get_audio:
        data, name = msg.get_audio()
        kv.rb.setex(f"botaudio:{msg.sender}", TTL, data)
        state["audio_name"] = name
        state["has_audio"] = True
    kv.r.setex(key, TTL, json.dumps(state))

    has_evidence = state.get("text") or state.get("has_photo") or state.get("has_audio")
    if "lat" not in state:
        return "Got it. Now share the location (📎 > Location). / Ab location bhejiye."
    if not has_evidence:
        return "Location saved. Now send a photo, a voice note or a message. / Ab photo, voice note ya message bhejiye."

    photo = kv.rb.get(f"botphoto:{msg.sender}")
    audio = kv.rb.get(f"botaudio:{msg.sender}")
    try:
        res = intake.create_report(db, user, lat=state["lat"], lng=state["lng"], text=state.get("text"), photo=photo,
                                   audio=audio, audio_name=state.get("audio_name", "voice.ogg"),
                                   source="telegram" if msg.sender.startswith("tg:") else "whatsapp")
    except RateLimited:
        return "You have sent many reports. Please try again later."
    except Rejected as e:
        _clear(msg.sender)
        return str(e)
    if not user.consent_at:
        user.consent_at = now()
    _clear(msg.sender)
    r = res.report
    if res.duplicate:
        return f"Thanks. Someone already reported this place (ticket #{r.duplicate_of_id}). We added your report. / Dhanyavaad."
    if r.type == "manual_cleaning":
        return (f"Ticket #{r.id}: this is treated as an emergency and a certified operator is being sent. "
                "Please keep people away from the tank. / Aapatkaal: operator bheja ja raha hai.")
    return f"Ticket #{r.id} received ({r.type}). Thank you. / Aapki shikayat darj ho gayi."
