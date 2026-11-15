"""Batch scheduled jobs into tanker trips with OR-Tools. Road distances from OSRM, haversine fallback."""
import logging
from datetime import date

import httpx
from shapely.geometry import Point
from geoalchemy2.shape import to_shape
from sqlalchemy import select

from ..config import settings
from ..geo import haversine_m, latlng
from ..models import Driver, Job, Operator, Plant, Trip, TripStop, Vehicle

log = logging.getLogger(__name__)


def distance_matrix(coords: list[tuple[float, float]]) -> list[list[int]]:
    """coords are (lat, lng). Returns metres."""
    try:
        path = ";".join(f"{lng},{lat}" for lat, lng in coords)
        res = httpx.get(f"{settings.osrm_url}/table/v1/driving/{path}", params={"annotations": "distance"}, timeout=20).json()
        if res.get("code") == "Ok":
            return [[int(d or 0) for d in row] for row in res["distances"]]
    except Exception:
        log.warning("OSRM unavailable, using straight-line x1.3", exc_info=True)
    return [[int(haversine_m(a[0], a[1], b[0], b[1]) * 1.3) for b in coords] for a in coords]


def solve_vrp(matrix: list[list[int]], demands: list[int], capacities: list[int], priorities: list[float],
              seconds: int = 5) -> tuple[list[list[int]], list[int]]:
    """Node 0 = depot, node 1 = plant, nodes 2.. = jobs. All vehicles start at 0 and end at 1.
    Returns (routes as lists of node ids, dropped node ids). Higher priority jobs are dropped last."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    nv = len(capacities)
    manager = pywrapcp.RoutingIndexManager(len(matrix), nv, [0] * nv, [1] * nv)
    routing = pywrapcp.RoutingModel(manager)

    def dist(i, j):
        return matrix[manager.IndexToNode(i)][manager.IndexToNode(j)]

    cb = routing.RegisterTransitCallback(dist)
    routing.SetArcCostEvaluatorOfAllVehicles(cb)
    dcb = routing.RegisterUnaryTransitCallback(lambda i: demands[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(dcb, 0, capacities, True, "cap")
    for node in range(2, len(matrix)):
        routing.AddDisjunction([manager.NodeToIndex(node)], 50_000 + int(priorities[node] * 1000))
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = seconds
    sol = routing.SolveWithParameters(p)
    if sol is None:
        return [], list(range(2, len(matrix)))
    routes, served = [], set()
    for v in range(nv):
        idx, nodes = routing.Start(v), []
        while not routing.IsEnd(idx):
            n = manager.IndexToNode(idx)
            if n >= 2:
                nodes.append(n)
            idx = sol.Value(routing.NextVar(idx))
        routes.append(nodes)
        served.update(nodes)
    return routes, [n for n in range(2, len(matrix)) if n not in served]


def nearest_plant(db, lat: float, lng: float, on: date) -> Plant | None:
    best, best_d = None, 1e18
    for pl in db.scalars(select(Plant).where(Plant.status == "active", Plant.valid_until >= on)):
        c = to_shape(pl.geofence).centroid
        d = haversine_m(lat, lng, c.y, c.x)
        if d < best_d:
            best, best_d = pl, d
    return best


def plant_centroid(plant: Plant) -> tuple[float, float]:
    c = to_shape(plant.geofence).centroid
    return c.y, c.x


def plan_routes(db, operator_id: int, plan_date: date | None = None) -> tuple[list[Trip], list[Job]]:
    plan_date = plan_date or date.today()
    op = db.get(Operator, operator_id)
    jobs = db.scalars(select(Job).where(Job.operator_id == operator_id, Job.status == "scheduled")
                      .order_by(Job.priority_score.desc())).all()
    if not jobs:
        return [], []
    vehicles = db.scalars(select(Vehicle).where(Vehicle.operator_id == operator_id, Vehicle.status == "active")
                          .order_by(Vehicle.capacity_litres.desc())).all()
    drivers = db.scalars(select(Driver).where(Driver.operator_id == operator_id, Driver.status == "active")
                         .order_by(Driver.id)).all()
    n = min(len(vehicles), len(drivers))
    if n == 0:
        raise ValueError("operator needs at least one active vehicle and one active driver")
    vehicles, drivers = vehicles[:n], drivers[:n]

    locs = [latlng(j.location) for j in jobs]
    clat, clng = sum(a for a, _ in locs) / len(locs), sum(b for _, b in locs) / len(locs)
    plant = nearest_plant(db, clat, clng, plan_date)
    if plant is None:
        raise ValueError("no authorized plant available on this date")
    depot = latlng(op.depot) if op.depot is not None else (clat, clng)
    coords = [depot, plant_centroid(plant)] + locs
    matrix = distance_matrix(coords)
    demands = [0, 0] + [max(1, int(j.estimated_litres)) for j in jobs]
    prios = [0, 0] + [j.priority_score for j in jobs]
    routes, dropped = solve_vrp(matrix, demands, [v.capacity_litres for v in vehicles], prios)

    trips = []
    for v, d, nodes in zip(vehicles, drivers, routes):
        if not nodes:
            continue
        seq = [0] + nodes + [1]
        dist_m = sum(matrix[a][b] for a, b in zip(seq, seq[1:]))
        trip = Trip(operator_id=operator_id, vehicle_id=v.id, driver_id=d.id, plant_id=plant.id, status="planned",
                    planned_date=plan_date, planned_distance_m=dist_m, planned_route=[list(coords[i]) for i in seq])
        for k, node in enumerate(nodes, start=1):
            job = jobs[node - 2]
            job.status = "routed"
            trip.stops.append(TripStop(job_id=job.id, sequence=k))
        db.add(trip)
        trips.append(trip)
    db.flush()
    return trips, [jobs[n - 2] for n in dropped]
