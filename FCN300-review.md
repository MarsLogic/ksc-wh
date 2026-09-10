## 1. EXECUTIVE VERDICT

**Keep the present V/I cutover. Do not call the complete meter feed validated or the persistence path healthy.**

This read-only review inspected the live server on **2026-09-08, 12:05–12:13 UTC**, the requested source files, frontend, historical captures, field images, services, ports, APIs, and logs. No remote files, services, serial settings, or registers were changed. Offline reproductions ran only against local copies.

What is solved: FC03 phase voltage at `0x0042–0x0047` and phase/average current at `0x0058–0x005F`, high word first, uint32 divided by 10000. The production code reads complete blocks, commits the complete V/I set, excludes corrections, and supervises poller exceptions. These mappings should remain in service.

What is not solved: trustworthy P/Q/S/PF/frequency/energy, CT/PT interpretation, fully honest freshness, and persistence. At 12:09:32 UTC, the API returned approximately **231.85/233.64/232.42 V** and **7.212/7.068/7.856 A**, alongside unvalidated `50.01 Hz`, `0.484 kW`, `0.156 kvar`, **PF −3.04**, and **563.947 “kWh”**. The latter fields must leave the operational measurement contract.

Actual runtime:

- Production is **`systemctl --user ... ais-energy.service`**, PID 15402, active since 11:51:01 UTC, `NRestarts=0` at inspection. The system-level unit is absent; querying that scope alone misleadingly reports inactive.
- `/dev/ttyUSB0` had one visible owner: production PID 15402. Port 8090 PID 12158 runs `python3 app.py` from the diagnostics directory, attached to an existing login session rather than a diagnostic service unit.
- The frontend renders rejected current channels and omits the validated quad cards, although `/api/live` contains them.
- PostgreSQL **14-main is down**. Its boot log says `/mnt/sambashare/pgdata` was inaccessible or absent. That directory and its ext4 mount exist now. PostgREST cannot find its PostgreSQL socket and returns 503/PGRST002. Mount ordering is a plausible underlying cause, not yet proven.
- The existing energy watch remains running: **9 identical rows, 11:33:08–12:13:09 UTC**. Older saved captures and a current successful raw snapshot extend the observed equality to approximately **104 minutes**, crossing the production restart. The scheduled three-hour watch is not complete.

The remaining defects deserve the first bounded maintenance change, but I found no currently demonstrated emergency requiring an unreviewed production edit during this session. In particular, persistence is failing rather than currently accepting the bad payloads. **Remove unvalidated payload fields before restoring database writes.**

Preserved evidence is in `audit-source/` and `audit-evidence/`; `audit-checks.py` reproduces the freshness defects without serial access. Five core source hashes matched the server. The report is a decision and execution handoff, not a claim that unresolved quantities have been discovered.

## 2. AUTHORITATIVE REGISTER STATE

All addresses below are **zero-based hexadecimal PDU addresses**. Width counts 16-bit registers. `BE-u32` means `(word_at_start << 16) | word_at_start_plus_1`; Modbus specifies register-byte ordering, while the multi-register word convention here is established empirically on this meter.

Evidence classes: **A** = actual-meter observations; **B** = exact-model documentation; **C** = related-family documentation; **D** = fitted or structural hypothesis. No mapping currently has class B support. Family documentation does not supply reliable address-level corroboration.

