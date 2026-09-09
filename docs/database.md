# Database

The deployed database is PostgreSQL 14 with PostgREST in front of the `public.water_monitoring` table. PGDATA is mounted at `/mnt/sambashare/pgdata`; a systemd mount dependency is installed so PostgreSQL starts after the mount is available.

Accepted persisted fields are device name, voltage L1/L2/L3, current A/B/C, and `energy_kwh`. Provisional active/reactive/apparent power, power factor, frequency, kvarh, and kVAh remain NULL/not accepted. No schema or retention change is part of this freeze.
