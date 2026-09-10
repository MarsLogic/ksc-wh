# Database

The deployed database is PostgreSQL 14 with PostgREST in front of the `public.water_monitoring` table. PGDATA is mounted at `/mnt/sambashare/pgdata`; a systemd mount dependency is installed so PostgreSQL starts after the mount is available.

Accepted persisted fields are device name, voltage L1/L2/L3, current A/B/C, total active/reactive/apparent power, power factor, frequency, and primary positive `energy_kwh`, `reactive_energy_kvarh`, and `apparent_energy_kvah`.

The 2026-09-09 migration only added the two nullable energy columns. Existing rows and columns were not rewritten. Rollback is to restore the prior collector/dashboard; the additive nullable columns may safely remain unused.
