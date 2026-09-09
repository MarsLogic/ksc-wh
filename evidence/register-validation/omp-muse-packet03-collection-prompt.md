Continue the FCN300 Packet 03 observation on `ais@100.73.124.7`. This is raw evidence collection only. Do not infer, decode, rank, or promote register mappings.

The temporary production owner is `ais-energy.service`, currently using `/home/ais/ais-energy/fcn300_api.py` SHA-256 `4ae40bfe80e14054294b85e257bcbaa4acf76d0344e82ab4be2663d30f404bcb`. The sole serial owner must remain that service. Never open `/dev/powermeter` or `/dev/ttyUSB0`, import a serial library, execute a Modbus client, restart a process, change a file, change meter settings, switch loads, repair PostgreSQL, or query any register directly.

Read only these repaired loopback endpoints:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/diag/raw`

The enabled rotating FC03 windows are exactly `(0x0040,2)`, `(0x0064,8)`, `(0x006C,4)`, `(0x0070,8)`, `(0x0078,4)`, `(0x007C,8)`, and `(0x0084,8)`. `0x0060+4` is disabled. Do not expand this list. Each `/diag/raw` response contains validated V/I words plus at most one rotating candidate block. Candidate block metadata includes `ok`, `coherent`, `attempt_timestamp`, `source_timestamp`, `completed_timestamp`, `session_id`, `sequence`, `function_code`, `start`, `count`, and `elapsed_ms`.

Before collection, read and preserve these files in the manifest without modifying them:

- `/home/ais/fcn300-diagnostics/evidence/discovery-allowlist.json`
- `/home/ais/fcn300-diagnostics/evidence/existing-evidence-reanalysis.json`
- `/home/ais/fcn300-diagnostics/evidence/reconciled-baseline-20260908T150842Z.json`

Create one new evidence directory named `/home/ais/fcn300-diagnostics/evidence/packet03-observation-<UTC>/`. Write `samples.jsonl` and `manifest.json` there. Poll no more often than once every 5 seconds. Stop at 20 minutes or 240 attempts, whichever occurs first. Use a monotonic schedule so an endpoint timeout does not cause a catch-up burst.

For every attempt, record one client UTC timestamp, the complete unmodified JSON bodies from both endpoints, HTTP/error status for each request, request start/end timestamps, and the measured skew between the two requests. Preserve all source timestamps and the complete `blocks` object. Do not flatten away block provenance and do not replace missing data with zero. Duplicate sequences are valid raw evidence and must remain present.

A usable attempt requires all of the following: the root response has `serial_ok=true`, `vi_status="VALID"`, and `sample_age_seconds<=5`; `/diag/raw` has `serial_ok=true`; exactly one block whose `source` begins `Packet 03 discovery` is present; that block has `ok=true`, `coherent=true`, FC03, a start/count in the enabled list, non-null session/sequence/timestamps, and every word in its declared range is present in `raw`. Mark other attempts unusable without repairing or retrying them early.

Stop immediately after five consecutive unusable attempts. Also stop if the discovery session changes, production is no longer the sole serial owner, validated V/I becomes stale, a candidate start/count falls outside the allowlist, or repeated candidate `elapsed_ms` values exceed approximately 1000 ms. Record the stop reason verbatim. Do not restart or fix anything.

Observe only natural machine load. Do not request or perform load actuation. If the operator independently supplies timestamped panel readings, preserve them verbatim in `panel-reference.jsonl` with the operator timestamp and receipt timestamp; do not interpolate or associate them to a register in this collection task.

At completion, compute file SHA-256 hashes and write them into `manifest.json`. Report attempt count, usable/unusable count, first/last client and source timestamps, observed session ID, sequence range, count per enabled block, V/I ranges, any operator-reference record count, stop reason, paths, and hashes. Return raw evidence and this manifest only. Make no mapping claims.
