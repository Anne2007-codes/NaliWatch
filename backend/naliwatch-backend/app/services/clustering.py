"""DBSCAN over open failure reports and recent sickness counts. Overlap of both => risk zone."""
from datetime import timedelta

import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import delete, select

from ..config import settings
from ..geo import latlng, point
from ..models import OPEN_REPORT, Cluster, HealthSignal, Report, now

EARTH_M = 6371000.0
SEV_WEIGHT = {1: 1.0, 2: 2.0, 3: 3.0}


def compute_clusters(points: list[dict], eps_m: float, min_samples: int) -> list[dict]:
    """points: {lat, lng, kind: 'report'|'health', weight: int, score: float}. Pure function."""
    if not points:
        return []
    X = np.radians([[p["lat"], p["lng"]] for p in points])
    w = np.array([p["weight"] for p in points], dtype=float)
    labels = DBSCAN(eps=eps_m / EARTH_M, min_samples=min_samples, metric="haversine", algorithm="ball_tree").fit(
        X, sample_weight=w
    ).labels_
    out = []
    for lab in sorted(set(labels) - {-1}):
        idx = [i for i, l in enumerate(labels) if l == lab]
        pts = [points[i] for i in idx]
        lat = sum(p["lat"] * p["weight"] for p in pts) / sum(p["weight"] for p in pts)
        lng = sum(p["lng"] * p["weight"] for p in pts) / sum(p["weight"] for p in pts)
        radius = max(50.0, max(_hav(lat, lng, p["lat"], p["lng"]) for p in pts))
        reports = [p for p in pts if p["kind"] == "report"]
        health = [p for p in pts if p["kind"] == "health"]
        out.append({
            "lat": lat, "lng": lng, "radius_m": radius,
            "status": "risk" if reports and health else "watch",
            "score": round(sum(p["score"] for p in pts), 1),
            "report_count": len(reports), "case_count": sum(p["weight"] for p in health),
        })
    return out


def _hav(lat1, lng1, lat2, lng2) -> float:
    from ..geo import haversine_m
    return haversine_m(lat1, lng1, lat2, lng2)


def recompute_clusters(db) -> int:
    t = now()
    reports = db.scalars(
        select(Report).where(
            Report.status.in_(OPEN_REPORT), Report.duplicate_of_id.is_(None),
            Report.type.in_(("overflow", "dumping", "manual_cleaning")), Report.created_at >= t - timedelta(days=30),
        )
    ).all()
    signals = db.scalars(select(HealthSignal).where(HealthSignal.reported_at >= t - timedelta(days=14))).all()
    pts = []
    for r in reports:
        lat, lng = latlng(r.location)
        pts.append({"lat": lat, "lng": lng, "kind": "report", "weight": 1, "score": SEV_WEIGHT.get(r.severity, 1.0)})
    for h in signals:
        lat, lng = latlng(h.location)
        pts.append({"lat": lat, "lng": lng, "kind": "health", "weight": h.case_count, "score": float(h.case_count)})
    found = compute_clusters(pts, settings.cluster_eps_m, settings.cluster_min_samples)

    from ..geo import assign_ward
    db.execute(delete(Cluster))
    for c in found:
        db.add(Cluster(center=point(c["lat"], c["lng"]), radius_m=c["radius_m"], status=c["status"], score=c["score"],
                       report_count=c["report_count"], case_count=c["case_count"],
                       ward=assign_ward(db, c["lat"], c["lng"]), computed_at=t))
    return len(found)
