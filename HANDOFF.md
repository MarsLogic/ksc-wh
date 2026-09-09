# KSC-WH Current Handoff

Snapshot: 2026-09-09. This is the authoritative freeze entry point.

## Current project state

Production monitoring is operational. Accepted and persisted measurements are voltage L1/L2/L3, current A/B/C, and total positive active energy `energy_kwh`. PostgreSQL 14, PostgREST, the production API, and the dashboard were healthy at snapshot time.

## Remote access

Server: `ais@100.73.124.7` via Tailscale/SSH. No password is stored here; credentials must be supplied locally.

Important paths:

- `/home/ais/ais-energy/`
- `/home/ais/fcn300-diagnostics/`
- PostgreSQL data mount: `/mnt/sambashare/pgdata`

## Architecture

FCN300 → RS485/Modbus RTU → `/home/ais/ais-energy/fcn300_api.py` → HTTP API → PostgreSQL/PostgREST → `/home/ais/fcn300-diagnostics/app.py` → operator dashboard.

## Accepted data contract

- Voltage: `voltage_l1`, `voltage_l2`, `voltage_l3`.
- Current: `current_a`, `current_b`, `current_c`.
- Energy: `energy_kwh`, FC03 address `0x008A`, two registers, IEEE-754 float32 ABCD, decoded raw value divided by 1000.
- Energy polling is intentionally slow relative to V/I (approximately 30 seconds).
- Provisional P/Q/S/PF/f/kvarh/kVAh are not accepted or persisted.

## Dashboard

The deployed dashboard has OVERVIEW, LIVE, ENERGY, COMPARE, and SYSTEM views. It includes accepted V/I/kWh, interval-derived demand, bounded server-side aggregation, deterministic observations, coverage/gap reporting, responsive light/dark themes, and collapsed engineering details.

## Database and recovery

The PostgreSQL mount-dependency repair is deployed at a high level: PostgreSQL startup waits for the PGDATA mount before starting. Do not alter PGDATA, WAL, database files, schemas, tables, or records as part of ordinary continuation.

## Current unresolved work

1. Field-seal P/Q/S/PF/f.
2. Decide/validate kvarh and kVAh.
3. Authoritative CT/PT field verification.
4. Optional retention/aggregation later.
5. Controlled reboot-resilience verification if still not completed.
6. Final closure documentation after those tasks.

## Safety rules

- No Modbus writes or broad scans.
- No second serial owner.
- Do not promote guessed measurements.
- Protect accepted V/I/kWh and keep unresolved values out of persistence.

## Resume sequence

1. Clone this repository and read this file.
2. Establish local Tailscale access.
3. SSH to `ais@100.73.124.7`.
4. Check `/health`, `/diag/raw`, dashboard `/healthz`, PostgREST, PostgreSQL readiness, and `/dev/ttyUSB0` ownership.
5. Compare deployed hashes with `docs/project-status.md`.
6. Continue only from **Current unresolved work** with explicit scope approval.
