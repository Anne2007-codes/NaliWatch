"""End-to-end trip simulator against a running API (needs OTP_DEV_ECHO=true and ENV=dev, after scripts.seed).
  python -m scripts.simulate_trip --mode matched     # verified drop
  python -m scripts.simulate_trip --mode mismatch    # plant reports a much smaller volume -> flag
  python -m scripts.simulate_trip --mode skipped     # never reaches the plant -> flag"""
import argparse
from datetime import datetime, timedelta, timezone

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8000")
ap.add_argument("--driver", default="+919000000004", help="seed drivers: +919000000004 or +919000000005")
ap.add_argument("--mode", choices=["matched", "mismatch", "skipped"], default="matched")
a = ap.parse_args()


def login(phone: str) -> httpx.Client:
    c = httpx.Client(base_url=a.base, timeout=60)
    otp = c.post("/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    tok = c.post("/auth/otp/verify", json={"phone": phone, "otp": otp, "consent": True}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    return c


def ok(r: httpx.Response):
    r.raise_for_status()
    return r.json()


admin, officer, operator = login("+919000000001"), login("+919000000002"), login("+919000000003")
driver, plant = login(a.driver), login("+919000000006")

print("refresh + schedule:", ok(officer.post("/jobs/refresh")), ok(officer.post("/jobs/run-scheduler")))
for j in ok(operator.get("/jobs", params={"status": "offered"})):
    ok(operator.post(f"/jobs/{j['id']}/accept"))
plan = ok(operator.post("/trips/plan", json={}))
print("planned trips:", [t["id"] for t in plan["trips"]], "unrouted:", plan["unrouted_job_ids"])

mine = [t for t in ok(driver.get("/trips")) if t["status"] == "planned"]
if not mine:
    raise SystemExit("this driver has no planned trip (try --driver with the other seed driver, or re-seed)")
trip = mine[0]
tid = trip["id"]
ok(driver.post(f"/trips/{tid}/start", json={"consent_gps": True}))

total = 0
for s in trip["stops"]:
    otp = ok(driver.post(f"/trips/{tid}/stops/{s['id']}/otp"))
    litres = int(s["estimated_litres"] * 0.95)
    total += litres
    ok(driver.post(f"/trips/{tid}/stops/{s['id']}/confirm",
                   json={"otp": otp.get("dev_otp"), "volume_pumped_litres": litres, "lat": s["lat"], "lng": s["lng"]}))
    print(f"  stop {s['sequence']}: pumped {litres} L")

route = trip["planned_route"]
path = route if a.mode != "skipped" else route[:-1]  # skipped: the last leg to the plant never happens
pts, t0 = [], datetime.now(timezone.utc)
for (la, ln), (lb, lm) in zip(path, path[1:]):
    for k in range(10):
        f = k / 10
        pts.append({"lat": la + (lb - la) * f, "lng": ln + (lm - ln) * f,
                    "recorded_at": (t0 + timedelta(seconds=5 * len(pts))).isoformat()})
pts.append({"lat": path[-1][0], "lng": path[-1][1], "recorded_at": (t0 + timedelta(seconds=5 * len(pts))).isoformat()})
ok(driver.post(f"/trips/{tid}/gps", json={"points": pts}))
ok(driver.post(f"/trips/{tid}/finish"))

if a.mode == "skipped":
    print("force-expiring:", ok(admin.post("/dev/flag-skipped")))
else:
    received = total if a.mode == "matched" else int(total * 0.6)
    print("plant says:", ok(plant.post("/plant/disposals", json={"trip_id": tid, "volume_received_litres": received})))

print("open flags:")
for f in ok(officer.get("/flags", params={"status": "open"})):
    print("  ", f["id"], f["reason"], f["detail"])
print("kpis:", ok(officer.get("/metrics/kpis")))
