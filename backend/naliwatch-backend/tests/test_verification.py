from datetime import datetime, timedelta, timezone

from shapely.geometry import box

from app.services.verification import Fix, entered_geofence, evaluate, find_gaps, volume_ok

T0 = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
PLANT = box(73.89, 18.49, 73.91, 18.51)  # lng/lat


def fixes(inside=True, gap=False):
    pts = [Fix(T0 + timedelta(minutes=m), 18.50, 73.85) for m in (0, 5, 10)]
    if gap:
        pts.append(Fix(T0 + timedelta(minutes=60), 18.50, 73.86))
    if inside:
        pts.append(Fix(T0 + timedelta(minutes=70), 18.50, 73.90))
    return pts


def run(received, f, arrival_min=71, valid=True, stops=2):
    return evaluate(pumped=1000, received=received, fixes=f, polygon=PLANT, start=T0, end=T0 + timedelta(hours=12),
                    arrival=T0 + timedelta(minutes=arrival_min), plant_valid=valid, confirmed_stops=stops)


def test_volume_tolerance_uses_percent_or_minimum():
    assert volume_ok(1000, 1090, 10, 100)[0]       # inside 10%
    assert volume_ok(200, 290, 10, 100)[0]         # inside the 100 L minimum
    assert not volume_ok(1000, 800, 10, 100)[0]


def test_matched_trip_is_verified():
    reasons, _ = run(1000, fixes())
    assert reasons == []


def test_volume_mismatch_flags():
    reasons, detail = run(600, fixes())
    assert reasons == ["volume_mismatch"] and detail["diff"] == -400


def test_gap_is_checked_before_blaming_the_driver():
    reasons, detail = run(1000, fixes(inside=False, gap=True))
    assert reasons == ["gps_gap_unverified"] and detail["gaps"]


def test_no_gps_and_no_entry():
    assert run(1000, [])[0] == ["no_gps_trail"]
    assert run(1000, fixes(inside=False))[0] == ["no_geofence_entry"]


def test_unauthorized_plant_and_no_stops():
    assert "plant_not_authorized" in run(1000, fixes(), valid=False)[0]
    assert "no_confirmed_stops" in run(1000, fixes(), stops=0)[0]


def test_helpers():
    assert entered_geofence(fixes(), PLANT, T0, T0 + timedelta(hours=12))
    assert find_gaps(fixes(gap=True), 10)
