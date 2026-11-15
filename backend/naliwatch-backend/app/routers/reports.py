from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings
from ..db import get_db
from ..deps import current_user, require_roles, ward_clause
from ..errors import Rejected, RateLimited
from ..models import Report, User, now
from ..schemas import ReportPatch
from ..serializers import report_out
from ..services import intake

router = APIRouter(prefix="/reports", tags=["reports"])


def _read(f: UploadFile | None) -> bytes | None:
    if not f:
        return None
    data = f.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "file too large")
    return data


@router.post("", status_code=201)
def submit_report(lat: float = Form(..., ge=-90, le=90), lng: float = Form(..., ge=-180, le=180),
                  text: str | None = Form(None), claimed_type: str | None = Form(None),
                  photo: UploadFile | None = File(None), audio: UploadFile | None = File(None),
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not (text or photo or audio):
        raise HTTPException(400, "send a photo, a voice note or some text")
    try:
        res = intake.create_report(db, user, lat=lat, lng=lng, text=text, photo=_read(photo), audio=_read(audio),
                                   audio_name=audio.filename if audio else "voice.ogg", source="api",
                                   claimed_type=claimed_type)
    except RateLimited as e:
        raise HTTPException(429, str(e))
    except Rejected as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {**report_out(res.report, user), "duplicate": res.duplicate}


@router.get("")
def list_reports(status: str | None = None, type: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Report)
    if user.role in ("officer", "admin"):
        wc = ward_clause(user, Report.ward)
        if wc is not None:
            q = q.where(wc)
    else:
        q = q.where(Report.reporter_id == user.id)  # everyone else sees only their own
    if status:
        q = q.where(Report.status == status)
    if type:
        q = q.where(Report.type == type)
    rows = db.scalars(q.order_by(Report.created_at.desc()).limit(limit).offset(offset))
    return [report_out(r, user) for r in rows]


@router.patch("/{report_id}")
def review_report(report_id: int, body: ReportPatch, user: User = Depends(require_roles("officer")),
                  db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r or (user.role == "officer" and r.ward != user.ward):
        raise HTTPException(404, "report not found")
    d = body.model_dump(exclude_unset=True)
    before = {"type": r.type, "severity": r.severity, "status": r.status}
    for k in ("type", "severity", "status"):
        if k in d:
            setattr(r, k, d[k])
    if "note" in d:
        r.officer_note = d["note"]
    r.reviewed_by = user.id
    if d.get("status") == "resolved":
        r.resolved_at = now()
    db.flush()
    if before["status"] == "needs_review" and r.status in ("triaged",) or ("type" in d and r.status == "triaged"):
        intake.dispatch_report(db, r)
    audit.log(db, user, "review", f"report:{r.id}", before=before, after=d)
    db.commit()
    return report_out(r, user)
