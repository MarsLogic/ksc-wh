"""Minimal deterministic smoke checks for the dashboard reporting contract."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "dashboard"))
import app

now = datetime.now(timezone.utc)
points = [(now - timedelta(seconds=10), 1), (now - timedelta(seconds=5), 2)]
assert app.cadence(points) == 5
assert round(app.imbalance([230, 231, 232]), 3) == 0.866
assert app.availability(points, now - timedelta(seconds=10), now, 5)["coverage"] == 100
print("reporting smoke test: PASS")
