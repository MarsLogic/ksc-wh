# KSC-WH Current Handoff

Snapshot: 2026-09-10. This is the authoritative freeze entry point.

## Current project state

Production monitoring is operational. The FCN300-3E4Y register map is documented and empirically verified for V/I/P/Q/S/PF/f and primary positive kWh/kvarh/kVAh. PostgreSQL 14, PostgREST, the production API, and the dashboard were healthy at snapshot time.
The collector and dashboard are enabled user services; user lingering is enabled. The legacy OMP `diag` process has been stopped.

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
- Power: phase and total P/Q/S from `0x0064–0x007B`; PF from `0x007C–0x007F`; frequency from `0x0080`.
- Primary positive energy: `energy_kwh` at `0x008A`, `reactive_energy_kvarh` at `0x008E`, and `apparent_energy_kvah` at `0x0096`; IEEE-754 float32 ABCD divided by 1000.
- Energy polling is intentionally slow relative to V/I (approximately 30 seconds).

## Dashboard

The deployed dashboard has OVERVIEW, LIVE, ENERGY, COMPARE, and SYSTEM views. It includes accepted V/I/P/Q/S/PF/f and kWh/kvarh/kVAh, interval-derived demand, bounded server-side aggregation, deterministic observations, coverage/gap reporting, responsive light/dark themes, and collapsed engineering details.

## Database and recovery

The PostgreSQL mount-dependency repair is deployed at a high level: PostgreSQL startup waits for the PGDATA mount before starting. Do not alter PGDATA, WAL, database files, schemas, tables, or records as part of ordinary continuation.

## Current unresolved work

1. Physically confirm the exact meter model suffix on the device label.
2. Resolve the vendor wording for raw CT quantity `0x002A=256`; effective primary/secondary ratio 40 is already verified.
3. Optional retention/aggregation later.
4. Controlled full-host reboot-resilience verification if required by operations.

## Safety rules

- No Modbus writes or broad scans.
- No second serial owner.
- Do not promote guessed measurements.
- Protect accepted measurements and keep unresolved interpretations out of persistence.

## Resume sequence

1. Clone this repository and read this file.
2. Establish local Tailscale access.
3. SSH to `ais@100.73.124.7`.
4. Check `/health`, `/diag/raw`, dashboard `/healthz`, PostgREST, PostgreSQL readiness, and `/dev/ttyUSB0` ownership.
5. Compare deployed hashes with `docs/project-status.md`.
6. Continue only from **Current unresolved work** with explicit scope approval.
