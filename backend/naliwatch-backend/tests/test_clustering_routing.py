from app.services.clustering import compute_clusters
from app.services.routing import solve_vrp


def pt(lat, lng, kind="report", weight=1, score=2.0):
    return {"lat": lat, "lng": lng, "kind": kind, "weight": weight, "score": score}


def test_overlap_of_reports_and_sickness_is_a_risk_zone():
    pts = [pt(18.5150, 73.8600), pt(18.5151, 73.8601), pt(18.5149, 73.8599),
           pt(18.5150, 73.8602, "health", 4, 4.0), pt(18.60, 73.95)]  # last one is isolated noise
    out = compute_clusters(pts, eps_m=150, min_samples=3)
    assert len(out) == 1 and out[0]["status"] == "risk" and out[0]["case_count"] == 4


def test_reports_alone_are_a_watch_zone():
    out = compute_clusters([pt(18.5, 73.8), pt(18.5001, 73.8001), pt(18.5002, 73.8002)], 150, 3)
    assert out[0]["status"] == "watch"


def test_vrp_serves_all_jobs_within_capacity():
    # node 0 depot, 1 plant, 2..4 jobs (metres)
    m = [[0, 5000, 1000, 2000, 3000], [5000, 0, 4000, 3000, 2000], [1000, 4000, 0, 1000, 2000],
         [2000, 3000, 1000, 0, 1000], [3000, 2000, 2000, 1000, 0]]
    routes, dropped = solve_vrp(m, [0, 0, 1000, 1000, 1000], [3000], [0, 0, 10, 10, 10], seconds=1)
    assert dropped == [] and sorted(routes[0]) == [2, 3, 4]


def test_vrp_drops_lowest_priority_when_capacity_is_short():
    m = [[0, 5000, 1000, 2000, 3000], [5000, 0, 4000, 3000, 2000], [1000, 4000, 0, 1000, 2000],
         [2000, 3000, 1000, 0, 1000], [3000, 2000, 2000, 1000, 0]]
    routes, dropped = solve_vrp(m, [0, 0, 1000, 1000, 1000], [2000], [0, 0, 5, 50, 100], seconds=1)
    assert dropped == [2]
