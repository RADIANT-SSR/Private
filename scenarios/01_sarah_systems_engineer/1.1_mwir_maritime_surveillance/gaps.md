# Scenario 1.1 — Gaps and Friction

Issues encountered building/running the MWIR maritime surveillance
trade study. Registry items mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED before this scenario

### MODTRAN tape7 parser (was the primary gap)
The catalog flagged "no MODTRAN tape7 parser for wavenumber-domain
data." **`radiant.atmosphere.modtran.Tape7Reader`** now exists, with
name-based column mapping (CU-066) fixed 2026-07-10. This scenario is
its first real-config consumer (beyond the`Tape7Reader`'s own unit
tests).

### NEDT / NIIRS in result.metrics
Both `nedt_K` and `niirs` are populated by `PerformanceStage` — the
catalog's "not surfaced" note is stale.

### Detection range calculator
`radiant.performance.detection_range_beer_lambert` exists and is used
directly by this scenario.

---

## OPEN

### No wind-state-dependent ocean emissivity model
**Severity:** Low-Medium
**Description:** RADIANT's emissivity library has one calm-water curve
(`data/emissivity/water_calm.csv`); the catalog's sea-state-3 case has
no curve to use. This scenario uses calm water for both atmosphere
comparisons, so it doesn't affect the SimpleAtmosphere-vs-MODTRAN
delta, but it does mean absolute SNR/range numbers don't reflect a
choppy sea.
**Workaround:** none currently; would need a wind-speed-parameterized
ocean emissivity model (Cox-Munk-style) — out of scope here.

### No rust-specific / partially-rusted steel hull emissivity
**Severity:** Low
**Description:** the library's `steel.csv` is generic steel, not
"partially rusted" as the catalog's target description says. Rust
typically raises MWIR emissivity somewhat vs. bare/painted steel.
**Workaround:** used the library curve as-is; documented as a
simplification in walkthrough.md.

### No PowerPoint/slide-table export
**Severity:** Low
**Description:** the catalog's desired output includes "a summary table
for a PowerPoint slide deck" — this scenario prints a text table and
saves a PNG figure, no PPTX export exists.
**Workaround:** manual copy from the printed summary table.

### Real (non-synthetic) MODTRAN data still absent — RESOLVED 2026-07-17
The real MODTRAN 6 run set delivered 2026-07-17 supplies `D2.tp7`
(`modtran/real_runs/`); the script auto-detects it (synthetic remains
the loud fallback for bare clones) and the walkthrough's results table
and figure are regenerated from the real data. Headline: real maritime
in-band τ = 0.432 vs SimpleAtmosphere's 0.239 (~45% too absorbing —
consistent with scenario 6.2's PWV over-response finding), detection
range 2114 vs 1690 km (+25%).
**Current values (re-run 2026-08-02):** τ 0.4319 (MODTRAN — a measured
constant, unmoved) vs 0.4593 (SimpleAtmosphere, now the *more* transparent
of the two after the CU-155/CU-161 water recalibration and CU-267's
gas-region blend), detection range 2239.7 vs 2415.6 km. The sign of the gap
has reversed since the 2026-07-17 snapshot above; the gap itself stays
resolved.

---

## Friction / lessons

- **The 30 m ship at 532 km is NOT safely a point source** at these
  apertures — `_validate_psf_regime_consistency` (Matrix §7) rejected
  `point_source` with √A_t/d = 2.9e-5 rad vs. a PSF_FWHM-derived limit of
  ~4.2e-6 rad (0.1× threshold). Switched to `sub_pixel`. Worth
  remembering: at long standoff ranges with small apertures, "the target
  is tiny, it must be a point source" is not automatically true — the
  diffraction PSF is *also* tiny at 15 cm aperture in MWIR.
- **`atmosphere.model="tabulated"` requires BOTH transmittance and
  path-radiance files** — the schema's individual-parameter docstrings
  don't make the joint requirement obvious until `build_atmosphere_model`
  raises. A single combined error message naming both missing files
  (already exists) is fine; the friction was not knowing path radiance
  was mandatory even when the scenario doesn't otherwise use it.
- **`detector.qe_table_path` alone was rejected** ("required parameter
  `detector.qe_value` not set" even with `qe_table_path` set). Worked
  around by band-averaging the QE curve to a scalar, matching scenario
  1.2's established pattern. **Update 2026-07-11: filed and FIXED as
  Gap 66** — the resolver now supports `ParameterDef.required_unless`,
  so `qe_table_path` works standalone; this scenario's band-average
  workaround remains valid (same in-band result) and is kept as-is.
