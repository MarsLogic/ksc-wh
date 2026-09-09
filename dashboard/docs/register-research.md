# FCN300 Register Research — documentation-assisted validation

Date: 2026-09-08. Meter: FORT FCN300 family, repo consensus FCN300-3E4Y
(suffix NOT visually confirmed from field photos; only `FORT` legible).
Slave 1, 9600 8N1, `/dev/powermeter` (production owns serial).

Field refs: V 230.1/230.3/229.9 V; I 93.5/104.0/93.1 A;
kWh 1055.20 (image1 bottom); Kvarh 726.52 (image2 bottom, NOT kWh).

## 1. Sources

| # | Source | Claimed model | Class |
|---|---|---|---|
| S1 | Scribd `973888794` "Power Meter Fort FCN300 E13ZY(D)" (25 pp, garbled OCR) | E13ZY family | C (related family) |
| S2 | Tokopedia listing "FORT FCN300-3E4Y" + YouTube `lwGWuda-jD4` | 3E4Y exists, 3-phase | D (existence only) |
| S3 | `fcn300_reader.py` header "verified against FCN300 Modbus map" | 3E4Y (claimed) | D (no map shipped; claim uncorroborated) |
| S4 | `data.csv` + `snapshot.json` (Sep 3) | this meter history | A (meter evidence) |
| S5 | Live `/diag/raw` sweeps 2026-09-08 (this investigation) | this meter | A |

No exact-model manual found. S1 usable for concepts only (FC03+FC04 both
mentioned; 32-bit "long|4"/float quantities; programmable CT
primary/secondary with primary-side display, e.g. 400/5 -> enter 0080;
multi-rate energy; 12-digit energy). No address adopted from S1 (OCR
unrecoverable at register granularity; related-model only).

## 2. Anchor comparison (brief Phase 2)

Proven: V 0x42-47 + I 0x58-5F, BE-uint32 /10000, contiguous 0x40-0x6F
neighborhood. S1 predicts the same ENCODING FAMILY (32-bit pairs, /10000
class) but gives no addresses to confirm/deny layout. No conflict exists,
so nothing is marked variant-incompatible; empirical map stands alone (A),
S1 supports concepts only (C).

## 3. Candidate table (DOCUMENT CLAIM vs ACTUAL-METER EVIDENCE)

| Qty | Doc claim | Meter evidence | Verdict |
|---|---|---|---|
| V L-N | S1: 32-bit pairs (no addr) | 0x42/43,44/45,46/47 BE-u32/10000, 0.3% vs photo | CONFIRMED (A) |
| I ph | S1: none usable | 0x58-5F quad BE-u32/10000, avg-identity 0.06% mean, B-highest 14/14 | CONFIRMED (A); production mapping |
| I alt | none | 0x64-69 BE-u32 with FITTED /1790, <1% twice, pattern-perfect | HYPOTHESIS (D), divisor unattested |
| V L-L | none | 0x4C-53 BE-u32/10000 ~399.7 vs 398.5 derived; historical per-word captures could tear | MEDIUM (A), assignment pending |
| P/Q/S/PF/f | S3: 0x20/22/24/26, 0x1A (scales differ between reader and api!) | 0x00-0x27 block frozen 5+ days; no live candidate anywhere swept | UNKNOWN |
| kWh | S3: 0x53 x0.01 | 0x53 = L-L low-word (PROVEN wrong); E2 ~1050-cluster static -0.4%; C1 monotonic counters rate-unresolved | UNKNOWN |
| kvarh | none | no candidate in any swept range | UNKNOWN |
| CT/PT | S1: programmable, primary display | static config words (5000/6000/3000/257/266/1063/519/…) — no decode | UNKNOWN |
| FC04 | S1: FC03 "or 4" | FC04 answers 0x42-5F, mirrors FC03 within drift | SUPPORTED (A), no new quantities |

## 4. Rejections with reason

- 0x70-75 as phase I: -58..-85% vs photo, no rescale/swap/permutation fixes (all <2^31, unswapped = 60 kA).
- Production 0x00-block: bit-identical Sep 3 -> Sep 8 (raws 8888/33281/33537/33793); aliasing 0x02=0x12, 0x0E=0x16, 0x0F=0x13=0x17. Frozen meter-side.
- 0x53-as-kWh: line-voltage low-word; +21 kWh/2 min (=623 kW vs 0.484 reported); 16-bit caps 902 < 1055 panel.
- CDAB/1e6 (22A,22B)=1057.2 (+0.19%): single-sample coincidence, teleported to 1769.5 in 60 s. Exactly the false-hit pattern the method warns about.
- 0x100-107 signed ~-2000s, 0x110/0x140 fast bidirectional, 0x222-22F teleporters, D1/D2 rotated echoes: no physics fit (P/S/PF/f/E all fail magnitudes or monotonicity).

## 5. Production containment state

Production uses only FC03 0x42 count 6 and 0x58 count 8, decoded as
BE-uint32 /10000. Those complete blocks are committed together and no
correction is applied. Frequency, P, Q, S, PF, kWh, kvarh and kVAh remain
UNKNOWN. The diagnostic page treats 0x70-0x75 as rejected evidence and does
not present it as phase current. Further discovery is outside this task.

## 6. Energy stakeout verdict (2026-09-08 11:33 -> 14:33 UTC)

37 samples, 5-min cadence, `evidence/energy-watch.csv`: 0x210-217 cluster
(1050.0848 / 1050.1759 / 1050.1262 / 1051.1324) bit-identical across the
full 3 h while load swung 95 A -> 7 A -> idle. A live /1e6 counter at this
load moves ~1e5+ counts/hour; observed 0. REJECTED as live kWh per the
static-reject rule. Possible record/max-demand/frozen-engine value;
kvarh still has no candidate anywhere swept.
