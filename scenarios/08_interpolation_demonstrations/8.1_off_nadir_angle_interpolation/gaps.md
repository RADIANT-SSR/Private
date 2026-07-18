# Scenario 8.1 — Gaps and Friction

---

## OPEN

### Family registry is hand-curated, not derived from the CSV
**Severity:** Low (deliberate design choice, not a defect)
**Description:** `FAMILIES` in `family_interpolate.py` is a small,
explicit dict, not auto-detected from `modtran_run_matrix.csv`'s
`block` column. This was a deliberate scope decision (see the design
conversation recorded in `docs/archive/MODTRAN_Run_Matrix_Plan.md` and
the module's own docstring) — auto-detection was assessed as
unwarranted complexity for a 39-run matrix with only a handful of
genuinely single-axis families.
**Consequence:** adding a new interpolatable family requires a manual
registry entry, not just a CSV edit. Acceptable at this scale;
revisit if the matrix grows substantially.

### No chain-ready helper (raw arrays only)
**Severity:** Low
**Description:** `interpolate_family` returns raw
`(wavelength_um, transmittance, path_radiance)` arrays; every caller
(this script, scenario 8.2) hand-writes the same CSV round-trip to
feed `atmosphere.model="tabulated"`.
**Workaround:** the CSV-writing helper is duplicated across this
scenario and 6.2/1.1's scripts — a shared utility would remove the
duplication.

---

## Friction / lessons

- **37.5° is exactly the family's midpoint between 30° and 45°**, so
  the "naive nearest-neighbor" comparison's tie-break (this script
  picks 45° when the query is equidistant) is somewhat arbitrary — a
  real operator facing an exact tie would reasonably pick either
  neighbor. The demonstrated ~1% error is representative of the
  worst-case nearest-neighbor error for this family's 15°/10° spacing,
  which is the honest point of picking a midpoint query.

---

## Upgrade record (2026-07-17): real MODTRAN data + holdout validation

The real MODTRAN 6 zenith fan replaced the synthetic data
(`family_interpolate` auto-detects `modtran/real_runs/`; synthetic
remains the loud fallback). The new holdout test — predict the real
45° run from 30°+60° — validated the method (−4.07% vs +6.84% for
nearest-neighbor) and surfaced a quantified improvement:

### Interpolation axis should be airmass sec(θ), not angle — CU-160
**Severity:** Low-Medium (knowable −4% in-band τ bias at off-node
zenith queries; affects `family_interpolate` and the shipped
`data/atmospheres/us_standard_zenith_fan/` through
`InterpolatedAtmosphere`'s `path_zenith_rad` axis).
**Evidence:** same log-τ machinery interpolated in sec(θ) reproduces
the real 45° run to −0.10% (vs −4.07% linear-in-angle).
**Fix:** coordinate transform at the axis, no new data; mirrored to
`docs/tracking/Cleanup_Backlog.md` CU-160.