| Quantity | Address | FC | Width | Encoding | Scale | Confidence | Evidence | Production status |
|---|---|---|---|---|---|---|---|---|
| Phase voltage A | `0x0042–0043` | 03 | 2 | BE-u32 | ÷10000 V | **PROVEN**, within empirical scope | A: field image, saved/live raw, correct production decode | Enabled |
| Phase voltage B | `0x0044–0045` | 03 | 2 | BE-u32 | ÷10000 V | **PROVEN** | A: same | Enabled |
| Phase voltage C | `0x0046–0047` | 03 | 2 | BE-u32 | ÷10000 V | **PROVEN** | A: same | Enabled |
| Average phase voltage candidate | `0x0048–0049` | 03 | 2 | BE-u32 candidate | ÷10000 V | **PLAUSIBLE** | A+D: values agree approximately with phase mean | Diagnostic raw only |
| Phase current A | `0x0058–0059` | 03 | 2 | BE-u32 | ÷10000 A | **HIGH CONFIDENCE** | A: recorded load response, field correspondence, current live comparison | Enabled |
| Phase current B | `0x005A–005B` | 03 | 2 | BE-u32 | ÷10000 A | **HIGH CONFIDENCE** | A: reported B-highest 14/14 at the historical load | Enabled |
| Phase current C | `0x005C–005D` | 03 | 2 | BE-u32 | ÷10000 A | **HIGH CONFIDENCE** | A: recorded field and load correspondence | Enabled |
| Average current | `0x005E–005F` | 03 | 2 | BE-u32 | ÷10000 A | **HIGH CONFIDENCE** | A: reported mean-identity error ~0.06%; live consistency | Enabled |
| L-L voltage group; exact phase labels unknown | `0x004C–004D`, `004E–004F`, `0050–0051` | 03 | 2 each | BE-u32 candidate | ÷10000 V | **PLAUSIBLE** | A+D: ~400 V and phase-voltage consistency; no direct L-L panel seal | Diagnostic only |
| L-L average candidate | `0x0052–0053` | 03 | 2 | BE-u32 candidate | ÷10000 V | **PLAUSIBLE** | A+D: consistent with mean of preceding triple | Diagnostic; low word also misused as energy |
| Old phase currents | `0x0070–0075` | 03 | 2 each | Mixed i32/u32 as implemented | ÷10000 A | **REJECTED as phase currents** | A: substantial phase mismatch at high and low load | Still shown as Current A/B/C in diagnostic UI |
| H2 phase-current interpretation | `0x0064–0069` | 03 | 2 each | BE-u32 | Fitted ÷1790 A | **REJECTED as a reliable current mapping** | D: fitted scale; present B/C mismatch about 10–11% in the 12:07 snapshot | Diagnostic API candidate only |
| H2 power interpretation | `0x0064–0069`; inspect adjacent pair `006A–006B` | 03 candidate | 2 each candidate | Signed/unsigned 32-bit to determine | ÷10000 kW is a hypothesis | **PLAUSIBLE hypothesis; quantity UNKNOWN** | D: natural decimal scale gives plausible phase kW at low/high load; no P reference | Do not publish |
| Legacy frequency | `0x001A` | 03 | 1 | u16 | ×0.001447 | **REJECTED as a validated mapping** | D: fitted coefficient; no independent current validation | Still published |
| Legacy active power | `0x0020` | 03 | 1 | u16 | ×0.00001466 in API | **REJECTED** | D: fitted, frozen-looking; reader uses another scale | Published and submitted in attempted POSTs |
| Legacy reactive power | `0x0022` | 03 | 1 | u16 | ×0.0000406 in API | **REJECTED** | D: same problem | Still published |
| Legacy apparent power | `0x0024` | 03 | 1 | u16 | ×0.01 in old reader | **REJECTED as a validated mapping** | D: unsupported legacy definition | Absent from active API; present in dormant reader |
| Legacy PF | `0x0026` | 03 | 1 | u16 plus offset | ×0.000934 −3.28 | **REJECTED** | A: live −3.04 violates PF bounds | Still published |
| Legacy kWh | `0x0053` | 03 | 1 | u16 plus offset | ×0.01 +246.867 | **REJECTED** | A: volatile voltage-like low word; energy falls across current snapshots | Published and submitted in attempted POSTs |
| “1050” energy cluster | `0x0210–0217` | 03 | Four 2-word hypotheses | BE-u32 hypothesis | ÷1e6 kWh hypothesis | **REJECTED for promotion as live total kWh; actual meaning UNKNOWN** | A+D: identical words across ~104 min; fitted magnitude; no P/panel delta | Observation only |
| C1 counter candidate | `0x008E–008F` | 03 recorded | 2 captured; true width unknown | Undetermined | Unknown | **PLAUSIBLE counter, UNKNOWN quantity** | A summary: +15360 counts/~60 s; original rate series not recovered | Not enabled |
| True f, P, Q, S, PF | Not established | Unknown beyond candidates | Unknown | Unknown | Unknown | **UNKNOWN** | No direct reference-backed candidate yet | Must be null/unknown |
| True kWh, kvarh, kVAh | Not established | Unknown | 2/4+ possible, unproven | Unknown | Unknown | **UNKNOWN** | Displayed kWh/kvarh totals exist; no proven register association | Must be null/unknown |
| CT/PT and wiring configuration | Not established | Read function not established | Unknown | Unknown | Unknown | **UNKNOWN** | C: family supports programmable ratios; static words are not a ratio decode | No external multiplier permitted |

The legacy `0x0000/0002/0004/0006/000A/000E` live V/I interpretations are **REJECTED** and absent from active production V/I. Static/aliased data need not be defective hardware: they may be configuration or another data class. Do not extend rejection to every possible use of those addresses.

FC04 response/mirroring on tested V/I addresses has **HIGH CONFIDENCE as a recorded observation**, not proof of a complete FC03/FC04 alias map. Keep production on FC03. The original 14-sample current series was not found among the inspected evidence files; its statistics survive in notes. This limits reproducibility, but does not justify repeating the entire successful discovery or downgrading the useful V/I result.

## 3. WHAT IS STILL UNKNOWN

1. **Whether downstream users can distinguish valid measurements from legacy nonsense and stale data.** This is the immediate operational defect.
2. **Active power, apparent power, PF, reactive power, and frequency.** They need actual display/reference anchors, definitions, and signedness. Frequency can be identified in parallel with power; a stable 50.xx-looking number alone is weak evidence.
3. **Persistence recovery and historical gaps.** The cluster failure is identified; the precise boot/mount failure and durable correction remain to be established. Meter correctness and database readiness are separate gates.
4. **kWh register, direction, tariff/total meaning, width, scale, reset and rollover behavior.** The old mapping and “1050” coincidence are not usable.
5. **kvarh and kVAh semantics and availability.** Reactive totals may be quadrant/direction counters; apparent energy might not be exposed by this variant.
6. **Exact model/firmware, wiring mode, configured versus installed CT/PT ratios.** The photos identify FORT but do not establish the suffix. Agreement with the display validates replication of that display, not independent verification of the installed CT ratio.
7. **Exact L-L phase assignment and final A/C current seal.** Useful to close during the next panel capture, but not a reason to undo current production V/I.

## 4. CRITIQUE OF PREVIOUS WORK

**The V/I correction was valuable and should stand.** The active implementation corroborates its essential safeguards. Production and diagnostic current snapshots are acquired separately, so their small live differences are not decoding failures. A single FC03 transaction protects pair acquisition; it does not prove that the meter internally latches every channel simultaneously. The average register's reported short lag already argues against assuming that stronger property.

**Remaining publication defects are real.** `fcn300_api.py:296` includes legacy P/kWh in every V/I-eligible POST; `post_to_postgrest()` logs failure only at DEBUG while the service uses INFO. Restoring PostgreSQL before filtering that payload would resume contamination. Root API and `/health` do not test measurement age: an offline reproduction served `serial_ok=true` with a year-2000 validated timestamp. No stalled poller was observed live; the failure path is nevertheless present.

