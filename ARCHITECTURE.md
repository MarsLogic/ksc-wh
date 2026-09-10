# Production architecture

```text
FCN300-POWER-1
  │ read-only Modbus RTU; sole serial owner
  ▼
ais-energy.service · /home/ais/ais-energy/fcn300_api.py · :8080
  ├─ live accepted telemetry ──────────────────────────────┐
  └─ accepted fields every ~5 s → PostgREST :3000 → PostgreSQL 14
                                                           │
fcn300-dashboard.service · /home/ais/fcn300-diagnostics/app.py · :8090
  ├─ /api/live combines :8080 with observable recorder state
  ├─ /api/history performs bounded, display-resolution aggregation
  ├─ /api/energy derives consumption from cumulative counters
  └─ static vanilla HTML/CSS/JS + vendored uPlot ◀─────────┘
```

`ais-energy` is the only `/dev/ttyUSB0` owner and the only recorder. The dashboard has no serial code and no write path to the meter. Recording continues without a browser or dashboard client.

Live and history fail independently: `/api/live` remains usable if PostgreSQL/PostgREST or the optional diagnostics side-channel fails. PostgreSQL uses `/mnt/sambashare/pgdata`; its existing mount dependency must remain intact. PostgREST is the established persistence/history boundary; do not add another database, queue, broker, or acquisition process speculatively.

Current persistence stores phase voltage/current; total P/Q/S/PF/f; and positive active/reactive/apparent energy. Per-phase P/Q/S/PF are live-only because they are not persisted. Historical UI must never imply otherwise.

At the current scale (37,449 rows at the 2026-09-10 audit), the dashboard reads at most 60,000 selected rows, caches reports for 30 seconds, and returns fixed visualization buckets: live 5 s, 1 h 10 s, 24 h 1 min, 7 d 5 min, and 30 d 15 min. When real volume reaches that ceiling, add a narrow PostgreSQL aggregate view/RPC; TimescaleDB is not justified.

Rollback: restore the timestamped dashboard backup and restart only `fcn300-dashboard.service`. Collector/database rollback is outside ordinary dashboard changes.
