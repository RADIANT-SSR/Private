# Scenario 4.2 — Gaps and Friction

Issues encountered building/running the maritime ship-classification
scenario. Registry items are mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED during this scenario

### Johnson-criteria DRI model (was the primary gap)
The catalog flagged "no Johnson criteria / DRI range model". **Built as
`radiant.performance.johnson_criteria`** (committed 0df9e15):
`johnson_range_m`, `resolved_cycles`, and the standard `JOHNSON_N50`
table. 11 Level-0 tests, hand truth anchors. This scenario is its first
consumer.

---

## Framework gaps (mirrored to docs/tracking/gaps.md)

### Gap 53 — DRI model is sampling-limited (no MRC/MRT contrast coupling)
`johnson_criteria` counts geometric cycles across the target; it assumes
the target has enough contrast to see those cycles. A full acquisition
model couples the resolved cycles to the minimum-resolvable-contrast (MRC,
reflective) or minimum-resolvable-temperature (MRT, thermal) curve, so a
low-contrast target identifies at shorter range than the geometric Johnson
value. The current model is the optimistic (high-contrast) bound. At the
resolution-limited ranges (small craft in 4.2) the difference is
operationally significant. Filed as Gap 53. Medium effort; the sampling-
limited form is the correct first layer and is clearly documented as such.

---

## Friction / lessons

- **The horizon, not resolution, binds for large targets.** A 12.5 µrad
  MWIR sensor resolves a frigate's identification cycles out to 276 km,
  but the 5 km platform's geometric horizon is 252 km — so line-of-sight
  is the operational limit for anything frigate-sized or larger. The
  scenario reports `min(DRI, horizon)` per task to make this explicit; a
  DRI-only answer would badly overstate large-ship ranges.
- **Critical dimension convention matters.** √(L·H) is the standard 2-D
  target measure; using length alone would roughly triple the ranges for
  long, low hulls. Documented in the walkthrough so the convention is not
  silently assumed.
- **No chain run needed.** DRI is pure geometry — this scenario exercises
  the new performance model directly, without a signal-chain evaluation.
  A contrast-limited extension (Gap 53) would bring the chain back in.