**Diagnostic freshness contradicts the comments.** At `fcn300_api.py:331`, `_raw_words.update(raw_new)` retains failed addresses while advancing the timestamp. The supervisor invalidates production flags but not raw health. A failed diagnostic block can also fall back to individual words, losing pair coherence without identifying that loss to the decoder. The watch ignores both health and upstream timestamp. Old words therefore cannot be treated as fresh merely because the collector wrote a new CSV row. The successful current snapshot and cross-restart equality strengthen this particular static-cluster finding, but do not repair the collector.

**The UI problem is larger than duplicate naming.** `app.py:363` selects only the original eight cards, including Current A/B/C at `0x0070–0075`; validated A2/B2/C2 never get DOM elements. `app.js` only patches existing cards. Initial HTML displays historical values under a live badge. Separate `/api/state` and `/api/live` requests can show health for one snapshot and values from another; there is no request deadline, and card stamps can remain “LIVE CANDIDATE” under stale/error conditions. Fix labels, selection, initial state, and one-fetch freshness; no redesign is needed.

**The evidence table is not a lossless capture.** In `register-observations.csv`, line 5's words reconstruct `000EF380`, not `000EF340`; line 8 reconstructs `000FECC5`, not `000FCCD5`. Lines 9/10 decode with their stated `/1790` to **93.6536/104.4469**, not **93.40/142.74**. Preserve these originals as disputed transcriptions; do not silently choose which column represented the meter. The legacy energy row also mixes a corrected output with a description of uncorrected scaling.

**Fitted scale hunting created false authority.** `/1790` and “raw integer /1e6 looks near the panel total” are hypotheses, not identified encodings. The 0x0210 cluster also decodes as ordinary IEEE floats around 0.295–0.326; that is an illustration of ambiguity, not a new PF mapping. The research note's “hours needed for fine energy resolution” rationale is backwards: finer resolution makes a live energy change easier to detect. Historical **~67 kVA is not 67 kW** without PF/P evidence.

**Some historical rejections were too broad.** `0x0070–0075` is rejected as phase current, not as every possible electrical quantity. Signed/bidirectional data cannot be rejected as P or Q just because they decrease. Likewise, a low fragment of a wider counter can jump. Reopen these only for a concrete width/quantity hypothesis using existing contiguous captures first; do not rescan whole regions.

**Diagnostics do affect acquisition cadence.** Current programmed sleeps alone total **2.47 seconds per successful cycle**, before other overhead, so the 1.8-second acquisition claim is false. A failed nine-register diagnostic block plus three-attempt single-word fallback can consume roughly **33 seconds** before other work. The next production V/I cycle waits behind that work. The parsers reject exception frames rather than accepting them as measurements, but do not classify the five-byte exceptions and waste normal-response timeouts/retries. Modbus specifies an exception function code with bit 7 set and an exception code; preserve that distinction. [Modbus application protocol](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf)

**Dormant code and rollback instructions are hazardous.** `fcn300_reader.py` retains frozen mappings, photo constants, zero-as-missing fallback, and fabricated power; it was not the running process. The September 7 handoff's broad rollback restores pre-cutover behavior. Neither `.bak` nor the pre-cutover backup is an acceptable routine rollback for current work. Back up the currently audited file immediately before each maintenance change.

No present serial contention, CRC storm, CT/PT multiplier on validated V/I, or specific cable defect was demonstrated. Do not spend work “fixing” those hypotheses. The diagnostics process lacking service supervision is a small durability issue, not evidence that it has failed.

## 5. SHORTEST PATH TO COMPLETION

1. **Contain misleading output and make evidence trustworthy.** Why: discovery and database recovery otherwise propagate invalid data. Scope: Packet 1; remove legacy operational values/POST fields, correct current cards, publish immutable current-pass raw data, block timestamps/status, age-based V/I readiness, and visible persistence errors. Preserve FC03 V/I. Information gain: subsequent observations have identifiable freshness and coherence. Stop: offline failure checks pass and one deployment smoke check confirms V/I continuity and honest UNKNOWN/error states.

2. **Obtain one useful panel/reference session.** Why: the missing information is identity and units, not another voltage scan. Scope: timestamped model/firmware label if accessible, normal display pages for V/I, total/per-phase P/Q/S/PF/f, kWh/kvarh/kVAh, and documented read-only configuration information. Use natural machine operation; do not actuate loads, enter unverified setting sequences, or alter ratios. Capture at least two stable load levels, ideally three with a holdout; seal A/C assignment if the load distinguishes them. Information gain: anchors for scale, sign, phase order, CT/PT context and energy direction. Stop: usable paired records obtained, or a 20-minute window expires; missing pages remain explicit blockers.

3. **Test the compact measurement neighborhood.** Why: `0x0042/004C/0058/0064/0070` suggests structured groups; H2's natural decimal decode is a better power hypothesis than another fitted current scale. Initial exact scope, FC03 only: `(0x0040,2)`, `(0x0060,4)`, `(0x0064,8)`, `(0x006C,4)`, `(0x0070,8)`, `(0x0078,4)`, `(0x007C,8)`, `(0x0084,8)`. These are request start/count pairs, not asserted mappings. Use one rotating candidate block per production pass, reuse existing V/I samples, and enforce a diagnostic time budget. Do not add every window permanently. The gaps can contain frequency, PF, status, or unrelated values; test against display evidence. Inspect existing captures before any repeated acquisition. Information gain: group roles, totals, plausible signedness, and scale. Stop: unique reference-supported candidates emerge, all eight windows are evaluated, or freshness/error budgets fail. If unresolved, issue a specific next-evidence request; do not automatically expand to `0x00C0–00FF`, `0x0258+`, or FC04 sweeps.

