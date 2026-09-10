# Agent rules

1. Read `HANDOFF.md`, `DEFAULT.md`, `ARCHITECTURE.md`, and `REGISTER-MAP.md` before significant changes.
2. Preserve current production behavior and rollback paths.
3. Never issue FCN300 Modbus writes or broad register scans.
4. The production process must remain the sole `/dev/ttyUSB0` owner.
5. Use accepted measurements only unless explicit evidence and approval promote another value.
6. Do not persist provisional fields or change the database schema casually.
7. Prefer stdlib and vanilla HTML/CSS/JS; avoid unnecessary frameworks/services.
8. Write deterministic tests before any production deployment.
9. Keep the dashboard industrial, compact, readable, and preserve `Made by iw3_`.
10. Use low-cost models for deterministic execution; escalate reasoning only for genuine ambiguity.
