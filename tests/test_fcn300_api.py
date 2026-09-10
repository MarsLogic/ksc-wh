"""Deterministic checks for the authoritative FCN300 decoder."""
import importlib.util
import sys
import types
from pathlib import Path

sys.modules.setdefault("serial", types.SimpleNamespace(Serial=object))
path = Path(__file__).parents[1] / "production" / "ais-energy" / "fcn300_api.py"
spec = importlib.util.spec_from_file_location("fcn300_api", path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def words32(value):
    value &= 0xFFFFFFFF
    return [value >> 16, value & 0xFFFF]


power_words = []
for group in ((10000, -20000, 30000, 20000),
              (40000, 50000, -60000, 30000),
              (70000, 80000, 90000, 240000)):
    for value in group:
        power_words.extend(words32(value))
power_words.extend((950, 960, 970, 960, 5001))
power, error = api.decode_power(power_words)
assert error is None
assert power["active_power_a_kw"] == 1.0
assert power["active_power_b_kw"] == -2.0
assert power["reactive_power_c_kvar"] == -6.0
assert power["apparent_power_kva"] == 24.0
assert power["power_factor"] == 0.96
assert power["frequency"] == 50.01

# Exact 2026-09-09 commissioning snapshot. Primary/secondary values agree at
# the configured 40x multiplier for all four non-zero energy counters.
energy_words = [
    0, 45522, 0, 0, 0, 33251, 0, 1361,
    18910, 18048, 0, 0, 18850, 23488, 18260, 43008,
    0, 57168, 0, 0, 18955, 37376, 0, 0,
]
energy, error = api.decode_energy(energy_words)
assert error is None
assert energy["energy_kwh"] == 1820.88
assert energy["reactive_energy_kvarh"] == 1330.04
assert energy["reactive_energy_export_kvarh"] == 54.44
assert energy["apparent_energy_kvah"] == 2286.72
assert round(energy["energy_kwh"] / energy["secondary_active_import_kwh"], 6) == 40
assert round(energy["reactive_energy_kvarh"] / energy["secondary_reactive_import_kvarh"], 6) == 40
assert round(energy["apparent_energy_kvah"] / energy["secondary_apparent_import_kvah"], 6) == 40
assert api.decode_energy(energy_words, 1820.881)[1] == "energy decreased"
assert api.decode_energy(energy_words[:-1])[1] == "incomplete FC03 block"
assert {"active_power_kw", "reactive_power_kvar", "apparent_power_kva",
        "power_factor", "frequency", "energy_kwh",
        "reactive_energy_kvarh", "apparent_energy_kvah"} <= api.PERSISTED_KEYS

print("FCN300 decoder test: PASS")