4. **Validate power/frequency before new energy hunting.** Why: validated P supplies the energy-rate reference. Scope: two stable load plateaus plus an independent holdout/transition; same-block phase/total identities where applicable; V/I/P/Q/S/PF capture skew recorded and preferably ≤2 seconds. At the recorded high-load reference, arithmetic `ΣVI/1000 ≈ 66.87 kVA`; at this audit's low load it is **~5.15 kVA**. These are calculated constraints, not measured P or an authoritative S register. Test `|P|≤S`, PF bounds, and `P/S` only for matching definitions. Use `S²≈P²+Q²` as a conditional consistency check: harmonic distortion, unbalance, and different definitions of total/reactive power can prevent equality. True PF differs from displacement cosφ in distorted systems. Information gain: an independently validated P and an honest classification for every other quantity. Stop: each candidate passes an independent reference and holdout, or remains UNKNOWN with the failed constraint recorded. A conventional 1% power/current comparison and ±0.02 Hz frequency comparison may be provisional screening limits; final limits must include documented instrument accuracy, display resolution, and timing uncertainty. [Fluke measurement definitions](https://assets.fluke.com/manuals/F430-II_umeng0100.pdf)

5. **Observe energy only with a validated rate and identified direction.** Why: absolute numerical resemblance is weak; counter increments and panel deltas discriminate. Scope: first analyze existing `/tmp/sweep*.json`, `e1*.json`, `e2*.json` offline, including intact four-word groups. First new bounded candidate block, if still justified: **FC03 `0x008C`, count 12**, containing recorded C1 `0x008E` and adjacent words for width/order checks. No automatic high-address search. Pair counter samples with fresh P; add Q/S integrations only after those definitions are validated. Use positive/negative P separately for import/export, and the meter's stated quadrant/tariff rules. Choose duration from expected increment and candidate resolution: target at least ten counts and a detectable panel increment, normally two 10–30-minute loaded intervals. Integrate timestamped P trapezoidally; do not fill missing spans. Stop at decisive agreement/rejection, at 60 minutes without sufficient excitation, or on invalid samples. Static 0x0210 words stay rejected for live-total promotion; do not choose a new divisor to revive them. Unknown width, reset, direction or tariff means no production energy promotion.

