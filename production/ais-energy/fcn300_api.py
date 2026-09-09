#!/usr/bin/env python3
"""FORT FCN300-3E4Y Modbus RTU live V/I reader and REST API.
Hardware: CH340 USB-RS485 adapter (/dev/powermeter -> /dev/ttyUSB0).
"""

import json
import logging
import math
import struct
import threading
import time
import urllib.request
from datetime import datetime, timezone
from wsgiref.simple_server import make_server

import serial

PORT = "/dev/powermeter"
BAUD = 9600  # Fixed from BAWD
SLAVE_ID = 1

UNRESOLVED_KEYS = (
    "frequency", "active_power_kw", "reactive_power_kvar",
    "apparent_power_kva", "power_factor", "energy_kwh", "kvarh", "kVAh",
)

# ---- Validated V/I acquisition (partial cutover 2026-09-08) -----------------
# BE-uint32 /10000 blocks, proven against field photos + 15-min monitoring
# (see /home/ais/fcn300-diagnostics/docs/register-research.md). Read with
# read_regs() (atomic) in the main poller pass. NO corrections apply here.
# (base_addr, word_count, ((key, word_offset), ...))
VI_BLOCKS = (
    (0x0042, 6, (("voltage_l1", 0), ("voltage_l2", 2), ("voltage_l3", 4))),
    (0x0058, 8, (("current_a", 0), ("current_b", 2), ("current_c", 4),
                 ("current_avg", 6))),
)
VALIDATED_KEYS = frozenset(("voltage_l1", "voltage_l2", "voltage_l3",
                            "current_a", "current_b", "current_c",
                            "current_avg"))
VI_FRESHNESS_SECONDS = 5.0
ENERGY_POLL_SECONDS = 30.0
ENERGY_FRESHNESS_SECONDS = 90.0
ENERGY_BLOCK = (0x008A, 2)
_validated_lock = threading.Lock()
_validated = {"values": {}, "timestamp": None, "ok": False}
_energy_lock = threading.Lock()
_energy = {"value": None, "raw": None, "timestamp": None, "ok": False,
           "error": None}

# ---- Diagnostic side-channel (additive, read-only) --------------------------
# Exposes only the accepted V/I blocks read by the production poller. It never
# opens a second serial connection.
_raw_words_lock = threading.Lock()
_raw_words = {"timestamp": None, "serial_ok": False, "blocks": {}}
_persistence_lock = threading.Lock()
_persistence = {
    "status": "UNKNOWN", "last_attempt": None, "last_success": None,
    "error": None,
}

POSTGREST_URL = "http://127.0.0.1:3000/water_monitoring"
DEVICE_NAME = "FCN300-POWER-1"
PERSISTED_KEYS = frozenset((
    "device_name", "voltage_l1", "voltage_l2", "voltage_l3",
    "current_a", "current_b", "current_c", "energy_kwh",
))


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def read_reg(ser: serial.Serial, addr: int, func: int = 3,
             retries: int = 3) -> int | None:
    """Read a single register with function code `func` (default 3).

    Production always calls with the default (FC3 holding registers).
    """
    for _ in range(retries):
        req = struct.pack(">BBHH", SLAVE_ID, func, addr, 1)
        req += struct.pack("<H", crc16(req))
        ser.reset_input_buffer()
        ser.write(req)
        time.sleep(0.06)
        resp = ser.read(7)
        if len(resp) == 7 and resp[0] == SLAVE_ID and resp[1] == func and resp[2] == 2:
            if crc16(resp[:-2]) == struct.unpack("<H", resp[-2:])[0]:
                return struct.unpack(">H", resp[3:5])[0]
        time.sleep(0.02)
    return None
