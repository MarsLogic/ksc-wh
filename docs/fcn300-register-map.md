# FCN300 authoritative register map

Reconciled 2026-09-09 against the FCN300-3E4Y User Manual and the existing live evidence. The live unit's exact physical suffix remains unconfirmed, but every tested address, type, scale, phase relationship, and energy ratio matches this map.

| Measurement | FC03 register(s) | Decode | Final status |
|---|---:|---|---|
| Phase voltage A/B/C | `0x0042/44/46`, 2 words each | unsigned BE32 ÷ 10,000 V | DOCUMENTED + EMPIRICALLY VERIFIED |
| Phase current A/B/C | `0x0058/5A/5C`, 2 words each | unsigned BE32 ÷ 10,000 A | DOCUMENTED + EMPIRICALLY VERIFIED |
| Active power A/B/C/total | `0x0064/66/68/6A`, 2 words each | signed BE32 ÷ 10,000 kW | DOCUMENTED + EMPIRICALLY VERIFIED |
| Reactive power A/B/C/total | `0x006C/6E/70/72`, 2 words each | signed BE32 ÷ 10,000 kvar | DOCUMENTED + EMPIRICALLY VERIFIED |
| Apparent power A/B/C/total | `0x0074/76/78/7A`, 2 words each | signed BE32 ÷ 10,000 kVA | DOCUMENTED + EMPIRICALLY VERIFIED |
| PF A/B/C/total | `0x007C–0x007F` | signed int16 ÷ 1,000 | DOCUMENTED + EMPIRICALLY VERIFIED |
| Frequency | `0x0080` | unsigned int16 ÷ 100 Hz | DOCUMENTED + EMPIRICALLY VERIFIED |
| Secondary +active/+reactive/+apparent energy | `0x0082`, `0x0086`, `0x0092` | unsigned BE32 ÷ 1,000 | DOCUMENTED + EMPIRICALLY VERIFIED |
| Primary +active/+reactive/+apparent energy | `0x008A`, `0x008E`, `0x0096` | float32 ABCD ÷ 1,000 | DOCUMENTED + EMPIRICALLY VERIFIED |
| Negative/export energy families | `0x0084`, `0x0088`, `0x008C`, `0x0090`, `0x0094`, `0x0098` | manual-specific unsigned/float forms | DOCUMENTED + LIVE DECODED |

The 2026-09-09 commissioning snapshot produced exact primary/secondary ratios of `40.000` for all four non-zero energy pairs: active import, reactive import, reactive export, and apparent import. This independently confirms the float order and `/1000` primary-side conversion.

Configuration read-only result: `0x002A=256`, `0x002C=1`, `0x002D=1`, `0x002E=40`. The effective current/primary multiplier is 40; the manual's wording for the raw CT quantity value at `0x002A` is ambiguous, so no more specific interpretation is claimed.

Rejected legacy mappings remain rejected: `0x0053` is part of a voltage pair, `0x0210–0x0217` is not live total kWh, and `0x008E–0x008F` is primary positive reactive energy—not kWh.
