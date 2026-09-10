# MFM300 manual notes

Source: [`ilec-mfm300-manual.pdf`](../ilec-mfm300-manual.pdf), manufacturer manual `MFM300V2408` (37 pages, accessed 2026-09-10).

The manual describes the MFM300 family as a three-phase multifunction meter with three-phase voltage/current, four-quadrant active/reactive/apparent power, frequency, power factor, import/export kWh/kvarh/kVAh, and an RS485 Modbus-RTU interface. It documents use in energy-management and power-monitoring systems and a display for voltage, current, power, PF, frequency, and energy.

Relevant manufacturer limits/specifications:

- Rated voltage: AC 300 V line-to-neutral / 500 V line-to-line.
- Rated current: 5 A; stated measurement range 30 mA–6 A on the meter input.
- Frequency: 45–65 Hz.
- Accuracy classes stated: voltage class 1, current class 0.5, frequency ±0.02 (manual notation), active energy class 1, reactive energy class 2.
- CT ratio and PT ratio are configurable from 1 to 9999. The current input is from the CT secondary and must be wired to the matching phase input.

These are manufacturer-family facts, not live readings or alarm thresholds. The project’s accepted FCN300 values and register addresses remain governed by [REGISTER-MAP.md](../REGISTER-MAP.md) and [docs/fcn300-register-map.md](fcn300-register-map.md). The PDF does not resolve the vendor wording for raw `0x002A=256`, does not confirm the exact physical suffix, and must not be used to promote a guessed mapping.
