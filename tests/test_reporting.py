"""Deterministic dashboard reporting contract checks."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
import app

now = datetime.now(timezone.utc)
points = [(now - timedelta(seconds=10), 1), (now - timedelta(seconds=5), 2)]
assert app.cadence(points) == 5
assert round(app.imbalance([230, 231, 232]), 3) == 0.866
assert app.availability(points, now - timedelta(seconds=10), now, 5)["coverage"] == 100
assert app.availability([(now - timedelta(seconds=30),)], now - timedelta(seconds=30), now, 5)["current_gap"]

# A failed diagnostics side-channel must not make healthy live telemetry appear offline.
original_get_json = app.get_json
app._cache.clear()
def fake_get_json(url, timeout=3):
    if url == app.PROD_ROOT:
        return {"timestamp": now.isoformat(), "serial_ok": True, "persistence": {"status": "OK"}}
    if url == app.PROD_DIAG:
        raise TimeoutError("diagnostics unavailable")
    if url.startswith(app.POSTGREST):
        return [{"created_at": now.isoformat()}]
    raise AssertionError(url)
app.get_json = fake_get_json
snapshot = app.live()
assert snapshot["state"] == "LIVE" and snapshot["error"] is None
assert snapshot["diag"] == {} and "TimeoutError" in snapshot["diag_error"]
assert snapshot["recorder"]["status"] == "HEALTHY"
app.get_json = original_get_json

# Aggregation aligns series and preserves an empty bucket as null (never fake continuity).
original_fetch_rows = app.fetch_rows
start = datetime(2026, 1, 1, tzinfo=timezone.utc)
app.fetch_rows = lambda fields, begin, end, max_rows=app.MAX_REPORT_ROWS: ([
    {"created_at": start.isoformat(), "active_power_kw": 4.0},
    {"created_at": (start + timedelta(seconds=5)).isoformat(), "active_power_kw": 6.0},
    {"created_at": (start + timedelta(seconds=25)).isoformat(), "active_power_kw": 8.0},
], False)
report = app.telemetry_history({"range": ["custom"], "from": [start.isoformat()],
                                "to": [(start + timedelta(seconds=30)).isoformat()],
                                "metrics": ["active_power_kw"]})
assert report["series"]["active_power_kw"] == [4.0, 6.0, None, None, None, 8.0, None]
assert report["bucket_seconds"] == 5  # Custom ranges retain high resolution at this span.
app.fetch_rows = original_fetch_rows

html = (ROOT / "dashboard" / "static" / "index.html").read_text()
script = (ROOT / "dashboard" / "static" / "app.js").read_text()
for view in ("overview", "electrical", "energy", "history", "diagnostics"):
    assert f'data-view="{view}"' in html and f'id="{view}"' in html
for key in ("active_power_a_kw", "reactive_power_kvar", "apparent_power_kva", "power_factor",
            "frequency", "reactive_energy_kvarh", "apparent_energy_kvah"):
    assert key in script
vendor = ROOT / "dashboard" / "static" / "vendor" / "uplot"
assert (vendor / "uPlot.iife.min.js").stat().st_size < 60_000
assert "MIT License" in (vendor / "LICENSE").read_text()
print("dashboard reporting contract: PASS")
