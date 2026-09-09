# Architecture

The meter is owned by one production Python process. That process performs read-only Modbus RTU polling, exposes accepted values over HTTP, and writes accepted fields to PostgreSQL through the existing persistence path. PostgREST exposes the table for read-only reporting. The dashboard server adds bounded reporting endpoints and serves the vanilla HTML/CSS/JS operator console.

The dashboard's historical endpoints aggregate on the server. The browser never receives the raw five-second table history. Energy uses cumulative-counter differences, never sums cumulative samples.
