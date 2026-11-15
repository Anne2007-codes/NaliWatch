from .models import AuditLog


def log(db, actor, action: str, record: str, **detail) -> None:
    db.add(AuditLog(actor_id=getattr(actor, "id", None), action=action, record=record, detail=detail or None))
