# Project status snapshot

Snapshot date: 2026-09-10 after FCN300-3E4Y manual reconciliation (PIDs are not permanent identifiers).

- Production meter process: healthy, snapshot PID `112097`.
- Dashboard process: healthy, snapshot PID `112923`; `fcn300-dashboard.service` is enabled under user lingering.
- `/dev/ttyUSB0`: owned only by production PID `112097`.
- PostgreSQL/PostgREST: healthy and responding.
- Accepted: V/I, phase and total P/Q/S, phase and total PF, frequency, and primary positive kWh/kvarh/kVAh.
- Production hashes: `fcn300_api.py` `354d422870a25b844d4853983f62bbc78220f68d6739217bc8b650d9e81f66d3`; `fcn300_reader.py` `969106446053dc44c18f8b851dd3b2865a9ce31b135256952d182dd63a860d86`.
- Dashboard hashes: `app.py` `611be429cc2b084a8cd4ff55851ce0011bf4273ff92c8d158f06f39a44b0243f`; `index.html` `48e2a4ddbbcd0e4f3835c9cad7b24323a698a9a4ed382b48d56cf69c8ca9eba1`; `app.js` `53234ab5ca6966f63a36971c65685419d68b8ed5bc10530f563336e91e8cfdff`; `style.css` `80b1ab38e745d7520f807d8d3f49c9ffcc6260bd203e918197336d42e42c0ec7`.
- Immediate rollback backups: `/home/ais/ais-energy/backups/manual-commissioning-20260909T1805Z/` (pre-task API) and `/home/ais/fcn300-diagnostics/backups/manual-final-20260909T1815Z/` (pre-final API/dashboard/schema).
- PostgreSQL and PostgREST were live-verified healthy; the PGDATA mount dependency is installed and active.
- Manual commissioning evidence: `evidence/energy/manual-commissioning-20260909T180623Z.json`.
- Closure report: `docs/final-status-20260910.md`.
- Known physical risk: RS485/UTP route and field wiring remain a physical verification item.
