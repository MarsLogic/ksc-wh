# Project status snapshot

Snapshot date: 2026-09-09 (runtime snapshot; PIDs are not permanent identifiers).

- Production meter process: healthy, snapshot PID `78981`.
- Dashboard process: healthy, snapshot PID `89584`.
- `/dev/ttyUSB0`: owned only by production PID `78981`.
- PostgreSQL/PostgREST: healthy and responding.
- Accepted: voltage L1/L2/L3, current A/B/C, total positive active energy `energy_kwh`.
- Unaccepted: active/reactive/apparent power, PF, frequency, kvarh, kVAh.
- Production hashes: `fcn300_api.py` `4327fdbb6e6154aef964c47824a14a85b95cad4f5889b7ebc8d1cb372544870f`; `fcn300_reader.py` `969106446053dc44c18f8b851dd3b2865a9ce31b135256952d182dd63a860d86`.
- Dashboard hashes: `app.py` `611be429cc2b084a8cd4ff55851ce0011bf4273ff92c8d158f06f39a44b0243f`; `index.html` `3dfc23f926ebea43c6549a96089e36a3ab09b59fb291093274871f0619d35192`; `app.js` `2acb41b05dd5b97be12c670fc41a8c6b80c1de6aabe334ff1524130aef69816c`; `style.css` `80b1ab38e745d7520f807d8d3f49c9ffcc6260bd203e918197336d42e42c0ec7`.
- Dashboard rollback backup: `/home/ais/fcn300-diagnostics/backups/final-pass-20260909T124102Z/`.
- PostgreSQL mount repair plan/evidence remains on the server and in the summarized evidence set.
- Known physical risk: RS485/UTP route and field wiring remain a physical verification item.
