# Scenario 8.1 — Gaps and Friction

---

## OPEN

### Family registry is hand-curated, not derived from the CSV
**Severity:** Low (deliberate design choice, not a defect)
**Description:** `FAMILIES` in `family_interpolate.py` is a small,
explicit dict, not auto-detected from `modtran_run_matrix.csv`'s
`block` column. This was a deliberate scope decision (see the design
conversation recorded in `docs/plans/MODTRAN_Run_Matrix_Plan.md` and
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
