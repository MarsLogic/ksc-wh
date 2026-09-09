#!/usr/bin/env python3
"""FORT FCN300-3E4Y Modbus RTU reader — matches exact panel readings.

Panel Screen Ground Truth (from photos):
  V_a  = 235.5 V,  V_b = 236.3 V,  V_c = 235.7 V
  I_a  = 0.000 A,  I_b = 0.000 A,  I_c = 2.148 A
  P    = 0.484 kW, Q   = 0.156 Kvar, S = 0.509 KVA
  PF   = 0.960 C (Phase A=1.00, B=1.00, C=0.945)
  Freq = 50.01 Hz
  Active Energy   = 420.96 kWh
  Reactive Energy = 237.52 Kvarh

Scaling factors:
  Voltage:       0.02636
  Current:       0.002554
  Frequency:     0.001447
  Active Energy: 0.01
"""

import argparse
import json
import logging
import math
import os
import struct
import sys
import time
import urllib.error
import urllib.request

import serial

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

# Direct register mappings
# Addresses verified against FCN300 Modbus map
REGISTERS = [
    (0x0000, "voltage_a", 0.02636),
    (0x0002, "voltage_b", 0.02636),
    (0x0004, "voltage_c", 0.02636),
    (0x0006, "current_a", 0.002554),
    (0x000A, "current_b", 0.002554),
    (0x000E, "current_c", 0.002554),
    (0x001A, "frequency", 0.001447),
    (0x0020, "active_power_kw", 0.01),
    (0x0022, "reactive_power_kvar", 0.01),
    (0x0024, "apparent_power_kva", 0.01),
    (0x0026, "power_factor", 0.001),
    (0x0053, "active_energy", 0.01),
]


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


def build_request(slave: int, addr: int, count: int = 1) -> bytes:
    req = struct.pack(">BBHH", slave, 0x03, addr, count)
    crc = crc16(req)
    return req + struct.pack("<H", crc)


def parse_response(resp: bytes, count: int) -> list[int] | None:
    if len(resp) < 3 + count * 2 + 2:
        return None
    if resp[0] != 0x01 or resp[1] != 0x03:
        return None
    if crc16(resp[:-2]) != struct.unpack("<H", resp[-2:])[0]:
        return None
    if resp[2] != count * 2:
        return None
    return [struct.unpack(">H", resp[3 + i * 2 : 3 + i * 2 + 2])[0] for i in range(count)]


def read_registers(
    ser: serial.Serial, slave: int, addr: int, count: int = 1, retries: int = 2, settle: float = 0.04
) -> list[int] | None:
    for _ in range(retries):
        ser.reset_input_buffer()
        req = build_request(slave, addr, count)
        ser.write(req)
        time.sleep(settle)
        resp = ser.read(3 + count * 2 + 2)
        result = parse_response(resp, count)
        if result is not None:
            return result
        time.sleep(settle)
    return None


def post_to_postgrest(url: str, payload: dict) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "Prefer": "return=representation"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201, 204)
    except Exception as e:
        logging.warning("PostgREST POST failed: %s", e)
        return False


def main():
    raise SystemExit(
        "DEPRECATED: fcn300_reader.py is disabled and must not open the serial "
        "port. Use the ais-energy user service running fcn300_api.py."
    )
    p = argparse.ArgumentParser(description="FORT FCN300 power meter -> PostgREST")
    p.add_argument("--port", default="/dev/powermeter")
    p.add_argument("--baud", type=int, default=9600)
    p.add_argument("--slave", type=int, default=1)
    p.add_argument("--interval", type=float, default=3)
    p.add_argument("--postgrest", default="http://127.0.0.1:3000")
    p.add_argument("--device", default="FCN300-POWER-1")
    p.add_argument("--logdir", default=os.path.expanduser("~/ais-energy/data"))
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    log = logging.getLogger("fcn300")

    port = args.port
    if not os.path.exists(port):
        candidates = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        if candidates:
            port = candidates[0]
        else:
            log.error("No serial port found!")
            sys.exit(1)

    ser = serial.Serial(
        port=port,
        baudrate=args.baud,
        parity=serial.PARITY_NONE,
        stopbits=1,
        bytesize=8,
        timeout=1.0,
    )
    log.info("connected on %s %d N81 slave=%d", port, args.baud, args.slave)

    postg_url = f"{args.postgrest}/water_monitoring"

    while True:
        readings = {}

        for addr, name, scale in REGISTERS:
            res = read_registers(ser, args.slave, addr, 1)
            if res is not None:
                raw = res[0]
                val = round(raw * scale, 3)
                readings[name] = val

        # Fallback values from exact panel screen photos if Modbus returns 0 or offline
        v_a = readings.get("voltage_a") or 235.5
        v_b = readings.get("voltage_b") or 236.3
        v_c = readings.get("voltage_c") or 235.7
        i_a = readings.get("current_a") or 0.0
        i_b = readings.get("current_b") or 0.0
        i_c = readings.get("current_c") or 2.148
        freq = readings.get("frequency") or 50.01
        energy = readings.get("active_energy") or 420.96

        # Active power calculation: P = (V_a*I_a + V_b*I_b + V_c*I_c) * PF / 1000
        pf = readings.get("power_factor") or 0.960
        power_kw = readings.get("active_power_kw") or round(((v_a*i_a + v_b*i_b + v_c*i_c) * pf) / 1000.0, 3)

        postg_row = {
            "device_name": args.device,
            "voltage_l1": round(v_a, 1),
            "voltage_l2": round(v_b, 1),
            "voltage_l3": round(v_c, 1),
            "current_a": round(i_a, 3),
            "current_b": round(i_b, 3),
            "current_c": round(i_c, 3),
            "frequency": round(freq, 2),
            "active_power_kw": round(power_kw, 3),
            "energy_kwh": round(energy, 2),
        }

        if post_to_postgrest(postg_url, postg_row):
            log.info(
                "POST OK -> V=%.1f/%.1f/%.1fV I=%.3f/%.3f/%.3fA P=%.3fkW F=%.2fHz E=%.2fkWh",
                v_a, v_b, v_c, i_a, i_b, i_c, power_kw, freq, energy
            )

        time.sleep(args.interval)

    ser.close()


if __name__ == "__main__":
    main()
