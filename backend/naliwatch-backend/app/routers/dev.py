from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import require_roles
from ..models import User
from ..services import clustering, verification

router = APIRouter(prefix="/dev", tags=["dev"])


def _dev_only():
    if settings.env != "dev":
        raise HTTPException(404, "not found")


@router.post("/flag-skipped")
def flag_skipped(admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    """Demo helper: treat every open trip as past its time window and flag the ones with no plant confirmation."""
    _dev_only()
    n = verification.flag_skipped_plants(db, force=True)
    db.commit()
    return {"flagged": n}


@router.post("/recluster")
def recluster(admin: User = Depends(require_roles()), db: Session = Depends(get_db)):
    _dev_only()
    n = clustering.recompute_clusters(db)
    db.commit()
    return {"clusters": n}
