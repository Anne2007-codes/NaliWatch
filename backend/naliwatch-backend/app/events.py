import json

from . import kv


def publish(kind: str, ward: str | None = None, **data) -> None:
    """Push a live update to /ws/live subscribers. Never raises."""
    try:
        kv.r.publish("naliwatch:live", json.dumps({"type": kind, "ward": ward, "data": data}, default=str))
    except Exception:
        pass