6. **Recover persistence separately, after payload containment.** Why: PostgreSQL failure is now concrete and independent of Modbus. Scope: inspect `postgresql@14-main`, the `/mnt/sambashare` mount, existing cluster identity, permissions and mount/unit timing; verify why boot access failed. If mount ordering is confirmed, a small dependency such as `RequiresMountsFor=/mnt/sambashare/pgdata` may be appropriate after checking existing units. Start only the verified existing cluster; do not initialize a replacement, change ownership recursively, or delete recovery files. Validate PostgREST readiness and the real table contract before enabling proven-only writes. Information gain: confirmed recovery cause and a separately testable persistence gate. Stop: schema access and a tracked valid insert succeed, or escalate the precise database/storage problem. PGRST002 is consistent with PostgreSQL being unavailable while building the schema cache. [PostgREST error reference](https://docs.postgrest.org/en/v12/references/errors.html)

Execution order is **Packet 1 → Packet 3 preflight/allowlist → Packet 2 collection → Packet 3 analysis → Packet 4 → Packet 5**. Database diagnosis can run independently; recovery of writes must follow containment. Promote newly proven fields incrementally; do not wait for every optional quantity.

## 6. FINAL TARGET ARCHITECTURE

Keep one serial owner and the existing small Python applications. No broker, new database, framework, or general register-scanning service is needed.

- **One authoritative measurement table:** stable key, PDU address, FC, word count/order, signedness, rational scale, unit, phase/direction semantics, confidence, evidence ID, and map version. Only accepted entries feed production. A separate candidate list cannot override them. Reuse the same pure decode function in diagnostics; remove the swap-to-fit-historical-snapshot convention. Preserve original historical captures unchanged and normalize them explicitly when needed.
- **Raw acquisition:** validated V/I first; reuse those words for diagnostics. Publish complete immutable blocks with boot/session ID, sequence, start/end times, FC, address/count, raw words and result. Missing/failed blocks do not inherit old words. No single-word fallback for multiword measurements. Bound serial read/write/retry time; distinguish timeout, CRC, wrong slave/function/count and Modbus exception code. Close failed serial handles explicitly.
- **Validation:** separate mapping confidence from sample quality. Validate complete width, successful transaction, freshness, finite/type/range constraints and relevant physical identities. Do not cap real current at the historical maximum or force a power triangle to hide unbalance/distortion. Keep V/I group commit complete; a failure in an optional field need not erase good V/I.
- **Freshness and serial health:** monotonic acquisition age and deadlines govern validity; UTC timestamps identify records. `serial_ok` has a documented transport meaning. `measurement_ok`/readiness requires fresh accepted fields. A stopped or blocked poller ages out without needing another poll. Liveness can stay HTTP 200; readiness must expose failure. Diagnostic illegal addresses do not imply that the whole serial link is offline.
- **API:** keep stable measurement keys where consumers need them, with `null` and explicit `unknown/invalid/stale` reason. Expose last-good values only as clearly named historical values with original timestamps. Do not return photo constants, guessed zeros, adjusted PF, or legacy energy as current measurements. Freshness and confidence are independent metadata.
- **PostgREST:** accepted fresh fields only; obey actual schema nullability/defaults. Never substitute zeros to satisfy constraints. Track last attempt/success, status, bounded error detail and failure count. Use a bounded worker/backoff; meter polling must continue independently. Record lost intervals. Do not claim that reconstructed energy recreates missed instantaneous measurements; durable local buffering is a separate requirement to size explicitly, not an unlimited queue added by default.
- **Frontend/diagnostics:** correct canonical current cards, UNKNOWN on first paint, one `/api/live` request per refresh with deadline and no overlap, client-side age progression, honest per-card states, and a separate rejected-candidate evidence area. A small user service for 8090 is appropriate if the dashboard must survive logout/reboot.
- **Retention:** raw transaction records, reference images with timestamps, map versions, analysis scripts and explicit acceptance/rejection records. Derived CSV is generated from raw evidence. Preserve full counter width; use integer/decimal arithmetic for large counters, and strings where JSON consumers would lose uint64 precision. Recognize rollover only when width and boundary/rate evidence support it; resets, replacements and gaps start a new segment. No compensating offsets that conceal resets.

## 7. TASK PACKET — LUNA/SOL MEDIUM

**OBJECTIVE**

Perform one bounded containment and presentation cleanup on `ais@100.73.124.7`. Prefer Sol Medium for the health/cache portion; Luna is suitable for the deterministic UI/data portion. Preserve the current proven V/I behavior. Do not perform discovery.

**FILES**

`/home/ais/ais-energy/fcn300_api.py`, `/home/ais/ais-energy/fcn300_reader.py`; `/home/ais/fcn300-diagnostics/{app.py,decoder.py,register_map.py,static/app.js,static/style.css,docs/register-research.md,data/register-observations.csv}`. Create a focused offline regression check and a dated change/evidence note. Inspect `/home/ais/.config/systemd/user/ais-energy.service` for the actual service scope.

**KNOWN INPUTS**

Production FC03 `(0x42,6)` decodes V A/B/C; `(0x58,8)` decodes I A/B/C/average, BE-u32/10000, no corrections. Active service is a user unit. Root API still publishes legacy f/P/Q/PF/kWh; attempted POST includes invalid P/kWh. `_raw_words.update()` retains failed words; production readiness lacks age validation. UI selects old Current A/B/C only. PostgreSQL 14-main is down; leave its repair separate. The historical `.bak` files predate safe V/I and are not rollback targets.

**EXACT ALLOWED ACTIONS**

1. Inspect current hashes/diffs and create timestamped backups of the currently running revision before editing. If another agent has changed it, reconcile that revision first.
2. Make unresolved operational f/P/Q/S/PF/kWh/kvarh/kVAh null with explicit status. Remove unresolved fields from POSTs, subject to an inspected schema contract; while the DB is unavailable, keep those writes disabled or omit them, never invent placeholders. Decouple V/I health from the obsolete legacy-read `cache_ok` path; merely emptying `REG_MAP` would leave the old health logic false.
3. Replace raw snapshots per pass; include per-block success/source time and mark multiword fallback data invalid for discovery. Reuse validated V/I block words. Add a five-second initial V/I age deadline, expose sample age, and invalidate raw status on poller exceptions. Bound diagnostic retries so they cannot keep readiness falsely healthy. Prefer skipping failed candidate blocks over per-word fallback.
4. Show the validated quad as canonical Current A/B/C, retain rejected addresses only in an evidence area, initialize cards UNKNOWN, and use one timed `/api/live` fetch with age-aware card states. Keep the current visual layout.
5. Surface PostgREST failures at an observable level and expose persistence health independently. Disable the obsolete reader entry point with a clear deprecation message before it opens serial. Correct misleading documentation, preserving disputed original CSV rows and generating a separate corrected/annotated table rather than rewriting history.
6. Run offline mocked failure checks before deployment. Use one coordinated production restart and, if Python diagnostic code changed, one targeted restart of its verified PID/launcher. A JS-only edit needs no process restart.

**FORBIDDEN ACTIONS**

No new register acquisition regions, independent serial client, Modbus writes, CT/PT/settings changes, database recovery, guessed power/energy, bulk kill command, UI redesign or framework. Do not restore pre-cutover code or “correct” V/I numerically.

**ACCEPTANCE CRITERIA**

V/I remains BE-u32/10000 FC03 with complete group commit and no corrections. Failed/missing pairs are not fresh decodes; a stalled poller ages out; a serial exception invalidates both production and diagnostic health. Startup has UNKNOWN values. The visible current cards use `0x58/5A/5C`. Unvalidated operational fields are null and cannot reach persistence. PostgREST failure is visible while V/I remains usable. Perform a short post-deploy API/serial-owner check, not a prolonged observation.

**OUTPUT FORMAT**

Changed-file/line summary; pre/post hashes and backups; offline test command/results; one live API snapshot; service/PID and sole-owner result; remaining issues. Save the note under `/home/ais/fcn300-diagnostics/evidence/cleanup-<UTC>.md`.

**ROLLBACK**

Restore only the immediately pre-task audited files, restart only affected processes, and recheck V/I. If rollback reintroduces invalid POST fields, keep persistence disabled pending repair. Never use the September 7 `.bak` or pre-cutover backup as the default.

## 8. TASK PACKET — OMP/MUSE

**OBJECTIVE**

Collect a bounded, trustworthy set of natural-load observations for power/frequency analysis on `ais@100.73.124.7`. Run a small collector process; do not spend an agent turn repeatedly polling or interpreting registers.

**FILES**

Read `/home/ais/fcn300-diagnostics/evidence/cleanup-*.md` and the latest `discovery-allowlist.json` created by the discovery analyst. Write `/home/ais/fcn300-diagnostics/evidence/power-observation-<UTC>.jsonl`, a manifest and a summary. Read loopback `:8080/diag/raw`, `:8080/`, and/or the repaired block-provenance endpoint documented in the cleanup note. Do not open serial.

**KNOWN INPUTS**

V A/B/C are FC03 0x42/44/46 pairs; I A/B/C/average are 0x58/5A/5C/5E pairs; all BE-u32/10000. The old root P/Q/PF/f/kWh values are not references. H2 0x64/66/68 is an unknown quantity; /1790 is not an accepted current scale. The previous energy collector ignored freshness and must not be reused unchanged.

**EXACT ALLOWED ACTIONS**

1. Confirm cleanup has introduced trustworthy block timestamps, success flags and sequence/session identity. If not, report the missing prerequisite without collecting misleading evidence.
2. If an analyst allowlist is absent, collect only already exposed validated V/I and existing raw 0x64–69/0x70–75, clearly marking the restricted coverage. Do not edit production to add addresses.
3. Fetch at most once every five seconds for at most **20 minutes/240 attempts**. Store collector UTC, source UTC, sequence/session, every block's start/end and status, raw words, stable V/I values, and gaps/errors. Deduplicate by source identity, not by equal word values; successful unchanged values remain legitimate observations.
4. Attach operator-provided panel photos/video references and their times/units. Observe naturally occurring loads only. Retain records for three stable load bands if available; do not claim an artificial timestamp match or force machine operation.
5. Stop early after sufficient paired plateaus and a holdout are captured, or after five consecutive unusable fetches. If insufficient load/reference variation occurs, stop at the deadline and say so.

**FORBIDDEN ACTIONS**

No serial access, service restarts, new address ranges, mapping promotion, fitted divisors, meter/configuration writes, load switching, modified evidence, or unlimited background jobs. Never fill failed samples from prior values.

**ACCEPTANCE CRITERIA**

The manifest identifies the server revision and map/allowlist. Every usable word belongs to a successful identified block; cache repeats, block skew and gaps are explicit. Counts distinguish attempts, unique successful samples and usable panel matches. “Insufficient evidence” is an acceptable completed collection result.

**OUTPUT FORMAT**

File paths, command/PID, start/end/deadline, attempts/unique/invalid counts, load range and plateau times, panel reference index, gap summary, and a one-paragraph handoff to the analyst. No claim that P or energy is solved.

**ROLLBACK**

No service or meter change is permitted. Stop only this collector's recorded PID if cancellation is needed; retain partial data with its stop reason.

## 9. TASK PACKET — SOL MEDIUM P/Q/S/PF/f

**OBJECTIVE**

Identify and validate f/P/Q/S/PF using the smallest bounded experiment on `ais@100.73.124.7`. Produce a separate decision for each quantity; UNKNOWN is preferable to a fitted answer.

**FILES**

`/home/ais/ais-energy/fcn300_api.py`; `/home/ais/fcn300-diagnostics/{register_map.py,decoder.py,docs/register-research.md,data/register-observations.csv,evidence/}`; existing `/tmp/{sweep1,sweep2,e1a,e1b,e2a,e2b,diag-pre-cutover}.json` if still present. Write `evidence/discovery-allowlist.json`, `power-analysis-<UTC>.json`, raw fixtures and an executable offline analysis/check script. Read Packet 1's cleanup note and Packet 2's manifest if available.

**KNOWN INPUTS**

Validated FC03 V: start 0x42 count 6; I: start 0x58 count 8; BE-u32/10000 without CT/PT multiplication. H2 0x64/66/68 is not validated current; BE32/10000 as phase kW is a testable hypothesis. 0x70–75 is rejected only as phase current. Legacy 0x1A/20/22/24/26 and root API power/frequency are not references. Related-family manuals and code comments are not exact-model authority. High-load arithmetic S anchor ~66.87 kVA; audit low-load anchor ~5.15 kVA; neither is measured kW.

**EXACT ALLOWED ACTIONS**

1. Recompute existing raw evidence before new reads. Preserve conflicting CSV columns as disputed; do not treat transcribed decimal values as authoritative bytes. Obtain timestamped normal-display/reference P/Q/S/PF/f and configuration/nameplate context through the operator; do not contact third parties without authorization.
2. After cleanup, define this maximum FC03 start/count allowlist: `(0x40,2),(0x60,4),(0x64,8),(0x6C,4),(0x70,8),(0x78,4),(0x7C,8),(0x84,8)`. Document the hypothesis for each enabled window. Enable only necessary windows through the sole production owner, one rotating candidate block per pass, with a bounded ≤1-second diagnostic transaction budget; abort/skip on failure, never fall back to separate words. Preserve V/I cadence and readiness. Use one backed-up, tested deployment to install this temporary acquisition if needed, not repeated restarts per window.
3. Prefer existing captures and one normal-load dataset; delegate repetitive collection through Packet 2's collector instructions. Retain transaction timing and reference association. Analyze only stable plateaus when cross-block skew is material.
4. Evaluate natural documented decimal scales and standard signed/unsigned/float interpretations selectively. A family-style grouping or plausible number is only a hypothesis. Require scale, order, phase/total and sign behavior to survive independent load points. No free divisor fitting. Frequency needs independent panel/reference agreement; if grid variation is too small to distinguish candidates, obtain exact documentation or a longer cheap reference record instead of declaring proof.
5. Test phase identities, `|P|≤S`, PF bounds and matched-definition `P/S`. Use the power triangle conditionally with documented Q/S definitions. Distinguish displacement PF from true PF, total from phase quantities, and sign of energy flow from inductive/capacitive indication. CT/PT remains unchanged and is applied zero extra times unless independent evidence requires it.
6. Stop after the allowed windows and available plateaus. If nothing uniquely survives, specify one missing reference or a newly justified exact range for later review; do not expand the search automatically.

**FORBIDDEN ACTIONS**

No independent serial reader, FC04 sweep, broad register scan, meter write/config change, unapproved new region, production promotion, power fabricated from assumed PF, or energy hunt. No finding is “proven” merely because it resembles the expected magnitude.

**ACCEPTANCE CRITERIA**

For each of f/P/Q/S/PF: exact mapping/definition with raw fixtures, uncertainty-aware reference comparison, and independent holdout, or UNKNOWN plus the failing/missing test. Require at least two distinct stable load levels and a holdout for load-dependent candidates. Explain any incomplete phase/sign coverage. Preserve existing V/I and enforce freshness/error budgets throughout.

**OUTPUT FORMAT**

One row per quantity: status, FC, PDU address, width/order/type/scale/unit, phase/total/sign semantics, evidence IDs, timestamp/skew, residuals/tolerances, holdout result and promotion eligibility. Include analysis command, exact temporary code diff, acquisition stop condition and the next smallest action. Save the allowlist and machine-readable decisions for the energy/migration agents.

**ROLLBACK**

Back up the immediately pre-task revision. Disable temporary acquisition after collection, restoring the bounded normal diagnostic configuration and verifying V/I. Roll back only task changes if acquisition degrades; never restore old V/I mappings.

## 10. TASK PACKET — ENERGY

**OBJECTIVE**

On `ais@100.73.124.7`, collect and evaluate bounded evidence for kWh first, then kvarh/kVAh only when their corresponding rates and semantics are validated. Do not repeat the static “1050” watch.

**FILES**

`/home/ais/fcn300-diagnostics/evidence/{power-analysis-*.json,energy-watch.csv}`; `docs/register-research.md`; existing `/tmp/{sweep1,sweep2,e1a,e1b,e2a,e2b}.json`; the repaired production raw API. Write `energy-allowlist.json`, `energy-observation-<UTC>.jsonl`, reference metadata and a summary/analysis script under `evidence/`.

**KNOWN INPUTS**

0x0053 is rejected kWh. FC03 0x0210–217 had nine identical watch rows through 12:13:09 UTC on September 8 and matched successful snapshots over ~104 minutes; its /1e6 numerical resemblance is not valid energy evidence. Recorded C1 0x008E/8F increased about 15360 counts/60 seconds, but type/width/unit are unresolved. Panel references historically showed 1055.20 kWh and 726.52 kvarh; these are old references, not current totals. P must come from an accepted analyst mapping, not legacy 0.484 kW or arithmetic kVA.

**EXACT ALLOWED ACTIONS**

1. Verify accepted P evidence and block freshness before any loaded observation. Without accepted P, perform only offline capture analysis and return the missing prerequisite. For kvarh/kVAh, require accepted Q/S definitions as well.
2. Analyze complete two-/four-word groups in saved captures before new reads. Establish explicit candidate order/width and plausible units; do not exhaustively fit scales. First additional candidate acquisition may be **FC03 start 0x008C count 12** only, installed through the discovery agent's bounded sole-owner mechanism. As the collection agent, do not modify production or open serial; if the required block is not available, request that exact prerequisite from the discovery owner.
3. Record at most one snapshot per five seconds, full raw block/quality/times, fresh P and where applicable Q/S, and operator-provided panel totals at interval boundaries. Use two naturally loaded 10–30-minute intervals, with a rate change if available, capped at 60 minutes/720 attempts. Set duration from expected rate and candidate quantum: target ≥10 counts and a visible panel increment. Stop for five consecutive invalid fetches or inadequate excitation at the cap.
4. Integrate actual timestamped rate samples trapezoidally. Segment gaps and resets; distinguish import/export by validated direction. Compare counter and panel increments across both intervals with measurement, sampling, rounding and quantization uncertainty. Fit nothing to a single interval; any proposed conversion must pass the holdout and have an independent unit anchor.
5. Preserve all words for width checks. Treat decreasing raw values as an unresolved reset/wrap/direction event unless a known modulus and near-boundary/rate evidence identify rollover. Do not turn arbitrary negative deltas into `+2^32` energy. Investigate tariff/quadrant totals only from evidence; mark unavailable/unknown kVAh honestly.

**FORBIDDEN ACTIONS**

No resets, energy writes, CT/PT changes, load actuation, broad scans, restoring rejected scales, linear gap filling, production promotion, or additional observation beyond the cap without a new information-gain justification.

**ACCEPTANCE CRITERIA**

A candidate is promotion-eligible only with fresh coherent full-width raw data, correct panel identity/unit/direction, independently anchored conversion, and rate/panel increments agreeing over both intervals. Static data is rejected for the tested live counter role once nonzero expected accumulation is independently established. Missing excitation or references is INCONCLUSIVE, not proof of zero consumption. Optional energy quantities may remain UNKNOWN.

**OUTPUT FORMAT**

Paths/PID/deadline; candidate address/FC/width/order/unit/direction; interval timestamps and coverage; start/end words and panel totals; integrated rate, observed delta and uncertainty; wraps/resets/gaps; ACCEPT/REJECT/INCONCLUSIVE per candidate. Return raw JSONL and a reproducible calculation command.

**ROLLBACK**

Stop only the recorded collector process. Have the discovery owner disable the temporary candidate schedule if one was installed. Preserve partial evidence and existing production V/I/P unchanged.

## 11. TASK PACKET — FINAL PRODUCTION MIGRATION

**OBJECTIVE**

On `ais@100.73.124.7`, migrate only newly accepted measurement fields into the existing production/API/UI/persistence path. Recover persistence as a separately gated operational subtask. Do not rediscover registers or wait for every optional field.

**FILES**

`/home/ais/ais-energy/{fcn300_api.py,fcn300_reader.py}`; `/home/ais/fcn300-diagnostics/{app.py,decoder.py,register_map.py,static/app.js,docs/register-research.md,evidence/}`; user `ais-energy.service`. A small shared `fcn300_map.py` in the production project is allowed if it removes duplicate definitions cleanly. For persistence, inspect `postgresql@14-main.service`, mount/unit configuration for `/mnt/sambashare`, and the existing PostgREST table contract without exposing credentials.

**KNOWN INPUTS**

Keep FC03 V 0x42 count 6 and I 0x58 count 8, BE-u32/10000, no corrections. Accept only evidence packets explicitly passing independent reference/holdout checks; the old API and related-family manual are not acceptance evidence. UNKNOWN optional quantities remain null. Production is a user service. PostgreSQL 14-main failed at boot with inaccessible `/mnt/sambashare/pgdata`; the mount subsequently existed and PostgREST returned 503 because its socket was absent. Containment of invalid fields must precede database recovery.

**EXACT ALLOWED ACTIONS**

1. Audit current files and consumer/schema expectations, snapshot hashes and make immediate backups. Refuse promotion for a field missing address/FC/width/order/scale, quantity/direction definition, reference fixtures, or required holdout.
2. Add accepted fields to one authoritative pure map/decoder and reuse it in production/diagnostics. Keep unknowns null, valid zero distinct from missing, negative P/Q and PF sign meaning intact, and CT/PT multiplication absent unless independently established. Preserve full-width energy integers/decimals and map/reset epochs.
3. Add focused offline tests for accepted raw fixtures and wrong byte/word order, incomplete blocks, exception/timeout/CRC handling, invalid/future timestamps and stale age, real zeros, signed quantities, and documented counter boundary/reset behavior. Do not invent a field-specific limit from the historic load range.
4. Publish acquisition-group snapshots atomically with per-field/group quality; reject invalid persistence fields and separate transport, measurement freshness and DB health. Keep a bounded persistence worker/backoff and observable gaps. Do not make a large architectural rewrite.
5. Persistence subtask: read cluster/mount logs and confirm the existing data directory/cluster identity and permissions. If healthy storage and the boot failure cause are established, make only the minimal evidenced service dependency correction and start the existing cluster. Do not create a replacement database. If evidence suggests damaged storage/recovery or ambiguous cluster identity, stop that subtask and report it while completing unaffected code work. Once schema readiness is restored, inspect nullability/defaults/constraints and enable only schema-compatible accepted-field writes; no zero placeholders. Verify an identifiable valid production row by readback.
6. Deploy one tested revision, restarting only affected services/processes. Compare a short set of fresh production/diagnostic samples within recorded skew, verify one serial owner, and verify readiness plus persistence independently. Remove temporary acquisition windows and retire obsolete fallback paths.

**FORBIDDEN ACTIONS**

No Modbus/configuration writes, energy reset, new scan, fitted divisor, restoration of photo constants, guessed billing data/backfill, schema weakening to accept nonsense, new cluster initialization, recursive ownership changes, deletion of database/WAL/recovery files, or unrelated infrastructure redesign.

**ACCEPTANCE CRITERIA**

Every promoted field traces to a passing evidence packet and a reproducible fixture. Existing V/I is unchanged. Unknown/stale/failing quantities cannot masquerade as current healthy measurements or be written as valid data. UI and API use the same map. Database readiness, a tracked valid insert/readback and visible failures are verified separately; if DB recovery is blocked, report migration and persistence as separate incomplete/complete outcomes. No false claim that lost history was recovered.

**OUTPUT FORMAT**

Promoted/deferred field table; evidence/map version; changed files and hashes; test command/results; deployment UTC/PIDs; serial-owner and live comparison; DB root-cause evidence and insert/readback result; gaps; exact rollback commands using newly created backups.

**ROLLBACK**

Restore the immediately pre-migration revision and only task-specific service overrides. Keep proven V/I and already accepted fields from that baseline. Stop/disable the new writer path if schema or data validity fails; do not undo existing database contents or mount storage merely to roll back Python code. Recheck V/I and independent health after rollback.

## 12. THINGS WE SHOULD STOP DOING

- Fitting divisors or additive offsets to make one photograph match.
- Showing rejected register interpretations as phase-current cards or operational power/energy.
- Treating the successful V/I cutover as proof that every field, freshness path or database write is healthy.
- Repeating the V/I discovery, FC04 mirror experiment, or broad scans without a new discriminating hypothesis.
- Waiting three hours to rescue the “1050” numerical coincidence; changing scale cannot make identical words accumulate.
- Treating repeated HTTP responses/collector timestamps as new Modbus observations.
- Using per-word fallback to produce apparently coherent multiword measurements.
- Allowing exploratory retries and scattered legacy single reads to delay the production poller.
- Treating related-model OCR, old code comments, or transcribed CSV decimals as exact-model authority.
- Rejecting an entire address region because one current/energy interpretation failed, or because signed data moves downward.
- Applying guessed CT/PT multipliers, equating kVA to kW, or enforcing a power triangle without matching quantity definitions.
- Silently dropping PostgREST failures or restoring the DB while invalid fields remain in the writer payload.
- Using the obsolete reader or September 7 rollback recipe to undo the current safe V/I baseline.
- Adding frameworks, polling services, or long-running model supervision when a bounded collector and one analysis script suffice.
