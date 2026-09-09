# FCN300 register status

This table separates empirical/documentary candidates from the accepted production contract. Provisional values are not persisted or shown as accepted.

| Measurement | Register family | Encoding/evidence | Status |
|---|---:|---|---|
| Voltage L1/L2/L3 | `0x0042+` | Empirically matched voltage family | ACCEPTED |
| Current A/B/C | `0x0058+` | Empirically matched current family | ACCEPTED |
| Active power | `0x0064+` | Empirically matched; field seal pending | HIGH CONFIDENCE / NOT ACCEPTED |
| Reactive power | `0x006C+` | Empirically matched; field seal pending | HIGH CONFIDENCE / NOT ACCEPTED |
| Apparent power | `0x0074+` | Empirically matched; field seal pending | HIGH CONFIDENCE / NOT ACCEPTED |
| Power factor | `0x007C–0x007F` | Empirically matched; field seal pending | HIGH CONFIDENCE / NOT ACCEPTED |
| Frequency | `0x0080` | Empirically matched; field seal pending | HIGH CONFIDENCE / NOT ACCEPTED |
| Total positive active energy | `0x008A–0x008B` | FORT FCN300-family manual; float32 ABCD; raw `/1000` kWh; integration error about `-0.0075%` | ACCEPTED / PRODUCTION |
| Total negative active energy | `0x008C–0x008D` | Documented negative pair; observed zero/stable | NOT ACCEPTED |
| Positive reactive-energy family | `0x008E–0x008F` | ABCD float; 30-minute integration and manual correlation | HIGH-CONFIDENCE CANDIDATE / NOT ACCEPTED |
| Possible phase/tariff accumulator | `0x0092–0x0093` | Short-run structural candidate only | PLAUSIBLE / NOT ACCEPTED |
| Positive apparent-energy family | `0x0096–0x0097` | ABCD float; 30-minute integration and manual correlation | HIGH-CONFIDENCE CANDIDATE / NOT ACCEPTED |
| kvarh | undocumented candidate family | Needs field seal/OEM corroboration | HIGH-CONFIDENCE CANDIDATE / NOT ACCEPTED |
| kVAh | undocumented candidate family | Needs field seal/OEM corroboration | HIGH-CONFIDENCE CANDIDATE / NOT ACCEPTED |

The FORT E13ZY(D)/FCN300-family manual is the documentary correlation used for the accepted `0x008A` mapping and the provisional energy-family interpretation. Historical `dashboard/register_map.py` is retained only as legacy evidence and is not the production source of truth.