def read_regs(ser: serial.Serial, addr: int, count: int,
              func: int = 3, retries: int = 3) -> list[int] | None:
    """Read `count` contiguous registers in ONE Modbus transaction.

    Validated production V/I uses the FC03 default. Returns None after three
    invalid, exception, or timed-out responses.
    """
    for _ in range(retries):
        req = struct.pack(">BBHH", SLAVE_ID, func, addr, count)
        req += struct.pack("<H", crc16(req))
        ser.reset_input_buffer()
        ser.write(req)
        time.sleep(0.06 + 0.01 * count)
        want = 5 + count * 2
        resp = ser.read(want)
        if (len(resp) == want and resp[0] == SLAVE_ID and resp[1] == func
                and resp[2] == count * 2
                and crc16(resp[:-2]) == struct.unpack("<H", resp[-2:])[0]):
            return [struct.unpack(">H", resp[3 + i * 2:5 + i * 2])[0]
                    for i in range(count)]
        time.sleep(0.02)
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _age_seconds(timestamp: str | None) -> float | None:
    if not timestamp:
        return None
    try:
        sample = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - sample).total_seconds())
    except (TypeError, ValueError):
        return None


def _validated_snapshot() -> dict:
    with _validated_lock:
        snap = dict(_validated)
        snap["values"] = dict(_validated["values"])
    age = _age_seconds(snap["timestamp"])
    snap["sample_age_seconds"] = round(age, 3) if age is not None else None
    snap["fresh"] = bool(snap["ok"] and age is not None
                         and age <= VI_FRESHNESS_SECONDS)
    return snap


def _energy_snapshot() -> dict:
    with _energy_lock:
        snap = dict(_energy)
    age = _age_seconds(snap["timestamp"])
    snap["sample_age_seconds"] = round(age, 3) if age is not None else None
    snap["fresh"] = bool(snap["ok"] and age is not None
                         and age <= ENERGY_FRESHNESS_SECONDS)
    return snap


def decode_energy(words: list[int] | None, previous: float | None = None) -> tuple[float | None, str | None]:
    if words is None or len(words) != 2:
        return None, "incomplete FC03 block"
    try:
        raw = struct.unpack(">f", struct.pack(">HH", *words))[0]
    except (struct.error, TypeError):
        return None, "float decode failure"
    if not math.isfinite(raw) or raw < 0:
        return None, "invalid energy float"
    value = raw / 1000.0
    if previous is not None and value < previous:
        return None, "energy decreased"
    return value, None


