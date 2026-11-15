"""Low-level HTTP calls to Telegram and the WhatsApp Cloud API."""
import logging

import httpx

from ..config import settings

log = logging.getLogger(__name__)
TG = "https://api.telegram.org"
WA = "https://graph.facebook.com/v20.0"


def tg_send(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        log.info("[telegram %s] %s", chat_id, text)
        return
    httpx.post(f"{TG}/bot{settings.telegram_bot_token}/sendMessage", json={"chat_id": chat_id, "text": text},
               timeout=10).raise_for_status()


def tg_download(file_id: str) -> bytes:
    tok = settings.telegram_bot_token
    info = httpx.get(f"{TG}/bot{tok}/getFile", params={"file_id": file_id}, timeout=10).json()["result"]
    return httpx.get(f"{TG}/file/bot{tok}/{info['file_path']}", timeout=30).content


def _wa_headers() -> dict:
    return {"Authorization": f"Bearer {settings.whatsapp_token}"}


def wa_send_text(to: str, text: str) -> None:
    httpx.post(f"{WA}/{settings.whatsapp_phone_id}/messages", headers=_wa_headers(), timeout=10,
               json={"messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "text", "text": {"body": text}}
               ).raise_for_status()


def wa_send_template(to: str, name: str, lang: str, params: list[str]) -> None:
    """Needed for messages outside the 24-hour reply window (templates must be pre-approved)."""
    httpx.post(f"{WA}/{settings.whatsapp_phone_id}/messages", headers=_wa_headers(), timeout=10, json={
        "messaging_product": "whatsapp", "to": to.lstrip("+"), "type": "template",
        "template": {"name": name, "language": {"code": lang},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]},
    }).raise_for_status()


def wa_download(media_id: str) -> bytes:
    meta = httpx.get(f"{WA}/{media_id}", headers=_wa_headers(), timeout=10).json()
    return httpx.get(meta["url"], headers=_wa_headers(), timeout=30).content
