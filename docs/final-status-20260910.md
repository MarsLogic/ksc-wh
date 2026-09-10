# FCN300 final status — 2026-09-10

| Item | Result |
|---|---|
| A. Manual match | FCN300-3E4Y addresses, data types, scales, phase relationships, and energy layout match the live meter. Exact physical suffix is not claimed. |
| B. Register map | V/I/P/Q/S/PF/f and primary positive kWh/kvarh/kVAh are **DOCUMENTED + EMPIRICALLY VERIFIED**. |
| C. Energy | One bounded FC03 `0x0082+24` read decoded 1820.88 kWh, 1330.04 kvarh, 54.44 reverse kvarh, and 2286.72 kVAh; every non-zero primary/secondary pair was exactly 40×. |
| D. CT/PT | `0x002A=256`, `0x002C=1`, `0x002D=1`, `0x002E=40`. Effective ratio 40 verified; `0x002A` vendor wording remains ambiguous. No writes were made. |
| E. PostgreSQL root cause | Historical boot failure: `/mnt/sambashare/pgdata` was unavailable before the cluster start. Current mount and PostgreSQL 14 cluster are healthy; `RequiresMountsFor=/mnt/sambashare/pgdata` is active. |
| F. PostgREST root cause | Historical PGRST002/503 was downstream of PostgreSQL being unavailable. `postgrest-ais.service` is now active and read/write-through succeeds. |
| G. Repairs | Preserved the existing cluster; no PGDATA/WAL/record rewrite. Added only nullable `reactive_energy_kvarh` and `apparent_energy_kvah` columns. |
| H. Migration | Production collector now uses authoritative FC03 blocks, persists accepted totals, exposes phase details and metadata, and contains no discovery hook. Dashboard shows direct power/quality and cumulative energy. Legacy OMP `diag` was retired and replaced with enabled `fcn300-dashboard.service`. |
| I. Tests | Decoder, reporting, Python compile, JavaScript syntax, live physics, exact 40× energy ratios, PostgREST readback, health endpoints, and single-owner checks passed. |
| J. System | Collector/dashboard/PostgreSQL/PostgREST active; persistence OK; sole `/dev/ttyUSB0` owner is the collector. |
| K. Physical check | Confirm the device-label suffix; optionally clarify the vendor meaning of raw CT quantity 256. RS485 cable/routing inspection remains physical-only. |
| L. Next step | With an approved maintenance window, reboot the host once and repeat the documented health/ownership checks. |

Rollback backups: `/home/ais/ais-energy/backups/manual-commissioning-20260909T1805Z/` and `/home/ais/fcn300-diagnostics/backups/manual-final-20260909T1815Z/`.
