# Register-map authority

The authoritative register evidence and statuses remain in [docs/fcn300-register-map.md](docs/fcn300-register-map.md). Do not duplicate or reinterpret that table here.

Production invariants:

- V/I/P/Q/S/PF/f and primary positive kWh/kvarh/kVAh are `DOCUMENTED + EMPIRICALLY VERIFIED`.
- Positive primary energy uses `0x008A`, `0x008E`, and `0x0096`, IEEE-754 float32 ABCD divided by 1000.
- Effective primary/secondary ratio is exactly 40. Raw `0x002A=256` remains vendor-ambiguous and must stay `UNKNOWN`.
- Exact physical model suffix remains pending a device-label check.
- Rejected mappings remain rejected. No broad scans, Modbus writes, CT/PT changes, guessed correction factors, or second serial reader.
