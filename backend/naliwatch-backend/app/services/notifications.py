import logging

import httpx

from ..config import settings
from . import channels

log = logging.getLogger(__name__)


def _safe(fn, *a) -> bool:
    try:
        fn(*a)
        return True
    except Exception:
        log.exception("send failed")
        return False


def send_sms(phone: str, text: str) -> bool:
    """Generic JSON webhook to your SMS gateway. India needs DLT registration + approved templates for real sends."""
    if not settings.sms_webhook_url:
        log.info("[sms %s] %s", phone, text)
        return True
    return _safe(lambda: httpx.post(settings.sms_webhook_url, json={"to": phone, "message": text}, timeout=10).raise_for_status())


def send_text(phone: str, text: str) -> bool:
    if phone.startswith("tg:"):
        return _safe(channels.tg_send, phone[3:], text)
    if settings.whatsapp_token and _safe(channels.wa_send_text, phone, text):
        return True
    return send_sms(phone, text)


def notify_user(user, text: str) -> bool:
    return send_text(user.phone, text) if user else False


def send_login_otp(phone: str, code: str) -> bool:
    return send_sms(phone, f"Your NaliWatch login code is {code}. It is valid for 5 minutes.")
