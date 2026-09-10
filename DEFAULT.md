# Dashboard product baseline

The KSC-WH dashboard is a read-only industrial monitoring product for three audiences: the factory operator first, the owner/manager second, and maintenance engineers through progressive detail.

## Product decisions

- **Overview** is the default. In one screen it answers state, active power, energy today, PF, frequency, phase V/I, sample age, recorder health, last DB write, 24-hour load, comparison, peak, and important data events.
- **Electrical** contains the accepted V/I/P/Q/S/PF/f matrix, stable phase identity, live phase-power context, and clearly labelled derived spreads/sanity checks.
- **Energy** leads with counter deltas and comparable periods; cumulative counters remain secondary.
- **History** owns range, measure, comparison, series toggle, tooltip, drag zoom/reset, summaries, quality, and gap investigation.
- **Diagnostics** separates sample quality, mapping provenance, collector, recorder, database, history API, service state, and advanced register provenance.

Live and history are separate failure domains. A database, PostgREST, or diagnostics failure must not make healthy live telemetry appear offline. The browser never records data.

## Visual and chart system

The canonical theme is calm dark industrial with an accessible light alternative. Surfaces are square-edged and compact; numeric values use tabular monospace figures. Green is accepted/healthy, amber is partial/stale/unknown, and red is error/offline. Phase identity is permanent: A green, B blue, C amber. `Made by iw3_` remains visible.

Charts use vendored uPlot 1.6.32 (MIT, zero dependencies) with native canvas performance, tooltips/legend toggles, gaps, responsive sizing, and drag zoom. Large ranges are aggregated by the dashboard server before reaching the browser. Missing values remain null.

## Data semantics

- Sample quality: `LIVE`, `STALE`, `OFFLINE`, `ERROR`, `UNKNOWN`.
- Provenance: `DOCUMENTED + VERIFIED`, `DOCUMENTED — LIVE VERIFY PENDING`, `DERIVED`, `UNKNOWN`.
- Consumption is a difference of accepted cumulative energy counters, never a sum.
- Comparisons are withheld when either period has less than 80% observed coverage.
- Recorder cadence is approximately 5 seconds; a gap is more than 20 seconds (or three measured cadences, whichever is larger).
- Electrical events require a manufacturer limit, operator setting, engineering standard, or explicitly labelled learned baseline. The current UI does not invent thresholds.

## Reuse and change rules

UI concepts are `site`, `machine`, `device`, and canonical `metric`; vendor register addresses appear only in Diagnostics/docs. Do not build multi-factory infrastructure until required. Add a SQL aggregate view only when measured row volume makes the current bounded server aggregation insufficient. Add store-and-forward only when outages become an explicit data-loss requirement.

Before significant changes, read [ARCHITECTURE.md](ARCHITECTURE.md), [REGISTER-MAP.md](REGISTER-MAP.md), and the current [HANDOFF.md](HANDOFF.md). Preserve rollback paths and all hardware safety rules.