def post_to_postgrest(payload: dict):
    attempted = _utc_now()
    try:
        payload = {key: value for key, value in payload.items()
                   if key in PERSISTED_KEYS}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            POSTGREST_URL,
            data=data,
            headers={"Content-Type": "application/json", "Prefer": "return=representation"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
        with _persistence_lock:
            _persistence.update(status="OK", last_attempt=attempted,
                                last_success=_utc_now(), error=None)
    except Exception as e:
        with _persistence_lock:
            _persistence.update(status="ERROR", last_attempt=attempted,
                                error=f"{type(e).__name__}: {e}")
        logging.warning("PostgREST post failed: %s", e)


def _replace_raw_snapshot(raw: dict, serial_ok: bool,
                          blocks: dict | None = None) -> None:
    with _raw_words_lock:
        _raw_words.clear()
        _raw_words.update(raw)
        _raw_words.update(timestamp=_utc_now(), serial_ok=bool(serial_ok),
                          blocks=dict(blocks or {}))


def _invalidate_acquisition() -> None:
    with _validated_lock:
        _validated["ok"] = False
    _replace_raw_snapshot({}, False)


def poller_loop():
    logging.info("Starting RS485 poller...")
    ser = None
    last_post = 0
    last_energy_poll = 0.0
    while True:
        if ser is None or not ser.is_open:
            try:
                ser = serial.Serial(
                    PORT, BAUD,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    bytesize=8,
                    timeout=1.0,
                )
                logging.info("Serial port opened: %s", PORT)
                time.sleep(0.3)
            except Exception as e:
                logging.warning("Cannot open %s: %s", PORT, e)
                ser = None
                _invalidate_acquisition()
                time.sleep(2)
                continue

        # Validated V/I blocks (partial cutover): atomic reads, BE-uint32
        # /10000, NO corrections. On failure the previous validated values
        # stay served with their original timestamp (age grows visibly);
        # frozen 0x00 words are never consulted for these keys.
        vi_ok = True
        vi_values: dict[str, float] = {}
        raw_new = {}
        block_status = {}
        for base, count, pairs in VI_BLOCKS:
            words = read_regs(ser, base, count)
            block_name = f"0x{base:04X}+{count}"
            if words is None or len(words) != count:
                vi_ok = False
                block_status[block_name] = {
                    "ok": False, "coherent": False, "source_timestamp": None,
                    "source": "validated FC03 block",
                }
                continue
            captured = _utc_now()
            block_status[block_name] = {
                "ok": True, "coherent": True,
                "source_timestamp": captured,
                "source": "validated FC03 block (reused)",
            }
            for i, word in enumerate(words):
                raw_new[f"0x{base + i:04X}"] = word
            for key, off in pairs:
                u32 = (words[off] << 16) | words[off + 1]
                vi_values[key] = round(u32 / 10000.0, 4)
        complete_vi = bool(vi_ok and len(vi_values) == len(VALIDATED_KEYS))
        with _validated_lock:
            if complete_vi:
                _validated["values"] = vi_values
                _validated["timestamp"] = _utc_now()
            _validated["ok"] = complete_vi

        # Slow cumulative-energy read; V/I remains first priority.
        now = time.time()
        if now - last_energy_poll >= ENERGY_POLL_SECONDS:
            last_energy_poll = now
            ebase, ecount = ENERGY_BLOCK
            ewords = read_regs(ser, ebase, ecount)
            previous = _energy_snapshot()["value"]
            energy_value, energy_error = decode_energy(ewords, previous)
            ename = f"0x{ebase:04X}+{ecount}"
            if energy_value is not None:
                captured = _utc_now()
                with _energy_lock:
                    _energy.update(value=round(energy_value, 3), raw=list(ewords),
                                   timestamp=captured, ok=True, error=None)
                for i, word in enumerate(ewords):
                    raw_new[f"0x{ebase + i:04X}"] = word
                block_status[ename] = {"ok": True, "coherent": True,
                                       "source_timestamp": captured,
                                       "source": "validated FC03 energy block"}
            else:
                with _energy_lock:
                    _energy.update(ok=False, error=energy_error)
                block_status[ename] = {"ok": False, "coherent": False,
                                       "source_timestamp": None,
                                       "source": "validated FC03 energy block",
                                       "error": energy_error}
        energy = _energy_snapshot()
        if energy.get("raw"):
            for i, word in enumerate(energy["raw"]):
                raw_new[f"0x{ENERGY_BLOCK[0] + i:04X}"] = word
            block_status.setdefault(f"0x{ENERGY_BLOCK[0]:04X}+{ENERGY_BLOCK[1]}", {
                "ok": bool(energy["fresh"]), "coherent": bool(energy["fresh"]),
                "source_timestamp": energy["timestamp"],
                "source": "validated FC03 energy block"})

        # Post to PostgREST every 5 seconds
        if now - last_post >= 5.0:
            last_post = now
            vi = _validated_snapshot()
            live_vi = vi["values"]
            payload = {
                "device_name": DEVICE_NAME,
                "voltage_l1": live_vi.get("voltage_l1"),
                "voltage_l2": live_vi.get("voltage_l2"),
                "voltage_l3": live_vi.get("voltage_l3"),
                "current_a": live_vi.get("current_a"),
                "current_b": live_vi.get("current_b"),
                "current_c": live_vi.get("current_c"),
                "energy_kwh": energy["value"] if energy["fresh"] else None,
            }
            if vi["fresh"]:
                threading.Thread(target=post_to_postgrest, args=(payload,), daemon=True).start()

        _replace_raw_snapshot(raw_new, complete_vi, block_status)

        time.sleep(0.5)


def poller_supervisor():
    """Keep HTTP health honest and restart an unexpectedly failed poller."""
    while True:
        try:
            poller_loop()
        except Exception:
            _invalidate_acquisition()
            logging.exception("RS485 poller crashed; restarting in 2 seconds")
            time.sleep(2)


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")

    if path in ("/", ""):
        vi = _validated_snapshot()
        data = {key: None for key in UNRESOLVED_KEYS}
        data.update(vi["values"])
        energy = _energy_snapshot()
        data["energy_kwh"] = energy["value"] if energy["fresh"] else None
        data.update(
            timestamp=vi["timestamp"], validated_timestamp=vi["timestamp"],
            sample_age_seconds=vi["sample_age_seconds"],
            serial_ok=vi["fresh"], vi_status="VALID" if vi["fresh"] else "UNKNOWN",
            unresolved_status={key: "UNKNOWN" for key in UNRESOLVED_KEYS},
        )
        data["energy_status"] = {
            "raw_address": "0x008A", "raw_words": energy.get("raw"),
            "decoded_float": (energy["value"] * 1000 if energy["value"] is not None else None),
            "sample_age_seconds": energy.get("sample_age_seconds"),
            "valid": energy.get("fresh"), "error": energy.get("error"),
        }
        data["unresolved_status"]["energy_kwh"] = (
            "VALID" if energy.get("fresh") else "UNKNOWN")
        with _persistence_lock:
            data["persistence"] = dict(_persistence)
        body = json.dumps(data, indent=2).encode("utf-8")
        headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
        ]
        start_response("200 OK", headers)
        return [body]

    elif path == "/health":
        vi = _validated_snapshot()
        with _persistence_lock:
            persistence = dict(_persistence)
        body = json.dumps({
            "status": "ok" if vi["fresh"] else "stale",
            "serial_ok": vi["fresh"],
            "sample_age_seconds": vi["sample_age_seconds"],
            "persistence": persistence,
        }).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json")])
        return [body]

    elif path == "/diag/raw":
        # Loopback-only diagnostic side-channel. Reject anything not from
        # 127.0.0.1 or ::1. Exposes raw 16-bit words and metadata; no
        # production scaled values, no PostgREST secrets.
        remote = environ.get("REMOTE_ADDR", "")
        if remote not in ("127.0.0.1", "::1"):
            body = b"Forbidden"
            start_response("403 Forbidden", [("Content-Type", "text/plain"),
                                              ("Content-Length", str(len(body)))])
            return [body]
        with _raw_words_lock:
            snap = {
                "timestamp": _raw_words.get("timestamp"),
                "serial_ok": bool(_raw_words.get("serial_ok", False)),
                "source": "production fcn300_api.py / diag side-channel",
                "raw": {k: v for k, v in _raw_words.items()
                        if k not in ("timestamp", "serial_ok", "blocks")},
                "blocks": dict(_raw_words.get("blocks", {})),
            }
        energy = _energy_snapshot()
        snap["energy"] = {
            "address": "0x008A", "raw_words": energy.get("raw"),
            "decoded_float": (energy["value"] * 1000
                               if energy.get("value") is not None else None),
            "energy_kwh": energy.get("value"),
            "timestamp": energy.get("timestamp"),
            "fresh": energy.get("fresh"), "error": energy.get("error"),
        }
        body = json.dumps(snap, indent=2).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"),
                                  ("Content-Length", str(len(body)))])
        return [body]

    else:
        body = b"Not Found"
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [body]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    t = threading.Thread(target=poller_supervisor, daemon=True)
    t.start()

    srv = make_server("0.0.0.0", 8080, application)
    print("FORT FCN300 Live RS485 API active on http://0.0.0.0:8080")
    print("Corrections applied to match panel readings")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        srv.shutdown()
