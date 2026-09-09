# Recovery notes

Known application backups:

- `/home/ais/fcn300-diagnostics/backups/final-pass-20260909T124102Z/`
- `/home/ais/fcn300-diagnostics/backups/dashboard-20260909T115259Z/`
- `/home/ais/ais-energy/fcn300_api.py.state-bak-20260908T133709Z`

Dashboard rollback is a file-level restore from the matching dashboard backup followed by the existing approved dashboard process procedure. Production meter rollback is a file-level restore only after explicit approval and a pre-change hash capture.

The PostgreSQL repair is a mount-order dependency fix. Investigate in this order: confirm the PGDATA mount, run `pg_isready`, inspect PostgreSQL service state/journal, inspect PostgREST, then inspect application health. Do not use destructive database recovery commands, alter WAL, initialize PGDATA, or modify records as part of routine recovery.
